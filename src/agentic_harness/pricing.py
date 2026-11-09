"""Token prices and the cost of one model call (S01-AC9, D-25).

Harness part: the loop's cost limit. Prices live in ``pricing.toml``, a data
file, so no model name is written in code. An unknown model is an error at
startup: a missing price would let the cost limit silently count $0.

Does not: talk to Google, or know about the free tier (it prices every call
as paid, so the cost limit works the same either way).
"""

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

PER = 1_000_000  # prices are per million tokens


class PriceNotFoundError(LookupError):
    """No price for this model in pricing.toml."""


@dataclass(frozen=True, slots=True)
class ModelPrice:
    input: float
    output: float  # thinking tokens are billed at this rate too
    cached_input: float


class Prices:
    def __init__(self, table: Mapping[str, Mapping[str, float]]) -> None:
        self._table = {name: ModelPrice(**row) for name, row in table.items()}

    def for_model(self, model: str) -> ModelPrice:
        try:
            return self._table[model]
        except KeyError:
            known = ", ".join(sorted(self._table))
            raise PriceNotFoundError(
                f"No price for model {model!r} in pricing.toml (known: {known})."
            ) from None

    def cost(self, model: str, usage: Mapping[str, Any]) -> float:
        """USD for one call, from Gemini's usage block. Thought tokens count as output."""
        price = self.for_model(model)

        def count(key: str) -> int:
            return int(usage.get(key) or 0)  # missing or None → 0

        tokens_in = count("total_input_tokens") + count("total_tool_use_tokens")
        cached = count("total_cached_tokens")
        tokens_out = count("total_output_tokens") + count("total_thought_tokens")
        return (
            max(tokens_in - cached, 0) * price.input
            + cached * price.cached_input
            + tokens_out * price.output
        ) / PER


def load_prices() -> Prices:
    text = files("agentic_harness").joinpath("pricing.toml").read_text()
    return Prices(tomllib.loads(text)["models"])
