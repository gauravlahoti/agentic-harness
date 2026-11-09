"""Running a task from the page (S01-AC13 backend): POST /api/run streams the loop's events."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from agentic_harness.config import Settings
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.workspace import Workspace

HELLO = Path(__file__).resolve().parents[2] / "workspaces" / "hello"


def client(tmp_path: Path, workspace: Path | None = HELLO) -> TestClient:
    app = create_app(
        Settings(),
        project_root=tmp_path,
        workspace=Workspace.load(workspace) if workspace else None,
        trace_dir=tmp_path / "traces",
    )
    return TestClient(app, base_url="http://127.0.0.1")


def events(response_text: str) -> list[dict[str, object]]:
    return [json.loads(line) for line in response_text.splitlines()]


def test_s01_ac13_fake_run_streams_every_event(tmp_path: Path) -> None:
    response = client(tmp_path).post(
        "/api/run", headers=PAGE_HEADER, json={"task": "What time is it?", "mode": "fake"}
    )
    assert response.status_code == 200
    stream = events(response.text)
    assert stream[0]["type"] == "run_started"
    assert stream[-1]["type"] == "run_finished"
    assert stream[-1]["data"]["outcome"] == "completed"  # type: ignore[index]
    assert any(e["type"] == "tool_finished" for e in stream)


def test_s01_ac13_health_describes_the_workspace(tmp_path: Path) -> None:
    body = client(tmp_path).get("/api/health").json()
    assert body["workspace"] == {"name": "hello", "tools": ["get_time"], "fake": True}
    assert client(tmp_path, workspace=None).get("/api/health").json()["workspace"] is None


def test_s01_ac13_run_needs_the_page_header(tmp_path: Path) -> None:
    response = client(tmp_path).post("/api/run", json={"task": "hi", "mode": "fake"})
    assert response.status_code == 403


def test_s01_ac13_run_needs_a_workspace(tmp_path: Path) -> None:
    web = client(tmp_path, workspace=None)
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "hi", "mode": "fake"})
    assert response.status_code == 409


def test_s01_ac13_live_without_key_is_refused(tmp_path: Path) -> None:
    web = client(tmp_path)
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "hi", "mode": "live"})
    assert response.status_code == 400
    assert ".env" in response.json()["detail"]


def test_s01_ac13_task_must_be_sensible(tmp_path: Path) -> None:
    web = client(tmp_path)
    for body in (
        {"task": "", "mode": "fake"},
        {"task": "x" * 5000, "mode": "fake"},
        {"task": "hi", "mode": "other"},
    ):
        assert web.post("/api/run", headers=PAGE_HEADER, json=body).status_code == 422


def test_s01_ac13_one_run_at_a_time(tmp_path: Path) -> None:
    web = client(tmp_path)
    web.app.state.run_active = True  # type: ignore[attr-defined]
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "hi", "mode": "fake"})
    assert response.status_code == 409
