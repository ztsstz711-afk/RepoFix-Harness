import subprocess
import sys
import os
import time
from pathlib import Path
from .permissions import PermissionPolicy
from .registry import validate_action
from .schemas import Observation

class ToolRuntime:
    def __init__(self, repo: str):
        self.repo = Path(repo).resolve()
        self.permissions = PermissionPolicy(self.repo)

    def execute(self, name: str, args: dict) -> Observation:
        try:
            error = validate_action(name, args)
            if error:
                raise ValueError(error)
            if name == "list":
                files = (p for p in self.repo.rglob("*") if p.is_file() and self.permissions.is_visible(p))
                return Observation(name, "\n".join(str(p.relative_to(self.repo)) for p in files))
            if name == "search":
                needle = args["query"]; hits = []
                root = self.permissions.ensure_readable(args.get("path", "."))
                candidates = [root] if root.is_file() else root.rglob("*.py")
                for p in candidates:
                    if not self.permissions.is_visible(p):
                        continue
                    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                        if needle in line: hits.append(f"{p.relative_to(self.repo)}:{i}: {line}")
                        if len(hits) >= 100:
                            return Observation(name, "\n".join(hits) + "\n[results truncated at 100 matches]")
                return Observation(name, "\n".join(hits))
            if name == "read":
                lines = self.permissions.ensure_readable(args["path"]).read_text(encoding="utf-8").splitlines()
                start = max(int(args.get("start_line", 1)), 1)
                end = min(int(args.get("end_line", len(lines))), len(lines))
                return Observation(name, "\n".join(lines[start - 1 : end]))
            if name == "apply_patch":
                p = self.permissions.ensure_writable(args["path"])
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(args["content"], encoding="utf-8")
                return Observation(name, f"updated {args['path']}")
            if name in {"git_diff", "git_status"}:
                return self._command(name, ["git", "diff"] if name == "git_diff" else ["git", "status", "--short"])
            if name == "run_command":
                command = args["command"]
                parts = command.split()
                if parts[:1] == ["pytest"]:
                    return self._command(name, [sys.executable, "-m", "pytest", *parts[1:]])
                if parts[:3] == ["python", "-m", "pytest"]:
                    return self._command(name, [sys.executable, "-m", "pytest", *parts[3:]])
                raise PermissionError("command denied; only pytest is permitted")
            return Observation(name, f"unknown tool: {name}", False)
        except Exception as e: return Observation(name, str(e), False)

    def _command(self, tool_name: str, command: list[str]) -> Observation:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        started = time.perf_counter()
        p = subprocess.run(command, cwd=self.repo, text=True, capture_output=True, timeout=30, env=env)
        duration_ms = int((time.perf_counter() - started) * 1000)
        return Observation(tool_name, (p.stdout + p.stderr)[-12000:], p.returncode == 0, duration_ms)
