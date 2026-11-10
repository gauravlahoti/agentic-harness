"""Long-term memory on the page: see and forget saved facts, per profile (S07-AC4; D-101)."""

from pathlib import Path

from fastapi.testclient import TestClient

from agentic_harness.config import Settings
from agentic_harness.memory import forget_note, list_notes, note_path
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
HELLO = CLOUDCO.parent / "hello"


def web(tmp_path: Path, workspace: Path = CLOUDCO) -> TestClient:
    app = create_app(
        Settings(), project_root=tmp_path, workspace=Workspace.load(workspace), trace_dir=tmp_path
    )
    return TestClient(app, base_url="http://127.0.0.1")


def seed(tmp_path: Path, profile: str, *lines: str) -> Path:
    file = note_path(tmp_path / ".agentic-harness", "cloudco", profile)
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("".join(f"{line}\n" for line in lines))
    return file


def test_s07_ac4_facts_are_listed_for_every_profile(tmp_path: Path) -> None:
    seed(tmp_path, "sales", "- 2026-11-10 · The CFO capped ShopCo at 20%.")
    body = web(tmp_path).get("/api/facts").json()
    assert body["on"] is True
    by_id = {p["id"]: p for p in body["profiles"]}
    assert by_id["sales"]["label"] == "Sales"
    assert by_id["sales"]["facts"] == ["- 2026-11-10 · The CFO capped ShopCo at 20%."]
    assert by_id["engineering"]["facts"] == []


def test_s07_ac4_a_fact_can_be_forgotten_from_the_page_only(tmp_path: Path) -> None:
    line = "- 2026-11-10 · ShopCo pays late."
    file = seed(tmp_path, "sales", line, "- 2026-11-10 · Keep me.")
    client = web(tmp_path)
    body = {"profile": "sales", "line": line}
    assert client.post("/api/facts/forget", json=body).status_code == 403
    assert client.post("/api/facts/forget", headers=PAGE_HEADER, json=body).status_code == 200
    assert list_notes(file) == ["- 2026-11-10 · Keep me."]
    assert client.post("/api/facts/forget", headers=PAGE_HEADER, json=body).status_code == 404
    bad = {"profile": "pirates", "line": line}
    assert client.post("/api/facts/forget", headers=PAGE_HEADER, json=bad).status_code == 400


def test_s07_ac4_forget_removes_only_that_line(tmp_path: Path) -> None:
    file = seed(tmp_path, "sales", "- a", "- b", "- c")
    assert forget_note(file, "- b") is True
    assert list_notes(file) == ["- a", "- c"]
    assert forget_note(file, "- z") is False


def test_s07_ac4_a_workspace_without_notes_says_so(tmp_path: Path) -> None:
    body = web(tmp_path, HELLO).get("/api/facts").json()
    assert body["on"] is False
    assert body["profiles"] == [{"id": None, "label": "Everyone", "facts": []}]
