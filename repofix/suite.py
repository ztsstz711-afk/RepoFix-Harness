import hashlib
import json
import math
import re
import shutil
import statistics
import tempfile
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .loop import AgentLoop
from .reporting import render_evaluation_markdown, validate_evaluation_report
from .schemas import TokenUsage, utc_now
from .tools import parse_pytest_invocation


class EvaluationInputChangedError(RuntimeError):
    pass


@dataclass(frozen=True)
class SuiteTask:
    id: str
    repo: str
    task: str
    max_steps: int = 12
    max_requests: int | None = None
    max_tokens: int | None = None
    max_identical_actions: int | None = None
    max_changed_files: int | None = None
    rollback_on_failure: bool | None = None
    test_command: str = "pytest -q"
    final_test_command: str | None = None
    execution_backend: str = "local"
    docker_image: str = "repofix-pytest:latest"
    command_timeout_seconds: int = 30
    seed_failure_context: bool = True
    verify_after_patch: bool = False
    tags: tuple[str, ...] = ()
    expected_changed_files: tuple[str, ...] = ()
    variant: str = "default"
    repetitions: int = 1
    case: str = ""
    source_sha256: str = ""


@dataclass(frozen=True)
class EvaluationSuite:
    name: str
    tasks: list[SuiteTask]
    baseline_variant: str | None = None
    manifest_path: str = ""
    manifest_sha256: str = ""
    max_total_requests: int | None = None


def load_suite(path: str) -> EvaluationSuite:
    manifest = Path(path).resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    name = data.get("name", manifest.stem)
    baseline_variant = data.get("baseline_variant")
    max_total_requests = data.get("max_total_requests")
    if max_total_requests is not None and (
        isinstance(max_total_requests, bool)
        or not isinstance(max_total_requests, int)
        or max_total_requests < 1
    ):
        raise ValueError("max_total_requests must be a positive JSON integer")
    if baseline_variant is not None and (
        not isinstance(baseline_variant, str)
        or not re.fullmatch(r"[A-Za-z0-9._-]+", baseline_variant)
    ):
        raise ValueError(f"invalid baseline_variant: {baseline_variant}")
    tasks = []
    seen = set()
    for item in data.get("tasks", []):
        task_id = item["id"]
        if not re.fullmatch(r"[A-Za-z0-9._-]+", task_id):
            raise ValueError(f"invalid task id: {task_id}")
        if task_id in seen:
            raise ValueError(f"duplicate task id: {task_id}")
        seen.add(task_id)
        repo = (manifest.parent / item["repo"]).resolve()
        if not repo.is_dir():
            raise FileNotFoundError(f"task repository not found: {repo}")
        rollback_on_failure = item.get("rollback_on_failure")
        if rollback_on_failure is not None and not isinstance(rollback_on_failure, bool):
            raise ValueError("rollback_on_failure must be a JSON boolean")
        seed_failure_context = item.get("seed_failure_context", True)
        if not isinstance(seed_failure_context, bool):
            raise ValueError("seed_failure_context must be a JSON boolean")
        verify_after_patch = item.get("verify_after_patch", False)
        if not isinstance(verify_after_patch, bool):
            raise ValueError("verify_after_patch must be a JSON boolean")
        tags = _string_list(item, "tags")
        expected_changed_files = _string_list(item, "expected_changed_files")
        test_command = item.get("test_command", "pytest -q")
        parse_pytest_invocation(test_command)
        final_test_command = item.get("final_test_command")
        if final_test_command is not None:
            parse_pytest_invocation(final_test_command)
        variant = item.get("variant", "default")
        if not isinstance(variant, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", variant):
            raise ValueError(f"invalid variant: {variant}")
        case = item.get("case", task_id)
        if not isinstance(case, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", case):
            raise ValueError(f"invalid case: {case}")
        repetitions = item.get("repetitions", 1)
        if isinstance(repetitions, bool) or not isinstance(repetitions, int):
            raise ValueError("repetitions must be a JSON integer")
        if repetitions < 1 or repetitions > 100:
            raise ValueError("repetitions must be between 1 and 100")
        for expected_path in expected_changed_files:
            path = Path(expected_path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe expected changed file: {expected_path}")
        max_steps = _positive_int(item, "max_steps", default=12)
        max_requests = _positive_int(item, "max_requests")
        max_tokens = _positive_int(item, "max_tokens")
        max_identical_actions = _positive_int(item, "max_identical_actions")
        max_changed_files = _positive_int(item, "max_changed_files")
        command_timeout_seconds = _positive_int(
            item, "command_timeout_seconds", default=30
        )
        tasks.append(SuiteTask(
            id=task_id,
            repo=str(repo),
            task=item["task"],
            max_steps=max_steps,
            max_requests=max_requests,
            max_tokens=max_tokens,
            max_identical_actions=max_identical_actions,
            max_changed_files=max_changed_files,
            rollback_on_failure=rollback_on_failure,
            test_command=test_command,
            final_test_command=final_test_command,
            execution_backend=item.get("execution_backend", "local"),
            docker_image=item.get("docker_image", "repofix-pytest:latest"),
            command_timeout_seconds=command_timeout_seconds,
            seed_failure_context=seed_failure_context,
            verify_after_patch=verify_after_patch,
            tags=tags,
            expected_changed_files=tuple(sorted(expected_changed_files)),
            variant=variant,
            repetitions=repetitions,
            case=case,
            source_sha256=_source_tree_sha256(repo),
        ))
    if not tasks:
        raise ValueError("evaluation suite must contain at least one task")
    if sum(task.repetitions for task in tasks) > 100:
        raise ValueError("evaluation suite must not exceed 100 total trials")
    run_keys = [
        task.id if task.repetitions == 1 else f"{task.id}--trial-{trial:02d}"
        for task in tasks
        for trial in range(1, task.repetitions + 1)
    ]
    if len(run_keys) != len(set(run_keys)):
        raise ValueError("evaluation trial output IDs collide")
    case_variants = [(task.case, task.variant) for task in tasks]
    if len(case_variants) != len(set(case_variants)):
        raise ValueError("evaluation case and variant pairs must be unique")
    if baseline_variant is not None:
        grouped: dict[str, list[SuiteTask]] = {}
        for task in tasks:
            grouped.setdefault(task.case, []).append(task)
        for case, case_tasks in grouped.items():
            variants = {task.variant for task in case_tasks}
            if baseline_variant not in variants:
                raise ValueError(
                    f"case {case} is missing baseline variant {baseline_variant}"
                )
            if len(variants) < 2:
                raise ValueError(f"case {case} requires at least two variants")
            if len({task.repetitions for task in case_tasks}) != 1:
                raise ValueError(f"case {case} variants must use equal repetitions")
    planned_request_ceiling = _planned_request_ceiling(tasks)
    if max_total_requests is not None:
        if planned_request_ceiling is None:
            raise ValueError(
                "max_total_requests requires max_requests on every task"
            )
        if planned_request_ceiling > max_total_requests:
            raise ValueError(
                "planned task requests exceed max_total_requests "
                f"({planned_request_ceiling}/{max_total_requests})"
            )
    return EvaluationSuite(
        name,
        tasks,
        baseline_variant,
        str(manifest),
        hashlib.sha256(manifest.read_bytes()).hexdigest(),
        max_total_requests,
    )


def _string_list(item: dict, key: str) -> tuple[str, ...]:
    value = item.get(key, [])
    if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
        raise ValueError(f"{key} must be a JSON string array")
    if len(value) != len(set(value)):
        raise ValueError(f"{key} must not contain duplicates")
    return tuple(value)


def _positive_int(
    item: dict, key: str, default: int | None = None
) -> int | None:
    value = item.get(key, default)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{key} must be a positive JSON integer")
    return value


def _planned_request_ceiling(tasks: list[SuiteTask]) -> int | None:
    if any(task.max_requests is None for task in tasks):
        return None
    return sum(task.max_requests * task.repetitions for task in tasks)


_IGNORED_SOURCE_PARTS = {
    ".git",
    ".repofix",
    ".venv",
    "__pycache__",
    ".pytest_cache",
}


def _source_tree_sha256(repo: Path) -> str:
    """Hash the source snapshot that an evaluation trial is expected to copy."""
    digest = hashlib.sha256()
    paths = [
        path
        for path in repo.rglob("*")
        if not (_IGNORED_SOURCE_PARTS & set(path.relative_to(repo).parts))
    ]
    symlinks = [path.relative_to(repo).as_posix() for path in paths if path.is_symlink()]
    if symlinks:
        raise ValueError(
            "evaluation source repositories must not contain symbolic links: "
            + ", ".join(sorted(symlinks)[:5])
        )
    files = sorted(path for path in paths if path.is_file())
    for path in files:
        relative = path.relative_to(repo).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with path.open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
    return digest.hexdigest()


class EvaluationRunner:
    def __init__(
        self,
        provider_factory: Callable,
        on_event: Callable[[dict], None] | None = None,
        experiment_metadata: dict | None = None,
    ):
        self.provider_factory = provider_factory
        self.on_event = on_event
        self.experiment_metadata = dict(experiment_metadata or {})

    def run(
        self, suite: EvaluationSuite, output_dir: str, resume: bool = False
    ) -> dict:
        destination = Path(output_dir).resolve()
        has_output = destination.exists() and any(destination.iterdir())
        if has_output and not resume:
            raise FileExistsError(f"evaluation output directory is not empty: {destination}")
        if resume and not has_output:
            raise FileNotFoundError(
                f"evaluation resume data not found: {destination}"
            )
        destination.mkdir(parents=True, exist_ok=True)
        if resume:
            saved = self._load_resume_report(destination)
            self._validate_resume_report(suite, saved)
            if saved["completed"]:
                return saved
            started_at = saved["started_at"]
            results = list(saved["tasks"])
        else:
            started_at = utc_now()
            results = []

        trial_plan = self._trial_plan(suite)
        completed_keys = {result["id"] for result in results}
        if not results:
            self._write_progress(destination, suite, started_at, results)
        for index, (task, trial, run_key) in enumerate(trial_plan, start=1):
            if run_key in completed_keys:
                self._notify({
                    "type": "task_skip",
                    "index": index,
                    "total": len(trial_plan),
                    "task_id": run_key,
                    "base_task_id": task.id,
                    "variant": task.variant,
                    "trial": trial,
                })
                continue
            self._notify({
                "type": "task_start",
                "index": index,
                "total": len(trial_plan),
                "task_id": run_key,
                "base_task_id": task.id,
                "variant": task.variant,
                "trial": trial,
            })
            try:
                result = self._run_task(task, destination, trial, run_key)
            except EvaluationInputChangedError:
                raise
            except Exception as exc:
                result = self._runner_error_result(task, trial, run_key, exc)
                run_dir = destination / "runs" / run_key
                run_dir.mkdir(parents=True, exist_ok=True)
                self._atomic_write(
                    run_dir / "result.json", json.dumps(result, indent=2)
                )
                self._notify({
                    "type": "task_crash",
                    "task_id": run_key,
                    "base_task_id": task.id,
                    "variant": task.variant,
                    "trial": trial,
                    "error": result["error"],
                })
            results.append(result)
            self._write_progress(destination, suite, started_at, results)
            self._notify({
                "type": "task_end",
                "task_id": run_key,
                "base_task_id": task.id,
                "variant": task.variant,
                "trial": trial,
                "status": result["status"],
            })

        report = self._build_report(suite, started_at, results, completed=True)
        validate_evaluation_report(report)
        self._atomic_write(destination / "report.json", json.dumps(report, indent=2))
        self._atomic_write(
            destination / "report.md", render_evaluation_markdown(report)
        )
        return report

    @staticmethod
    def _trial_plan(suite: EvaluationSuite) -> list[tuple[SuiteTask, int, str]]:
        plan = []
        for trial in range(1, max(task.repetitions for task in suite.tasks) + 1):
            for task in suite.tasks:
                if trial <= task.repetitions:
                    run_key = (
                        task.id
                        if task.repetitions == 1
                        else f"{task.id}--trial-{trial:02d}"
                    )
                    plan.append((task, trial, run_key))
        return plan

    def _write_progress(
        self,
        destination: Path,
        suite: EvaluationSuite,
        started_at: str,
        results: list[dict],
    ) -> None:
        progress = self._build_report(suite, started_at, results, completed=False)
        self._atomic_write(
            destination / "progress.json", json.dumps(progress, indent=2)
        )

    @staticmethod
    def _load_resume_report(destination: Path) -> dict:
        report_path = destination / "report.json"
        progress_path = destination / "progress.json"
        path = report_path if report_path.exists() else progress_path
        if not path.exists():
            raise FileNotFoundError(
                f"evaluation progress.json not found: {destination}"
            )
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"invalid evaluation resume data: {path}") from exc
        if not isinstance(saved, dict):
            raise ValueError(f"invalid evaluation resume data: {path}")
        return saved

    def _validate_resume_report(
        self, suite: EvaluationSuite, saved: dict
    ) -> None:
        if saved.get("report_schema_version") != 1:
            raise ValueError("evaluation resume report schema does not match")
        if saved.get("suite") != suite.name:
            raise ValueError("evaluation resume suite name does not match")
        if saved.get("manifest", {}).get("sha256") != suite.manifest_sha256:
            raise ValueError("evaluation resume manifest fingerprint does not match")
        if saved.get("sources") != self._source_fingerprints(suite):
            raise ValueError("evaluation resume source fingerprints do not match")
        if saved.get("experiment", {}) != self.experiment_metadata:
            raise ValueError("evaluation resume metadata does not match")
        plan = self._trial_plan(suite)
        if saved.get("planned_trial_count") != len(plan):
            raise ValueError("evaluation resume trial count does not match")
        if not isinstance(saved.get("started_at"), str) or not isinstance(
            saved.get("completed"), bool
        ):
            raise ValueError("evaluation resume lifecycle data is invalid")
        expected = {
            run_key: (task, trial) for task, trial, run_key in plan
        }
        results = saved.get("tasks")
        if not isinstance(results, list):
            raise ValueError("evaluation resume tasks are invalid")
        seen = set()
        for result in results:
            if not isinstance(result, dict) or result.get("id") in seen:
                raise ValueError("evaluation resume task IDs are invalid")
            run_key = result["id"]
            seen.add(run_key)
            if run_key not in expected:
                raise ValueError(f"unexpected evaluation resume task: {run_key}")
            task, trial = expected[run_key]
            identity = (
                result.get("task_id"),
                result.get("variant"),
                result.get("case"),
                result.get("trial"),
                result.get("repetitions"),
                result.get("source_repo_sha256"),
            )
            expected_identity = (
                task.id,
                task.variant,
                task.case,
                trial,
                task.repetitions,
                task.source_sha256,
            )
            if identity != expected_identity:
                raise ValueError(
                    f"evaluation resume task fingerprint does not match: {run_key}"
                )
        if saved["completed"] and seen != set(expected):
            raise ValueError("completed evaluation resume report is missing tasks")

    def _build_report(
        self,
        suite: EvaluationSuite,
        started_at: str,
        results: list[dict],
        completed: bool,
    ) -> dict:
        total_usage = TokenUsage()
        for result in results:
            total_usage.add(TokenUsage(**result["usage"]))
        successes = sum(result["status"] == "success" for result in results)
        scoped_results = [result for result in results if result["changed_files_match"] is not None]
        scope_matches = sum(result["changed_files_match"] is True for result in scoped_results)
        failure_counts = {}
        for result in results:
            if result["failure_kind"]:
                failure_counts[result["failure_kind"]] = failure_counts.get(result["failure_kind"], 0) + 1
        report = {
            "report_schema_version": 1,
            "suite": suite.name,
            "manifest": {
                "path": suite.manifest_path,
                "sha256": suite.manifest_sha256,
            },
            "sources": self._source_fingerprints(suite),
            "experiment": self.experiment_metadata,
            "models": dict(sorted(Counter(
                result["model"] for result in results if result["model"]
            ).items())),
            "docker_runtime_fingerprints": self._docker_runtime_fingerprints(results),
            "request_budget": {
                "max_total_requests": suite.max_total_requests,
                "planned_request_ceiling": _planned_request_ceiling(suite.tasks),
                "actual_requests": total_usage.requests,
                "remaining_requests": (
                    max(suite.max_total_requests - total_usage.requests, 0)
                    if suite.max_total_requests is not None
                    else None
                ),
            },
            "started_at": started_at,
            "updated_at": utc_now(),
            "completed_at": utc_now() if completed else None,
            "completed": completed,
            "planned_trial_count": sum(task.repetitions for task in suite.tasks),
            "task_definition_count": len(suite.tasks),
            "task_count": len(results),
            "successes": successes,
            "success_rate": successes / len(results) if results else None,
            "total_steps": sum(result["steps"] for result in results),
            "usage": asdict(total_usage),
            "estimated_cost_usd": round(sum(result["estimated_cost_usd"] for result in results), 8),
            "failure_counts": failure_counts,
            "change_scope_evaluated": len(scoped_results),
            "change_scope_matches": scope_matches,
            "change_scope_rate": scope_matches / len(scoped_results) if scoped_results else None,
            "variants": self._variant_summaries(results),
            "baseline_variant": suite.baseline_variant,
            "variant_comparisons": self._variant_comparisons(
                results, suite.baseline_variant
            ),
            "cases": self._case_summaries(results, suite.baseline_variant),
            "tasks": results,
        }
        return report

    @staticmethod
    def _source_fingerprints(suite: EvaluationSuite) -> dict[str, dict[str, str]]:
        return {
            task.id: {
                "path": task.repo,
                "sha256": task.source_sha256,
            }
            for task in suite.tasks
        }

    @staticmethod
    def _docker_runtime_fingerprints(results: list[dict]) -> list[str]:
        return sorted({
            check["message"]
            for result in results
            for check in result.get("preflight_checks", [])
            if check.get("name") == "docker_runtime"
            and check.get("status") == "pass"
        })

    def _run_task(
        self,
        task: SuiteTask,
        destination: Path,
        trial: int,
        run_key: str,
    ) -> dict:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix=f"repofix-{task.id}-") as temporary:
            workspace = Path(temporary) / "repo"
            shutil.copytree(
                task.repo,
                workspace,
                ignore=shutil.ignore_patterns(".git", ".repofix", ".venv", "__pycache__", ".pytest_cache"),
            )
            copied_sha256 = _source_tree_sha256(workspace)
            if copied_sha256 != task.source_sha256:
                raise EvaluationInputChangedError(
                    f"evaluation source changed after suite load: {task.id}"
                )
            def forward_agent_event(state, event):
                self._notify({
                    "type": "agent_event",
                    "task_id": run_key,
                    "base_task_id": task.id,
                    "variant": task.variant,
                    "trial": trial,
                    "event": event,
                })

            state = AgentLoop(
                self.provider_factory(),
                str(workspace),
                task.max_steps,
                on_event=forward_agent_event,
                max_requests=task.max_requests,
                max_tokens=task.max_tokens,
                max_identical_actions=task.max_identical_actions,
                max_changed_files=task.max_changed_files,
                rollback_on_failure=task.rollback_on_failure,
                test_command=task.test_command,
                final_test_command=task.final_test_command,
                execution_backend=task.execution_backend,
                docker_image=task.docker_image,
                command_timeout_seconds=task.command_timeout_seconds,
                seed_failure_context=task.seed_failure_context,
                verify_after_patch=task.verify_after_patch,
            ).run(task.task)
            source_artifacts = workspace / ".repofix" / "runs" / state.run_id
            target_artifacts = destination / "runs" / run_key
            if source_artifacts.exists():
                shutil.copytree(source_artifacts, target_artifacts)

        changed_files_match = (
            state.evaluation.changed_files == list(task.expected_changed_files)
            if task.expected_changed_files
            else None
        )
        return {
            "id": run_key,
            "task_id": task.id,
            "variant": task.variant,
            "case": task.case,
            "trial": trial,
            "repetitions": task.repetitions,
            "source_repo": task.repo,
            "source_repo_sha256": task.source_sha256,
            "run_id": state.run_id,
            "status": state.status,
            "model": state.model,
            "steps": state.step,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "usage": asdict(state.usage),
            "preflight_success": state.preflight.success,
            "preflight_checks": [asdict(check) for check in state.preflight.checks],
            "baseline_success": getattr(state.evaluation.baseline, "success", None),
            "final_success": getattr(state.evaluation.final, "success", None),
            "baseline_execution": (
                state.evaluation.baseline.metadata if state.evaluation.baseline else None
            ),
            "final_execution": (
                state.evaluation.final.metadata if state.evaluation.final else None
            ),
            "test_command": state.test_command,
            "final_test_command": state.final_test_command,
            "execution_backend": state.execution_backend,
            "docker_image": state.docker_image,
            "command_timeout_seconds": state.command_timeout_seconds,
            "seed_failure_context": state.seed_failure_context,
            "verify_after_patch": state.verify_after_patch,
            "changed_files": state.evaluation.changed_files,
            "tags": list(task.tags),
            "expected_changed_files": list(task.expected_changed_files),
            "changed_files_match": changed_files_match,
            "summary": state.summary,
            "error": state.error,
            "failure_kind": state.failure_kind,
            "estimated_cost_usd": state.estimated_cost_usd,
            "context_snapshots": state.context_snapshots,
            "rollback_performed": state.evaluation.rollback_performed,
            "rollback_files": state.evaluation.rollback_files,
            "post_rollback_success": getattr(state.evaluation.post_rollback, "success", None),
            "rollback_error": state.evaluation.rollback_error,
        }

    @staticmethod
    def _runner_error_result(
        task: SuiteTask,
        trial: int,
        run_key: str,
        exc: Exception,
    ) -> dict:
        return {
            "id": run_key,
            "task_id": task.id,
            "variant": task.variant,
            "case": task.case,
            "trial": trial,
            "repetitions": task.repetitions,
            "source_repo": task.repo,
            "source_repo_sha256": task.source_sha256,
            "run_id": "",
            "status": "error",
            "model": "",
            "steps": 0,
            "duration_ms": 0,
            "usage": asdict(TokenUsage()),
            "preflight_success": False,
            "preflight_checks": [],
            "baseline_success": None,
            "final_success": None,
            "baseline_execution": None,
            "final_execution": None,
            "test_command": task.test_command,
            "final_test_command": task.final_test_command or task.test_command,
            "execution_backend": task.execution_backend,
            "docker_image": task.docker_image,
            "command_timeout_seconds": task.command_timeout_seconds,
            "seed_failure_context": task.seed_failure_context,
            "verify_after_patch": task.verify_after_patch,
            "changed_files": [],
            "tags": list(task.tags),
            "expected_changed_files": list(task.expected_changed_files),
            "changed_files_match": False if task.expected_changed_files else None,
            "summary": "",
            "error": f"{type(exc).__name__}: {exc}"[:2000],
            "failure_kind": "runner_error",
            "estimated_cost_usd": 0.0,
            "context_snapshots": [],
            "rollback_performed": False,
            "rollback_files": [],
            "post_rollback_success": None,
            "rollback_error": "",
        }

    @classmethod
    def _variant_summaries(cls, results: list[dict]) -> dict[str, dict]:
        grouped: dict[str, list[dict]] = {}
        for result in results:
            grouped.setdefault(result["variant"], []).append(result)
        summaries = {}
        for variant, trials in sorted(grouped.items()):
            successes = sum(trial["status"] == "success" for trial in trials)
            scoped = [trial for trial in trials if trial["changed_files_match"] is not None]
            scope_matches = sum(trial["changed_files_match"] is True for trial in scoped)
            summaries[variant] = {
                "trials": len(trials),
                "successes": successes,
                "success_rate": successes / len(trials),
                "change_scope_evaluated": len(scoped),
                "change_scope_matches": scope_matches,
                "change_scope_rate": scope_matches / len(scoped) if scoped else None,
                "requests": cls._metric_summary(
                    [trial["usage"]["requests"] for trial in trials]
                ),
                "tokens": cls._metric_summary(
                    [trial["usage"]["total_tokens"] for trial in trials]
                ),
                "steps": cls._metric_summary([trial["steps"] for trial in trials]),
                "estimated_cost_usd": cls._metric_summary(
                    [trial["estimated_cost_usd"] for trial in trials], digits=8
                ),
            }
        return summaries

    @staticmethod
    def _metric_summary(values: list[float], digits: int = 2) -> dict:
        return {
            "total": round(sum(values), digits),
            "mean": round(statistics.mean(values), digits),
            "median": round(statistics.median(values), digits),
            "min": min(values),
            "max": max(values),
        }

    @classmethod
    def _case_summaries(
        cls, results: list[dict], baseline_variant: str | None
    ) -> dict[str, dict]:
        grouped: dict[str, list[dict]] = {}
        for result in results:
            grouped.setdefault(result["case"], []).append(result)
        return {
            case: {
                "trials": len(case_results),
                "variants": cls._variant_summaries(case_results),
                "comparisons": cls._variant_comparisons(
                    case_results, baseline_variant
                ),
            }
            for case, case_results in sorted(grouped.items())
        }

    @classmethod
    def _variant_comparisons(
        cls, results: list[dict], baseline_variant: str | None
    ) -> dict[str, dict]:
        if baseline_variant is None:
            return {}
        grouped: dict[str, list[dict]] = {}
        for result in results:
            grouped.setdefault(result["variant"], []).append(result)
        baseline = grouped.get(baseline_variant)
        if not baseline:
            return {}
        comparisons = {}
        for variant, candidate in sorted(grouped.items()):
            if variant == baseline_variant:
                continue
            comparisons[variant] = {
                "baseline_variant": baseline_variant,
                "paired_outcomes": cls._paired_outcomes(baseline, candidate),
                "success_rate_delta_points": round(
                    100
                    * (
                        cls._success_rate(candidate)
                        - cls._success_rate(baseline)
                    ),
                    2,
                ),
                "requests": cls._mean_comparison(
                    [result["usage"]["requests"] for result in baseline],
                    [result["usage"]["requests"] for result in candidate],
                ) | cls._paired_metric_summary(
                    baseline, candidate, lambda result: result["usage"]["requests"]
                ),
                "tokens": cls._mean_comparison(
                    [result["usage"]["total_tokens"] for result in baseline],
                    [result["usage"]["total_tokens"] for result in candidate],
                ) | cls._paired_metric_summary(
                    baseline,
                    candidate,
                    lambda result: result["usage"]["total_tokens"],
                ),
                "steps": cls._mean_comparison(
                    [result["steps"] for result in baseline],
                    [result["steps"] for result in candidate],
                ) | cls._paired_metric_summary(
                    baseline, candidate, lambda result: result["steps"]
                ),
                "estimated_cost_usd": cls._mean_comparison(
                    [result["estimated_cost_usd"] for result in baseline],
                    [result["estimated_cost_usd"] for result in candidate],
                    digits=8,
                ) | cls._paired_metric_summary(
                    baseline,
                    candidate,
                    lambda result: result["estimated_cost_usd"],
                    digits=8,
                ),
            }
        return comparisons

    @staticmethod
    def _success_rate(results: list[dict]) -> float:
        return sum(result["status"] == "success" for result in results) / len(results)

    @staticmethod
    def _mean_comparison(
        baseline: list[float], candidate: list[float], digits: int = 2
    ) -> dict:
        baseline_mean = statistics.mean(baseline)
        candidate_mean = statistics.mean(candidate)
        delta = candidate_mean - baseline_mean
        relative = 100 * delta / baseline_mean if baseline_mean else None
        return {
            "baseline_mean": round(baseline_mean, digits),
            "candidate_mean": round(candidate_mean, digits),
            "delta": round(delta, digits),
            "relative_change_percent": (
                round(relative, 2) if relative is not None else None
            ),
        }

    @classmethod
    def _paired_metric_summary(
        cls,
        baseline: list[dict],
        candidate: list[dict],
        value: Callable[[dict], float],
        digits: int = 2,
    ) -> dict:
        baseline_by_trial = {
            (result["case"], result["trial"]): value(result)
            for result in baseline
        }
        candidate_by_trial = {
            (result["case"], result["trial"]): value(result)
            for result in candidate
        }
        keys = sorted(set(baseline_by_trial) & set(candidate_by_trial))
        deltas = [
            candidate_by_trial[key] - baseline_by_trial[key]
            for key in keys
        ]
        if not deltas:
            return {
                "paired_delta": None,
                "candidate_better_pairs": 0,
                "tied_pairs": 0,
                "baseline_better_pairs": 0,
                "paired_sign_test_p_value": None,
            }
        return {
            "paired_delta": cls._metric_summary(deltas, digits=digits),
            "candidate_better_pairs": sum(delta < 0 for delta in deltas),
            "tied_pairs": sum(delta == 0 for delta in deltas),
            "baseline_better_pairs": sum(delta > 0 for delta in deltas),
            "paired_sign_test_p_value": cls._two_sided_sign_test(deltas),
        }

    @staticmethod
    def _two_sided_sign_test(deltas: list[float]) -> float | None:
        better = sum(delta < 0 for delta in deltas)
        worse = sum(delta > 0 for delta in deltas)
        trials = better + worse
        if trials == 0:
            return None
        smaller = min(better, worse)
        tail = sum(math.comb(trials, index) for index in range(smaller + 1))
        return round(min(1.0, 2 * tail / (2 ** trials)), 8)

    @staticmethod
    def _paired_outcomes(baseline: list[dict], candidate: list[dict]) -> dict:
        baseline_by_trial = {
            (result["case"], result["trial"]): result for result in baseline
        }
        candidate_by_trial = {
            (result["case"], result["trial"]): result for result in candidate
        }
        keys = sorted(set(baseline_by_trial) & set(candidate_by_trial))
        counts = {
            "pairs": len(keys),
            "both_success": 0,
            "candidate_only_success": 0,
            "baseline_only_success": 0,
            "both_failed": 0,
        }
        for key in keys:
            baseline_success = baseline_by_trial[key]["status"] == "success"
            candidate_success = candidate_by_trial[key]["status"] == "success"
            if baseline_success and candidate_success:
                counts["both_success"] += 1
            elif candidate_success:
                counts["candidate_only_success"] += 1
            elif baseline_success:
                counts["baseline_only_success"] += 1
            else:
                counts["both_failed"] += 1
        return counts

    def _notify(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
