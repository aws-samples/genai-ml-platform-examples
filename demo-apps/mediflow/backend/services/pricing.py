"""Cost estimation for Bedrock model invocations."""

from backend.config import settings

# Pricing per 1M tokens (USD) — Bedrock cross-region inference
PRICING = {
    "apac.anthropic.claude-sonnet-4-20250514-v1:0": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
    "us.anthropic.claude-sonnet-4-20250514-v1:0": {
        "input_per_1m": 3.00,
        "output_per_1m": 15.00,
    },
}

_DEFAULT_RATES = {"input_per_1m": 3.00, "output_per_1m": 15.00}


def estimate_cost(
    input_tokens: int, output_tokens: int, model_id: str | None = None
) -> float:
    """Estimate USD cost from token counts."""
    model = model_id or settings.bedrock_model_id
    rates = PRICING.get(model, _DEFAULT_RATES)
    return (
        input_tokens * rates["input_per_1m"] / 1_000_000
        + output_tokens * rates["output_per_1m"] / 1_000_000
    )
