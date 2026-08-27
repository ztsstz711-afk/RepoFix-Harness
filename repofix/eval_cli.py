import argparse
from datetime import datetime
from pathlib import Path

from .provider import OpenAICompatibleProvider
from .suite import EvaluationRunner, load_suite


def print_suite_progress(event: dict) -> None:
    if event["type"] == "task_start":
        print(f"[{event['index']}/{event['total']}] task={event['task_id']} starting")
    elif event["type"] == "task_end":
        print(f"task={event['task_id']} status={event['status']}")
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
    args = parser.parse_args()

    suite = load_suite(args.suite)
    output = args.output or str(Path("eval-results") / f"{suite.name}-{datetime.now():%Y%m%d-%H%M%S}")
    report = EvaluationRunner(OpenAICompatibleProvider, print_suite_progress).run(suite, output)
    print(
        f"suite={report['suite']} success={report['successes']}/{report['task_count']} "
        f"scope={report['change_scope_matches']}/{report['change_scope_evaluated']} "
        f"tokens={report['usage']['total_tokens']} report={Path(output).resolve() / 'report.json'}"
        f" cost_usd={report['estimated_cost_usd']:.6f} failures={report['failure_counts']}"
    )
    return 0 if report["successes"] == report["task_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
