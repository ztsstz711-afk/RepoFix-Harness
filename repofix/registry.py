from dataclasses import dataclass


@dataclass(frozen=True)
class ArgumentSpec:
    prompt: str
    description: str
    type: str = "string"
    minimum: int | None = None

    def json_schema(self) -> dict:
        schema = {"type": self.type, "description": self.description}
        if self.minimum is not None:
            schema["minimum"] = self.minimum
        return schema


@dataclass(frozen=True)
class ActionSpec:
    name: str
    description: str
    arguments: dict[str, ArgumentSpec]
    required: tuple[str, ...] = ()

    def prompt_line(self) -> str:
        shape = ", ".join(
            f'"{key}": {value.prompt}' for key, value in self.arguments.items()
        )
        return f'- {self.name}: {{{shape}}} — {self.description}'

    def tool_definition(self) -> dict:
        parameters = {
            "type": "object",
            "properties": {
                name: argument.json_schema()
                for name, argument in self.arguments.items()
            },
            "required": list(self.required),
            "additionalProperties": False,
        }
        if self.name == "apply_patch":
            parameters["oneOf"] = [
                {
                    "required": ["old_text", "new_text"],
                    "not": {"required": ["content"]},
                },
                {
                    "required": ["content"],
                    "not": {
                        "anyOf": [
                            {"required": ["old_text"]},
                            {"required": ["new_text"]},
                        ]
                    },
                },
            ]
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": parameters,
            },
        }


def text_argument(prompt: str, description: str) -> ArgumentSpec:
    return ArgumentSpec(prompt, description)


def line_argument(description: str) -> ArgumentSpec:
    return ArgumentSpec("optional integer", description, type="integer", minimum=1)


ACTION_SPECS = {
    spec.name: spec
    for spec in (
        ActionSpec(
            "list",
            "List repository files while excluding control and cache directories.",
            {},
        ),
        ActionSpec(
            "search",
            "Search Python source text. Prefer this before reading a large file.",
            {
                "query": text_argument('"text"', "Exact text or symbol to find."),
                "path": text_argument(
                    '"optional/subdir"',
                    "Optional repository-relative file or directory scope.",
                ),
            },
            ("query",),
        ),
        ActionSpec(
            "read",
            "Read a UTF-8 text file. Prefer a narrow inclusive line range after search.",
            {
                "path": text_argument(
                    '"relative/path.py"', "Repository-relative UTF-8 text file."
                ),
                "start_line": line_argument("Optional first line, inclusive."),
                "end_line": line_argument("Optional last line, inclusive."),
            },
            ("path",),
        ),
        ActionSpec(
            "apply_patch",
            "Edit exactly one text file using one mode only. For an existing file, use a small exact old_text/new_text replacement and omit content. Use content only to create a new file or replace a complete file.",
            {
                "path": text_argument(
                    '"relative/path.py"', "Repository-relative file to edit."
                ),
                "old_text": text_argument(
                    '"exact existing text (localized mode)"',
                    "Exact, non-empty, unique text copied from the latest read. Use together with new_text and omit content.",
                ),
                "new_text": text_argument(
                    '"replacement text (localized mode)"',
                    "Replacement for old_text. Use together with old_text and omit content.",
                ),
                "content": text_argument(
                    '"complete file content (full-file mode)"',
                    "Complete file text. Use only for a new file or intentional whole-file replacement; omit old_text and new_text.",
                ),
            },
            ("path",),
        ),
        ActionSpec(
            "run_command",
            "Run a focused pytest command only.",
            {
                "command": text_argument(
                    '"pytest -q"', "A pytest command scoped inside the repository."
                )
            },
            ("command",),
        ),
        ActionSpec("git_diff", "Show the current repository diff.", {}),
        ActionSpec("git_status", "Show concise repository status.", {}),
        ActionSpec(
            "finish",
            "Finish only after tests verify the repair.",
            {
                "summary": text_argument(
                    '"what changed and how it was verified"',
                    "Concise repair and verification summary.",
                )
            },
            ("summary",),
        ),
    )
}

ALL_ACTION_NAMES = tuple(ACTION_SPECS)

PHASE_ACTIONS = {
    "patch_due": ("apply_patch",),
    "patch_attempt_failed": ("read", "apply_patch", "git_diff"),
    "patch_needs_verification": ("run_command", "git_diff", "git_status"),
    "patch_needs_revision": (
        "search",
        "read",
        "apply_patch",
        "run_command",
        "git_diff",
    ),
    "verified_patch": ("git_diff", "git_status", "finish"),
}


def allowed_actions_for_phase(phase: str) -> tuple[str, ...]:
    return PHASE_ACTIONS.get(phase, ALL_ACTION_NAMES)


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
    for key, value in arguments.items():
        argument = spec.arguments[key]
        if argument.type == "string" and not isinstance(value, str):
            return f"{name} {key} must be a string"
        if argument.type == "integer" and (
            not isinstance(value, int) or isinstance(value, bool)
        ):
            return f"{name} {key} must be an integer"
        if argument.minimum is not None and value < argument.minimum:
            return f"{name} {key} must be at least {argument.minimum}"
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
        if has_old and has_new and arguments["old_text"] == arguments["new_text"]:
            return "apply_patch new_text must differ from old_text"
    return None


def render_action_instructions(names: tuple[str, ...] | None = None) -> str:
    selected = names or ALL_ACTION_NAMES
    return "\n".join(ACTION_SPECS[name].prompt_line() for name in selected)


def render_action_names(names: tuple[str, ...] | None = None) -> str:
    return ", ".join(names or ALL_ACTION_NAMES)


def render_tool_definitions(names: tuple[str, ...] | None = None) -> list[dict]:
    selected = names or ALL_ACTION_NAMES
    return [ACTION_SPECS[name].tool_definition() for name in selected]
