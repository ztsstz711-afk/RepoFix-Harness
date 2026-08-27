from __future__ import annotations


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
            "| Candidate | Baseline | Success delta | Request delta | Token delta | Request pairs better/tied/worse | Token pairs better/tied/worse |",
            "|---|---|---:|---:|---:|---:|---:|",
        ])
        for candidate, comparison in comparisons.items():
            requests = comparison["requests"]
            tokens = comparison["tokens"]
            lines.append(
                f"| {_cell(candidate)} | {_cell(comparison['baseline_variant'])} | "
                f"{comparison['success_rate_delta_points']:+.2f} points | "
                f"{requests['delta']:+} ({_signed_percent(requests['relative_change_percent'])}) | "
                f"{tokens['delta']:+} ({_signed_percent(tokens['relative_change_percent'])}) | "
                f"{_pair_counts(requests)} | {_pair_counts(tokens)} |"
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


def _cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("`", "\\`")
