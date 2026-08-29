from __future__ import annotations

import math
from pathlib import Path

from .reporting import validate_evaluation_report


_EXPERIMENT_IDENTITY_FIELDS = (
    "harness_version",
    "harness_source_sha256",
    "python_executable",
    "harness_module_path",
    "max_output_tokens",
    "patch_max_output_tokens",
    "thinking_mode",
    "json_mode",
    "native_tool_calls",
)

_TASK_IDENTITY_FIELDS = (
    "id",
    "task_id",
    "variant",
    "case",
    "trial",
    "repetitions",
    "source_repo_sha256",
    "test_command",
    "final_test_command",
    "execution_backend",
    "docker_image",
    "command_timeout_seconds",
    "seed_failure_context",
    "verify_after_patch",
    "tags",
    "expected_changed_files",
)


def compare_evaluation_reports(baseline: dict, candidate: dict) -> dict:
    validate_evaluation_report(baseline)
    validate_evaluation_report(candidate)
    if not baseline.get("completed") or not candidate.get("completed"):
        raise ValueError("model comparison requires two completed reports")
    _validate_comparable_identity(baseline, candidate)

    baseline_tasks = {task["id"]: task for task in baseline["tasks"]}
    candidate_tasks = {task["id"]: task for task in candidate["tasks"]}
    task_ids = sorted(baseline_tasks)
    request_deltas = [
        candidate_tasks[task_id]["usage"]["requests"]
        - baseline_tasks[task_id]["usage"]["requests"]
        for task_id in task_ids
    ]
    token_deltas = [
        candidate_tasks[task_id]["usage"]["total_tokens"]
        - baseline_tasks[task_id]["usage"]["total_tokens"]
        for task_id in task_ids
    ]

    return {
        "comparison_schema_version": 1,
        "suite": baseline["suite"],
        "manifest_sha256": baseline["manifest"]["sha256"],
        "harness_version": baseline["experiment"]["harness_version"],
        "harness_source_sha256": baseline["experiment"]["harness_source_sha256"],
        "docker_runtime_fingerprints": baseline["docker_runtime_fingerprints"],
        "baseline": _report_summary(baseline),
        "candidate": _report_summary(candidate),
        "delta": {
            "successes": candidate["successes"] - baseline["successes"],
            "success_rate_points": round(
                100 * (candidate["success_rate"] - baseline["success_rate"]), 2
            ),
            "scope_matches": (
                candidate["change_scope_matches"] - baseline["change_scope_matches"]
            ),
            "requests": _total_delta(
                baseline["usage"]["requests"], candidate["usage"]["requests"]
            ),
            "tokens": _total_delta(
                baseline["usage"]["total_tokens"],
                candidate["usage"]["total_tokens"],
            ),
            "estimated_cost_usd": _total_delta(
                baseline["estimated_cost_usd"],
                candidate["estimated_cost_usd"],
                digits=8,
            ),
        },
        "paired_outcomes": _paired_outcomes(baseline_tasks, candidate_tasks),
        "paired_requests": _paired_resource_summary(request_deltas),
        "paired_tokens": _paired_resource_summary(token_deltas),
        "trials": [
            {
                "id": task_id,
                "baseline_status": baseline_tasks[task_id]["status"],
                "candidate_status": candidate_tasks[task_id]["status"],
                "request_delta": (
                    candidate_tasks[task_id]["usage"]["requests"]
                    - baseline_tasks[task_id]["usage"]["requests"]
                ),
                "token_delta": (
                    candidate_tasks[task_id]["usage"]["total_tokens"]
                    - baseline_tasks[task_id]["usage"]["total_tokens"]
                ),
            }
            for task_id in task_ids
        ],
    }


def _validate_comparable_identity(baseline: dict, candidate: dict) -> None:
    checks = {
        "suite": (baseline.get("suite"), candidate.get("suite")),
        "manifest SHA-256": (
            baseline.get("manifest", {}).get("sha256"),
            candidate.get("manifest", {}).get("sha256"),
        ),
        "source snapshots": (
            _source_identity(baseline),
            _source_identity(candidate),
        ),
        "planned trials": (
            baseline.get("planned_trial_count"),
            candidate.get("planned_trial_count"),
        ),
        "request authorization": (
            _request_identity(baseline),
            _request_identity(candidate),
        ),
        "Docker runtime": (
            baseline.get("docker_runtime_fingerprints"),
            candidate.get("docker_runtime_fingerprints"),
        ),
        "Harness experiment": (
            _experiment_identity(baseline),
            _experiment_identity(candidate),
        ),
        "task definitions": (
            _task_identity(baseline),
            _task_identity(candidate),
        ),
    }
    mismatches = [name for name, (left, right) in checks.items() if left != right]
    if mismatches:
        raise ValueError(
            "evaluation reports are not comparable: " + ", ".join(mismatches)
        )


def _source_identity(report: dict) -> dict:
    return {
        name: source.get("sha256")
        for name, source in sorted(report.get("sources", {}).items())
    }


def _request_identity(report: dict) -> tuple:
    budget = report.get("request_budget", {})
    return budget.get("max_total_requests"), budget.get("planned_request_ceiling")


def _experiment_identity(report: dict) -> tuple:
    experiment = report.get("experiment", {})
    return tuple(experiment.get(field) for field in _EXPERIMENT_IDENTITY_FIELDS)


def _task_identity(report: dict) -> dict:
    return {
        task["id"]: tuple(_freeze(task.get(field)) for field in _TASK_IDENTITY_FIELDS)
        for task in report["tasks"]
    }


def _freeze(value: object) -> object:
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple((key, _freeze(item)) for key, item in sorted(value.items()))
    return value


def _report_summary(report: dict) -> dict:
    return {
        "model": report["experiment"]["provider_model"],
        "trials": report["task_count"],
        "successes": report["successes"],
        "success_rate": report["success_rate"],
        "scope_matches": report["change_scope_matches"],
        "scope_evaluated": report["change_scope_evaluated"],
        "requests": report["usage"]["requests"],
        "tokens": report["usage"]["total_tokens"],
        "retries": report["usage"]["retries"],
        "estimated_cost_usd": report["estimated_cost_usd"],
        "failure_counts": report["failure_counts"],
    }


def _total_delta(baseline: float, candidate: float, digits: int = 2) -> dict:
    delta = candidate - baseline
    relative = 100 * delta / baseline if baseline else None
    return {
        "baseline": baseline,
        "candidate": candidate,
        "delta": round(delta, digits),
        "relative_change_percent": round(relative, 2) if relative is not None else None,
    }


def _paired_outcomes(baseline: dict, candidate: dict) -> dict:
    counts = {
        "pairs": len(baseline),
        "both_success": 0,
        "candidate_only_success": 0,
        "baseline_only_success": 0,
        "both_failed": 0,
    }
    for task_id, baseline_task in baseline.items():
        baseline_success = baseline_task["status"] == "success"
        candidate_success = candidate[task_id]["status"] == "success"
        if baseline_success and candidate_success:
            counts["both_success"] += 1
        elif candidate_success:
            counts["candidate_only_success"] += 1
        elif baseline_success:
            counts["baseline_only_success"] += 1
        else:
            counts["both_failed"] += 1
    return counts


def _paired_resource_summary(deltas: list[int]) -> dict:
    return {
        "candidate_better_pairs": sum(delta < 0 for delta in deltas),
        "tied_pairs": sum(delta == 0 for delta in deltas),
        "baseline_better_pairs": sum(delta > 0 for delta in deltas),
        "paired_sign_test_p_value": _two_sided_sign_test(deltas),
    }


def _two_sided_sign_test(deltas: list[int]) -> float | None:
    better = sum(delta < 0 for delta in deltas)
    worse = sum(delta > 0 for delta in deltas)
    trials = better + worse
    if trials == 0:
        return None
    smaller = min(better, worse)
    tail = sum(math.comb(trials, index) for index in range(smaller + 1))
    return round(min(1.0, 2 * tail / (2**trials)), 8)


def load_evaluation_report(path: str | Path) -> dict:
    import json

    return json.loads(Path(path).read_text(encoding="utf-8"))
