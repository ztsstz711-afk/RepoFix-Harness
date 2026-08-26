import json
import re
from pathlib import Path

from .schemas import RunState


class RunStore:
    def __init__(self, repo: str):
        self.root = Path(repo).resolve() / ".repofix"

    def save(self, state: RunState, update_latest: bool = True) -> None:
        payload = json.dumps(state.to_dict(), indent=2)
        run_dir = self._run_dir(state.run_id)
        self._atomic_write(run_dir / "trace.json", payload)
        if update_latest:
            self._atomic_write(self.root / "trace.json", payload)
        if state.status != "running":
            self._atomic_write(run_dir / "result.json", payload)
            if update_latest:
                self._atomic_write(self.root / "result.json", payload)

    def load_latest(self) -> RunState:
        path = self.root / "trace.json"
        if not path.exists():
            raise FileNotFoundError(f"checkpoint not found: {path}")
        return RunState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def load_run(self, run_id: str) -> RunState:
        run_dir = self._run_dir(run_id)
        path = run_dir / "result.json"
        if not path.exists():
            path = run_dir / "trace.json"
        if not path.exists():
            raise FileNotFoundError(f"run not found: {run_id}")
        return RunState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _run_dir(self, run_id: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", run_id):
            raise ValueError(f"invalid run ID: {run_id}")
        return self.root / "runs" / run_id

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
