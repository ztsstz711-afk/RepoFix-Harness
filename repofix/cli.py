import argparse
from .config import Settings
from .loop import AgentLoop
from .provider import OpenAICompatibleProvider


def main():
    settings = Settings.from_env()
    p = argparse.ArgumentParser(description="Repair a Python repository with an LLM agent")
    p.add_argument("--repo", required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--max-steps", type=int, default=settings.max_steps)
    p.add_argument("--resume", action="store_true", help="continue from repo/.repofix/trace.json")
    a = p.parse_args()
    state = AgentLoop(OpenAICompatibleProvider(), a.repo, a.max_steps, settings.max_context_chars).run(a.task, resume=a.resume)
    print(
        f"status={state.status} steps={state.step} requests={state.usage.requests} "
        f"tokens={state.usage.total_tokens} trace={state.repo}/.repofix/trace.json"
    )
    return 0 if state.status == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
