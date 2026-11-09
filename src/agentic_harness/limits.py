"""Stop rules: the loop's brakes (S01-AC9, D-27).

Harness part: the loop. A run stops when it has made too many model calls,
spent too much, or taken too long, and it says which one.

Does not: price tokens (pricing.py does) or stop a call midway (the loop
wraps each call in a timeout built from ``seconds_left``).
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

StopReason = Literal["step_limit", "cost_limit", "time_limit"]


@dataclass(frozen=True, slots=True)
class Limits:
    """The brakes for one run. Defaults are deliberately small (D-27)."""

    max_steps: int = 25  # model calls
    max_usd: float = 1.00
    max_seconds: float = 120.0

    def __post_init__(self) -> None:
        for name in ("max_steps", "max_usd", "max_seconds"):
            if getattr(self, name) <= 0:
                raise ValueError(f"{name} must be above zero")


class Budget:
    """What one run has used so far, checked against its Limits."""

    def __init__(self, limits: Limits, clock: Callable[[], float] = time.monotonic) -> None:
        self.limits = limits
        self.steps = 0
        self.usd = 0.0
        self._clock = clock
        self._start = clock()

    def count_step(self) -> None:
        self.steps += 1

    def charge(self, usd: float) -> None:
        self.usd += usd

    def elapsed(self) -> float:
        return self._clock() - self._start

    def seconds_left(self) -> float:
        return max(self.limits.max_seconds - self.elapsed(), 0.0)

    def exceeded(self) -> StopReason | None:
        """The first limit that is used up, or None if the run may continue."""
        if self.steps >= self.limits.max_steps:
            return "step_limit"
        if self.usd >= self.limits.max_usd:
            return "cost_limit"
        if self.seconds_left() <= 0:
            return "time_limit"
        return None
