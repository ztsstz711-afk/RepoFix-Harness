import copy

import pytest

from repofix.comparison import compare_evaluation_reports
from repofix.comparison_cli import render_model_comparison_markdown


def _report(model, statuses, requests, tokens, costs):
    tasks = []
    for index, status in enumerate(statuses, 1):
        usage = {
            "input_tokens": tokens[index - 1] - 100,
            "output_tokens": 100,
            "total_tokens": tokens[index - 1],
            "cached_input_tokens": 0,
            "requests": requests[index - 1],
            "retries": 0,
            "format_retries": 0,
            "transient_retries": 0,
        }
        tasks.append(
            {
                "id": f"case--trial-{index:02d}",
                "task_id": "case",
                "variant": "frozen",
                "case": "case",
                "trial": index,
                "repetitions": len(statuses),
                "source_repo_sha256": "b" * 64,
                "status": status,
                "model": model,
                "steps": requests[index - 1],
                "usage": usage,
                "estimated_cost_usd": costs[index - 1],
                "changed_files_match": True,
                "failure_kind": "" if status == "success" else "request_budget",
                "preflight_checks": [
                    {"name": "docker_runtime", "status": "pass", "message": "docker-id"}
                ],
                "test_command": "pytest -q focused",
                "final_test_command": "pytest -q",
                "execution_backend": "docker",
                "docker_image": "repofix:test",
                "command_timeout_seconds": 30,
                "seed_failure_context": True,
                "verify_after_patch": True,
                "tags": ["external"],
                "expected_changed_files": ["package.py"],
            }
        )
    usage = {
        field: sum(task["usage"][field] for task in tasks)
        for field in tasks[0]["usage"]
    }
    successes = sum(status == "success" for status in statuses)
    failure_counts = {}
    if successes != len(tasks):
        failure_counts["request_budget"] = len(tasks) - successes
    return {
        "report_schema_version": 1,
        "suite": "frozen-suite",
        "manifest": {"sha256": "a" * 64},
        "sources": {"case": {"sha256": "b" * 64}},
        "experiment": {
            "harness_version": "3.7.0",
            "harness_source_sha256": "c" * 64,
            "python_executable": "python",
            "harness_module_path": "repofix/eval_cli.py",
            "provider_model": model,
            "request_timeout_seconds": 120,
            "max_output_tokens": 2048,
            "patch_max_output_tokens": 4096,
            "thinking_mode": "disabled",
            "json_mode": True,
            "native_tool_calls": True,
            "input_cost_per_million": 1,
            "cached_input_cost_per_million": 1,
            "output_cost_per_million": 1,
        },
        "models": {model: len(tasks)},
        "docker_runtime_fingerprints": ["docker-id"],
        "request_budget": {
            "max_total_requests": 30,
            "planned_request_ceiling": 30,
            "actual_requests": usage["requests"],
            "remaining_requests": 30 - usage["requests"],
        },
        "completed": True,
        "planned_trial_count": len(tasks),
        "task_definition_count": 1,
        "task_count": len(tasks),
        "successes": successes,
        "success_rate": successes / len(tasks),
        "total_steps": sum(task["steps"] for task in tasks),
        "usage": usage,
        "estimated_cost_usd": round(sum(costs), 8),
        "failure_counts": failure_counts,
        "change_scope_evaluated": len(tasks),
        "change_scope_matches": len(tasks),
        "change_scope_rate": 1.0,
        "tasks": tasks,
    }


def test_compare_reports_calculates_totals_and_paired_outcomes():
    baseline = _report("flash", ["success", "budget_exhausted"], [6, 8], [1000, 2000], [0.01, 0.02])
    candidate = _report("pro", ["success", "success"], [4, 9], [600, 1800], [0.03, 0.04])

    comparison = compare_evaluation_reports(baseline, candidate)

    assert comparison["delta"]["successes"] == 1
    assert comparison["delta"]["requests"]["delta"] == -1
    assert comparison["delta"]["tokens"]["relative_change_percent"] == -20.0
    assert comparison["delta"]["estimated_cost_usd"]["delta"] == 0.04
    assert comparison["paired_outcomes"]["candidate_only_success"] == 1
    assert comparison["paired_requests"]["candidate_better_pairs"] == 1
    assert comparison["paired_requests"]["baseline_better_pairs"] == 1


def test_compare_reports_rejects_changed_experiment_identity():
    baseline = _report("flash", ["success"], [4], [1000], [0.01])
    candidate = _report("pro", ["success"], [3], [800], [0.02])
    candidate["experiment"]["thinking_mode"] = "enabled"

    with pytest.raises(ValueError, match="Harness experiment"):
        compare_evaluation_reports(baseline, candidate)


def test_compare_reports_rejects_changed_request_timeout():
    baseline = _report("flash", ["success"], [4], [1000], [0.01])
    candidate = _report("pro", ["success"], [3], [800], [0.02])
    candidate["experiment"]["request_timeout_seconds"] = 45

    with pytest.raises(ValueError, match="Harness experiment"):
        compare_evaluation_reports(baseline, candidate)


def test_compare_reports_rejects_tampered_aggregate_before_comparison():
    baseline = _report("flash", ["success"], [4], [1000], [0.01])
    candidate = copy.deepcopy(baseline)
    candidate["successes"] = 0

    with pytest.raises(ValueError, match="success count"):
        compare_evaluation_reports(baseline, candidate)


def test_model_comparison_markdown_surfaces_resource_tradeoff():
    comparison = compare_evaluation_reports(
        _report("flash", ["success"], [5], [1000], [0.01]),
        _report("pro", ["success"], [3], [600], [0.02]),
    )

    rendered = render_model_comparison_markdown(comparison)

    assert "# Evaluation comparison: frozen-suite" in rendered
    assert "| Requests | 5 | 3 | -2 (-40.00%) |" in rendered
    assert "| Tokens | 1,000 | 600 | -400 (-40.00%) |" in rendered
    assert "Both successful: 1/1" in rendered
    assert f"Manifest SHA-256: `{'a' * 64}`" in rendered


def test_compare_reports_can_isolate_thinking_mode():
    baseline = _report("pro", ["success"], [5], [1000], [0.02])
    candidate = _report("pro", ["success"], [4], [900], [0.02])
    baseline["experiment"]["thinking_mode"] = "disabled"
    candidate["experiment"]["thinking_mode"] = "enabled"

    comparison = compare_evaluation_reports(
        baseline, candidate, dimension="thinking_mode"
    )

    assert comparison["comparison_dimension"] == "thinking_mode"
    assert comparison["baseline"]["model"] == comparison["candidate"]["model"]


def test_thinking_comparison_rejects_model_change():
    baseline = _report("flash", ["success"], [5], [1000], [0.01])
    candidate = _report("pro", ["success"], [4], [900], [0.02])
    baseline["experiment"]["thinking_mode"] = "disabled"
    candidate["experiment"]["thinking_mode"] = "enabled"

    with pytest.raises(ValueError, match="Harness experiment"):
        compare_evaluation_reports(baseline, candidate, dimension="thinking_mode")
