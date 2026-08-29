import copy

import pytest

from repofix.reporting import (
    aggregate_phase_telemetry,
    render_evaluation_markdown,
    validate_evaluation_report,
)


def test_render_evaluation_markdown_surfaces_paired_results_and_fingerprints():
    report = {
        "report_schema_version": 1,
        "suite": "context|matrix",
        "completed": True,
        "started_at": "2026-08-27T10:00:00Z",
        "completed_at": "2026-08-27T10:01:00Z",
        "experiment": {"provider_model": "model-v1"},
        "successes": 2,
        "task_count": 2,
        "change_scope_matches": 2,
        "change_scope_evaluated": 2,
        "usage": {"requests": 8, "retries": 1, "total_tokens": 12_345},
        "estimated_cost_usd": 0.01234567,
        "variants": {
            "context_off": {
                "trials": 1,
                "successes": 1,
                "change_scope_matches": 1,
                "change_scope_evaluated": 1,
                "requests": {"mean": 5},
                "tokens": {"mean": 8000},
                "estimated_cost_usd": {"mean": 0.008},
            },
            "context_on": {
                "trials": 1,
                "successes": 1,
                "change_scope_matches": 1,
                "change_scope_evaluated": 1,
                "requests": {"mean": 3},
                "tokens": {"mean": 4345},
                "estimated_cost_usd": {"mean": 0.00434567},
            },
        },
        "variant_comparisons": {
            "context_on": {
                "baseline_variant": "context_off",
                "success_rate_delta_points": 0,
                "paired_outcomes": {"pairs": 1, "both_success": 1},
                "requests": {
                    "delta": -2,
                    "relative_change_percent": -40,
                    "candidate_better_pairs": 1,
                    "tied_pairs": 0,
                    "baseline_better_pairs": 0,
                    "paired_sign_test_p_value": 1,
                },
                "tokens": {
                    "delta": -3655,
                    "relative_change_percent": -45.69,
                    "candidate_better_pairs": 1,
                    "tied_pairs": 0,
                    "baseline_better_pairs": 0,
                    "paired_sign_test_p_value": 1,
                },
            }
        },
        "cases": {
            "addition": {
                "comparisons": {
                    "context_on": {
                        "paired_outcomes": {"pairs": 1, "both_success": 1},
                        "requests": {"relative_change_percent": -40},
                        "tokens": {"relative_change_percent": -45.69},
                    }
                }
            }
        },
        "manifest": {"sha256": "a" * 64},
        "sources": {"addition": {"sha256": "b" * 64}},
        "failure_counts": {},
    }

    rendered = render_evaluation_markdown(report)

    assert "# Evaluation report: context\\|matrix" in rendered
    assert "| Successful repairs | 2/2 |" in rendered
    assert "| Model requests | 8 |" in rendered
    assert "| Total tokens | 12,345 |" in rendered
    assert "context_on | context_off | +0.00 points | -2 (-40.00%)" in rendered
    assert "1/0/0" in rendered
    assert "1.000000" in rendered
    assert "addition | context_on | -40.00% | -45.69%" in rendered
    assert f"Manifest SHA-256: `{'a' * 64}`" in rendered
    assert "## Failures\n\nNone." in rendered


def test_render_evaluation_markdown_handles_zero_baseline_percentages():
    report = {
        "report_schema_version": 1,
        "suite": "errors",
        "completed": True,
        "started_at": "start",
        "completed_at": "end",
        "experiment": {},
        "successes": 0,
        "task_count": 2,
        "change_scope_matches": 0,
        "change_scope_evaluated": 0,
        "usage": {"requests": 0, "retries": 0, "total_tokens": 0},
        "estimated_cost_usd": 0,
        "variants": {},
        "variant_comparisons": {
            "candidate": {
                "baseline_variant": "baseline",
                "success_rate_delta_points": 0,
                "requests": {
                    "delta": 0,
                    "relative_change_percent": None,
                    "candidate_better_pairs": 0,
                    "tied_pairs": 1,
                    "baseline_better_pairs": 0,
                },
                "tokens": {
                    "delta": 0,
                    "relative_change_percent": None,
                    "candidate_better_pairs": 0,
                    "tied_pairs": 1,
                    "baseline_better_pairs": 0,
                },
            }
        },
        "cases": {},
        "manifest": {"sha256": "a" * 64},
        "sources": {},
        "failure_counts": {"runner_error": 2},
    }

    rendered = render_evaluation_markdown(report)

    assert "+0 (n/a)" in rendered
    assert "`runner_error`: 2" in rendered


def _valid_aggregate_report():
    usage = {
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "cached_input_tokens": 10,
        "requests": 1,
        "retries": 0,
        "format_retries": 0,
        "transient_retries": 0,
    }
    task = {
        "id": "trial-1",
        "status": "success",
        "steps": 2,
        "usage": usage,
        "estimated_cost_usd": 0.001,
        "changed_files_match": True,
        "failure_kind": "",
        "model": "model-v1",
        "preflight_checks": [],
    }
    return {
        "report_schema_version": 1,
        "completed": True,
        "planned_trial_count": 1,
        "task_count": 1,
        "successes": 1,
        "success_rate": 1.0,
        "total_steps": 2,
        "usage": dict(usage),
        "request_budget": {
            "max_total_requests": 2,
            "planned_request_ceiling": 2,
            "actual_requests": 1,
            "remaining_requests": 1,
        },
        "estimated_cost_usd": 0.001,
        "change_scope_evaluated": 1,
        "change_scope_matches": 1,
        "change_scope_rate": 1.0,
        "failure_counts": {},
        "experiment": {"provider_model": "model-v1"},
        "models": {"model-v1": 1},
        "docker_runtime_fingerprints": [],
        "tasks": [task],
    }


def test_validate_evaluation_report_accepts_consistent_aggregates():
    validate_evaluation_report(_valid_aggregate_report())


def test_phase_telemetry_aggregates_counts_transitions_and_grace_activations():
    tasks = [
        {
            "context_snapshots": [
                {"repair_phase": "locating", "target_read_grace": False},
                {"repair_phase": "inspecting", "target_read_grace": False},
                {"repair_phase": "inspecting", "target_read_grace": False},
                {"repair_phase": "target_read_due", "target_read_grace": True},
                {"repair_phase": "patch_due", "target_read_grace": False},
            ]
        },
        {
            "context_snapshots": [
                {"repair_phase": "locating", "target_read_grace": False},
                {"repair_phase": "target_read_due", "target_read_grace": True},
            ]
        },
    ]

    assert aggregate_phase_telemetry(tasks) == {
        "snapshot_count": 7,
        "phase_counts": {
            "inspecting": 2,
            "locating": 2,
            "patch_due": 1,
            "target_read_due": 2,
        },
        "transition_counts": {
            "inspecting -> target_read_due": 1,
            "locating -> inspecting": 1,
            "locating -> target_read_due": 1,
            "target_read_due -> patch_due": 1,
        },
        "target_read_grace_activations": 2,
    }


def test_validate_schema_v2_recomputes_phase_telemetry():
    report = _valid_aggregate_report()
    report["report_schema_version"] = 2
    report["tasks"][0]["context_snapshots"] = [
        {"repair_phase": "locating", "target_read_grace": False},
        {"repair_phase": "target_read_due", "target_read_grace": True},
    ]
    report["phase_telemetry"] = aggregate_phase_telemetry(report["tasks"])

    validate_evaluation_report(report)
    report["phase_telemetry"]["target_read_grace_activations"] = 0

    with pytest.raises(ValueError, match="phase telemetry"):
        validate_evaluation_report(report)


def test_render_evaluation_markdown_includes_phase_telemetry():
    report = {
        "report_schema_version": 2,
        "suite": "phase-policy",
        "completed": True,
        "started_at": "start",
        "completed_at": "end",
        "experiment": {},
        "successes": 1,
        "task_count": 1,
        "change_scope_matches": 1,
        "change_scope_evaluated": 1,
        "usage": {"requests": 2, "retries": 0, "total_tokens": 100},
        "estimated_cost_usd": 0,
        "variants": {},
        "variant_comparisons": {},
        "cases": {},
        "manifest": {"sha256": "a" * 64},
        "sources": {},
        "failure_counts": {},
        "phase_telemetry": {
            "snapshot_count": 2,
            "phase_counts": {"locating": 1, "target_read_due": 1},
            "transition_counts": {"locating -> target_read_due": 1},
            "target_read_grace_activations": 1,
        },
    }

    rendered = render_evaluation_markdown(report)

    assert "## Agent phase telemetry" in rendered
    assert "Target-read grace activations: 1" in rendered
    assert "| target_read_due | 1 |" in rendered
    assert "| locating -> target_read_due | 1 |" in rendered


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda report: report.update(task_count=2), "task_count"),
        (lambda report: report["usage"].update(total_tokens=121), "total_tokens"),
        (lambda report: report.update(estimated_cost_usd=9), "estimated cost"),
        (lambda report: report.update(successes=0), "success count"),
        (lambda report: report.update(models={"other": 1}), "model counts"),
        (
            lambda report: report.update(docker_runtime_fingerprints=["changed"]),
            "Docker runtime fingerprints",
        ),
        (
            lambda report: (
                report["tasks"][0].update(model="other"),
                report.update(models={"other": 1}),
            ),
            "declared provider model",
        ),
        (
            lambda report: report["request_budget"].update(remaining_requests=2),
            "remaining request budget",
        ),
        (
            lambda report: report["tasks"].append(copy.deepcopy(report["tasks"][0])),
            "task IDs",
        ),
    ],
)
def test_validate_evaluation_report_rejects_inconsistent_aggregates(mutation, message):
    report = _valid_aggregate_report()
    mutation(report)

    with pytest.raises(ValueError, match=message):
        validate_evaluation_report(report)
