import pytest

from repofix.budget import BudgetLimits, ModelPricing, classify_provider_failure
from repofix.schemas import TokenUsage


def test_budget_limits_zero_is_unlimited():
    usage = TokenUsage(total_tokens=50_000, requests=100)
    assert BudgetLimits().exceeded(usage) is None


def test_token_budget_reports_reason():
    result = BudgetLimits(max_tokens=500).exceeded(TokenUsage(total_tokens=500))
    assert result == ("token_budget", "token budget reached (500/500)")


def test_negative_budget_is_rejected():
    with pytest.raises(ValueError, match="zero or positive"):
        BudgetLimits(max_requests=-1)


def test_pricing_uses_separate_cached_input_rate():
    usage = TokenUsage(input_tokens=1_000, output_tokens=200, cached_input_tokens=400)
    pricing = ModelPricing(input_per_million=2, output_per_million=5, cached_input_per_million=0.5)
    assert pricing.estimate_usd(usage) == 0.0024


def test_negative_price_is_rejected():
    with pytest.raises(ValueError, match="zero or positive"):
        ModelPricing(output_per_million=-1)


def test_provider_failure_classification():
    assert classify_provider_failure(TimeoutError("late")) == "timeout"
    assert classify_provider_failure(RuntimeError("HTTP 429 rate limit")) == "rate_limit"
    assert classify_provider_failure(ValueError("invalid model action after retries")) == "invalid_model_output"
