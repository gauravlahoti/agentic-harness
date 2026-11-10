"""Approvals waiting for a person on the page (S05-AC12; D-79).

Harness part: the page side of "human in the loop". When the gate says a tool needs a
person, the loop calls ``Approvals.ask`` and waits; the page shows a ⏸ card, and the
person's click arrives at ``POST /api/approval``, which calls ``answer``.

Does not: decide what needs approval (the gate does) or time out (the loop does).
"""

import asyncio

from agentic_harness.gate import ApprovalRequest


class Approvals:
    def __init__(self) -> None:
        self._waiting: dict[str, asyncio.Future[tuple[bool, str]]] = {}

    async def ask(self, request: ApprovalRequest) -> tuple[bool, str]:
        """Wait until the person answers on the page (or the run is cancelled)."""
        answer: asyncio.Future[tuple[bool, str]] = asyncio.get_running_loop().create_future()
        self._waiting[request.call_id] = answer
        try:
            return await answer
        finally:
            self._waiting.pop(request.call_id, None)

    def answer(self, call_id: str, approved: bool, note: str) -> bool:
        """The person's click. False if nothing is waiting under that ID."""
        waiting = self._waiting.get(call_id)
        if waiting is None or waiting.done():
            return False
        waiting.set_result((approved, note))
        return True

    def waiting(self) -> list[str]:
        return list(self._waiting)
