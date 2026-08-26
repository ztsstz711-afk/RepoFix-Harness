import json
from dataclasses import asdict
from pathlib import Path
from .schemas import RunState
from .tools import ToolRuntime

class AgentLoop:
    def __init__(self, provider, repo: str, max_steps: int = 12):
        self.provider, self.runtime, self.max_steps = provider, ToolRuntime(repo), max_steps
        self.state = RunState("", str(Path(repo).resolve()))
    def run(self, task: str) -> RunState:
        self.state.task = task
        context = f"Repository: {self.state.repo}\nTask: {task}\nStart by inspecting the repository."
        for step in range(self.max_steps):
            self.state.step = step + 1
            decision = self.provider.next_action(context)
            action = decision.action
            self.state.model = decision.model or self.state.model
            self.state.usage.add(decision.usage)
            if action.name == "finish":
                self.state.status = "success"
                self.state.summary = action.arguments.get("summary", "")
                self.state.record({"step": self.state.step, "action": asdict(action), "usage": asdict(decision.usage)})
                self._save_checkpoint()
                break
            obs = self.runtime.execute(action.name, action.arguments)
            self.state.record({"step": self.state.step, "action": asdict(action), "observation": asdict(obs), "usage": asdict(decision.usage)})
            self._save_checkpoint()
            context += f"\nAction: {json.dumps(asdict(action))}\nObservation: {json.dumps(asdict(obs))}"
        else:
            self.state.status = "budget_exhausted"
            self._save_checkpoint()
        return self.state

    def _save_checkpoint(self) -> None:
        Path(self.state.repo, ".repofix").mkdir(exist_ok=True)
        Path(self.state.repo, ".repofix", "trace.json").write_text(json.dumps(self.state.to_dict(), indent=2), encoding="utf-8")
