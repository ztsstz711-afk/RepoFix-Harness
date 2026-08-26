import subprocess
from pathlib import Path
from .schemas import Observation

class ToolRuntime:
    def __init__(self, repo: str): self.repo = Path(repo).resolve()
    def _path(self, rel: str) -> Path:
        p = (self.repo / rel).resolve()
        if self.repo not in p.parents and p != self.repo: raise ValueError("path escapes repository")
        return p
    def execute(self, name: str, args: dict) -> Observation:
        try:
            if name == "list": return Observation(name, "\n".join(str(p.relative_to(self.repo)) for p in self.repo.rglob("*") if p.is_file()))
            if name == "search":
                needle = args["query"]; hits = []
                for p in self.repo.rglob("*.py"):
                    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                        if needle in line: hits.append(f"{p.relative_to(self.repo)}:{i}: {line}")
                return Observation(name, "\n".join(hits))
            if name == "read": return Observation(name, self._path(args["path"]).read_text(encoding="utf-8"))
            if name == "apply_patch":
                p = self._path(args["path"]); p.write_text(args["content"], encoding="utf-8"); return Observation(name, f"updated {args['path']}")
            if name in {"git_diff", "git_status"}: return self._command(["git", "diff"] if name == "git_diff" else ["git", "status", "--short"])
            if name == "run_command":
                command = args["command"]
                if not command.startswith("pytest") and command not in {"python -m pytest", "python -m pytest -q"}: raise ValueError("command not allowed in V0.1")
                return self._command(command.split())
            return Observation(name, f"unknown tool: {name}", False)
        except Exception as e: return Observation(name, str(e), False)
    def _command(self, command: list[str]) -> Observation:
        p = subprocess.run(command, cwd=self.repo, text=True, capture_output=True, timeout=30)
        return Observation("command", (p.stdout + p.stderr)[-12000:], p.returncode == 0)
