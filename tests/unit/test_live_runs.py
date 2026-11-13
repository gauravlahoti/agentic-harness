"""A run outlives the page that started it (S14, D-212).

Found live 2026-11-13: a send paused for approval, the owner opened another chat, then
reloaded, and the approval card was gone for good. The run waited 30 minutes for a click no
page could give. Now a run goes on in the background: its events are kept while it runs, the
chat list says which chat is waiting, and reopening the chat follows the run again, cards
included.

- AC21: ``LiveRun`` keeps every line, replays it to a late follower, and knows when the run
  waits for a person.
- AC22: through the server, a run whose page went away still finishes once approved from
  a reopened chat.
"""

import asyncio
import json
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import httpx

from agentic_harness.config import Secret, Settings
from agentic_harness.memory import TITLE_PROMPT
from agentic_harness.model import ModelReply, Step
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.server.live import LiveRun
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"


def line(type_: str, **data: Any) -> str:
    return json.dumps({"type": type_, "run_id": "r", "seq": 0, "time": 0.0, "data": data}) + "\n"


async def test_s14_ac21_a_late_follower_gets_every_line_then_the_rest() -> None:
    live = LiveRun("Send it")
    await live.add(line("run_started"))
    await live.add(line("approval_requested", call_id="c1", approver="Sales"))
    assert live.state() == "waiting"
    got: list[str] = []

    async def follow() -> None:
        async for text in live.follow():
            got.append(json.loads(text)["type"])

    follower = asyncio.create_task(follow())
    await asyncio.sleep(0)
    await live.add(line("approval_decided", call_id="c1", approved=True))
    assert live.state() == "running"
    await live.add(line("run_finished", answer="Sent."))
    assert live.state() is None  # answered: the chat shows it as a finished turn now
    await live.close()
    await asyncio.wait_for(follower, 1)
    assert got == ["run_started", "approval_requested", "approval_decided", "run_finished"]


async def test_s14_ac21_a_helper_finishing_is_not_the_answer() -> None:
    live = LiveRun("Review it")
    await live.add(line("run_finished", agent_id="helper-1", answer="notes"))
    assert live.state() == "running"


class Scripted:
    """Scope says IN, the title is fixed, the agent sends once, then reports it."""

    def __init__(self, settings: Settings) -> None:
        self.name = settings.model

    async def create(self, system: str, steps: Sequence[Step], tools: Sequence[Step]) -> ModelReply:
        if system.startswith("You decide whether"):
            text = "IN: a send"
        elif system == TITLE_PROMPT:
            text = '"ShopCo counter-offer."'
        elif any(s.get("type") == "function_result" for s in steps):
            text = "Sent to Maya Chen, approved by Sales, Engineering and the CFO."
        else:
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
            return ModelReply([send], "completed", {"total_input_tokens": 10}, self.name)
        step = {"type": "model_output", "content": [{"type": "text", "text": text}]}
        return ModelReply([step], "completed", {"total_input_tokens": 10}, self.name)


async def test_s14_ac22_a_run_survives_its_page_and_finishes_from_a_reopened_chat(
    tmp_path: Path,
) -> None:
    workspace = Workspace.load(shutil.copytree(CLOUDCO, tmp_path / "cloudco"))
    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=workspace,
        trace_dir=tmp_path / "traces",
        memory_dir=tmp_path / "memory",
        model_factory=Scripted,  # type: ignore[arg-type]
    )
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as web:
        body = {"task": "Send ShopCo the counter-offer.", "profile": "sales", "person": "priya"}
        page = asyncio.create_task(web.post("/api/run", headers=PAGE_HEADER, json=body))

        async def listed() -> dict[str, Any]:
            for _ in range(200):
                found = (await web.get("/api/sessions?profile=sales")).json()["sessions"]
                if found and found[0].get("live") == "waiting":
                    return dict(found[0])
                await asyncio.sleep(0.01)
            raise AssertionError("the chat never showed as waiting")

        chat = await listed()  # the list says which chat waits for a person
        page.cancel()  # the page went away (reload, closed tab)
        await asyncio.sleep(0.05)
        opened = (await web.get(f"/api/sessions/{chat['id']}?profile=sales")).json()
        assert opened["live"]["task"] == body["task"]

        # The reopened chat follows the run and answers each card as it comes.
        async def approve() -> None:
            approvals = app.state.approvals
            for person, role in (("priya", "Sales"), ("elena", "Engineering"), ("dana", "CFO")):
                for _ in range(300):
                    fresh = [c for c in approvals.waiting() if approvals.role_for(c) == role]
                    if fresh:
                        break
                    await asyncio.sleep(0.01)
                answer = {"call_id": fresh[0], "approved": True, "note": "", "person": person}
                assert (
                    await web.post("/api/approval", headers=PAGE_HEADER, json=answer)
                ).is_success

        approving = asyncio.create_task(approve())
        followed = await web.get(f"/api/sessions/{chat['id']}/live?profile=sales")
        await approving
        kinds = [json.loads(x)["type"] for x in followed.text.splitlines()]
        assert kinds[0] == "session_started"  # from the start, as if it never left
        assert kinds.count("approval_requested") == 3
        assert "run_finished" in kinds
        assert list((tmp_path / "cloudco" / "outbox").glob("*CUS-0042.md"))  # it was sent

        done = (await web.get(f"/api/sessions/{chat['id']}?profile=sales")).json()
        assert done["live"] is None
        assert done["turns"][-1]["answer"].startswith("Sent to Maya Chen")
        gone = await web.get(f"/api/sessions/{chat['id']}/live?profile=sales")
        assert gone.status_code == 404


def test_s14_ac23_the_page_follows_a_running_chat_and_marks_it() -> None:
    """D-212: opening a chat with a run still going follows it; the list says it waits."""
    web = Path(__file__).resolve().parents[2] / "src" / "agentic_harness" / "web"
    app_js = (web / "app.js").read_text()
    assert "if (session.live) followLive(id, session.live.task);" in app_js
    assert "/live${withProfile()}`, { signal: stop.signal }" in app_js
    assert '"Waiting for approval" : "Running"' in app_js
    assert app_js.count("stopFollowing();") >= 2  # leaving the chat stops this page following
    assert ".work-live.waiting { color: var(--part-guard); }" in (web / "app.css").read_text()
