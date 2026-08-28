from repofix.registry import (
    render_action_instructions,
    render_action_names,
    render_tool_definitions,
    validate_action,
)


def test_registry_renders_prompt_and_validates_arguments():
    prompt = render_action_instructions()
    assert "apply_patch" in prompt
    assert "old_text" in prompt
    assert validate_action("read", {"path": "a.py"}) is None
    assert "missing required" in validate_action("read", {})
    assert "unknown arguments" in validate_action("list", {"extra": True})
    assert render_action_names().startswith("list, search, read, apply_patch")
    assert "must be an integer" in validate_action(
        "read", {"path": "a.py", "start_line": "2"}
    )
    assert "at least 1" in validate_action(
        "read", {"path": "a.py", "start_line": 0}
    )


def test_apply_patch_registry_accepts_exactly_one_edit_mode():
    assert validate_action(
        "apply_patch", {"path": "a.py", "old_text": "old", "new_text": "new"}
    ) is None
    assert validate_action("apply_patch", {"path": "a.py", "content": "new"}) is None
    assert "requires content" in validate_action("apply_patch", {"path": "a.py"})
    assert "not both" in validate_action(
        "apply_patch",
        {"path": "a.py", "content": "new", "old_text": "old", "new_text": "new"},
    )
    assert "must not be empty" in validate_action(
        "apply_patch", {"path": "a.py", "old_text": "", "new_text": "new"}
    )


def test_registry_renders_openai_compatible_function_tools():
    tools = render_tool_definitions()
    definitions = {tool["function"]["name"]: tool["function"] for tool in tools}

    assert set(definitions) >= {"read", "apply_patch", "run_command", "finish"}
    read = definitions["read"]["parameters"]
    assert read["required"] == ["path"]
    assert read["properties"]["start_line"]["type"] == "integer"
    assert read["properties"]["start_line"]["minimum"] == 1
    assert "inclusive" in read["properties"]["start_line"]["description"]
    assert read["additionalProperties"] is False
    assert definitions["list"]["parameters"]["properties"] == {}

    patch = definitions["apply_patch"]["parameters"]
    assert len(patch["oneOf"]) == 2
    assert patch["oneOf"][0]["required"] == ["old_text", "new_text"]
    assert patch["oneOf"][1]["required"] == ["content"]
    assert "omit content" in patch["properties"]["old_text"]["description"]
