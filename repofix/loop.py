from dataclasses import asdict
from pathlib import Path
from typing import Callable
from .budget import BudgetLimits, ModelPricing, classify_provider_failure
from .config import Settings
from .context import ContextBuilder
from .evaluation import RepairEvaluator
from .schemas import RunState
from .stability import RepeatedActionGuard
from .storage import RunStore
from .tools import ToolRuntime
from .workspace import WorkspaceJournal

class AgentLoop:
    def __init__(
        self,
        provider,
        repo: str,
        max_steps: int = 12,
        max_context_chars: int | None = None,
        on_event: Callable[[RunState, dict], None] | None = None,
        max_requests: int | None = None,
        max_tokens: int | None = None,
        pricing: ModelPricing | None = None,
        max_identical_actions: int | None = None,
        max_changed_files: int | None = None,
        rollback_on_failure: bool | None = None,
    ):
        settings = Settings.from_env()
        self.provider, self.max_steps = provider, max_steps
        self.repo = Path(repo).resolve()
        self.state = RunState("", str(self.repo))
        self.store = RunStore(repo)
        self.max_changed_files = (
            settings.max_changed_files if max_changed_files is None else max_changed_files
        )
        self.rollback_on_failure = (
            settings.rollback_on_failure if rollback_on_failure is None else rollback_on_failure
        )
        self._configure_runtime()
        self.max_context_chars = max_context_chars or settings.max_context_chars
        self.on_event = on_event
        self.budget = BudgetLimits(
            settings.max_requests if max_requests is None else max_requests,
            settings.max_tokens if max_tokens is None else max_tokens,
        )
        self.pricing = pricing or ModelPricing(
            settings.input_cost_per_million,
            settings.output_cost_per_million,
            settings.cached_input_cost_per_million,
        )
        self.repeated_action_guard = RepeatedActionGuard(
            settings.max_identical_actions
            if max_identical_actions is None
            else max_identical_actions
        )

    def run(self, task: str, resume: bool = False) -> RunState:
        if resume:
            self.state = self._load_checkpoint(task)
            self._configure_runtime()
            if self.state.status == "success":
                return self.state
            self.state.status = "running"
            self.state.error = ""
            self.state.failure_kind = ""
            self.state.evaluation.rollback_performed = False
            self.state.evaluation.rollback_files = []
            self.state.evaluation.post_rollback = None
            self.state.evaluation.rollback_error = ""
        else:
            self.state.task = task
            self.state.evaluation.baseline = self.evaluator.run_tests()
            self._save_checkpoint()
            self._notify({"type": "baseline", "success": self.state.evaluation.baseline.success})
        context_builder = ContextBuilder(self.state.repo, task, self.max_context_chars)
        for step in range(self.state.step, self.max_steps):
            exceeded = self.budget.exceeded(self.state.usage)
            if exceeded:
                self._finish_budget(*exceeded)
                break
            self.state.step = step + 1
            context = context_builder.build(self.state.history)
            self._notify({"type": "model_request", "step": self.state.step})
            try:
                decision = self.provider.next_action(context)
            except Exception as exc:
                self.state.status = "error"
                self.state.error = f"{type(exc).__name__}: {exc}"[:2000]
                self.state.failure_kind = classify_provider_failure(exc)
                self._record({"step": self.state.step, "error": self.state.error})
                break
            action = decision.action
            self.state.model = decision.model or self.state.model
            self.state.usage.add(decision.usage)
            self.state.estimated_cost_usd = self.pricing.estimate_usd(self.state.usage)
            repeated_action = self.repeated_action_guard.reason(self.state.history, action)
            if repeated_action:
                self._record({
                    "step": self.state.step,
                    "action": asdict(action),
                    "guard": "repeated_action",
                    "usage": asdict(decision.usage),
                })
                self._finish_stalled("repeated_action", repeated_action)
                break
            if action.name == "finish":
                self.state.summary = action.arguments.get("summary", "")
                self.state.evaluation.final = self.evaluator.run_tests()
                self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
                self.state.status = "success" if self.state.evaluation.final.success else "verification_failed"
                self.state.failure_kind = "" if self.state.status == "success" else "verification"
                self._record({"step": self.state.step, "action": asdict(action), "usage": asdict(decision.usage)})
                break
            obs = self.runtime.execute(action.name, action.arguments)
            self._record({"step": self.state.step, "action": asdict(action), "observation": asdict(obs), "usage": asdict(decision.usage)})
        else:
            self.state.status = "budget_exhausted"
            self.state.failure_kind = "step_budget"
            self.state.error = f"step budget reached ({self.max_steps}/{self.max_steps})"
            self.state.evaluation.final = self.evaluator.run_tests()
            self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
            self._save_checkpoint()
        self._maybe_rollback()
        return self.state

    def _configure_runtime(self) -> None:
        artifact_dir = self.store.root / "runs" / self.state.run_id / "workspace"
        self.journal = WorkspaceJournal(
            str(self.repo), artifact_dir, self.max_changed_files
        )
        self.runtime = ToolRuntime(str(self.repo), journal=self.journal)
        self.evaluator = RepairEvaluator(self.runtime)

    def _maybe_rollback(self) -> None:
        if self.state.status == "success" or not self.rollback_on_failure:
            return
        if not self.journal.has_pending_changes():
            return
        try:
            restored = self.journal.rollback()
        except Exception as exc:
            self.state.evaluation.rollback_error = f"{type(exc).__name__}: {exc}"[:2000]
            self._save_checkpoint()
            self._notify({"type": "rollback_error", "error": self.state.evaluation.rollback_error})
            return
        self.state.evaluation.rollback_performed = True
        self.state.evaluation.rollback_files = restored
        self.state.evaluation.post_rollback = self.evaluator.run_tests()
        self.state.evaluation.rollback_error = ""
        self._save_checkpoint()
        self._notify({"type": "rollback", "files": restored})

    def _finish_budget(self, failure_kind: str, message: str) -> None:
        self.state.status = "budget_exhausted"
        self.state.failure_kind = failure_kind
        self.state.error = message
        self.state.evaluation.final = self.evaluator.run_tests()
        self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
        self._save_checkpoint()
        self._notify({"type": "budget", "failure_kind": failure_kind, "error": message})

    def _finish_stalled(self, failure_kind: str, message: str) -> None:
        self.state.status = "stalled"
        self.state.failure_kind = failure_kind
        self.state.error = message
        self.state.evaluation.final = self.evaluator.run_tests()
        self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
        self._save_checkpoint()
        self._notify({"type": "stalled", "failure_kind": failure_kind, "error": message})

    def _save_checkpoint(self) -> None:
        self.store.save(self.state)

    def _record(self, event: dict) -> None:
        self.state.record(event)
        self._save_checkpoint()
        self._notify({"type": "step", **event})

    def _notify(self, event: dict) -> None:
        if self.on_event:
            self.on_event(self.state, event)

    def _load_checkpoint(self, task: str) -> RunState:
        state = self.store.load_latest()
        if Path(state.repo).resolve() != self.repo:
            raise ValueError("checkpoint repository does not match the requested repository")
        if state.task != task:
            raise ValueError("checkpoint task does not match --task")
        return state
