from pathlib import Path

from .evaluation import RepairEvaluator
from .schemas import RunState, utc_now
from .storage import RunStore
from .tools import ToolRuntime
from .workspace import WorkspaceJournal


class RunManager:
    def __init__(self, repo: str):
        self.repo = Path(repo).resolve()
        self.store = RunStore(str(self.repo))

    def list_runs(self) -> list[dict]:
        runs_root = self.store.root / "runs"
        if not runs_root.exists():
            return []
        summaries = []
        for directory in runs_root.iterdir():
            if not directory.is_dir():
                continue
            try:
                state = self.store.load_run(directory.name)
            except (FileNotFoundError, ValueError, TypeError):
                continue
            summaries.append(self.summary(state))
        return sorted(summaries, key=lambda item: item["created_at"], reverse=True)

    def show(self, run_id: str) -> RunState:
        state = self.store.load_latest() if run_id == "latest" else self.store.load_run(run_id)
        if Path(state.repo).resolve() != self.repo:
            raise ValueError("run repository does not match the requested repository")
        return state

    def rollback(self, run_id: str, force: bool = False) -> RunState:
        state = self.show(run_id)
        try:
            latest_id = self.store.load_latest().run_id
        except FileNotFoundError:
            latest_id = None
        journal = WorkspaceJournal(
            str(self.repo),
            self.store.root / "runs" / state.run_id / "workspace",
            max_changed_files=0,
        )
        if not journal.tracked_files():
            raise ValueError(f"run has no tracked file changes: {state.run_id}")
        restored = journal.rollback(force=force)
        state.evaluation.rollback_performed = True
        state.evaluation.rollback_files = restored
        state.evaluation.rollback_error = ""
        state.evaluation.post_rollback = RepairEvaluator(
            ToolRuntime(str(self.repo)), state.test_command
        ).run_tests()
        state.updated_at = utc_now()
        self.store.save(state, update_latest=state.run_id == latest_id)
        return state

    @staticmethod
    def summary(state: RunState) -> dict:
        return {
            "run_id": state.run_id,
            "status": state.status,
            "task": state.task,
            "model": state.model,
            "steps": state.step,
            "requests": state.usage.requests,
            "tokens": state.usage.total_tokens,
            "changed_files": state.evaluation.changed_files,
            "rollback_performed": state.evaluation.rollback_performed,
            "created_at": state.created_at,
            "updated_at": state.updated_at,
        }
