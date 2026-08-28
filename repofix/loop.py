from dataclasses import asdict
from math import ceil
from pathlib import Path
from typing import Callable
from .budget import BudgetLimits, ModelPricing, classify_provider_failure
from .config import Settings
from .context import ContextBuilder
from .evaluation import RepairEvaluator
from .preflight import RepositoryPreflight
from .provider import (
    InvalidModelActionError,
    ModelRequestLimitReached,
    ModelTokenLimitReached,
)
from .schemas import RunState
from .stability import RepeatedActionGuard
from .storage import RunStore
from .tools import ToolRuntime
from .text import compact_text
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
        test_command: str | None = None,
        final_test_command: str | None = None,
        execution_backend: str | None = None,
        docker_image: str | None = None,
        command_timeout_seconds: int | None = None,
        seed_failure_context: bool | None = None,
        verify_after_patch: bool | None = None,
    ):
        settings = Settings.from_env()
        self.provider, self.max_steps = provider, max_steps
        self.repo = Path(repo).resolve()
        if not self.repo.is_dir():
            raise FileNotFoundError(f"repository directory not found: {self.repo}")
        self.test_command = settings.test_command if test_command is None else test_command
        configured_final_command = (
            settings.final_test_command if final_test_command is None else final_test_command
        )
        self.final_test_command = configured_final_command or self.test_command
        self.execution_backend = (
            settings.execution_backend if execution_backend is None else execution_backend
        )
        self.docker_image = settings.docker_image if docker_image is None else docker_image
        self.command_timeout_seconds = (
            settings.command_timeout_seconds
            if command_timeout_seconds is None
            else command_timeout_seconds
        )
        if self.command_timeout_seconds <= 0:
            raise ValueError("command timeout must be positive")
        self.seed_failure_context = (
            settings.seed_failure_context
            if seed_failure_context is None
            else seed_failure_context
        )
        self.verify_after_patch = (
            settings.verify_after_patch
            if verify_after_patch is None
            else verify_after_patch
        )
        self.state = RunState(
            "", str(self.repo), test_command=self.test_command,
            final_test_command=self.final_test_command,
            execution_backend=self.execution_backend, docker_image=self.docker_image,
            command_timeout_seconds=self.command_timeout_seconds,
            seed_failure_context=self.seed_failure_context,
            verify_after_patch=self.verify_after_patch,
        )
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
        self.state.preflight = RepositoryPreflight(
            str(self.repo), self.test_command, self.execution_backend, self.docker_image,
            self.final_test_command,
        ).run()
        self._save_checkpoint()
        self._notify({"type": "preflight", "success": self.state.preflight.success})
        if not self.state.preflight.success:
            self.state.status = "preflight_failed"
            self.state.failure_kind = "preflight"
            self.state.error = "; ".join(
                check.message for check in self.state.preflight.checks if check.status == "fail"
            )[:2000]
            self._save_checkpoint()
            return self.state
        if not resume:
            self.state.evaluation.baseline = self.evaluator.run_tests()
            self._save_checkpoint()
            self._notify({
                "type": "baseline",
                "success": self.state.evaluation.baseline.success,
                "execution_backend": self.state.evaluation.baseline.execution_backend,
            })
        context_builder = ContextBuilder(
            self.state.repo,
            task,
            self.max_context_chars,
            baseline=self.state.evaluation.baseline,
            preflight=self.state.preflight,
            seed_failure_context=self.seed_failure_context,
        )
        for step in range(self.state.step, self.max_steps):
            context_result = context_builder.build_with_metadata(self.state.history)
            context = context_result.text
            estimated_next_tokens = self._estimate_next_request_tokens(context)
            denied = self.budget.admission_denied(self.state.usage, estimated_next_tokens)
            if denied:
                self._finish_budget(*denied)
                break
            self.state.step = step + 1
            context_snapshot = {"step": self.state.step, **context_result.metadata}
            self.state.context_snapshots.append(context_snapshot)
            self._save_checkpoint()
            source_count = len(
                context_result.metadata["failure_context"]["sources"]
            )
            self._notify({
                "type": "model_request",
                "step": self.state.step,
                "context_chars": context_result.metadata["context_chars"],
                "seeded_sources": source_count,
            })
            try:
                request_limiter = getattr(self.provider, "limit_next_action_requests", None)
                if request_limiter is not None:
                    request_limiter(self.budget.remaining_requests(self.state.usage))
                token_limiter = getattr(self.provider, "limit_next_action_tokens", None)
                if token_limiter is not None:
                    token_limiter(self.budget.remaining_tokens(self.state.usage))
                policy_setter = getattr(self.provider, "set_action_policy", None)
                if policy_setter is not None:
                    policy_setter(context_result.metadata["repair_phase"])
                decision = self.provider.next_action(context)
            except ModelRequestLimitReached as exc:
                self.state.usage.add(exc.usage)
                self.state.estimated_cost_usd = self.pricing.estimate_usd(self.state.usage)
                self._finish_budget(
                    "request_budget",
                    f"model request budget reached during provider retry "
                    f"({self.state.usage.requests}/{self.budget.max_requests})"
                    + (
                        f"; last format error: {exc.last_format_error}"
                        if exc.last_format_error
                        else ""
                    ),
                )
                break
            except ModelTokenLimitReached as exc:
                self.state.usage.add(exc.usage)
                self.state.estimated_cost_usd = self.pricing.estimate_usd(self.state.usage)
                self._finish_budget(
                    "token_budget_reserve",
                    f"provider retry estimated at {exc.estimated_next_tokens} tokens but "
                    f"only {max(exc.allowance - exc.usage.total_tokens, 0)} remain"
                    + (
                        f"; last format error: {exc.last_format_error}"
                        if exc.last_format_error
                        else ""
                    ),
                )
                break
            except InvalidModelActionError as exc:
                self.state.usage.add(exc.usage)
                self.state.estimated_cost_usd = self.pricing.estimate_usd(self.state.usage)
                self.state.error = f"{type(exc).__name__}: {exc}"[:2000]
                self.state.failure_kind = "invalid_model_output"
                self._record({
                    "step": self.state.step,
                    "error": self.state.error,
                    "usage": asdict(exc.usage),
                })
                self._finish_after_provider_error()
                break
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
            decision_metadata = {"usage": asdict(decision.usage)}
            if decision.diagnostics:
                decision_metadata["provider_diagnostics"] = decision.diagnostics
            repeated_action = self.repeated_action_guard.reason(self.state.history, action)
            if repeated_action:
                self._record({
                    "step": self.state.step,
                    "action": asdict(action),
                    "guard": "repeated_action",
                    **decision_metadata,
                })
                self._finish_stalled("repeated_action", repeated_action)
                break
            if action.name == "finish":
                self.state.summary = action.arguments.get("summary", "")
                self.state.evaluation.final = self.evaluator.run_final_tests()
                self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
                self.state.status = "success" if self.state.evaluation.final.success else "verification_failed"
                self.state.failure_kind = "" if self.state.status == "success" else "verification"
                self._record(
                    {
                        "step": self.state.step,
                        "action": asdict(action),
                        **decision_metadata,
                    }
                )
                break
            obs = self.runtime.execute(action.name, action.arguments)
            if (
                self.verify_after_patch
                and action.name == "apply_patch"
                and obs.success
                and obs.metadata.get("changed")
            ):
                self._attach_post_patch_verification(obs)
            self._record(
                {
                    "step": self.state.step,
                    "action": asdict(action),
                    "observation": asdict(obs),
                    **decision_metadata,
                }
            )
        else:
            self.state.status = "budget_exhausted"
            self.state.failure_kind = "step_budget"
            self.state.error = f"step budget reached ({self.max_steps}/{self.max_steps})"
            self.state.evaluation.final = self.evaluator.run_final_tests()
            self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
            self._save_checkpoint()
        self._maybe_rollback()
        return self.state

    def _configure_runtime(self) -> None:
        artifact_dir = self.store.root / "runs" / self.state.run_id / "workspace"
        self.journal = WorkspaceJournal(
            str(self.repo), artifact_dir, self.max_changed_files
        )
        self.runtime = ToolRuntime(
            str(self.repo), journal=self.journal,
            execution_backend=self.execution_backend,
            docker_image=self.docker_image,
            command_timeout_seconds=self.command_timeout_seconds,
        )
        self.evaluator = RepairEvaluator(
            self.runtime, self.test_command, self.final_test_command
        )

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
        self.state.evaluation.post_rollback = self.evaluator.run_final_tests()
        self.state.evaluation.rollback_error = ""
        self._save_checkpoint()
        self._notify({"type": "rollback", "files": restored})

    def _attach_post_patch_verification(self, observation) -> None:
        snapshot = self.evaluator.run_tests()
        observation.metadata["post_patch_test"] = asdict(snapshot)
        status = "passed" if snapshot.success else "failed"
        test_output = compact_text(snapshot.output, 4_000)[0]
        combined = (
            f"{observation.output}\n\n"
            f"Harness post-patch focused pytest: {status}\n"
            f"Command: {snapshot.command}\n{test_output}"
        )
        observation.output = compact_text(combined, self.runtime.max_output_chars)[0]

    def _finish_after_provider_error(self) -> None:
        changed_files = self.evaluator.changed_files(self.state.history)
        self.state.evaluation.changed_files = changed_files
        if changed_files:
            self.state.evaluation.final = self.evaluator.run_final_tests()
        repair_verified = (
            self.state.evaluation.final is not None
            and self.state.evaluation.final.success
            and bool(changed_files)
            and self.state.evaluation.baseline is not None
            and not self.state.evaluation.baseline.success
        )
        if repair_verified:
            self.state.status = "success"
            self.state.failure_kind = ""
            self.state.error = ""
            self.state.summary = (
                "Repair independently verified after malformed provider output."
            )
        else:
            self.state.status = "error"
        self._save_checkpoint()

    def _finish_budget(self, failure_kind: str, message: str) -> None:
        self.state.evaluation.final = self.evaluator.run_final_tests()
        self.state.evaluation.changed_files = self.evaluator.changed_files(self.state.history)
        repair_verified = (
            self.state.evaluation.final.success
            and bool(self.state.evaluation.changed_files)
            and self.state.evaluation.baseline is not None
            and not self.state.evaluation.baseline.success
        )
        if repair_verified:
            self.state.status = "success"
            self.state.failure_kind = ""
            self.state.error = ""
            self.state.summary = "Repair independently verified at the model budget boundary."
        else:
            self.state.status = "budget_exhausted"
            self.state.failure_kind = failure_kind
            self.state.error = message
        self._save_checkpoint()
        self._notify({
            "type": "budget",
            "failure_kind": failure_kind,
            "error": message,
            "repair_verified": repair_verified,
        })

    def _estimate_next_request_tokens(self, context: str) -> int:
        context_estimate = ceil(len(context) / 3) + 2_000
        if not self.state.usage.requests:
            return context_estimate
        historical_average = ceil(
            self.state.usage.total_tokens / self.state.usage.requests
        )
        return max(context_estimate, historical_average)

    def _finish_stalled(self, failure_kind: str, message: str) -> None:
        self.state.status = "stalled"
        self.state.failure_kind = failure_kind
        self.state.error = message
        self.state.evaluation.final = self.evaluator.run_final_tests()
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
        if state.test_command != self.test_command:
            raise ValueError("checkpoint test command does not match --test-command")
        if state.final_test_command != self.final_test_command:
            raise ValueError(
                "checkpoint final test command does not match --final-test-command"
            )
        if state.execution_backend != self.execution_backend:
            raise ValueError("checkpoint execution backend does not match")
        if state.docker_image != self.docker_image:
            raise ValueError("checkpoint Docker image does not match")
        if state.command_timeout_seconds != self.command_timeout_seconds:
            raise ValueError("checkpoint command timeout does not match")
        if state.seed_failure_context != self.seed_failure_context:
            raise ValueError("checkpoint failure-context setting does not match")
        if state.verify_after_patch != self.verify_after_patch:
            raise ValueError("checkpoint post-patch verification setting does not match")
        return state
