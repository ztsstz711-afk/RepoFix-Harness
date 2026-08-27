import ast
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

        snippets: list[str] = []
        seen: set[str] = set()
        referenced_files: list[Path] = []
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
            referenced_files.append(resolved)
            if len(snippets) >= self.max_files:
                break
        for referenced in referenced_files:
            if len(snippets) >= self.max_files or not self._looks_like_test(referenced):
                continue
            for imported, symbol in self._local_imports(referenced):
                relative = imported.relative_to(self.repo).as_posix()
                if relative in seen:
                    continue
                line_number = self._definition_line(imported, symbol)
                snippet = self._snippet(imported, relative, line_number, label="imported ")
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

    def _local_imports(self, source: Path) -> list[tuple[Path, str | None]]:
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            return []
        imports: list[tuple[Path, str | None]] = []
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = self._resolve_module(alias.name, source, level=0)
                    if target is not None:
                        imports.append((target, None))
            elif isinstance(node, ast.ImportFrom):
                target = self._resolve_module(node.module or "", source, node.level)
                for alias in node.names:
                    child_module = ".".join(
                        part for part in (node.module or "", alias.name) if part
                    )
                    child = (
                        self._resolve_module(child_module, source, node.level)
                        if target is None or target.name == "__init__.py"
                        else None
                    )
                    if child is not None:
                        imports.append((child, None))
                    elif target is not None:
                        imports.append((target, None if alias.name == "*" else alias.name))
        return imports

    def _resolve_module(self, module: str, source: Path, level: int) -> Path | None:
        parts = [part for part in module.split(".") if part]
        if level:
            base = source.parent
            for _ in range(level - 1):
                base = base.parent
            roots = [base]
        else:
            roots = [self.repo, self.repo / "src"]
        for root in roots:
            stem = root.joinpath(*parts)
            candidates = (
                [stem.with_suffix(".py"), stem / "__init__.py"]
                if parts
                else [stem / "__init__.py"]
            )
            for candidate in candidates:
                resolved = self._safe_python_file(candidate)
                if resolved is not None:
                    return resolved
        return None

    def _safe_python_file(self, candidate: Path) -> Path | None:
        try:
            resolved = candidate.resolve()
            relative = resolved.relative_to(self.repo).as_posix()
            resolved = self.permissions.ensure_readable(relative)
        except (OSError, PermissionError, ValueError):
            return None
        return resolved if resolved.is_file() and resolved.suffix.lower() == ".py" else None

    @staticmethod
    def _definition_line(path: Path, symbol: str | None) -> int:
        if not symbol:
            return 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            return 1
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == symbol:
                    return node.lineno
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(isinstance(target, ast.Name) and target.id == symbol for target in targets):
                    return node.lineno
        return 1

    def _looks_like_test(self, path: Path) -> bool:
        relative = path.relative_to(self.repo)
        return (
            path.name.startswith("test_")
            or path.name.endswith("_test.py")
            or "tests" in relative.parts
        )

    def _snippet(
        self,
        path: Path,
        relative: str,
        line_number: int,
        label: str = "",
    ) -> str:
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
        return f"--- {label}{relative}:{line_number} (lines {start}-{end}) ---\n{numbered}"
