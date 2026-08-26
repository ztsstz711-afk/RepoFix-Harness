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
    a = p.parse_args(); state = AgentLoop(OpenAICompatibleProvider(), a.repo, a.max_steps).run(a.task)
    print(f"status={state.status} steps={state.step} trace={state.repo}/.repofix/trace.json")


if __name__ == "__main__":
    main()
