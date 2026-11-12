"""Draft replies as cards, the person the agent helps, concerns first (S12-AC11 to AC14).

Found on a live run (your report, 2026-11-12): the draft came out as quoted text with
"Hi [contact first name]", and it went straight to a counter-offer without talking the
concerns through. D-164 (draft card), D-165 (concerns → agree → draft → send), D-166 (who).
No model is called.
"""

import json
import tomllib
from pathlib import Path

from fastapi.testclient import TestClient

from agentic_harness.api import create_harness
from agentic_harness.config import Settings
from agentic_harness.context import build_context
from agentic_harness.limits import Limits
from agentic_harness.server.app import create_app
from agentic_harness.tools import ToolContext
from agentic_harness.tools.registry import call_tool
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2]
CLOUDCO = ROOT / "workspaces" / "cloudco"
JS = (ROOT / "src" / "agentic_harness" / "web" / "app.js").read_text()
PAGE = {"X-Harness-Page": "1"}


# ── AC11 · draft_reply ───────────────────────────────────────────────────────────────────
async def test_s12_ac11_draft_reply_saves_a_mail_shaped_task_file_to_the_contact(
    tmp_path: Path,
) -> None:
    tool = {t.name: t for t in Workspace.load(CLOUDCO).tools}["draft_reply"]
    assert tool.risk == "read"  # a draft goes nowhere: no approval needed
    events: list[tuple[str, dict[str, object]]] = []
    ctx = ToolContext("run-7", tmp_path, emit=lambda kind, **d: events.append((kind, d)))
    result = await call_tool(
        tool,
        {"customer_id": "CUS-0042", "subject": "Our reply", "body": "Hi Maya,\n\nThanks.\n\nPriya"},
        ctx,
    )
    assert not result.is_error, result.output
    saved = json.loads(result.output)
    assert saved["file"].startswith("tasks/run-7/")
    assert not (tmp_path / "outbox").exists()  # a draft never reaches the outbox
    kind, data = events[-1]
    assert kind == "file_saved"
    assert data["folder"] == "tasks"
    text = str(data["text"])
    assert text.splitlines()[1].startswith("To: Maya Chen, ShopCo <")  # the real contact
    assert "Subject: Our reply" in text


def test_s12_ac11_every_customer_has_a_named_contact() -> None:
    rows = json.loads((CLOUDCO / "data" / "customers.json").read_text())["records"]
    for row in rows:
        assert row["contact"]["name"], row["id"]
        assert "@" in row["contact"]["email"], row["id"]


def test_s12_ac11_sales_may_draft_engineering_may_not() -> None:
    profiles = tomllib.loads((CLOUDCO / "workspace.toml").read_text())["profiles"]
    assert "draft_reply" in profiles["sales"]["tools"]
    assert "draft_reply" not in profiles["engineering"]["tools"]


# ── AC12 · the person reaches the run ────────────────────────────────────────────────────
def test_s12_ac12_the_context_names_the_person_it_helps() -> None:
    ws = Workspace.load(CLOUDCO)
    priya = next(p for p in ws.people if p.id == "priya")
    system = build_context(ws, "sales", person=priya).system
    assert "You are helping Priya Raman (Sales)" in system
    assert "Priya Raman" not in build_context(ws, "sales").system.split("## From")[0]


def test_s12_ac12_the_harness_passes_the_person_to_the_context() -> None:
    class Idle:
        name = "gemini-3.5-flash-lite"

    ws = Workspace.load(CLOUDCO)
    dana = next(p for p in ws.people if p.id == "dana")
    harness = create_harness(
        Idle(),  # type: ignore[arg-type]
        Limits(),
        ws,
        profile="sales",
        trace_dir=None,
        memory_dir=None,
        person=dana,
    )
    assert "You are helping Dana Whitfield (CFO)" in harness.system


def test_s12_ac12_the_server_refuses_an_unknown_person(tmp_path: Path) -> None:
    app = create_app(
        Settings(api_key=None), project_root=tmp_path, workspace=Workspace.load(CLOUDCO)
    )
    web = TestClient(app, base_url="http://127.0.0.1")
    reply = web.post("/api/run", headers=PAGE, json={"task": "hi", "person": "nobody"})
    assert reply.status_code == 400
    assert "nobody" in reply.json()["detail"]


def test_s12_ac12_the_page_sends_the_picked_person_with_each_run() -> None:
    assert "person: currentPerson()?.id" in JS.split("async function runTask")[1].split("\n}\n")[0]


# ── AC13 · the draft card on the page ────────────────────────────────────────────────────
def test_s12_ac13_a_task_file_with_mail_headers_is_a_draft_card() -> None:
    assert 'd.folder === "outbox" || d.folder === "tasks"' in JS  # both folders may hold mail
    assert '"✎ Draft"' in JS
    assert '"✉ Sent"' in JS
    assert "(turn.mail ??= []).push(d)" in JS  # shown open under the answer


def test_s12_ac13_quoted_lines_render_as_a_blockquote() -> None:
    prose = JS.split("function renderProse")[1].split("\n}\n")[0]
    assert 'el("blockquote"' in prose


# ── AC14 · concerns first, then agree, then draft, then send ─────────────────────────────
def test_s12_ac14_sales_prompts_say_concerns_first_then_draft_then_offer_to_send() -> None:
    team = (CLOUDCO / "teams" / "sales.md").read_text()
    review = (CLOUDCO / "skills" / "sales" / "contract-review" / "SKILL.md").read_text()
    reply = (CLOUDCO / "skills" / "sales" / "reply-to-customer" / "SKILL.md").read_text()
    style = (CLOUDCO / "answer-style.md").read_text()
    assert "Concerns first" in team
    assert "draft_reply" in team
    assert "Change anything, or send it as is?" not in team + reply  # D-163's step, replaced
    assert "Want to go through these" in review
    assert "draft_reply" in reply
    assert "Send it to" in reply
    assert "placeholder" in style.lower()
    assert "by first name" in style


def test_s12_ac14_golden_cases_cover_concerns_first_and_agree_then_draft() -> None:
    cases = {
        c["id"]: c
        for c in tomllib.loads((ROOT / "evals" / "cases" / "cloudco.toml").read_text())["case"]
    }
    first = cases["review-then-confirm"]
    assert {"send_to_customer", "draft_reply"} <= set(first["never_call"])
    then = cases["agree-then-draft"]
    assert len(then["turns"]) == 2
    assert "draft_reply" in then["expected_tools"]
    assert "send_to_customer" in then["never_call"]
