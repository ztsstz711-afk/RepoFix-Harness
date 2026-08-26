from dataclasses import dataclass

from .schemas import TokenUsage


@dataclass(frozen=True)
class BudgetLimits:
    """Zero means unlimited; positive values are hard run-level limits."""

    max_requests: int = 0
    max_tokens: int = 0

    def __post_init__(self) -> None:
        if self.max_requests < 0 or self.max_tokens < 0:
            raise ValueError("budget limits must be zero or positive")

    def exceeded(self, usage: TokenUsage) -> tuple[str, str] | None:
        if self.max_requests and usage.requests >= self.max_requests:
            return "request_budget", f"model request budget reached ({usage.requests}/{self.max_requests})"
        if self.max_tokens and usage.total_tokens >= self.max_tokens:
            return "token_budget", f"token budget reached ({usage.total_tokens}/{self.max_tokens})"
        return None


@dataclass(frozen=True)
class ModelPricing:
    input_per_million: float = 0.0
    output_per_million: float = 0.0
    cached_input_per_million: float = 0.0

    def __post_init__(self) -> None:
        if min(self.input_per_million, self.output_per_million, self.cached_input_per_million) < 0:
            raise ValueError("model prices must be zero or positive")

    def estimate_usd(self, usage: TokenUsage) -> float:
        uncached_input = max(usage.input_tokens - usage.cached_input_tokens, 0)
        cost = (
            uncached_input * self.input_per_million
            + usage.cached_input_tokens * self.cached_input_per_million
            + usage.output_tokens * self.output_per_million
        ) / 1_000_000
        return round(cost, 8)


def classify_provider_failure(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "ratelimit" in name or "rate limit" in message or "429" in message:
        return "rate_limit"
    if "timeout" in name or "timed out" in message:
        return "timeout"
    if "authentication" in name or "permissiondenied" in name or "401" in message or "403" in message:
        return "authentication"
    if "connection" in name or "connection" in message:
        return "connection"
    if isinstance(exc, ValueError) and "model action" in message:
        return "invalid_model_output"
    return "provider_error"
