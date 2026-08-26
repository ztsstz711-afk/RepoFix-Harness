from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

@dataclass
class Action:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    requests: int = 0

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_tokens += other.total_tokens
        self.cached_input_tokens += other.cached_input_tokens
        self.requests += other.requests


@dataclass
class ModelDecision:
    action: Action
    usage: TokenUsage = field(default_factory=TokenUsage)
    model: str = ""

@dataclass
class Observation:
    tool: str
    output: str
    success: bool = True
    duration_ms: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TestSnapshot:
    success: bool
    output: str
    duration_ms: int = 0


@dataclass
class EvaluationState:
    baseline: TestSnapshot | None = None
    final: TestSnapshot | None = None
    changed_files: list[str] = field(default_factory=list)

@dataclass
class RunState:
    task: str
    repo: str
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    model: str = ""
    step: int = 0
    status: str = "running"
    summary: str = ""
    error: str = ""
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    usage: TokenUsage = field(default_factory=TokenUsage)
    evaluation: EvaluationState = field(default_factory=EvaluationState)
    history: list[dict[str, Any]] = field(default_factory=list)

    def record(self, item: dict[str, Any]) -> None:
        self.history.append(item)
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunState":
        values = dict(data)
        values["usage"] = TokenUsage(**values.get("usage", {}))
        evaluation = values.get("evaluation", {})
        if isinstance(evaluation, dict):
            baseline = evaluation.get("baseline")
            final = evaluation.get("final")
            values["evaluation"] = EvaluationState(
                baseline=TestSnapshot(**baseline) if baseline else None,
                final=TestSnapshot(**final) if final else None,
                changed_files=evaluation.get("changed_files", []),
            )
        return cls(**values)
