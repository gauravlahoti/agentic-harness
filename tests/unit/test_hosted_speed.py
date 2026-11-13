"""Hosted speed and history (S14, D-200): what the live owner session measured as slow or lost.

- AC12: model SDKs warm up when the server starts, not inside the first run.
- AC13: with a staging folder, a run's trace is written locally and saved whole at its end;
  without one (the default, local use) traces go straight to the trace folder.
- AC14: a reopened chat gets each turn's steps from its trace, so the page can redraw them.
- AC15: the owner session's defaults and one-click approvals; the honest skills label.
"""

import sys
from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient

from agentic_harness.cli import warm_sdks
from agentic_harness.config import OWNER_MODEL, Secret, Settings, load_settings
from agentic_harness.model import ModelReply, Step
from agentic_harness.server.app import create_app
from agentic_harness.workspace import Workspace
from tests.unit.test_server_sessions import HELLO, Sent, make_app, run

WEB = Path(__file__).resolve().parents[2] / "src" / "agentic_harness" / "web"


def staged_app(tmp_path: Path) -> TestClient:
    """A one-reply scripted model, with a staging folder for traces."""

    class Scripted:
        def __init__(self, settings: Settings) -> None:
            self.name = settings.model

        async def create(
            self, system: str, steps: Sequence[Step], tools: Sequence[Step]
        ) -> ModelReply:
            step = {"type": "model_output", "content": [{"type": "text", "text": "Hello."}]}
            return ModelReply([step], "completed", {"total_input_tokens": 10}, self.name)

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key"), trace_staging=tmp_path / "stage"),
        project_root=tmp_path,
        workspace=Workspace.load(HELLO),
        trace_dir=tmp_path / "traces",
        model_factory=Scripted,  # type: ignore[arg-type]
    )
    return TestClient(app, base_url="http://127.0.0.1")


def test_s14_ac12_the_model_sdks_warm_up_at_start() -> None:
    warm_sdks().join(timeout=60)
    assert "anthropic" in sys.modules


def test_s14_ac13_a_staged_trace_is_saved_whole_at_the_end(tmp_path: Path) -> None:
    web = staged_app(tmp_path)
    events = run(web, "Hi")
    run_id = next(e["run_id"] for e in events if e["type"] == "run_started")
    saved = tmp_path / "traces" / f"{run_id}.jsonl"
    assert saved.is_file()
    assert '"run_finished"' in saved.read_text()
    assert not list((tmp_path / "stage").glob("*.jsonl"))  # nothing left behind


def test_s14_ac13_without_staging_traces_go_straight_to_the_folder(tmp_path: Path) -> None:
    web = make_app(tmp_path, Sent())
    events = run(web, "Hi")
    run_id = next(e["run_id"] for e in events if e["type"] == "run_started")
    assert (tmp_path / "traces" / f"{run_id}.jsonl").is_file()


def test_s14_ac13_staging_is_read_from_the_environment(tmp_path: Path) -> None:
    on = load_settings(tmp_path / "x.env", environ={"HARNESS_TRACE_STAGING": "/var/harness/stage"})
    assert on.trace_staging == Path("/var/harness/stage")
    assert load_settings(tmp_path / "x.env", environ={}).trace_staging is None


def test_s14_ac14_a_reopened_chat_has_every_step(tmp_path: Path) -> None:
    web = make_app(tmp_path, Sent())
    events = run(web, "Hi")
    session = next(e["data"]["session_id"] for e in events if e["type"] == "session_started")
    turns = web.get(f"/api/sessions/{session}").json()["turns"]
    kinds = [e["type"] for e in turns[0]["events"]]
    assert kinds[0] == "run_started"
    assert "run_finished" in kinds


def test_s14_ac14_a_turn_without_a_trace_has_no_steps(tmp_path: Path) -> None:
    web = make_app(tmp_path, Sent())
    events = run(web, "Hi")
    session = next(e["data"]["session_id"] for e in events if e["type"] == "session_started")
    for trace in (tmp_path / "traces").glob("*.jsonl"):
        trace.unlink()
    assert web.get(f"/api/sessions/{session}").json()["turns"][0]["events"] == []


def test_s14_ac15_the_owner_defaults_to_haiku_for_speed() -> None:
    """D-201, your choice: Haiku for live demos (D-200 had Sonnet)."""
    assert OWNER_MODEL == "claude-haiku-5-5"


def test_s14_ac16_the_owner_sees_live_step_status_locally_unchanged() -> None:
    """D-201: the hosted owner's run header says what is happening and for how long;
    a local page keeps "Working…"."""
    app_js = (WEB / "app.js").read_text()
    assert "function liveStatus(ev, turn)" in app_js
    assert 'if (!document.body.classList.contains("owner-mode")) return;' in app_js
    assert '"Model thinking"' in app_js
    assert "turn?.stopStatus?.();" in app_js
    assert 'el("span", "agent-stats working", "Working…")' in app_js  # local default kept


def test_s14_ac15_page_redraws_turns_and_approves_in_one_click() -> None:
    app_js = (WEB / "app.js").read_text()
    assert "function replayTurn(t)" in app_js
    assert "t.events?.length && replayTurn(t)" in app_js
    assert "oneClick ? `Approve as ${roleOf(p)}` : `Switch to ${roleOf(p)}`" in app_js
    assert "if (oneClick) approve.click();" in app_js
    assert 'plural(c.skills.length, "skill")} on offer' in app_js


def test_s14_ac17_a_hosted_page_is_marked_before_first_paint(tmp_path: Path) -> None:
    """D-202, your report: the chat screen flashed before the tour. A hosted page is served
    already marked, so CSS hides the chat until tour or owner mode; locally it's unchanged."""
    hosted = create_app(
        Settings(public=True), project_root=tmp_path, workspace=Workspace.load(HELLO)
    )
    page = TestClient(hosted, base_url="http://127.0.0.1").get("/")
    assert page.status_code == 200
    assert '<body class="hosted-boot">' in page.text
    assert page.headers["cache-control"] == "no-cache"
    local = TestClient(create_app(Settings(), project_root=tmp_path), base_url="http://127.0.0.1")
    assert "hosted-boot" not in local.get("/").text
    css = (WEB / "app.css").read_text()
    assert ".hosted-boot:not(.tour-mode):not(.owner-mode)" in css


def test_s14_ac17_a_hosted_page_never_stays_blank() -> None:
    """D-202: a failed health check lifts the marker, and CSS reveals the page after 4 s even
    if no script runs."""
    app_js = (WEB / "app.js").read_text()
    css = (WEB / "app.css").read_text()
    assert 'document.body.classList.remove("hosted-boot")' in app_js
    assert "@keyframes hosted-reveal { to { visibility: visible; } }" in css


def test_s14_ac18_locked_switches_say_why() -> None:
    """D-202, your request: hovering a locked switch explains it, only where it is locked."""
    app_js = (WEB / "app.js").read_text()
    css = (WEB / "app.css").read_text()
    assert "Read-only in this guided tour." in app_js  # your wording choice (D-202)
    assert "View the Code (in the sidebar)" in app_js
    assert (
        ":is(.tour-mode, .public-mode:not(.owner-mode)) "
        ".switch-wrap:is(:hover, :focus-within)::after" in css
    )


def test_s14_ac19_the_agentic_loop_reads_like_the_reference() -> None:
    """D-205, your review: the Agentic Loop rows follow the Agent SDK's loop (turns, tool results
    fed back, an end on a reply with no tool calls) and say what this harness adds."""
    app_js = (WEB / "app.js").read_text()
    assert "It ends when a reply asks for no tools: that's the answer" in app_js
    assert "the harness runs them one after another" in app_js
    assert "${l.max_steps} turns · $${l.max_usd}" in app_js
    # D-207, your review: only the loop itself stays (how it works, tools, model, stops)
    loop = app_js.split('paneSection("loop"')[1].split("paneSection(")[0]
    for gone in ('"Small jobs"', '"Before you see it"', '"Helpers"', '"Plans"', '"Prompt caching"'):
        assert gone not in loop, gone
