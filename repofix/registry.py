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
            "Replace one text file with complete content.",
            {"path": '"relative/path.py"', "content": '"complete file content"'},
            ("path", "content"),
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
    return None


def render_action_instructions() -> str:
    return "\n".join(spec.prompt_line() for spec in ACTION_SPECS.values())
