"""Events: how the loop tells the world what it did (S01-AC11, D-24).

Harness part: the loop's output. The loop emits one Event per step; anyone
can subscribe (the trace writer, the page, the CLI, tests). The loop never
knows who is listening: rule 2.

Does not: write files (trace.py does) or format text for people.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

# The event types, in the order a run produces them.
EVENT_TYPES = (
    "run_started",
    "model_called",
    "model_replied",
    "tool_started",
    "tool_finished",
    "run_finished",
)


@dataclass(frozen=True, slots=True)
class Event:
    type: str
    run_id: str
    seq: int  # 1, 2, 3 … within one run
    time: float  # seconds since the epoch
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


Listener = Callable[[Event], None]


class EventBus:
    """A plain list of listeners. Each event goes to each listener, in order."""

    def __init__(self) -> None:
        self._listeners: list[Listener] = []

    def subscribe(self, listener: Listener) -> None:
        self._listeners.append(listener)

    def emit(self, event: Event) -> None:
        for listener in self._listeners:
            listener(event)
