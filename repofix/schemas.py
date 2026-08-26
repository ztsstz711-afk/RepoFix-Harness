from dataclasses import dataclass, field
from typing import Any

@dataclass
class Action:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

@dataclass
class Observation:
    tool: str
    output: str
    success: bool = True

@dataclass
class RunState:
    task: str
    repo: str
    step: int = 0
    status: str = "running"
    history: list[dict[str, Any]] = field(default_factory=list)

    def record(self, item: dict[str, Any]) -> None:
        self.history.append(item)
