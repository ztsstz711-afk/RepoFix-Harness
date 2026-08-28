import argparse
import hashlib
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from .config import Settings
from .provider import OpenAICompatibleProvider
from .suite import EvaluationRunner, load_suite


def harness_source_sha256() -> str:
    package = Path(__file__).resolve().parent
    project = package.parent
    files = sorted(package.rglob("*.py"))
    pyproject = project / "pyproject.toml"
    if pyproject.is_file():
        files.append(pyproject)
    digest = hashlib.sha256()
    for path in sorted(files):
        relative = path.relative_to(project).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(path.read_bytes())
    return digest.hexdigest()


def harness_version() -> str:
    try:
        return version("repofix-harness")
    except PackageNotFoundError:
        return "uninstalled"


def print_suite_progress(event: dict) -> None:
    if event["type"] == "task_start":
        print(f"[{event['index']}/{event['total']}] task={event['task_id']} starting")
    elif event["type"] == "task_end":
        print(f"task={event['task_id']} status={event['status']}")
    elif event["type"] == "task_skip":
        print(f"[{event['index']}/{event['total']}] task={event['task_id']} resumed")
    elif event["type"] == "task_crash":
        print(f"task={event['task_id']} runner_error={event['error']}")
    elif event["type"] == "agent_event":
        inner = event["event"]
        if inner["type"] == "preflight":
            print(f"task={event['task_id']} preflight={inner['success']}")
        elif inner["type"] == "baseline":
            print(
                f"task={event['task_id']} baseline={inner['success']} "
                f"backend={inner['execution_backend']}"
            )
        elif inner["type"] == "model_request":
            print(
                f"task={event['task_id']} step={inner['step']} requesting model... "
                f"context_chars={inner.get('context_chars', 0)} "
                f"seeded_sources={inner.get('seeded_sources', 0)}"
            )
        elif inner["type"] == "budget":
            print(f"task={event['task_id']} stopped by {inner['failure_kind']}: {inner['error']}")
        elif inner["type"] == "stalled":
            print(f"task={event['task_id']} stalled by {inner['failure_kind']}: {inner['error']}")
        elif inner["type"] == "rollback":
            print(f"task={event['task_id']} rolled back files={','.join(inner['files'])}")
        elif inner["type"] == "rollback_error":
            print(f"task={event['task_id']} rollback failed: {inner['error']}")
        elif inner["type"] == "step":
            action = inner.get("action", {}).get("name")
            observation = inner.get("observation")
            if action:
                suffix = f" success={observation['success']}" if observation else ""
                print(f"task={event['task_id']} step={inner['step']} action={action}{suffix}")
            elif inner.get("error"):
                print(f"task={event['task_id']} step={inner['step']} error={inner['error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a RepoFix evaluation suite sequentially")
    parser.add_argument("--suite", required=True)
    parser.add_argument("--output")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    if args.resume and not args.output:
        parser.error("--resume requires --output")

    suite = load_suite(args.suite)
    output = args.output or str(Path("eval-results") / f"{suite.name}-{datetime.now():%Y%m%d-%H%M%S}")
    settings = Settings.from_env()
    report = EvaluationRunner(
        OpenAICompatibleProvider,
        print_suite_progress,
        experiment_metadata={
            "harness_version": harness_version(),
            "harness_source_sha256": harness_source_sha256(),
            "provider_model": settings.model,
            "max_output_tokens": settings.max_output_tokens,
            "patch_max_output_tokens": settings.patch_max_output_tokens,
            "json_mode": settings.json_mode,
            "native_tool_calls": settings.native_tool_calls,
            "input_cost_per_million": settings.input_cost_per_million,
            "cached_input_cost_per_million": settings.cached_input_cost_per_million,
            "output_cost_per_million": settings.output_cost_per_million,
        },
    ).run(suite, output, resume=args.resume)
    print(
        f"suite={report['suite']} success={report['successes']}/{report['task_count']} "
        f"scope={report['change_scope_matches']}/{report['change_scope_evaluated']} "
        f"tokens={report['usage']['total_tokens']} report={Path(output).resolve() / 'report.json'}"
        f" cost_usd={report['estimated_cost_usd']:.6f} failures={report['failure_counts']}"
    )
    for variant, summary in report["variants"].items():
        print(
            f"variant={variant} success={summary['successes']}/{summary['trials']} "
            f"requests_mean={summary['requests']['mean']} "
            f"tokens_mean={summary['tokens']['mean']} "
            f"cost_mean_usd={summary['estimated_cost_usd']['mean']}"
        )
    return 0 if report["successes"] == report["task_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
