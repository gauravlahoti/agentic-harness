"""Identity: an approval comes from its role (S12 Part B, AC6, AC8, AC9; D-137, D-138, D-139).

Found in the S11/S12 runs: one person at the page clicked Sales, Engineering and the CFO in
turn. Now each card is answered by a person with its role, and the server is what checks it.
No model is called.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentic_harness.api import create_harness
from agentic_harness.config import Settings
from agentic_harness.gate import ApprovalRequest
from agentic_harness.limits import Limits
from agentic_harness.model import ModelReply, Step
from agentic_harness.server.app import create_app
from agentic_harness.server.approvals import Approvals, WrongRoleError
from agentic_harness.workspace import Workspace, WorkspaceError

ROOT = Path(__file__).parents[2] / "workspaces" / "cloudco"
PAGE = {"X-Harness-Page": "1"}


def test_s12_ac6_people_come_from_the_workspace_and_cover_every_approval_role() -> None:
    ws = Workspace.load(ROOT)
    assert {(p.id, p.role) for p in ws.people} == {
        ("priya", "Sales"),
        ("elena", "Engineering"),
        ("farid", "Finance"),
        ("dana", "CFO"),
    }
    assert {a.approver for a in ws.approvals} <= {p.role for p in ws.people}


def test_s12_ac6_a_workspace_with_an_approval_role_nobody_has_is_refused(tmp_path: Path) -> None:
    copy = shutil.copytree(ROOT, tmp_path / "cloudco")
    toml = (copy / "workspace.toml").read_text().replace('role = "CFO"', 'role = "Nobody"')
    (copy / "workspace.toml").write_text(toml)
    with pytest.raises(WorkspaceError, match="no person has the role 'CFO'"):
        Workspace.load(copy)


async def test_s12_ac6_the_approvals_object_refuses_a_wrong_role() -> None:
    approvals = Approvals()
    request = ApprovalRequest("r", "c1", "send", {}, "chart", approver="CFO")
    waiting = asyncio.create_task(approvals.ask(request))
    await asyncio.sleep(0)
    assert approvals.role_for("c1") == "CFO"
    with pytest.raises(WrongRoleError):
        approvals.answer("c1", True, "", person="Priya (Sales)", role="Sales")
    assert approvals.waiting() == ["c1"]  # still waiting for the right person
    assert approvals.answer("c1", True, "ok", person="Dana (CFO)", role="CFO")
    assert await waiting == (True, "ok", "Dana (CFO)")


async def test_s12_ac6_the_endpoint_refuses_the_wrong_person_and_accepts_the_right_one(
    tmp_path: Path,
) -> None:
    class Idle:
        name = "gemini-3.5-flash-lite"

    app = create_app(
        Settings(api_key=None),
        project_root=tmp_path,
        workspace=Workspace.load(ROOT),
        model_factory=lambda s: Idle(),  # type: ignore[arg-type,return-value]
    )
    web = TestClient(app, base_url="http://127.0.0.1")
    request = ApprovalRequest("r", "c9", "send_to_customer", {}, "chart §1", approver="CFO")
    asking = asyncio.create_task(app.state.approvals.ask(request))
    await asyncio.sleep(0)
    answer = {"call_id": "c9", "approved": True}
    assert web.post("/api/approval", headers=PAGE, json=answer).status_code == 400  # who are you?
    sales = web.post("/api/approval", headers=PAGE, json=answer | {"person": "priya"})
    assert sales.status_code == 403
    assert "needs the CFO" in sales.json()["detail"]
    assert not asking.done()
    cfo = web.post("/api/approval", headers=PAGE, json=answer | {"person": "dana"})
    assert cfo.status_code == 200
    assert await asking == (True, "", "Dana Whitfield (CFO)")


def test_s12_ac6_the_page_gets_the_people() -> None:
    app = create_app(Settings(api_key=None), project_root=ROOT, workspace=Workspace.load(ROOT))
    web = TestClient(app, base_url="http://127.0.0.1")
    people = web.get("/api/health").json()["workspace"]["people"]
    assert [p["id"] for p in people] == ["priya", "elena", "farid", "dana"]


class Scripted:
    name = "gemini-3.5-flash-lite"

    def __init__(self, *replies: list[Step]) -> None:
        self.replies = list(replies)

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        return ModelReply(self.replies.pop(0), "completed", {}, self.name)


async def test_s12_ac8_ac9_the_sender_signs_off_the_send_and_the_outbox_names_each_person(
    tmp_path: Path,
) -> None:
    """Priya (Sales) gives the "any message" sign-off; Elena (Engineering) and Dana (CFO)
    answer their own cards. The outbox records who, not only the role (AC9)."""
    copy = shutil.copytree(ROOT, tmp_path / "cloudco")
    shutil.rmtree(copy / "outbox", ignore_errors=True)  # the real outbox came along: start empty
    workspace = Workspace.load(copy)
    who = {
        "Sales": "Priya Raman (Sales)",
        "Engineering": "Elena Brandt (Engineering)",
        "CFO": "Dana Whitfield (CFO)",
    }

    async def approve(request: ApprovalRequest) -> tuple[bool, str, str]:
        return True, "", who[request.approver]

    send: Step = {
        "type": "function_call",
        "id": "s1",
        "name": "send_to_customer",
        "arguments": {
            "customer_id": "CUS-0042",
            "subject": "Counter-offer",
            "body": "We can offer a 25% discount and 99.95% uptime.",
            "discount_pct": 25,
            "uptime_pct": 99.95,
        },
    }
    done: Step = {"type": "model_output", "content": [{"type": "text", "text": "Sent."}]}
    harness = create_harness(
        Scripted([send], [done]),
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
    decided = [e.data for e in events if e.type == "approval_decided"]
    assert [(d["approver"], d["person"]) for d in decided] == [
        ("Sales", "Priya Raman (Sales)"),
        ("Engineering", "Elena Brandt (Engineering)"),
        ("CFO", "Dana Whitfield (CFO)"),
    ]
    mail = next((tmp_path / "cloudco" / "outbox").glob("*CUS-0042.md")).read_text()
    assert "- Priya Raman (Sales) · " in mail
    assert "- Dana Whitfield (CFO) · " in mail
    finished = next(e.data for e in events if e.type == "tool_finished")
    assert "Dana Whitfield (CFO)" in finished["output"]
