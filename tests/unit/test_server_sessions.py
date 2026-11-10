"""Conversations through the server (S07-AC1, AC2, AC3, AC11).

A scripted model stands in for Gemini. The real store writes to a temp folder.
"""

import json
from collections.abc import Sequence
from pathlib import Path

from fastapi.testclient import TestClient

from agentic_harness.config import Secret, Settings
from agentic_harness.memory import TITLE_PROMPT
from agentic_harness.model import ModelClient, ModelReply, Step
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.workspace import Workspace

HELLO = Path(__file__).resolve().parents[2] / "workspaces" / "hello"
CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"


class Sent:
    """What the scripted models were sent, across every run in a test."""

    def __init__(self) -> None:
        self.runs: list[list[Step]] = []
        self.title = "Greeting and the time"
        self.fail_title = False


def make_app(tmp_path: Path, sent: Sent, workspace: Path = HELLO) -> TestClient:
    class Scripted:
        def __init__(self, settings: Settings) -> None:
            self.name = settings.model

        async def create(
            self, system: str, steps: Sequence[Step], tools: Sequence[Step]
        ) -> ModelReply:
            if system == TITLE_PROMPT:
                if sent.fail_title:
                    raise RuntimeError("503")
                text = f'"{sent.title}."'
            else:
                sent.runs.append(list(steps))
                text = f"Answer {len(sent.runs)}."
            step = {"type": "model_output", "content": [{"type": "text", "text": text}]}
            return ModelReply([step], "completed", {"total_input_tokens": 10}, self.name)

    def factory(settings: Settings) -> ModelClient:
        return Scripted(settings)

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=Workspace.load(workspace),
        trace_dir=tmp_path / "traces",
        model_factory=factory,
    )
    return TestClient(app, base_url="http://127.0.0.1")


def run(web: TestClient, task: str, session: str | None = None, profile: str | None = None):  # type: ignore[no-untyped-def]
    body: dict[str, object] = {"task": task}
    if session:
        body["session"] = session
    if profile:
        body["profile"] = profile
    response = web.post("/api/run", headers=PAGE_HEADER, json=body)
    assert response.status_code == 200, response.text
    return [json.loads(line) for line in response.text.splitlines()]


def named(events: list[dict[str, object]], type_: str) -> dict[str, object]:
    return next(e["data"] for e in events if e["type"] == type_)  # type: ignore[return-value]


def test_s07_ac1_a_first_task_starts_a_conversation_with_a_topic_title(tmp_path: Path) -> None:
    sent = Sent()
    web = make_app(tmp_path, sent)
    events = run(web, "Hello there, what time is it?")
    started = named(events, "session_started")
    assert started["new"] is True
    assert started["title"] == "Hello there, what time is it?"  # the first words, at once
    titled = named(events, "session_titled")
    assert titled["title"] == "Greeting and the time"  # then the topic from the small model
    assert titled["session_id"] == started["session_id"]
    listed = web.get("/api/sessions").json()["sessions"]
    assert [(s["id"], s["title"], s["turns"]) for s in listed] == [
        (started["session_id"], "Greeting and the time", 1)
    ]


def test_s07_ac11_a_failed_title_call_keeps_the_first_words(tmp_path: Path) -> None:
    sent = Sent()
    sent.fail_title = True
    web = make_app(tmp_path, sent)
    events = run(web, "Hello there, what time is it?")
    assert named(events, "session_titled")["title"] == "Hello there, what time is it?"
    assert (
        web.get("/api/sessions").json()["sessions"][0]["title"] == "Hello there, what time is it?"
    )


def test_s07_ac1_a_follow_up_resends_the_conversation(tmp_path: Path) -> None:
    sent = Sent()
    web = make_app(tmp_path, sent)
    first = named(run(web, "First question"), "session_started")["session_id"]
    again = run(web, "Second question", session=str(first))
    assert named(again, "session_started")["new"] is False
    assert not any(e["type"] == "session_titled" for e in again)  # titled once
    texts = [
        part["text"]
        for step in sent.runs[-1]
        for part in step.get("content", [])
        if part.get("type") == "text"
    ]
    assert texts == ["First question", "Answer 1.", "Second question"]
    opened = web.get(f"/api/sessions/{first}").json()
    assert [(t["task"], t["answer"]) for t in opened["turns"]] == [
        ("First question", "Answer 1."),
        ("Second question", "Answer 2."),
    ]


def test_s07_ac2_a_conversation_can_be_deleted_from_the_page_only(tmp_path: Path) -> None:
    web = make_app(tmp_path, Sent())
    session = str(named(run(web, "Hi"), "session_started")["session_id"])
    assert web.delete(f"/api/sessions/{session}").status_code == 403  # needs the page header
    assert web.delete(f"/api/sessions/{session}", headers=PAGE_HEADER).status_code == 200
    assert web.get("/api/sessions").json()["sessions"] == []
    assert web.get(f"/api/sessions/{session}").status_code == 404
    assert web.delete(f"/api/sessions/{session}", headers=PAGE_HEADER).status_code == 404


def test_s07_ac2_the_list_is_for_one_profile(tmp_path: Path) -> None:
    web = make_app(tmp_path, Sent(), workspace=CLOUDCO)
    run(web, "A sales question", profile="sales")
    run(web, "An engineering question", profile="engineering")
    sales = web.get("/api/sessions", params={"profile": "sales"}).json()["sessions"]
    engineering = web.get("/api/sessions", params={"profile": "engineering"}).json()["sessions"]
    assert len(sales) == 1
    assert len(engineering) == 1
    assert sales[0]["id"] != engineering[0]["id"]
    assert web.get("/api/sessions", params={"profile": "pirates"}).status_code == 400
    sales_id = sales[0]["id"]
    # Another profile can't open it.
    assert (
        web.get(f"/api/sessions/{sales_id}", params={"profile": "engineering"}).status_code == 404
    )


def test_s07_ac3_a_conversation_survives_a_server_restart(tmp_path: Path) -> None:
    sent = Sent()
    first = make_app(tmp_path, sent)
    session = str(named(run(first, "Before the restart"), "session_started")["session_id"])
    second = make_app(tmp_path, sent)  # a new server over the same folder
    assert [s["id"] for s in second.get("/api/sessions").json()["sessions"]] == [session]
    run(second, "After the restart", session=session)
    texts = [
        part["text"]
        for step in sent.runs[-1]
        for part in step.get("content", [])
        if part.get("type") == "text"
    ]
    assert texts[0] == "Before the restart"
    assert texts[-1] == "After the restart"


def test_s07_an_unknown_conversation_is_a_clear_error(tmp_path: Path) -> None:
    web = make_app(tmp_path, Sent())
    response = web.post(
        "/api/run", headers=PAGE_HEADER, json={"task": "hi", "session": "20990101-000000-abc123"}
    )
    assert response.status_code == 404
