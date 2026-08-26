import argparse
from .loop import AgentLoop
from .provider import OpenAICompatibleProvider

def main():
    p = argparse.ArgumentParser(); p.add_argument("--repo", required=True); p.add_argument("--task", required=True); p.add_argument("--max-steps", type=int, default=12)
    a = p.parse_args(); state = AgentLoop(OpenAICompatibleProvider(), a.repo, a.max_steps).run(a.task)
    print(f"status={state.status} steps={state.step} trace={state.repo}/.repofix/trace.json")
