import subprocess
import sys
import os
import time
from hashlib import sha256
from pathlib import Path
from .permissions import PermissionPolicy
from .registry import validate_action
from .schemas import Observation
from .text import compact_text
from .workspace import WorkspaceJournal

class ToolRuntime:
    def __init__(
        self,
        repo: str,
        max_output_chars: int = 12_000,
        journal: WorkspaceJournal | None = None,
    ):
        self.repo = Path(repo).resolve()
        self.permissions = PermissionPolicy(self.repo)
        self.max_output_chars = max_output_chars
        self.journal = journal

    def execute(self, name: str, args: dict) -> Observation:
        try:
            observation = self._execute(name, args)
        except Exception as exc:
            observation = Observation(name, str(exc), False)
        original_chars = len(observation.output)
        observation.output, omitted = compact_text(observation.output, self.max_output_chars)
        observation.metadata.setdefault("output_chars", original_chars)
        observation.metadata.setdefault("output_truncated", omitted > 0)
        return observation

    def _execute(self, name: str, args: dict) -> Observation:
        error = validate_action(name, args)
        if error:
            raise ValueError(error)
        if name == "list":
            files = (p for p in self.repo.rglob("*") if p.is_file() and self.permissions.is_visible(p))
            return Observation(name, "\n".join(str(p.relative_to(self.repo)) for p in files))
        if name == "search":
            needle = args["query"]
            hits = []
            root = self.permissions.ensure_readable(args.get("path", "."))
            candidates = [root] if root.is_file() else root.rglob("*.py")
            for p in candidates:
                if not self.permissions.is_visible(p):
                    continue
                for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                    if needle in line:
                        hits.append(f"{p.relative_to(self.repo)}:{i}: {line}")
                    if len(hits) >= 100:
                        return Observation(name, "\n".join(hits) + "\n[results truncated at 100 matches]")
            return Observation(name, "\n".join(hits))
        if name == "read":
            lines = self.permissions.ensure_readable(args["path"]).read_text(encoding="utf-8").splitlines()
            start = max(int(args.get("start_line", 1)), 1)
            end = min(int(args.get("end_line", len(lines))), len(lines))
            return Observation(name, "\n".join(lines[start - 1 : end]))
        if name == "apply_patch":
            path = self.permissions.ensure_writable(args["path"])
            before_hash = sha256(path.read_bytes()).hexdigest() if path.exists() else None
            encoded = args["content"].encode("utf-8")
            after_hash = sha256(encoded).hexdigest()
            changed = before_hash != after_hash
            if self.journal and changed:
                self.journal.capture(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded)
            if self.journal and changed:
                self.journal.record_after(path, after_hash)
            return Observation(
                name,
                f"{'updated' if changed else 'unchanged'} {args['path']}",
                metadata={
                    "path": args["path"],
                    "before_sha256": before_hash,
                    "after_sha256": after_hash,
                    "changed": changed,
                },
            )
        if name in {"git_diff", "git_status"}:
            return self._command(name, ["git", "diff"] if name == "git_diff" else ["git", "status", "--short"])
        if name == "run_command":
            command = args["command"]
            parts = command.split()
            if parts[:1] == ["pytest"]:
                self.permissions.ensure_pytest_arguments(parts[1:])
                return self._command(name, [sys.executable, "-m", "pytest", *parts[1:]])
            if parts[:3] == ["python", "-m", "pytest"]:
                self.permissions.ensure_pytest_arguments(parts[3:])
                return self._command(name, [sys.executable, "-m", "pytest", *parts[3:]])
            raise PermissionError("command denied; only pytest is permitted")
        return Observation(name, f"unknown tool: {name}", False)

    def _command(self, tool_name: str, command: list[str]) -> Observation:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        started = time.perf_counter()
        p = subprocess.run(command, cwd=self.repo, text=True, capture_output=True, timeout=30, env=env)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return Observation(tool_name, p.stdout + p.stderr, p.returncode == 0, duration_ms)
