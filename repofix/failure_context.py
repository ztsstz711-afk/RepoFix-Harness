import ast
import re
from dataclasses import dataclass
from pathlib import Path

from .permissions import PermissionPolicy
from .text import compact_text


TRACEBACK_FILE = re.compile(r'File\s+"(?P<path>.+?\.py)",\s+line\s+(?P<line>\d+)')
PYTEST_LOCATION = re.compile(
    r"^\s*(?:>\s*)?(?P<path>(?:[A-Za-z]:[\\/])?[^:\r\n]+?\.py):(?P<line>\d+)",
    re.MULTILINE,
)


@dataclass(frozen=True)
class FailureSourceSelection:
    path: str
    line: int
    reason: str
    snippet_chars: int
    imported_from: str = ""
    symbol: str = ""


@dataclass(frozen=True)
class FailureContextResult:
    text: str
    sources: tuple[FailureSourceSelection, ...] = ()
    truncated: bool = False


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
        return self.build_result(pytest_output).text

    def build_result(self, pytest_output: str) -> FailureContextResult:
        if not pytest_output or self.max_files <= 0 or self.max_chars <= 0:
            return FailureContextResult("")
        locations = []
        for pattern in (TRACEBACK_FILE, PYTEST_LOCATION):
            for match in pattern.finditer(pytest_output):
                locations.append((match.start(), match.group("path"), int(match.group("line"))))
        locations.sort(key=lambda item: item[0])

        snippets: list[str] = []
        selections: list[FailureSourceSelection] = []
        seen: set[str] = set()
        referenced_files: list[tuple[Path, int]] = []
        call_candidates: list[tuple[Path, str, str, str]] = []
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
            referenced_files.append((resolved, line_number))
            selections.append(
                FailureSourceSelection(
                    path=relative,
                    line=line_number,
                    reason="traceback",
                    snippet_chars=len(snippet),
                )
            )
            if len(snippets) >= self.max_files:
                break
        for referenced, referenced_line in referenced_files:
            if len(snippets) >= self.max_files or not self._looks_like_test(referenced):
                continue
            for imported, symbol in self._local_imports(referenced, referenced_line):
                relative = imported.relative_to(self.repo).as_posix()
                if relative in seen:
                    continue
                line_number = self._definition_line(imported, symbol)
                snippet = self._snippet(imported, relative, line_number, label="imported ")
                if not snippet:
                    continue
                snippets.append(snippet)
                seen.add(relative)
                selections.append(
                    FailureSourceSelection(
                        path=relative,
                        line=line_number,
                        reason="local_import",
                        snippet_chars=len(snippet),
                        imported_from=referenced.relative_to(self.repo).as_posix(),
                        symbol=symbol or "",
                    )
                )
                if symbol:
                    facade = self._resolve_import_chain(imported, symbol)
                    if facade is not None:
                        call_candidates.append(
                            (facade[0], facade[1], relative, "local_facade")
                        )
                    else:
                        for called, called_symbol in self._called_local_imports(
                            imported, symbol
                        ):
                            call_candidates.append(
                                (called, called_symbol, relative, "local_call")
                            )
                if len(snippets) >= self.max_files:
                    break
        for called, symbol, imported_from, reason in call_candidates:
            if len(snippets) >= self.max_files:
                break
            relative = called.relative_to(self.repo).as_posix()
            if relative in seen:
                continue
            line_number = self._definition_line(called, symbol)
            snippet = self._snippet(
                called, relative, line_number, label="called "
            )
            if not snippet:
                continue
            snippets.append(snippet)
            seen.add(relative)
            selections.append(
                FailureSourceSelection(
                    path=relative,
                    line=line_number,
                    reason=reason,
                    snippet_chars=len(snippet),
                    imported_from=imported_from,
                    symbol=symbol,
                )
            )
        if not snippets:
            return FailureContextResult("")
        content = "\n\n".join(snippets)
        return FailureContextResult(
            text=compact_text(content, self.max_chars)[0],
            sources=tuple(selections),
            truncated=len(content) > self.max_chars,
        )

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

    def _local_imports(
        self, source: Path, line_number: int | None = None
    ) -> list[tuple[Path, str | None]]:
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            return []
        imports: list[tuple[str, Path, str | None]] = []
        called_attributes = self._called_attributes(tree, line_number)
        names_at_failure = self._names_at_line(tree, line_number)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = self._resolve_module(alias.name, source, level=0)
                    if target is not None:
                        binding = alias.asname or alias.name.split(".")[0]
                        attributes = called_attributes.get(binding, [])
                        if attributes:
                            imports.extend(
                                (binding, target, attribute) for attribute in attributes
                            )
                        else:
                            imports.append((binding, target, None))
            elif isinstance(node, ast.ImportFrom):
                target = self._resolve_module(node.module or "", source, node.level)
                for alias in node.names:
                    binding = alias.asname or alias.name
                    attributes = called_attributes.get(binding, [])
                    child_module = ".".join(
                        part for part in (node.module or "", alias.name) if part
                    )
                    child = (
                        self._resolve_module(child_module, source, node.level)
                        if target is None or target.name == "__init__.py"
                        else None
                    )
                    if child is not None:
                        if attributes:
                            imports.extend(
                                (binding, child, attribute) for attribute in attributes
                            )
                        else:
                            imports.append((binding, child, None))
                    elif target is not None:
                        symbol = None if alias.name == "*" else alias.name
                        if symbol and attributes:
                            imports.extend(
                                (binding, target, f"{symbol}.{attribute}")
                                for attribute in attributes
                            )
                        else:
                            imports.append((binding, target, symbol))
        relevant = [item for item in imports if item[0] in names_at_failure]
        selected = relevant or imports
        return [(target, symbol) for _, target, symbol in selected]

    @staticmethod
    def _names_at_line(tree: ast.AST, line_number: int | None) -> set[str]:
        if line_number is None:
            return set()
        return {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
            and node.lineno <= line_number <= getattr(node, "end_lineno", node.lineno)
        }

    @staticmethod
    def _called_attributes(
        tree: ast.AST, line_number: int | None = None
    ) -> dict[str, list[str]]:
        scope = tree
        if line_number is not None:
            candidates = [
                node
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.lineno <= line_number <= getattr(node, "end_lineno", node.lineno)
            ]
            if candidates:
                scope = min(
                    candidates,
                    key=lambda node: getattr(node, "end_lineno", node.lineno) - node.lineno,
                )
        selected: dict[str, list[str]] = {}
        for call in sorted(
            (node for node in ast.walk(scope) if isinstance(node, ast.Call)),
            key=lambda node: (node.lineno, node.col_offset),
        ):
            parts: list[str] = []
            current = call.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if not isinstance(current, ast.Name) or not parts:
                continue
            attribute = ".".join(reversed(parts))
            values = selected.setdefault(current.id, [])
            if attribute not in values:
                values.append(attribute)
        return selected

    def _resolve_import_chain(
        self, source: Path, symbol: str, max_hops: int = 3
    ) -> tuple[Path, str] | None:
        current_source = source
        current_symbol = symbol
        moved = False
        for _ in range(max_hops):
            resolved = self._resolve_import_binding(current_source, current_symbol)
            if resolved is None:
                break
            current_source, current_symbol = resolved
            moved = True
        return (current_source, current_symbol) if moved else None

    def _resolve_import_binding(
        self, source: Path, symbol: str
    ) -> tuple[Path, str] | None:
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            return None
        first, separator, remainder = symbol.partition(".")
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    binding = alias.asname or alias.name.split(".")[0]
                    if binding != first:
                        continue
                    target = self._resolve_module(alias.name, source, level=0)
                    if target is not None and separator:
                        return target, remainder
            elif isinstance(node, ast.ImportFrom):
                target = self._resolve_module(node.module or "", source, node.level)
                for alias in node.names:
                    binding = alias.asname or alias.name
                    if binding != first:
                        continue
                    child_module = ".".join(
                        part for part in (node.module or "", alias.name) if part
                    )
                    child = (
                        self._resolve_module(child_module, source, node.level)
                        if target is None or target.name == "__init__.py"
                        else None
                    )
                    if child is not None:
                        return child, remainder if separator else alias.name
                    if target is not None:
                        next_symbol = alias.name
                        if separator:
                            next_symbol = f"{next_symbol}.{remainder}"
                        return target, next_symbol
        return None

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

    def _called_local_imports(
        self, source: Path, symbol: str
    ) -> list[tuple[Path, str]]:
        try:
            tree = ast.parse(source.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, SyntaxError):
            return []
        definition = next(
            (
                node
                for node in tree.body
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == symbol
            ),
            None,
        )
        if definition is None:
            return []

        function_bindings: dict[str, tuple[Path, str]] = {}
        module_bindings: dict[str, Path] = {}
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = self._resolve_module(alias.name, source, level=0)
                    if target is not None:
                        module_bindings[alias.asname or alias.name.split(".")[0]] = target
            elif isinstance(node, ast.ImportFrom):
                target = self._resolve_module(node.module or "", source, node.level)
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    binding = alias.asname or alias.name
                    child_module = ".".join(
                        part for part in (node.module or "", alias.name) if part
                    )
                    child = (
                        self._resolve_module(child_module, source, node.level)
                        if target is None or target.name == "__init__.py"
                        else None
                    )
                    if child is not None:
                        module_bindings[binding] = child
                    elif target is not None:
                        function_bindings[binding] = (target, alias.name)

        calls = sorted(
            (node for node in ast.walk(definition) if isinstance(node, ast.Call)),
            key=lambda node: (node.lineno, node.col_offset),
        )
        selected: list[tuple[Path, str]] = []
        seen: set[tuple[str, str]] = set()
        for call in calls:
            candidate: tuple[Path, str] | None = None
            if isinstance(call.func, ast.Name):
                candidate = function_bindings.get(call.func.id)
            elif (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id in module_bindings
            ):
                candidate = (
                    module_bindings[call.func.value.id],
                    call.func.attr,
                )
            if candidate is None:
                continue
            key = (candidate[0].as_posix(), candidate[1])
            if key not in seen:
                seen.add(key)
                selected.append(candidate)
        return selected

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
