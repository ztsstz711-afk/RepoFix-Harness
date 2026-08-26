from dataclasses import asdict
from pathlib import Path
from .config import Settings
from .context import ContextBuilder
from .evaluation import RepairEvaluator
from .schemas import RunState
from .storage import RunStore
from .tools import ToolRuntime

class AgentLoop:
    def __init__(self, provider, repo: str, max_steps: int = 12, max_context_chars: int | None = None):
        self.provider, self.runtime, self.max_steps = provider, ToolRuntime(repo), max_steps
        self.evaluator = RepairEvaluator(self.runtime)
        self.state = RunState("", str(Path(repo).resolve()))
        self.store = RunStore(repo)
        self.max_context_chars = max_context_chars or Settings.from_env().max_context_chars

    def run(self, task: str, resume: bool = False) -> RunState:
        if resume:
            self.state = self._load_checkpoint(task)
            if self.state.status == "success":
                return self.state
            self.state.status = "running"
            self.state.error = ""
        else:
            self.state.task = task
            self.state.evaluation.baseline = self.evaluator.run_tests()
            self._save_checkpoint()
        context_builder = ContextBuilder(self.state.repo, task, self.max_context_chars)
        for step in range(self.state.step, self.max_steps):
            self.state.step = step + 1
            context = context_builder.build(self.state.history)
            try:
                decision = self.provider.next_action(context)
            except Exception as exc:
                self.state.status = "error"
                self.state.error = f"{type(exc).__name__}: {exc}"[:2000]
                self.state.record({"step": self.state.step, "error": self.state.error})
                self._save_checkpoint()
                break
            action = decision.action
            self.state.model = decision.model or self.state.model
            self.state.usage.add(decision.usage)
            if action.name == "finish":
                self.state.summary = action.arguments.get("summary", "")
                self.state.evaluation.final = self.evaluator.run_tests()
                self.state.evaluation.changed_files = self.evaluator.changed_files()
                self.state.status = "success" if self.state.evaluation.final.success else "verification_failed"
                self.state.record({"step": self.state.step, "action": asdict(action), "usage": asdict(decision.usage)})
                self._save_checkpoint()
                break
            obs = self.runtime.execute(action.name, action.arguments)
            self.state.record({"step": self.state.step, "action": asdict(action), "observation": asdict(obs), "usage": asdict(decision.usage)})
            self._save_checkpoint()
        else:
            self.state.status = "budget_exhausted"
            self.state.evaluation.final = self.evaluator.run_tests()
            self.state.evaluation.changed_files = self.evaluator.changed_files()
            self._save_checkpoint()
        return self.state

    def _save_checkpoint(self) -> None:
        self.store.save(self.state)

    def _load_checkpoint(self, task: str) -> RunState:
        state = self.store.load_latest()
        if Path(state.repo).resolve() != self.runtime.repo:
            raise ValueError("checkpoint repository does not match the requested repository")
        if state.task != task:
            raise ValueError("checkpoint task does not match --task")
        return state
