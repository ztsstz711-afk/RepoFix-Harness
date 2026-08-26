import json
from pathlib import Path

from .schemas import RunState


class RunStore:
    def __init__(self, repo: str):
        self.root = Path(repo).resolve() / ".repofix"

    def save(self, state: RunState) -> None:
        payload = json.dumps(state.to_dict(), indent=2)
        run_dir = self.root / "runs" / state.run_id
        self._atomic_write(run_dir / "trace.json", payload)
        self._atomic_write(self.root / "trace.json", payload)
        if state.status != "running":
            self._atomic_write(run_dir / "result.json", payload)
            self._atomic_write(self.root / "result.json", payload)

    def load_latest(self) -> RunState:
        path = self.root / "trace.json"
        if not path.exists():
            raise FileNotFoundError(f"checkpoint not found: {path}")
        return RunState.from_dict(json.loads(path.read_text(encoding="utf-8")))

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
