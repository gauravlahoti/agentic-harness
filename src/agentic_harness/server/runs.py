"""Stream one harness run to the page as NDJSON, one event per line (S01-AC13).

Harness part: the page. The harness emits events; this module is just one
more listener that forwards them to the browser while the run goes on.

Does not: decide anything about the run. If the page goes away, the run is
cancelled; if the harness crashes, the page still gets a final event.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from agentic_harness.events import Event
from agentic_harness.loop import Harness


async def stream_run(harness: Harness, task: str) -> AsyncIterator[str]:
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    harness.subscribe(lambda event: queue.put_nowait(event.to_dict()))

    async def drive() -> None:
        try:
            await harness.run(task)
        except Exception as error:  # a harness bug must still end the stream
            queue.put_nowait(_crash(error))

    running = asyncio.create_task(drive())
    try:
        while True:
            event = await queue.get()
            yield json.dumps(event, ensure_ascii=False) + "\n"
            if event["type"] == "run_finished":
                break
    finally:
        if not running.done():  # the page closed mid-run: stop paying for it
            running.cancel()


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
