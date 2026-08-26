from repofix.registry import render_action_instructions, validate_action


def test_registry_renders_prompt_and_validates_arguments():
    prompt = render_action_instructions()
    assert "apply_patch" in prompt
    assert validate_action("read", {"path": "a.py"}) is None
    assert "missing required" in validate_action("read", {})
    assert "unknown arguments" in validate_action("list", {"extra": True})
