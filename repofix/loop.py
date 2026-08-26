from dataclasses import asdict
from pathlib import Path
from typing import Callable
from .budget import BudgetLimits, ModelPricing, classify_provider_failure
from .config import Settings
from .context import ContextBuilder
from .evaluation import RepairEvaluator
from .schemas import RunState
from .storage import RunStore
from .tools import ToolRuntime

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
    ):
        settings = Settings.from_env()
        self.provider, self.runtime, self.max_steps = provider, ToolRuntime(repo), max_steps
        self.evaluator = RepairEvaluator(self.runtime)
        self.state = RunState("", str(Path(repo).resolve()))
        self.store = RunStore(repo)
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

    def run(self, task: str, resume: bool = False) -> RunState:
        if resume:
            self.state = self._load_checkpoint(task)
            if self.state.status == "success":
                return self.state
            self.state.status = "running"
            self.state.error = ""
            self.state.failure_kind = ""
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
        return self.state

    def _finish_budget(self, failure_kind: str, message: str) -> None:
        self.state.status = "budget_exhausted"
        self.state.failure_kind = failure_kind
        self.state.error = message
        self.state.evaluation.final = self.evaluator.run_tests()
        self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
        self._save_checkpoint()
        self._notify({"type": "budget", "failure_kind": failure_kind, "error": message})

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
        if Path(state.repo).resolve() != self.runtime.repo:
            raise ValueError("checkpoint repository does not match the requested repository")
        if state.task != task:
            raise ValueError("checkpoint task does not match --task")
        return state
