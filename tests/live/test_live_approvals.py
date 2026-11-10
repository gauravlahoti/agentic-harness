"""Approvals on real Gemini (S06-AC12, S06-AC9). Runs only with ``make live``.

The "people" are functions that play the roles: the CFO says "max 20%" the first time, then
approves; Sales approves the send. The agent has to hear the rejection and offer 20%.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from agentic_harness.api import create_harness
from agentic_harness.config import load_settings
from agentic_harness.gate import ApprovalRequest
from agentic_harness.limits import Limits
from agentic_harness.model import GeminiModel
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
pytestmark = pytest.mark.live


def make(tmp_path: Path, approver):  # type: ignore[no-untyped-def]
    settings = load_settings()
    return create_harness(
        GeminiModel(settings),
        Limits(max_steps=12, max_seconds=180),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=tmp_path,
        secrets=[settings.require_key()],
        model_factory=lambda name: GeminiModel(replace(settings, model=name)),
        delegation=False,
        approver=approver,
    )


async def test_s06_ac12_cfo_rejects_25_percent_the_agent_offers_20(tmp_path: Path) -> None:
    asked: list[tuple[str, bool, dict[str, object]]] = []
    cfo_said_no = False

    async def people(request: ApprovalRequest) -> tuple[bool, str]:
        nonlocal cfo_said_no
        if request.approver == "CFO" and not cfo_said_no:
            cfo_said_no = True
            asked.append(("CFO", False, request.arguments))
            return False, "max 20%"
        asked.append((request.approver, True, request.arguments))
        return True, ""

    # Copy the workspace so the outbox of this test stays out of the real folder.
    import shutil

    copy = tmp_path / "cloudco"
    shutil.copytree(CLOUDCO, copy, ignore=shutil.ignore_patterns("outbox", "tasks"))
    settings = load_settings()
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_steps=12, max_seconds=180),
        Workspace.load(copy),
        profile="sales",
        trace_dir=tmp_path / "traces",
        secrets=[settings.require_key()],
        model_factory=lambda name: GeminiModel(replace(settings, model=name)),
        delegation=False,
        approver=people,
    )
    result = await harness.run(
        "Send ShopCo (CUS-0042) a short note offering a 25% renewal discount. Send it now."
    )
    assert result.outcome == "completed", result.reason
    assert asked[0][:2] == ("CFO", False)  # the CFO was asked first and said no
    later = [a for a in asked[1:] if a[1]]
    assert any(a[0] == "CFO" and a[2].get("discount_pct") == 20 for a in later), asked
    assert any(a[0] == "Sales" for a in later), asked
    sent = next((copy / "outbox").glob("*.md")).read_text()
    assert "Approved by:" in sent
    assert "CFO" in sent
    assert "Sales" in sent


async def test_s06_ac9_the_agent_asks_which_customer(tmp_path: Path) -> None:
    questions: list[str] = []

    async def person(request: ApprovalRequest) -> tuple[bool, str]:
        if request.kind == "question":
            questions.append(str(request.arguments.get("question")))
            return True, "ShopCo, CUS-0042"
        return True, ""

    harness = make(tmp_path, person)
    result = await harness.run("Pull in the customer details.")
    assert result.outcome == "completed", result.reason
    assert questions, "the agent should have asked which customer"
    assert "ShopCo" in result.answer or "CUS-0042" in result.answer
