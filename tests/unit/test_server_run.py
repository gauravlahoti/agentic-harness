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
    assert body["title"] == "Contract Agent"
    assert body["owner"] == "CloudCo"
    assert [p["id"] for p in body["profiles"]] == ["sales", "engineering"]  # D-74
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
    assert {s["name"] for s in body["skills"]} == {"technical-review", "uptime-check"}
    tools = {t["name"]: t for t in body["tools"]}
    assert tools["send_to_customer"]["risk"] == "action"
    assert tools["review_contract"]["delegate_only"] is True
    assert body["subagents"][0]["name"] == "clause-reviewer"
    assert body["remote_tools"] == []  # no MCP servers: every tool runs locally
    assert set(body) >= {"context", "skills", "tools", "subagents", "memory", "guardrails", "loop"}
    guard = body["guardrails"]
    assert guard["profile"] == "Engineering"
    assert "send_to_customer" in guard["not_allowed"]  # Engineering can't send (S05)
    assert "annual_value_usd" in guard["hidden_fields"]
    assert guard["approvals"] == []  # it can't send, so nothing to approve
    assert guard["never"] == []  # the hard limits are on a tool it can't use
    sales = web.get("/api/harness", params={"profile": "sales"}).json()["guardrails"]
    assert sales["approvals"][0]["tool"] == "send_to_customer"
    assert len(sales["never"]) == 4
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


async def test_s05_ac12_the_page_answers_a_waiting_approval() -> None:
    import asyncio

    from agentic_harness.gate import ApprovalRequest
    from agentic_harness.server.approvals import Approvals

    approvals = Approvals()
    request = ApprovalRequest("run-1", "c1", "send", {"body": "hi"}, "chart §3")
    waiting = asyncio.create_task(approvals.ask(request))
    await asyncio.sleep(0)
    assert approvals.waiting() == ["c1"]
    assert not approvals.answer("nope", True, "")  # nothing waits under that ID
    assert approvals.answer("c1", False, "wrong price")
    assert await waiting == (False, "wrong price")
    assert approvals.waiting() == []


def test_s05_ac12_approval_endpoint_needs_the_page_and_a_waiting_request(tmp_path: Path) -> None:
    web = client(tmp_path, workspace=CLOUDCO)
    body = {"call_id": "c1", "approved": True}
    assert web.post("/api/approval", json=body).status_code == 403
    assert web.post("/api/approval", headers=PAGE_HEADER, json=body).status_code == 404


def test_s05_effort_is_offered_checked_and_reaches_the_model(tmp_path: Path) -> None:
    from agentic_harness.model import GeminiModel

    built: list[Settings] = []

    def factory(settings: Settings) -> ModelClient:
        built.append(settings)
        return GeminiModel(settings, client=object())  # built, never called

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=Workspace.load(CLOUDCO),
        model_factory=factory,
    )
    web = TestClient(app, base_url="http://127.0.0.1")
    assert web.get("/api/health").json()["efforts"] == ["low", "medium", "high"]
    bad = web.post("/api/run", headers=PAGE_HEADER, json={"task": "Hi", "effort": "ludicrous"})
    assert bad.status_code == 422  # only Gemini's own levels
    web.post(
        "/api/run", headers=PAGE_HEADER, json={"task": "Hi", "profile": "sales", "effort": "low"}
    )
    assert built
    assert built[0].thinking == "low"  # the run's own model; a title call carries no effort


def test_s05_workspace_logo_and_agent_menu(tmp_path: Path) -> None:
    web = client(tmp_path, workspace=CLOUDCO)
    workspace = web.get("/api/health").json()["workspace"]
    assert workspace["logo"] is True
    (agent,) = workspace["agents"]
    assert (agent["id"], agent["name"]) == ("cloudco", "Contract Agent")
    assert "contract" in agent["description"].lower()  # what it does, under its name
    logo = web.get("/api/workspace/logo")
    assert logo.status_code == 200
    assert logo.headers["content-type"] == "image/svg+xml"
    assert b"fictional" in logo.content  # all CloudCo material is labelled made up
    assert client(tmp_path, workspace=HELLO).get("/api/workspace/logo").status_code == 404


def test_s05_a_logo_must_be_a_small_picture_inside_the_workspace(tmp_path: Path) -> None:
    import pytest

    from agentic_harness.workspace import WorkspaceError

    (tmp_path / "workspace.toml").write_text('logo = "../outside.svg"\n')
    with pytest.raises(WorkspaceError, match="inside the workspace"):
        Workspace.load(tmp_path)
    (tmp_path / "workspace.toml").write_text('logo = "missing.svg"\n')
    with pytest.raises(WorkspaceError, match="not found"):
        Workspace.load(tmp_path)
    (tmp_path / "workspace.toml").write_text('logo = "notes.txt"\n')
    with pytest.raises(WorkspaceError, match="inside the workspace"):
        Workspace.load(tmp_path)
