import pytest

from repofix.provider import parse_action_json, retry_delay_seconds


def test_parse_action_json_accepts_markdown_fence():
    result = parse_action_json('```json\n{"name":"list","arguments":{}}\n```')
    assert result["name"] == "list"


def test_parse_action_json_rejects_unknown_tool():
    with pytest.raises(ValueError, match="invalid action"):
        parse_action_json('{"name":"delete_everything","arguments":{}}')


def test_retry_delay_uses_provider_hint():
    assert retry_delay_seconds("Please retry in 38.5s") == 39.5
