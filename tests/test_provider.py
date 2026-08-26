import pytest

from types import SimpleNamespace

from repofix.provider import extract_usage, parse_action_json, retry_delay_seconds


def test_parse_action_json_accepts_markdown_fence():
    result = parse_action_json('```json\n{"name":"list","arguments":{}}\n```')
    assert result["name"] == "list"


def test_parse_action_json_rejects_unknown_tool():
    with pytest.raises(ValueError, match="invalid action"):
        parse_action_json('{"name":"delete_everything","arguments":{}}')


def test_retry_delay_uses_provider_hint():
    assert retry_delay_seconds("Please retry in 38.5s") == 39.5


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
