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
    retries: int = 0
    format_retries: int = 0
    transient_retries: int = 0

    def add(self, other: "TokenUsage") -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.total_tokens += other.total_tokens
        self.cached_input_tokens += other.cached_input_tokens
        self.requests += other.requests
        self.retries += other.retries
        self.format_retries += other.format_retries
        self.transient_retries += other.transient_retries


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
    command: str = "pytest -q"
    execution_backend: str = "local"


@dataclass
class PreflightCheck:
    name: str
    status: str
    message: str


@dataclass
class PreflightState:
    success: bool = False
    checks: list[PreflightCheck] = field(default_factory=list)


@dataclass
class EvaluationState:
    baseline: TestSnapshot | None = None
    final: TestSnapshot | None = None
    changed_files: list[str] = field(default_factory=list)
    rollback_performed: bool = False
    rollback_files: list[str] = field(default_factory=list)
    post_rollback: TestSnapshot | None = None
    rollback_error: str = ""

@dataclass
class RunState:
    task: str
    repo: str
    test_command: str = "pytest -q"
    execution_backend: str = "local"
    docker_image: str = "repofix-pytest:latest"
    command_timeout_seconds: int = 30
    run_id: str = field(default_factory=lambda: uuid4().hex[:12])
    model: str = ""
    step: int = 0
    status: str = "running"
    summary: str = ""
    error: str = ""
    failure_kind: str = ""
    estimated_cost_usd: float = 0.0
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    usage: TokenUsage = field(default_factory=TokenUsage)
    preflight: PreflightState = field(default_factory=PreflightState)
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
        preflight = values.get("preflight", {})
        if isinstance(preflight, dict):
            values["preflight"] = PreflightState(
                success=preflight.get("success", False),
                checks=[PreflightCheck(**check) for check in preflight.get("checks", [])],
            )
        evaluation = values.get("evaluation", {})
        if isinstance(evaluation, dict):
            baseline = evaluation.get("baseline")
            final = evaluation.get("final")
            post_rollback = evaluation.get("post_rollback")
            values["evaluation"] = EvaluationState(
                baseline=TestSnapshot(**baseline) if baseline else None,
                final=TestSnapshot(**final) if final else None,
                changed_files=evaluation.get("changed_files", []),
                rollback_performed=evaluation.get("rollback_performed", False),
                rollback_files=evaluation.get("rollback_files", []),
                post_rollback=TestSnapshot(**post_rollback) if post_rollback else None,
                rollback_error=evaluation.get("rollback_error", ""),
            )
        return cls(**values)
