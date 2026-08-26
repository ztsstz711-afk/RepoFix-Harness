import json
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
            action = self.provider.next_action(context)
            if action.name == "finish":
                self.state.status = "success"
                self.state.record({"step": self.state.step, "action": action.__dict__})
                self._save_checkpoint()
                break
            obs = self.runtime.execute(action.name, action.arguments)
            self.state.record({"step": self.state.step, "action": action.__dict__, "observation": obs.__dict__})
            self._save_checkpoint()
            context += f"\nAction: {json.dumps(action.__dict__)}\nObservation: {json.dumps(obs.__dict__)}"
        else:
            self.state.status = "budget_exhausted"
            self._save_checkpoint()
        return self.state

    def _save_checkpoint(self) -> None:
        Path(self.state.repo, ".repofix").mkdir(exist_ok=True)
        Path(self.state.repo, ".repofix", "trace.json").write_text(json.dumps(self.state.__dict__, indent=2), encoding="utf-8")
