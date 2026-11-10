"""Running a task from the page (S01-AC13 backend): what /api/run accepts and refuses."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from agentic_harness.config import Secret, Settings
from agentic_harness.model import ModelClient
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


def test_s01_ac13_health_describes_the_workspace(tmp_path: Path) -> None:
    body = client(tmp_path).get("/api/health").json()
    assert body["workspace"]["name"] == "hello"
    assert body["workspace"]["title"] == "Hello"
    assert body["workspace"]["tools"] == ["get_time"]
    assert body["workspace"]["profiles"] == []
    assert client(tmp_path, workspace=None).get("/api/health").json()["workspace"] is None


def test_s01_ac13_run_needs_the_page_header(tmp_path: Path) -> None:
    response = client(tmp_path).post("/api/run", json={"task": "hi"})
    assert response.status_code == 403


def test_s01_ac13_run_needs_a_workspace(tmp_path: Path) -> None:
    web = client(tmp_path, workspace=None)
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "hi"})
    assert response.status_code == 409


def test_s01_ac13_live_without_key_is_refused(tmp_path: Path) -> None:
    web = client(tmp_path)
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "hi"})
    assert response.status_code == 400
    assert ".env" in response.json()["detail"]


def test_s01_ac13_task_must_be_sensible(tmp_path: Path) -> None:
    web = client(tmp_path)
    for body in (
        {"task": ""},
        {"task": "x" * 5000},
        {"task": "hi", "model": "m" * 200},
    ):
        assert web.post("/api/run", headers=PAGE_HEADER, json=body).status_code == 422


def test_s01_ac13_one_run_at_a_time(tmp_path: Path) -> None:
    web = client(tmp_path)
    web.app.state.run_active = True  # type: ignore[attr-defined]
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "hi"})
    assert response.status_code == 409


def test_s01_ac13_health_lists_the_models_you_can_pick(tmp_path: Path) -> None:
    body = client(tmp_path).get("/api/health").json()
    assert "gemini-3.5-flash-lite" in body["models"]
    assert body["model"] in body["models"]


def test_s01_ac13_unpriced_model_is_refused(tmp_path: Path) -> None:
    built: list[str] = []

    def factory(settings: Settings) -> ModelClient:  # must never be reached
        built.append(settings.model)
        raise AssertionError("no model should be built for an unpriced name")

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=Workspace.load(HELLO),
        model_factory=factory,
    )
    web = TestClient(app, base_url="http://127.0.0.1")
    body = {"task": "Time?", "model": "gemini-made-up"}
    response = web.post("/api/run", headers=PAGE_HEADER, json=body)
    assert response.status_code == 400
    assert "pricing.toml" in response.json()["detail"]
    assert built == []


CLOUDCO = HELLO.parent / "cloudco"


def test_s02_ac12_health_describes_profiles_and_examples(tmp_path: Path) -> None:
    body = client(tmp_path, workspace=CLOUDCO).get("/api/health").json()["workspace"]
    assert body["title"] == "Contract Assistant"
    assert body["owner"] == "CloudCo"
    assert [p["id"] for p in body["profiles"]] == ["sales", "engineering", "finance", "cfo"]
    assert body["examples"]


def test_s02_ac12_unknown_profile_is_refused(tmp_path: Path) -> None:
    def factory(settings: Settings) -> ModelClient:
        raise AssertionError("no model should be built for an unknown profile")

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=Workspace.load(CLOUDCO),
        model_factory=factory,
    )
    web = TestClient(app, base_url="http://127.0.0.1")
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "Hi", "profile": "pirates"})
    assert response.status_code == 400
    assert "pirates" in response.json()["detail"]


def test_s04_ac11_harness_endpoint_shows_what_a_run_gets(tmp_path: Path) -> None:
    web = client(tmp_path, workspace=CLOUDCO)
    body = web.get("/api/harness", params={"profile": "engineering"}).json()
    assert body["profile"] == "engineering"
    assert [f["path"] for f in body["context"]["files"]] == ["AGENTS.md", "teams/engineering.md"]
    assert {s["name"] for s in body["skills"]} == {"contract-review", "uptime-check"}
    tools = {t["name"]: t for t in body["tools"]}
    assert tools["send_to_customer"]["risk"] == "action"
    assert tools["review_contract"]["delegate_only"] is True
    assert body["subagents"][0]["name"] == "clause-reviewer"
    assert body["remote_tools"] == []  # no MCP servers: every tool runs locally
    assert set(body) >= {"context", "skills", "tools", "subagents", "memory", "guardrails", "loop"}
    assert body["guardrails"]["risks"] == {"read": 3, "write": 0, "action": 1}  # D-73
    assert web.get("/api/harness", params={"profile": "pirates"}).status_code == 400
    assert client(tmp_path, workspace=None).get("/api/harness").status_code == 409


def test_s04_ac12_run_refuses_unknown_switches(tmp_path: Path) -> None:
    def factory(settings: Settings) -> ModelClient:
        from agentic_harness.model import GeminiModel

        return GeminiModel(settings, client=object())  # built, never called

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=Workspace.load(CLOUDCO),
        model_factory=factory,
    )
    web = TestClient(app, base_url="http://127.0.0.1")
    body = {"task": "Hi", "profile": "sales", "off": {"tools": ["launch_rockets"]}}
    response = web.post("/api/run", headers=PAGE_HEADER, json=body)
    assert response.status_code == 400
    assert "launch_rockets" in response.json()["detail"]
    too_many = {"task": "Hi", "off": {"tools": ["x"] * 200}}
    assert web.post("/api/run", headers=PAGE_HEADER, json=too_many).status_code == 422
