"""Sending starts the approvals (S06, S11; D-133). Found live 2026-11-12: asked to send, the
agent never called ``send_to_customer`` because CloudCo's Sales file read as "get approval
first, then send", so no approval card ever appeared.

The harness path (send → Sales → Engineering → CFO → outbox) is locked here with a scripted
model on a copy of the workspace, so the real outbox is never touched. No model is called.
"""

import shutil
from pathlib import Path
from typing import Any

from agentic_harness.api import create_harness
from agentic_harness.gate import ApprovalRequest
from agentic_harness.limits import Limits
from agentic_harness.model import ModelReply, Step
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2] / "workspaces" / "cloudco"


class Scripted:
    name = "gemini-3.5-flash-lite"

    def __init__(self, *replies: list[Step]) -> None:
        self.replies = list(replies)

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        return ModelReply(self.replies.pop(0), "completed", {}, self.name)


def test_d133_the_sales_prompt_says_sending_starts_the_approvals() -> None:
    system = create_harness(
        Scripted(), Limits(), Workspace.load(ROOT), profile="sales", trace_dir=None, memory_dir=None
    ).system
    assert "Sending starts the approvals" in system
    assert "Don't ask the person's permission again" in system
    assert "Review first, then ask." in system  # D-163: a review-and-send shows the review first
    assert "Nothing is sent to a customer without a person approving it first" not in system


async def test_d133_a_send_asks_sales_then_engineering_then_the_cfo(tmp_path: Path) -> None:
    workspace = Workspace.load(shutil.copytree(ROOT, tmp_path / "cloudco"))
    asked: list[str] = []

    async def approve(request: ApprovalRequest) -> tuple[bool, str]:
        asked.append(request.approver)
        return True, ""

    send: Step = {
        "type": "function_call",
        "id": "s1",
        "name": "send_to_customer",
        "arguments": {
            "customer_id": "CUS-0042",
            "subject": "Your changes to CT-2207",
            "body": "We can offer 99.95% uptime and a 24-month liability cap.",
            "uptime_pct": 99.95,
            "liability_cap_months": 24,
        },
    }
    answer: Step = {
        "type": "model_output",
        "content": [{"type": "text", "text": "Sent, approved by Sales, Engineering and the CFO."}],
    }
    harness = create_harness(
        Scripted([send], [answer]),
        Limits(),
        workspace,
        profile="sales",
        trace_dir=None,
        memory_dir=None,
        approver=approve,
    )
    harness.scope_check = None  # it would call a model
    result = await harness.run("Send ShopCo the counter-offer.")
    assert asked == ["Sales", "Engineering", "CFO"]  # from the sender up (D-120)
    assert list((tmp_path / "cloudco" / "outbox").glob("*CUS-0042.md"))
    assert result.outcome == "completed"


async def test_each_person_is_asked_once_and_every_card_shows_the_chain(tmp_path: Path) -> None:
    """Your report: card 1 of 4 (Sales) listed the 25% discount, so it read as if Sales
    approved it. Now: one card per person (the CFO once, for both rules), and every card
    carries the chain with what each person decides."""
    workspace = Workspace.load(shutil.copytree(ROOT, tmp_path / "cloudco"))
    asked: list[str] = []

    async def approve(request: ApprovalRequest) -> tuple[bool, str]:
        asked.append(request.approver)
        return True, ""

    send: Step = {
        "type": "function_call",
        "id": "s1",
        "name": "send_to_customer",
        "arguments": {
            "customer_id": "CUS-0042",
            "subject": "Counter-offer",
            "body": "We can offer a 25% discount, 99.95% uptime and a liability cap of 24 months.",
            "discount_pct": 25,
            "uptime_pct": 99.95,
            "liability_cap_months": 24,
        },
    }
    answer: Step = {
        "type": "model_output",
        "content": [{"type": "text", "text": "Sent, approved by all."}],
    }
    harness = create_harness(
        Scripted([send], [answer]),
        Limits(),
        workspace,
        profile="sales",
        trace_dir=None,
        memory_dir=None,
        approver=approve,
    )
    harness.scope_check = None
    events: list[Any] = []
    harness.subscribe(events.append)
    await harness.run("Send ShopCo the counter-offer.")
    assert asked == ["Sales", "Engineering", "CFO"]  # the CFO once, not twice
    cards = [e.data for e in events if e.type == "approval_requested"]
    assert [(c["step"], c["of"]) for c in cards] == [(1, 3), (2, 3), (3, 3)]
    chain = cards[0]["chain"]
    assert [c["approver"] for c in chain] == ["Sales", "Engineering", "CFO"]
    cfo = chain[2]["rules"]
    assert [(r["arg"], r["value"]) for r in cfo] == [
        ("discount_pct", 25),
        ("liability_cap_months", 24),
    ]
    assert cards[0]["rule"] == "Any message to a customer"  # what Sales approves: the send
    # Where each term started (D-141): today's contract, the customer's ask, the move.
    started = {r["arg"]: r for r in cards[2]["context"]}
    assert cards[2]["context_labels"] == {"current": "Contract today", "asked": "Customer asked"}
    assert started["discount_pct"] == {
        "arg": "discount_pct",
        "ref": "CT-2207 §3.2",
        "current": "10%",
        "asked": "25%",
        "offered": "25%",
        "change": "up",
    }
    assert (started["uptime_pct"]["current"], started["uptime_pct"]["asked"]) == ("99.9%", "99.99%")
    assert (
        started["liability_cap_months"]["current"],
        started["liability_cap_months"]["asked"],
    ) == ("12 months", "unlimited")
