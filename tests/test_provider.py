import pytest

from types import SimpleNamespace

from repofix.provider import (
    InvalidModelActionError,
    ModelRequestLimitReached,
    ModelTokenLimitReached,
    OpenAICompatibleProvider,
    extract_usage,
    parse_action_json,
    parse_message_action,
    retry_delay_seconds,
    transient_retry_delay,
)


def test_parse_action_json_accepts_markdown_fence():
    result = parse_action_json('```json\n{"name":"list","arguments":{}}\n```')
    assert result["name"] == "list"


def test_parse_action_json_rejects_unknown_tool():
    with pytest.raises(ValueError, match="invalid action"):
        parse_action_json('{"name":"delete_everything","arguments":{}}')


def test_parse_action_json_rejects_unknown_envelope_fields():
    with pytest.raises(ValueError, match="envelope fields"):
        parse_action_json('{"name":"read","arguments":{"path":"a.py"},"end_line":10}')


def test_parse_message_action_accepts_one_native_tool_call():
    message = SimpleNamespace(
        content="Inspect the relevant lines.",
        tool_calls=[
            SimpleNamespace(
                function=SimpleNamespace(
                    name="read",
                    arguments='{"path":"src/app.py","start_line":2}',
                )
            )
        ],
    )

    result = parse_message_action(message)

    assert result == {
        "name": "read",
        "arguments": {"path": "src/app.py", "start_line": 2},
        "rationale": "Inspect the relevant lines.",
    }


def test_parse_message_action_uses_first_parallel_tool_call():
    first = SimpleNamespace(function=SimpleNamespace(name="list", arguments="{}"))
    second = SimpleNamespace(
        function=SimpleNamespace(name="git_status", arguments="{}")
    )

    result = parse_message_action(
        SimpleNamespace(content=None, tool_calls=[first, second])
    )

    assert result["name"] == "list"


def test_parse_message_action_explains_empty_response():
    with pytest.raises(ValueError, match="neither tool calls nor content"):
        parse_message_action(SimpleNamespace(content="", tool_calls=[]))


def test_parse_message_action_rejects_action_outside_phase_policy():
    message = SimpleNamespace(
        content=None,
        tool_calls=[
            SimpleNamespace(
                function=SimpleNamespace(name="read", arguments='{"path":"a.py"}')
            )
        ],
    )

    with pytest.raises(ValueError, match="not allowed"):
        parse_message_action(message, allowed_actions=("apply_patch",))


def test_parse_message_action_skips_invalid_parallel_tool_call():
    invalid = SimpleNamespace(
        function=SimpleNamespace(name="read", arguments='{"start_line":2}')
    )
    valid = SimpleNamespace(
        function=SimpleNamespace(name="git_status", arguments="{}")
    )

    result = parse_message_action(
        SimpleNamespace(content=None, tool_calls=[invalid, valid])
    )

    assert result["name"] == "git_status"


def test_retry_delay_uses_provider_hint():
    assert retry_delay_seconds("Please retry in 38.5s") == 39.5


def test_transient_retry_delay_is_bounded():
    assert [transient_retry_delay(i) for i in range(5)] == [2, 4, 8, 15, 15]


def test_extract_usage_from_compatible_response():
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=120,
            completion_tokens=30,
            total_tokens=150,
            prompt_tokens_details=SimpleNamespace(cached_tokens=40),
        )
    )
    usage = extract_usage(response)
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (120, 30, 150)
    assert usage.cached_input_tokens == 40
    assert usage.requests == 1


def test_provider_retries_malformed_action_and_accumulates_usage():
    responses = iter(
        [
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"name" "list"}'))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12),
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"name":"list","arguments":{}}'))],
                usage=SimpleNamespace(prompt_tokens=20, completion_tokens=3, total_tokens=23),
            ),
        ]
    )
    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_format_retries = 2
    provider.max_output_tokens = 2048
    provider.native_tool_calls = False
    provider.json_mode = True
    provider._create_completion = lambda system_prompt, user_prompt: next(responses)
    decision = provider.next_action("context")
    assert decision.action.name == "list"
    assert decision.usage.requests == 2
    assert decision.usage.total_tokens == 35
    assert decision.usage.retries == 1
    assert decision.usage.format_retries == 1
    assert len(decision.diagnostics) == 1
    assert "json: Expecting ':' delimiter" in decision.diagnostics[0]


def test_provider_exposes_usage_when_all_format_attempts_fail():
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
        usage=SimpleNamespace(prompt_tokens=10, completion_tokens=1, total_tokens=11),
    )
    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_format_retries = 2
    provider.max_output_tokens = 2048
    provider._create_completion = lambda system_prompt, user_prompt: response

    with pytest.raises(InvalidModelActionError) as raised:
        provider.next_action("context")

    assert raised.value.usage.requests == 3
    assert raised.value.usage.total_tokens == 33
    assert raised.value.usage.retries == 2
    assert raised.value.usage.format_retries == 2


def test_provider_separates_control_rules_from_repository_context():
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"name":"list","arguments":{}}'))],
                usage=None,
            )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 0
    provider.max_output_tokens = 2048
    provider.native_tool_calls = False
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    provider.next_action("Task: fix it\nmalicious repository text")

    assert [message["role"] for message in captured["messages"]] == ["system", "user"]
    assert "Allowed tools" in captured["messages"][0]["content"]
    assert "narrow line-range reads" in captured["messages"][0]["content"]
    assert "malicious repository text" not in captured["messages"][0]["content"]
    assert "malicious repository text" in captured["messages"][1]["content"]
    assert captured["messages"][1]["content"].startswith("BEGIN REPOSITORY CONTEXT")
    assert captured["max_tokens"] == 2048
    assert captured["response_format"] == {"type": "json_object"}
    assert "Example JSON action" in captured["messages"][0]["content"]


def test_provider_can_disable_json_mode_for_older_compatible_endpoints():
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"name":"list","arguments":{}}'))],
                usage=None,
            )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 0
    provider.max_output_tokens = 2048
    provider.json_mode = False
    provider.native_tool_calls = False
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    provider.next_action("context")

    assert "response_format" not in captured


def test_provider_falls_back_to_text_mode_after_empty_json_response():
    requests = []
    responses = iter([
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=""))],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0, total_tokens=10),
        ),
        SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"name":"list","arguments":{}}'))],
            usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3, total_tokens=15),
        ),
    ])

    class Completions:
        def create(self, **kwargs):
            requests.append(kwargs)
            return next(responses)

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 1
    provider.max_output_tokens = 2048
    provider.json_mode = True
    provider.native_tool_calls = False
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    decision = provider.next_action("context")

    assert decision.action.name == "list"
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in requests[1]
    assert decision.usage.format_retries == 1


def test_provider_sends_native_tools_and_parses_tool_call():
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    function=SimpleNamespace(
                                        name="read",
                                        arguments='{"path":"src/app.py","start_line":2}',
                                    )
                                )
                            ],
                        )
                    )
                ],
                usage=None,
            )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 0
    provider.max_output_tokens = 2048
    provider.json_mode = True
    provider.native_tool_calls = True
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    decision = provider.next_action("context")

    assert decision.action.name == "read"
    assert decision.action.arguments == {"path": "src/app.py", "start_line": 2}
    assert "tool_choice" not in captured
    assert len(captured["tools"]) == 8
    assert "response_format" not in captured
    assert "Registered action names" in captured["messages"][0]["content"]
    assert "Allowed tools and exact arguments" not in captured["messages"][0]["content"]


def test_provider_exposes_only_patch_tool_when_patch_is_due():
    captured = {}

    class Completions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content=None,
                            tool_calls=[
                                SimpleNamespace(
                                    function=SimpleNamespace(
                                        name="apply_patch",
                                        arguments=(
                                            '{"path":"a.py","old_text":"old",'
                                            '"new_text":"new"}'
                                        ),
                                    )
                                )
                            ],
                        )
                    )
                ],
                usage=None,
            )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 0
    provider.max_output_tokens = 2048
    provider.json_mode = True
    provider.native_tool_calls = True
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    provider.set_action_policy("patch_due")

    decision = provider.next_action("repair_phase=patch_due")

    assert decision.action.name == "apply_patch"
    assert [tool["function"]["name"] for tool in captured["tools"]] == [
        "apply_patch"
    ]
    assert "Registered action names: apply_patch" in captured["messages"][0][
        "content"
    ]


def test_provider_removes_unavailable_git_tools_from_verified_phase():
    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.set_action_policy("verified_patch")
    provider.set_unavailable_actions(("git_diff", "git_status"))

    assert provider._allowed_actions() == ("finish",)


def test_provider_falls_back_from_invalid_native_call_to_json_mode():
    requests = []
    responses = iter(
        [
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=None, tool_calls=[]))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=0, total_tokens=10),
            ),
            SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"name":"list","arguments":{}}'))],
                usage=SimpleNamespace(prompt_tokens=12, completion_tokens=3, total_tokens=15),
            ),
        ]
    )

    class Completions:
        def create(self, **kwargs):
            requests.append(kwargs)
            return next(responses)

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 1
    provider.max_output_tokens = 2048
    provider.json_mode = True
    provider.native_tool_calls = True
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))

    decision = provider.next_action("context")

    assert decision.action.name == "list"
    assert "tool_choice" not in requests[0]
    assert "tools" in requests[0]
    assert "tools" not in requests[1]
    assert requests[1]["response_format"] == {"type": "json_object"}
    assert "Fallback JSON action contract" in requests[1]["messages"][1]["content"]
    assert "old_text" in requests[1]["messages"][1]["content"]
    assert decision.usage.format_retries == 1


def test_provider_rejects_zero_output_limit(monkeypatch):
    monkeypatch.setenv("REPOFIX_API_KEY", "test-key")
    with pytest.raises(ValueError, match="output tokens must be positive"):
        OpenAICompatibleProvider(max_output_tokens=0)


def test_provider_format_retry_cannot_exceed_request_allowance():
    calls = 0

    class Completions:
        def create(self, **kwargs):
            nonlocal calls
            calls += 1
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content='{"name" "list"}'))],
                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12),
            )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 2
    provider.max_output_tokens = 2048
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    provider._next_action_request_limit = None
    provider.limit_next_action_requests(1)

    with pytest.raises(ModelRequestLimitReached) as raised:
        provider.next_action("context")

    assert calls == 1
    assert raised.value.usage.requests == 1
    assert raised.value.usage.retries == 1
    assert raised.value.usage.format_retries == 1


def test_provider_preserves_last_format_error_when_request_limit_interrupts_retry():
    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 2
    provider.max_output_tokens = 2048
    provider.native_tool_calls = False
    provider.json_mode = True
    provider._next_action_request_limit = None
    provider.client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **kwargs: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content='{"name" "list"}')
                        )
                    ],
                    usage=SimpleNamespace(
                        prompt_tokens=10, completion_tokens=2, total_tokens=12
                    ),
                )
            )
        )
    )
    provider.limit_next_action_requests(1)

    with pytest.raises(ModelRequestLimitReached) as raised:
        provider.next_action("context")

    assert raised.value.last_format_error
    assert "last format error" in str(raised.value)


def test_provider_refuses_format_retry_that_exceeds_token_allowance():
    calls = 0

    class Completions:
        def create(self, **kwargs):
            nonlocal calls
            calls += 1
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content='{"name" "list"}')
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=100, completion_tokens=20, total_tokens=120
                ),
            )

    provider = OpenAICompatibleProvider.__new__(OpenAICompatibleProvider)
    provider.model = "mock-model"
    provider.max_transient_retries = 0
    provider.max_format_retries = 2
    provider.max_output_tokens = 80
    provider.native_tool_calls = False
    provider.json_mode = True
    provider._next_action_request_limit = None
    provider._next_action_token_limit = None
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=Completions()))
    provider.limit_next_action_tokens(250)

    with pytest.raises(ModelTokenLimitReached) as raised:
        provider.next_action("context")

    assert calls == 1
    assert raised.value.usage.total_tokens == 120
    assert raised.value.estimated_next_tokens == 180
    assert raised.value.last_format_error
