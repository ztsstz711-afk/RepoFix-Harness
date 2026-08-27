import argparse
from .config import Settings
from .loop import AgentLoop
from .provider import OpenAICompatibleProvider


def print_progress(state, event):
    if event["type"] == "preflight":
        warnings = sum(check.status == "warning" for check in state.preflight.checks)
        print(f"preflight success={event['success']} warnings={warnings}")
        for check in state.preflight.checks:
            if check.status == "fail":
                print(f"preflight failed {check.name}: {check.message}")
    elif event["type"] == "baseline":
        print(
            f"baseline pytest success={event['success']} "
            f"backend={event['execution_backend']}"
        )
    elif event["type"] == "model_request":
        print(
            f"step={event['step']} requesting model action... "
            f"context_chars={event.get('context_chars', 0)} "
            f"seeded_sources={event.get('seeded_sources', 0)}"
        )
    elif event["type"] == "budget":
        print(f"stopped by {event['failure_kind']}: {event['error']}")
    elif event["type"] == "stalled":
        print(f"stalled by {event['failure_kind']}: {event['error']}")
    elif event["type"] == "rollback":
        print(f"rolled back files={','.join(event['files'])}")
    elif event["type"] == "rollback_error":
        print(f"rollback failed: {event['error']}")
    elif event["type"] == "step":
        action = event.get("action", {}).get("name")
        observation = event.get("observation")
        if action:
            suffix = f" success={observation['success']}" if observation else ""
            print(f"step={event['step']} action={action}{suffix}")
        elif event.get("error"):
            print(f"step={event['step']} error={event['error']}")


def main():
    settings = Settings.from_env()
    p = argparse.ArgumentParser(description="Repair a Python repository with an LLM agent")
    p.add_argument("--repo", required=True)
    p.add_argument("--task", required=True)
    p.add_argument(
        "--test-command",
        default=settings.test_command,
        help='Harness-owned verification command; pytest only (default: "pytest -q")',
    )
    p.add_argument("--execution-backend", choices=("local", "docker"), default=settings.execution_backend)
    p.add_argument("--docker-image", default=settings.docker_image)
    p.add_argument("--command-timeout", type=int, default=settings.command_timeout_seconds)
    p.add_argument(
        "--failure-context",
        action=argparse.BooleanOptionalAction,
        default=settings.seed_failure_context,
        help="seed the first model request from pytest traceback context",
    )
    p.add_argument("--max-steps", type=int, default=settings.max_steps)
    p.add_argument("--max-requests", type=int, default=settings.max_requests, help="0 means unlimited")
    p.add_argument("--max-tokens", type=int, default=settings.max_tokens, help="0 means unlimited")
    p.add_argument(
        "--max-identical-actions",
        type=int,
        default=settings.max_identical_actions,
        help="allowed repeats before the loop is stopped",
    )
    p.add_argument("--max-changed-files", type=int, default=settings.max_changed_files, help="0 means unlimited")
    p.add_argument(
        "--rollback-on-failure",
        action="store_true",
        default=settings.rollback_on_failure,
        help="restore Agent-written files when the run does not succeed",
    )
    p.add_argument("--resume", action="store_true", help="continue from repo/.repofix/trace.json")
    p.add_argument("--quiet", action="store_true", help="only print the final result")
    a = p.parse_args()
    state = AgentLoop(
        OpenAICompatibleProvider(),
        a.repo,
        a.max_steps,
        settings.max_context_chars,
        on_event=None if a.quiet else print_progress,
        max_requests=a.max_requests,
        max_tokens=a.max_tokens,
        max_identical_actions=a.max_identical_actions,
        max_changed_files=a.max_changed_files,
        rollback_on_failure=a.rollback_on_failure,
        test_command=a.test_command,
        execution_backend=a.execution_backend,
        docker_image=a.docker_image,
        command_timeout_seconds=a.command_timeout,
        seed_failure_context=a.failure_context,
    ).run(a.task, resume=a.resume)
    print(
        f"status={state.status} steps={state.step} requests={state.usage.requests} "
        f"tokens={state.usage.total_tokens} "
        f"retries={state.usage.retries} cost_usd={state.estimated_cost_usd:.6f} "
        f"failure={state.failure_kind or 'none'} "
        f"preflight={state.preflight.success} "
        f"rollback={state.evaluation.rollback_performed} "
        f"rollback_error={state.evaluation.rollback_error or 'none'} "
        f"baseline={getattr(state.evaluation.baseline, 'success', None)} "
        f"final={getattr(state.evaluation.final, 'success', None)} "
        f"test_command={state.test_command!r} "
        f"backend={state.execution_backend} "
        f"result={state.repo}/.repofix/result.json"
    )
    return 0 if state.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
