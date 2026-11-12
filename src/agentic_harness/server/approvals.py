"""Approvals waiting for a person on the page (S05-AC12; D-79; S12 Part B, D-137).

Harness part: the page side of "human in the loop". When the gate says a tool needs a
person, the loop calls ``Approvals.ask`` and waits; the page shows a ⏸ card, and the
person's click arrives at ``POST /api/approval``, which calls ``answer``.

An approval is answered by a person with the card's role. The page hides the button for
anyone else, but the check that counts is here, on the server (D-137).

Does not: decide what needs approval (the gate does) or time out (the loop does).
"""

import asyncio
from dataclasses import dataclass

from agentic_harness.gate import ApprovalRequest


@dataclass(frozen=True, slots=True)
class Waiting:
    future: "asyncio.Future[tuple[bool, str, str]]"
    approver: str  # the role that must answer ("" for a question: anyone)


class WrongRoleError(Exception):
    """The person answering doesn't have the role the card names."""


class Approvals:
    def __init__(self) -> None:
        self._waiting: dict[str, Waiting] = {}

    async def ask(self, request: ApprovalRequest) -> tuple[bool, str, str]:
        """Wait until the right person answers on the page (or the run is cancelled).
        Returns (approved, note, who answered)."""
        answer: asyncio.Future[tuple[bool, str, str]] = asyncio.get_running_loop().create_future()
        self._waiting[request.call_id] = Waiting(answer, request.approver)
        try:
            return await answer
        finally:
            self._waiting.pop(request.call_id, None)

    def role_for(self, call_id: str) -> str | None:
        """The role the waiting card names, or None if nothing waits under that ID."""
        waiting = self._waiting.get(call_id)
        return None if waiting is None or waiting.future.done() else waiting.approver

    def answer(
        self, call_id: str, approved: bool, note: str, *, person: str = "", role: str | None = None
    ) -> bool:
        """The click. False if nothing is waiting under that ID. With ``role`` given (the
        answering person's role), a card for another role is refused (``WrongRoleError``)."""
        waiting = self._waiting.get(call_id)
        if waiting is None or waiting.future.done():
            return False
        if role is not None and waiting.approver and role != waiting.approver:
            raise WrongRoleError(waiting.approver)
        waiting.future.set_result((approved, note, person))
        return True

    def waiting(self) -> list[str]:
        return list(self._waiting)
