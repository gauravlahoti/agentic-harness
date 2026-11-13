"""Runs that outlive the page that started them (S14, D-212).

Harness part: the page. A run used to live inside its page's request: switch chats and its
approval card was gone from view; reload and nothing could reach the run again, so it waited
out the approval timeout. Now the server drives each run in the background and keeps its
NDJSON lines here. The page that started it follows them, and so can any page that opens
the chat later: it gets every line from the start, then the rest as they come.

Does not: run anything or decide anything. It only keeps lines, and says whether the run is
still going, waiting for a person, or has answered.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Callable


class LiveRun:
    def __init__(self, task: str) -> None:
        self.task = task
        self.lines: list[str] = []
        self.done = False  # no more lines will come
        self.answered = False  # the main agent's answer is in (online evals may still score it)
        self.waiting: set[str] = set()  # approval cards still open
        self._changed = asyncio.Condition()

    async def add(self, line: str) -> None:
        event = json.loads(line)
        kind, data = event["type"], event.get("data") or {}
        if kind == "approval_requested":
            self.waiting.add(str(data.get("call_id")))
        elif kind == "approval_decided":
            self.waiting.discard(str(data.get("call_id")))
        elif kind == "run_finished" and not data.get("agent_id"):
            self.answered = True
        async with self._changed:
            self.lines.append(line)
            self._changed.notify_all()

    async def close(self) -> None:
        async with self._changed:
            self.done = True
            self._changed.notify_all()

    def state(self) -> str | None:
        """Waiting for a person, running, or None once answered (a finished turn)."""
        if self.answered or self.done:
            return None
        return "waiting" if self.waiting else "running"

    async def follow(self) -> AsyncIterator[str]:
        """Every line so far, then each new one, until the run is done."""
        seen = 0
        while True:
            while seen < len(self.lines):
                yield self.lines[seen]
                seen += 1
            if self.done:
                return
            async with self._changed:
                await self._changed.wait_for(self._moved_past(seen))

    def _moved_past(self, seen: int) -> Callable[[], bool]:
        return lambda: self.done or len(self.lines) > seen
