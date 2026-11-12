"""Stream one harness run to the page as NDJSON, one event per line (S01-AC13).

Harness part: the page. The harness emits events; this module is just one
more listener that forwards them to the browser while the run goes on.

Does not: decide anything about the run. If the page goes away, the run is
cancelled; if the harness crashes, the page still gets a final event.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Any

from agentic_harness.events import Event
from agentic_harness.loop import Harness
from agentic_harness.model import Step


async def stream_run(
    harness: Harness,
    task: str,
    *,
    history: Sequence[Step] = (),
    record: Callable[[list[Step]], None] | None = None,
) -> AsyncIterator[str]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    harness.subscribe(lambda event: queue.put_nowait(event.to_dict()))

    async def drive() -> None:
        try:
            await harness.run(task, history=history, record=record)
        except Exception as error:  # a harness bug must still end the stream
            queue.put_nowait(_crash(error))

    running = asyncio.create_task(drive())
    try:
        while True:
            event = await queue.get()
            yield json.dumps(event, ensure_ascii=False) + "\n"
            if ends_stream(event):
                break
    finally:
        if not running.done():  # the page closed mid-run: stop paying for it
            running.cancel()


def ends_stream(event: dict[str, Any]) -> bool:
    """Only the main agent's finish ends the stream. A helper's finish carries agent_id
    (D-63); stopping on it would cancel the main run mid-call (seen live in S04). When
    online evals follow (D-148), the stream ends with their scores instead."""
    data = event["data"]
    if data.get("agent_id"):
        return False
    if event["type"] == "run_finished":
        return not data.get("online_evals")
    return bool(event["type"] == "online_evals_finished")


def _crash(error: Exception) -> dict[str, Any]:
    reason = f"harness_error: {type(error).__name__}: {error}"
    return Event(
        "run_finished",
        run_id="",
        seq=0,
        time=0.0,
        data={
            "outcome": "failed",
            "reason": reason,
            "answer": "",
            "model_calls": 0,
            "usd": 0.0,
            "seconds": 0.0,
        },
    ).to_dict()
