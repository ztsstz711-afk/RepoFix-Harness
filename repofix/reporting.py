from __future__ import annotations

from collections import Counter


_USAGE_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cached_input_tokens",
    "requests",
    "retries",
    "format_retries",
    "transient_retries",
)


def validate_evaluation_report(report: dict) -> None:
    """Reject internally inconsistent aggregate reports before publication."""
    errors = []
    tasks = report.get("tasks")
    if report.get("report_schema_version") != 1:
        errors.append("unsupported report schema")
    if not isinstance(tasks, list):
        raise ValueError("invalid evaluation report: tasks must be a list")
    if report.get("task_count") != len(tasks):
        errors.append("task_count does not match tasks")
    if report.get("completed") and report.get("planned_trial_count") != len(tasks):
        errors.append("completed report does not contain every planned trial")

    ids = [task.get("id") for task in tasks if isinstance(task, dict)]
    if len(ids) != len(tasks) or len(ids) != len(set(ids)):
        errors.append("task IDs are missing or duplicated")

    successes = sum(task.get("status") == "success" for task in tasks)
    if report.get("successes") != successes:
        errors.append("success count does not match tasks")
    expected_success_rate = successes / len(tasks) if tasks else None
    if not _same_number(report.get("success_rate"), expected_success_rate):
        errors.append("success rate does not match tasks")

    if report.get("total_steps") != sum(task.get("steps", 0) for task in tasks):
        errors.append("total steps do not match tasks")
    usage = report.get("usage", {})
    for field in _USAGE_FIELDS:
        expected = sum(task.get("usage", {}).get(field, 0) for task in tasks)
        if usage.get(field) != expected:
            errors.append(f"usage.{field} does not match tasks")

    expected_cost = round(sum(task.get("estimated_cost_usd", 0) for task in tasks), 8)
    if not _same_number(report.get("estimated_cost_usd"), expected_cost):
        errors.append("estimated cost does not match tasks")

    scoped = [task for task in tasks if task.get("changed_files_match") is not None]
    scope_matches = sum(task.get("changed_files_match") is True for task in scoped)
    if report.get("change_scope_evaluated") != len(scoped):
        errors.append("scope evaluation count does not match tasks")
    if report.get("change_scope_matches") != scope_matches:
        errors.append("scope match count does not match tasks")
    expected_scope_rate = scope_matches / len(scoped) if scoped else None
    if not _same_number(report.get("change_scope_rate"), expected_scope_rate):
        errors.append("scope match rate does not match tasks")

    failure_counts = Counter(
        task.get("failure_kind") for task in tasks if task.get("failure_kind")
    )
    if report.get("failure_counts") != dict(failure_counts):
        errors.append("failure counts do not match tasks")

    if errors:
        raise ValueError("invalid evaluation report: " + "; ".join(errors))


def _same_number(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is right
    return isinstance(left, (int, float)) and abs(left - right) <= 1e-10


def render_evaluation_markdown(report: dict) -> str:
    """Render the stable, human-facing subset of an evaluation JSON report."""
    lines = [
        f"# Evaluation report: {_cell(report['suite'])}",
        "",
        f"- Completed: `{str(report['completed']).lower()}`",
        f"- Started: `{_cell(report['started_at'])}`",
        f"- Finished: `{_cell(report.get('completed_at') or 'in progress')}`",
    ]
    model = report.get("experiment", {}).get("provider_model")
    if model:
        lines.append(f"- Model: `{_cell(model)}`")

    usage = report["usage"]
    lines.extend([
        "",
        "## Overall",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Successful repairs | {report['successes']}/{report['task_count']} |",
        (
            "| Expected scope matches | "
            f"{report['change_scope_matches']}/{report['change_scope_evaluated']} |"
        ),
        f"| Model requests | {_number(usage['requests'])} |",
        f"| Retries | {_number(usage['retries'])} |",
        f"| Total tokens | {_number(usage['total_tokens'])} |",
        f"| Estimated cost (USD) | ${report['estimated_cost_usd']:.8f} |",
    ])

    variants = report.get("variants", {})
    if variants:
        lines.extend([
            "",
            "## Variants",
            "",
            "| Variant | Success | Scope | Requests mean | Tokens mean | Cost mean (USD) |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for name, summary in variants.items():
            lines.append(
                f"| {_cell(name)} | {summary['successes']}/{summary['trials']} | "
                f"{summary['change_scope_matches']}/{summary['change_scope_evaluated']} | "
                f"{_number(summary['requests']['mean'])} | "
                f"{_number(summary['tokens']['mean'])} | "
                f"${summary['estimated_cost_usd']['mean']:.8f} |"
            )

    comparisons = report.get("variant_comparisons", {})
    if comparisons:
        lines.extend([
            "",
            "## Baseline comparisons",
            "",
            "Negative deltas mean the candidate used fewer resources than the baseline.",
            "",
            "| Candidate | Baseline | Success delta | Request delta | Token delta | Request pairs better/tied/worse | Request sign p | Token pairs better/tied/worse | Token sign p |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for candidate, comparison in comparisons.items():
            requests = comparison["requests"]
            tokens = comparison["tokens"]
            lines.append(
                f"| {_cell(candidate)} | {_cell(comparison['baseline_variant'])} | "
                f"{comparison['success_rate_delta_points']:+.2f} points | "
                f"{requests['delta']:+} ({_signed_percent(requests['relative_change_percent'])}) | "
                f"{tokens['delta']:+} ({_signed_percent(tokens['relative_change_percent'])}) | "
                f"{_pair_counts(requests)} | {_p_value(requests)} | "
                f"{_pair_counts(tokens)} | {_p_value(tokens)} |"
            )

    cases = report.get("cases", {})
    if cases and comparisons:
        candidate = next(iter(comparisons))
        lines.extend([
            "",
            "## Per-case comparison",
            "",
            "| Case | Candidate | Request change | Token change | Paired success |",
            "|---|---|---:|---:|---:|",
        ])
        for case, summary in cases.items():
            comparison = summary.get("comparisons", {}).get(candidate)
            if not comparison:
                continue
            outcomes = comparison["paired_outcomes"]
            lines.append(
                f"| {_cell(case)} | {_cell(candidate)} | "
                f"{_signed_percent(comparison['requests']['relative_change_percent'])} | "
                f"{_signed_percent(comparison['tokens']['relative_change_percent'])} | "
                f"{outcomes['both_success']}/{outcomes['pairs']} both successful |"
            )

    lines.extend([
        "",
        "## Reproducibility",
        "",
        f"- Report schema: `{report['report_schema_version']}`",
        f"- Manifest SHA-256: `{_cell(report['manifest']['sha256'])}`",
        "- Source snapshots:",
    ])
    for task_id, source in report.get("sources", {}).items():
        lines.append(f"  - `{_cell(task_id)}`: `{_cell(source['sha256'])}`")

    failures = report.get("failure_counts", {})
    lines.extend([
        "",
        "## Failures",
        "",
        "None." if not failures else ", ".join(
            f"`{_cell(kind)}`: {count}" for kind, count in failures.items()
        ),
        "",
    ])
    return "\n".join(lines)


def _pair_counts(metric: dict) -> str:
    return (
        f"{metric.get('candidate_better_pairs', 0)}/"
        f"{metric.get('tied_pairs', 0)}/"
        f"{metric.get('baseline_better_pairs', 0)}"
    )


def _number(value: int | float) -> str:
    return f"{value:,}"


def _signed_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.2f}%"


def _p_value(metric: dict) -> str:
    value = metric.get("paired_sign_test_p_value")
    return "n/a" if value is None else f"{value:.6f}"


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("`", "\\`")
