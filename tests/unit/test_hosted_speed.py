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


def test_s14_ac15_the_owner_defaults_to_sonnet() -> None:
    assert OWNER_MODEL == "claude-sonnet-5-5"


def test_s14_ac15_page_redraws_turns_and_approves_in_one_click() -> None:
    app_js = (WEB / "app.js").read_text()
    assert "function replayTurn(t)" in app_js
    assert "t.events?.length && replayTurn(t)" in app_js
    assert "oneClick ? `Approve as ${roleOf(p)}` : `Switch to ${roleOf(p)}`" in app_js
    assert "if (oneClick) approve.click();" in app_js
    assert 'plural(c.skills.length, "skill")} on offer' in app_js
