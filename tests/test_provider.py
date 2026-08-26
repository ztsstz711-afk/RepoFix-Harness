import pytest

from types import SimpleNamespace

from repofix.provider import extract_usage, parse_action_json, retry_delay_seconds, transient_retry_delay


def test_parse_action_json_accepts_markdown_fence():
    result = parse_action_json('```json\n{"name":"list","arguments":{}}\n```')
    assert result["name"] == "list"


def test_parse_action_json_rejects_unknown_tool():
    with pytest.raises(ValueError, match="invalid action"):
        parse_action_json('{"name":"delete_everything","arguments":{}}')


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
    provider._create_completion = lambda prompt: next(responses)
    decision = provider.next_action("context")
    assert decision.action.name == "list"
    assert decision.usage.requests == 2
    assert decision.usage.total_tokens == 35
