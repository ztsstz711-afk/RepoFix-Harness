import re
from pathlib import Path

from .permissions import PermissionPolicy
from .text import compact_text


TRACEBACK_FILE = re.compile(r'File\s+"(?P<path>.+?\.py)",\s+line\s+(?P<line>\d+)')
PYTEST_LOCATION = re.compile(
    r"^\s*(?:>\s*)?(?P<path>(?:[A-Za-z]:[\\/])?[^:\r\n]+?\.py):(?P<line>\d+)",
    re.MULTILINE,
)


class FailureContextExtractor:
    """Read bounded repository snippets referenced by pytest tracebacks."""

    def __init__(
        self,
        repo: str,
        max_files: int = 4,
        context_lines: int = 8,
        max_chars: int = 6_000,
    ):
        self.repo = Path(repo).resolve()
        self.permissions = PermissionPolicy(self.repo)
        self.max_files = max_files
        self.context_lines = context_lines
        self.max_chars = max_chars

    def build(self, pytest_output: str) -> str:
        if not pytest_output or self.max_files <= 0 or self.max_chars <= 0:
            return ""
        locations = []
        for pattern in (TRACEBACK_FILE, PYTEST_LOCATION):
            for match in pattern.finditer(pytest_output):
                locations.append((match.start(), match.group("path"), int(match.group("line"))))
        locations.sort(key=lambda item: item[0])

        snippets = []
        seen = set()
        for _, raw_path, line_number in locations:
            resolved = self._resolve(raw_path)
            if resolved is None:
                continue
            relative = resolved.relative_to(self.repo).as_posix()
            if relative in seen:
                continue
            snippet = self._snippet(resolved, relative, line_number)
            if not snippet:
                continue
            snippets.append(snippet)
            seen.add(relative)
            if len(snippets) >= self.max_files:
                break
        if not snippets:
            return ""
        content = "\n\n".join(snippets)
        return compact_text(content, self.max_chars)[0]

    def _resolve(self, raw_path: str) -> Path | None:
        normalized = raw_path.strip().replace("\\", "/")
        if normalized.startswith("/workspace/"):
            normalized = normalized[len("/workspace/") :]
        elif normalized.startswith("workspace/"):
            normalized = normalized[len("workspace/") :]
        try:
            path = Path(normalized)
            if path.is_absolute():
                resolved = path.resolve()
                if resolved != self.repo and self.repo not in resolved.parents:
                    return None
                resolved = self.permissions.ensure_readable(
                    resolved.relative_to(self.repo).as_posix()
                )
            else:
                resolved = self.permissions.ensure_readable(normalized)
        except (OSError, PermissionError, ValueError):
            return None
        if not resolved.is_file() or resolved.suffix.lower() != ".py":
            return None
        return resolved

    def _snippet(self, path: Path, relative: str, line_number: int) -> str:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            return ""
        if line_number < 1 or line_number > len(lines):
            return ""
        start = max(line_number - self.context_lines, 1)
        end = min(line_number + self.context_lines, len(lines))
        numbered = "\n".join(
            f"{number:>5} | {lines[number - 1]}" for number in range(start, end + 1)
        )
        return f"--- {relative}:{line_number} (lines {start}-{end}) ---\n{numbered}"
