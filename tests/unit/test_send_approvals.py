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
    assert "Don't wait for approvals or ask the person's permission first" in system
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
