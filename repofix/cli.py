import argparse
from .config import Settings
from .loop import AgentLoop
from .provider import OpenAICompatibleProvider


def print_progress(state, event):
    if event["type"] == "baseline":
        print(f"baseline pytest success={event['success']}")
    elif event["type"] == "model_request":
        print(f"step={event['step']} requesting model action...")
    elif event["type"] == "budget":
        print(f"stopped by {event['failure_kind']}: {event['error']}")
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
    p.add_argument("--max-steps", type=int, default=settings.max_steps)
    p.add_argument("--max-requests", type=int, default=settings.max_requests, help="0 means unlimited")
    p.add_argument("--max-tokens", type=int, default=settings.max_tokens, help="0 means unlimited")
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
    ).run(a.task, resume=a.resume)
    print(
        f"status={state.status} steps={state.step} requests={state.usage.requests} "
        f"tokens={state.usage.total_tokens} "
        f"retries={state.usage.retries} cost_usd={state.estimated_cost_usd:.6f} "
        f"failure={state.failure_kind or 'none'} "
        f"baseline={getattr(state.evaluation.baseline, 'success', None)} "
        f"final={getattr(state.evaluation.final, 'success', None)} "
        f"result={state.repo}/.repofix/result.json"
    )
    return 0 if state.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
