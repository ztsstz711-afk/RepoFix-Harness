import json
import re
import shutil
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from .loop import AgentLoop
from .schemas import TokenUsage, utc_now
from .tools import parse_pytest_invocation


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
    execution_backend: str = "local"
    docker_image: str = "repofix-pytest:latest"
    command_timeout_seconds: int = 30
    tags: tuple[str, ...] = ()
    expected_changed_files: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvaluationSuite:
    name: str
    tasks: list[SuiteTask]


def load_suite(path: str) -> EvaluationSuite:
    manifest = Path(path).resolve()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    name = data.get("name", manifest.stem)
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
        tags = _string_list(item, "tags")
        expected_changed_files = _string_list(item, "expected_changed_files")
        test_command = item.get("test_command", "pytest -q")
        parse_pytest_invocation(test_command)
        for expected_path in expected_changed_files:
            path = Path(expected_path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError(f"unsafe expected changed file: {expected_path}")
        tasks.append(SuiteTask(
            id=task_id,
            repo=str(repo),
            task=item["task"],
            max_steps=int(item.get("max_steps", 12)),
            max_requests=int(item["max_requests"]) if "max_requests" in item else None,
            max_tokens=int(item["max_tokens"]) if "max_tokens" in item else None,
            max_identical_actions=(
                int(item["max_identical_actions"]) if "max_identical_actions" in item else None
            ),
            max_changed_files=(
                int(item["max_changed_files"]) if "max_changed_files" in item else None
            ),
            rollback_on_failure=rollback_on_failure,
            test_command=test_command,
            execution_backend=item.get("execution_backend", "local"),
            docker_image=item.get("docker_image", "repofix-pytest:latest"),
            command_timeout_seconds=int(item.get("command_timeout_seconds", 30)),
            tags=tags,
            expected_changed_files=tuple(sorted(expected_changed_files)),
        ))
    if not tasks:
        raise ValueError("evaluation suite must contain at least one task")
    return EvaluationSuite(name, tasks)


def _string_list(item: dict, key: str) -> tuple[str, ...]:
    value = item.get(key, [])
    if not isinstance(value, list) or not all(isinstance(entry, str) for entry in value):
        raise ValueError(f"{key} must be a JSON string array")
    if len(value) != len(set(value)):
        raise ValueError(f"{key} must not contain duplicates")
    return tuple(value)


class EvaluationRunner:
    def __init__(self, provider_factory: Callable, on_event: Callable[[dict], None] | None = None):
        self.provider_factory = provider_factory
        self.on_event = on_event

    def run(self, suite: EvaluationSuite, output_dir: str) -> dict:
        destination = Path(output_dir).resolve()
        if destination.exists() and any(destination.iterdir()):
            raise FileExistsError(f"evaluation output directory is not empty: {destination}")
        destination.mkdir(parents=True, exist_ok=True)
        started_at = utc_now()
        total_usage = TokenUsage()
        results = []

        for index, task in enumerate(suite.tasks, 1):
            self._notify({"type": "task_start", "index": index, "total": len(suite.tasks), "task_id": task.id})
            result = self._run_task(task, destination)
            total_usage.add(TokenUsage(**result["usage"]))
            results.append(result)
            self._notify({"type": "task_end", "task_id": task.id, "status": result["status"]})

        successes = sum(result["status"] == "success" for result in results)
        scoped_results = [result for result in results if result["changed_files_match"] is not None]
        scope_matches = sum(result["changed_files_match"] is True for result in scoped_results)
        failure_counts = {}
        for result in results:
            if result["failure_kind"]:
                failure_counts[result["failure_kind"]] = failure_counts.get(result["failure_kind"], 0) + 1
        report = {
            "suite": suite.name,
            "started_at": started_at,
            "completed_at": utc_now(),
            "task_count": len(results),
            "successes": successes,
            "success_rate": successes / len(results),
            "total_steps": sum(result["steps"] for result in results),
            "usage": asdict(total_usage),
            "estimated_cost_usd": round(sum(result["estimated_cost_usd"] for result in results), 8),
            "failure_counts": failure_counts,
            "change_scope_evaluated": len(scoped_results),
            "change_scope_matches": scope_matches,
            "change_scope_rate": scope_matches / len(scoped_results) if scoped_results else None,
            "tasks": results,
        }
        self._atomic_write(destination / "report.json", json.dumps(report, indent=2))
        return report

    def _run_task(self, task: SuiteTask, destination: Path) -> dict:
        started = time.perf_counter()
        with tempfile.TemporaryDirectory(prefix=f"repofix-{task.id}-") as temporary:
            workspace = Path(temporary) / "repo"
            shutil.copytree(
                task.repo,
                workspace,
                ignore=shutil.ignore_patterns(".git", ".repofix", ".venv", "__pycache__", ".pytest_cache"),
            )
            def forward_agent_event(state, event):
                self._notify({"type": "agent_event", "task_id": task.id, "event": event})

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
                execution_backend=task.execution_backend,
                docker_image=task.docker_image,
                command_timeout_seconds=task.command_timeout_seconds,
            ).run(task.task)
            source_artifacts = workspace / ".repofix" / "runs" / state.run_id
            target_artifacts = destination / "runs" / task.id
            if source_artifacts.exists():
                shutil.copytree(source_artifacts, target_artifacts)

        changed_files_match = (
            state.evaluation.changed_files == list(task.expected_changed_files)
            if task.expected_changed_files
            else None
        )
        return {
            "id": task.id,
            "source_repo": task.repo,
            "run_id": state.run_id,
            "status": state.status,
            "model": state.model,
            "steps": state.step,
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "usage": asdict(state.usage),
            "preflight_success": state.preflight.success,
            "baseline_success": getattr(state.evaluation.baseline, "success", None),
            "final_success": getattr(state.evaluation.final, "success", None),
            "baseline_execution": (
                state.evaluation.baseline.metadata if state.evaluation.baseline else None
            ),
            "final_execution": (
                state.evaluation.final.metadata if state.evaluation.final else None
            ),
            "test_command": state.test_command,
            "execution_backend": state.execution_backend,
            "docker_image": state.docker_image,
            "command_timeout_seconds": state.command_timeout_seconds,
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

    def _notify(self, event: dict) -> None:
        if self.on_event:
            self.on_event(event)

    @staticmethod
    def _atomic_write(path: Path, content: str) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
