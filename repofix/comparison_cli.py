import argparse
import json
from pathlib import Path

from .comparison import compare_evaluation_reports, load_evaluation_report


def render_model_comparison_markdown(comparison: dict) -> str:
    baseline = comparison["baseline"]
    candidate = comparison["candidate"]
    delta = comparison["delta"]
    outcomes = comparison["paired_outcomes"]
    return "\n".join(
        [
            f"# Evaluation comparison: {comparison['suite']}",
            "",
            "| Metric | Baseline | Candidate | Delta |",
            "|---|---:|---:|---:|",
            f"| Model | `{baseline['model']}` | `{candidate['model']}` | — |",
            f"| Thinking mode | `{baseline['thinking_mode']}` | `{candidate['thinking_mode']}` | — |",
            f"| Verified repairs | {baseline['successes']}/{baseline['trials']} | {candidate['successes']}/{candidate['trials']} | {delta['successes']:+} |",
            f"| Scope matches | {baseline['scope_matches']}/{baseline['scope_evaluated']} | {candidate['scope_matches']}/{candidate['scope_evaluated']} | {delta['scope_matches']:+} |",
            f"| Requests | {baseline['requests']:,} | {candidate['requests']:,} | {_delta_cell(delta['requests'])} |",
            f"| Tokens | {baseline['tokens']:,} | {candidate['tokens']:,} | {_delta_cell(delta['tokens'])} |",
            f"| Estimated cost | ${baseline['estimated_cost_usd']:.8f} | ${candidate['estimated_cost_usd']:.8f} | {_delta_cell(delta['estimated_cost_usd'], currency=True)} |",
            "",
            "## Paired outcomes",
            "",
            f"- Both successful: {outcomes['both_success']}/{outcomes['pairs']}",
            f"- Candidate only successful: {outcomes['candidate_only_success']}",
            f"- Baseline only successful: {outcomes['baseline_only_success']}",
            f"- Both failed: {outcomes['both_failed']}",
            f"- Request pairs candidate better/tied/baseline better: {_pair_counts(comparison['paired_requests'])}",
            f"- Token pairs candidate better/tied/baseline better: {_pair_counts(comparison['paired_tokens'])}",
            "",
            "## Reproducibility",
            "",
            f"- Manifest SHA-256: `{comparison['manifest_sha256']}`",
            f"- Harness: `{comparison['harness_version']}` / `{comparison['harness_source_sha256']}`",
            *[
                f"- Docker: `{fingerprint}`"
                for fingerprint in comparison["docker_runtime_fingerprints"]
            ],
            "",
        ]
    )


def _delta_cell(metric: dict, currency: bool = False) -> str:
    delta = metric["delta"]
    rendered = f"${delta:+.8f}" if currency else f"{delta:+,}"
    relative = metric["relative_change_percent"]
    return f"{rendered} ({relative:+.2f}%)" if relative is not None else f"{rendered} (n/a)"


def _pair_counts(summary: dict) -> str:
    return "/".join(
        str(summary[field])
        for field in (
            "candidate_better_pairs",
            "tied_pairs",
            "baseline_better_pairs",
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare two identity-compatible RepoFix evaluation reports"
    )
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument(
        "--dimension", choices=("model", "thinking_mode"), default="model"
    )
    parser.add_argument("--output")
    args = parser.parse_args()

    comparison = compare_evaluation_reports(
        load_evaluation_report(args.baseline),
        load_evaluation_report(args.candidate),
        dimension=args.dimension,
    )
    markdown = render_model_comparison_markdown(comparison)
    if args.output:
        output = Path(args.output).resolve()
        output.mkdir(parents=True, exist_ok=True)
        (output / "comparison.json").write_text(
            json.dumps(comparison, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (output / "comparison.md").write_text(markdown, encoding="utf-8")
        print(f"comparison={output / 'comparison.json'}")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
