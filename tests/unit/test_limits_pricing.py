"""Stop rules and cost (S01-AC9).

A run stops on steps, cost or time, with a named reason. Cost counts thought tokens.
"""

import pytest

from agentic_harness.limits import Budget, Limits
from agentic_harness.pricing import PriceNotFoundError, Prices, load_prices

# Shaped like a real Gemini usage block (tests/fixtures/gemini/01_text.json).
USAGE = {
    "total_input_tokens": 1_000_000,
    "total_cached_tokens": 0,
    "total_output_tokens": 1_000_000,
    "total_thought_tokens": 1_000_000,
    "total_tool_use_tokens": 0,
}


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def test_s01_ac9_prices_come_from_the_data_file() -> None:
    prices = load_prices()
    flash = prices.for_model("gemini-3.8-flash")
    assert flash.input > 0
    assert flash.output > flash.input


def test_s01_ac9_unknown_model_has_no_price() -> None:
    with pytest.raises(PriceNotFoundError, match="no-such-model"):
        load_prices().for_model("no-such-model")


def test_s01_ac9_cost_counts_thought_tokens() -> None:
    prices = Prices({"m": {"input": 1.0, "output": 2.0, "cached_input": 0.5}})
    # 1M input at $1 + (1M output + 1M thought) at $2 = $5
    assert prices.cost("m", USAGE) == pytest.approx(5.0)
    without_thoughts = {**USAGE, "total_thought_tokens": 0}
    assert prices.cost("m", without_thoughts) == pytest.approx(3.0)


def test_s01_ac9_cached_input_is_billed_at_the_cached_rate() -> None:
    prices = Prices({"m": {"input": 1.0, "output": 2.0, "cached_input": 0.5}})
    usage = {"total_input_tokens": 1_000_000, "total_cached_tokens": 1_000_000}
    assert prices.cost("m", usage) == pytest.approx(0.5)


def test_s01_ac9_missing_usage_costs_nothing() -> None:
    prices = Prices({"m": {"input": 1.0, "output": 2.0, "cached_input": 0.5}})
    assert prices.cost("m", {}) == 0.0


def test_s01_ac9_step_limit() -> None:
    budget = Budget(Limits(max_steps=2))
    assert budget.exceeded() is None
    budget.count_step()
    budget.count_step()
    assert budget.exceeded() == "step_limit"


def test_s01_ac9_cost_limit() -> None:
    budget = Budget(Limits(max_usd=0.10))
    budget.charge(0.06)
    assert budget.exceeded() is None
    budget.charge(0.05)
    assert budget.exceeded() == "cost_limit"
    assert budget.usd == pytest.approx(0.11)


def test_s01_ac9_time_limit() -> None:
    clock = FakeClock()
    budget = Budget(Limits(max_seconds=10), clock=clock)
    clock.now = 4
    assert budget.exceeded() is None
    assert budget.seconds_left() == pytest.approx(6)
    clock.now = 10
    assert budget.exceeded() == "time_limit"
    assert budget.seconds_left() == 0


def test_s01_ac9_limits_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_steps"):
        Limits(max_steps=0)
