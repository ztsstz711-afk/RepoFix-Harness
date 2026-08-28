from dataclasses import dataclass


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    arguments: dict[str, str]
    required: tuple[str, ...] = ()

    def prompt_line(self) -> str:
        shape = ", ".join(f'"{key}": {value}' for key, value in self.arguments.items())
        return f'- {self.name}: {{{shape}}} — {self.description}'

    def tool_definition(self) -> dict:
        properties = {}
        for name, example in self.arguments.items():
            schema = {"type": "integer", "minimum": 1} if "integer" in example else {"type": "string"}
            properties[name] = schema
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": list(self.required),
                    "additionalProperties": False,
                },
            },
        }


ACTION_SPECS = {
    spec.name: spec
    for spec in (
        ActionSpec("list", "List repository files while excluding control and cache directories.", {}),
        ActionSpec("search", "Search Python source text.", {"query": '"text"', "path": '"optional/subdir"'}, ("query",)),
        ActionSpec(
            "read",
            "Read a UTF-8 text file, optionally by inclusive line range.",
            {"path": '"relative/path.py"', "start_line": "optional integer", "end_line": "optional integer"},
            ("path",),
        ),
        ActionSpec(
            "apply_patch",
            "Edit one text file. Prefer an exact, unique old_text/new_text replacement; content remains available for creating or replacing a complete file.",
            {
                "path": '"relative/path.py"',
                "old_text": '"exact existing text (localized mode)"',
                "new_text": '"replacement text (localized mode)"',
                "content": '"complete file content (full-file mode)"',
            },
            ("path",),
        ),
        ActionSpec("run_command", "Run pytest only.", {"command": '"pytest -q"'}, ("command",)),
        ActionSpec("git_diff", "Show the current repository diff.", {}),
        ActionSpec("git_status", "Show concise repository status.", {}),
        ActionSpec("finish", "Finish with a verified repair summary.", {"summary": '"what changed and how it was verified"'}, ("summary",)),
    )
}


def validate_action(name: str, arguments: dict) -> str | None:
    spec = ACTION_SPECS.get(name)
    if spec is None:
        return f"unknown action: {name}"
    if not isinstance(arguments, dict):
        return "arguments must be an object"
    missing = [key for key in spec.required if key not in arguments]
    if missing:
        return f"missing required arguments: {', '.join(missing)}"
    unknown = [key for key in arguments if key not in spec.arguments]
    if unknown:
        return f"unknown arguments for {name}: {', '.join(unknown)}"
    if name == "apply_patch":
        has_content = "content" in arguments
        has_old = "old_text" in arguments
        has_new = "new_text" in arguments
        if has_content and (has_old or has_new):
            return "apply_patch must use either content or old_text/new_text, not both"
        if not has_content and not (has_old and has_new):
            return "apply_patch requires content or both old_text and new_text"
        if has_old and not isinstance(arguments["old_text"], str):
            return "apply_patch old_text must be a string"
        if has_new and not isinstance(arguments["new_text"], str):
            return "apply_patch new_text must be a string"
        if has_content and not isinstance(arguments["content"], str):
            return "apply_patch content must be a string"
        if has_old and arguments["old_text"] == "":
            return "apply_patch old_text must not be empty"
    return None


def render_action_instructions() -> str:
    return "\n".join(spec.prompt_line() for spec in ACTION_SPECS.values())


def render_tool_definitions() -> list[dict]:
    return [spec.tool_definition() for spec in ACTION_SPECS.values()]
