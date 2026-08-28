import argparse
import json
from .config import Settings
from .loop import AgentLoop
from .presentation import format_progress, format_run_summary
from .provider import OpenAICompatibleProvider


def print_progress(state, event):
    for line in format_progress(state, event):
        print(line)


def build_parser(settings: Settings) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Repair a Python repository with an LLM agent")
    p.add_argument("--repo", required=True)
    p.add_argument("--task", required=True)
    p.add_argument(
        "--test-command",
        default=settings.test_command,
        help='Harness-owned verification command; pytest only (default: "pytest -q")',
    )
    p.add_argument(
        "--final-test-command",
        default=settings.final_test_command,
        help="optional full pytest command used only for final acceptance",
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
    p.add_argument(
        "--verify-after-patch",
        action=argparse.BooleanOptionalAction,
        default=settings.verify_after_patch,
        help="run the focused Harness pytest command after each changed patch",
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
    p.add_argument("--json", action="store_true", help="print only the final RunState JSON")
    return p


def main():
    settings = Settings.from_env()
    p = build_parser(settings)
    a = p.parse_args()
    state = AgentLoop(
        OpenAICompatibleProvider(),
        a.repo,
        a.max_steps,
        settings.max_context_chars,
        on_event=None if (a.quiet or a.json) else print_progress,
        max_requests=a.max_requests,
        max_tokens=a.max_tokens,
        max_identical_actions=a.max_identical_actions,
        max_changed_files=a.max_changed_files,
        rollback_on_failure=a.rollback_on_failure,
        test_command=a.test_command,
        final_test_command=a.final_test_command,
        execution_backend=a.execution_backend,
        docker_image=a.docker_image,
        command_timeout_seconds=a.command_timeout,
        seed_failure_context=a.failure_context,
        verify_after_patch=a.verify_after_patch,
    ).run(a.task, resume=a.resume)
    if a.json:
        print(json.dumps(state.to_dict(), ensure_ascii=False))
    else:
        print(format_run_summary(state))
    return 0 if state.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
