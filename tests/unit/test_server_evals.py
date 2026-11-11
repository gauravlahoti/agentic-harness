"""S10-AC9 (the Evals view's data) and S10-AC10 (start one fixed command; Stop; one at a time).

The project root is a temp folder with a tiny fake ``evals/run.py`` that echoes what it was
started with: the tests see exactly what the page can make the server run, and nothing
real (no model, no key) is ever touched.
"""

import asyncio
import json
import shutil
import textwrap
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentic_harness.config import Settings
from agentic_harness.server.app import create_app
from agentic_harness.server.evals import EvalError, EvalProcess, command
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
LOCAL = "http://127.0.0.1:8000"
PAGE = {"X-Harness-Page": "1"}

FAKE_RUN = textwrap.dedent(
    """
    import json, signal, sys, time
    args = sys.argv[1:]
    if "--plan" in args:
        print(json.dumps({"type": "plan", "args": args}))
        sys.exit(0)
    print(json.dumps({"type": "eval_started", "args": args}), flush=True)
    if "slow" in args:
        def stopped(*_):
            done = {"type": "eval_finished", "stop_reason": "Stopped by you."}
            print(json.dumps(done), flush=True)
            sys.exit(1)
        signal.signal(signal.SIGTERM, stopped)
        time.sleep(30)
    print("not json: ignored")
    print(json.dumps({"type": "eval_finished", "stop_reason": ""}), flush=True)
    """
)


def project(tmp_path: Path, *, cases: bool = True) -> Path:
    evals = tmp_path / "evals"
    (evals / "cases").mkdir(parents=True)
    (evals / "__init__.py").write_text("")
    (evals / "run.py").write_text(FAKE_RUN)
    shutil.copy(ROOT / "evals" / "catalog.json", evals / "catalog.json")
    if cases:
        (evals / "cases" / "cloudco.toml").write_text("# cases\n")
    return tmp_path


def result(eval_id: str, passed: int) -> dict[str, Any]:
    return {
        "id": eval_id,
        "started": eval_id,
        "status": "finished",
        "summary": {"cases": 2, "passed": passed},
        "cases": [{"id": "a"}],
    }


def client(root: Path, workspace: bool = True) -> TestClient:
    ws = Workspace.load(ROOT / "workspaces" / "cloudco") if workspace else None
    app = create_app(Settings(), project_root=root, workspace=ws, memory_dir=root / "memory")
    return TestClient(app, base_url=LOCAL)


def test_s10_ac9_lists_results_newest_first_with_the_catalog(tmp_path: Path) -> None:
    root = project(tmp_path)
    folder = root / "memory" / "evals"
    folder.mkdir(parents=True)
    for eval_id, passed in (("20261111-090000-aaaaaa", 1), ("20261111-100000-bbbbbb", 2)):
        (folder / f"{eval_id}.json").write_text(json.dumps(result(eval_id, passed)))
    (folder / "notes.json").write_text("{}")  # not an eval: skipped
    body = client(root).get("/api/evals").json()
    assert [r["id"] for r in body["results"]] == [
        "20261111-100000-bbbbbb",
        "20261111-090000-aaaaaa",
    ]
    assert "cases" not in body["results"][0]  # the list is short; the detail has the cases
    assert body["catalog"]["metrics"]["role_adherence"]["deepeval"] == "RoleAdherenceMetric"
    assert body["has_cases"] is True
    assert body["running"] is False
    one = client(root).get("/api/evals/20261111-100000-bbbbbb").json()
    assert one["cases"] == [{"id": "a"}]


def test_s10_ac9_result_ids_are_checked(tmp_path: Path) -> None:
    web = client(project(tmp_path))
    assert web.get("/api/evals/20991231-000000-abcdef").status_code == 404
    assert web.get("/api/evals/..%2F..%2Fsecret").status_code in (400, 404)
    assert web.get("/api/evals/not-an-id").status_code == 400


def test_s10_ac10_run_needs_the_page_and_checks_every_input(tmp_path: Path) -> None:
    web = client(project(tmp_path))
    assert web.post("/api/evals/run", json={}).status_code == 403
    assert web.post("/api/evals/run", json={"runs": 2}, headers=PAGE).status_code == 422
    bad_model = web.post("/api/evals/run", json={"model": "gpt-9"}, headers=PAGE)
    assert bad_model.status_code == 400
    assert "No price" in bad_model.json()["detail"]
    bad_judge = web.post("/api/evals/run", json={"judge": "gpt-9"}, headers=PAGE)
    assert bad_judge.status_code == 400
    assert "No price" in bad_judge.json()["detail"]
    bad_case = web.post("/api/evals/run", json={"cases": ["--out=/etc"]}, headers=PAGE)
    assert bad_case.status_code == 400
    assert "Not a case ID" in bad_case.json()["detail"]


def test_s10_ac10_run_starts_only_the_fixed_command_and_streams(tmp_path: Path) -> None:
    root = project(tmp_path)
    response = client(root).post(
        "/api/evals/run",
        json={
            "cases": ["off-topic", "find-changes"],
            "runs": 3,
            "model": "gemini-3.5-flash-lite",
            "judge": "gemini-3.6-flash",
        },
        headers=PAGE,
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [e["type"] for e in events] == ["eval_started", "eval_finished", "exit"]
    args = events[0]["args"]
    assert args == [
        "--json",
        "--suite",
        str(root / "evals" / "cases" / "cloudco.toml"),
        "--out",
        str(root / "memory" / "evals"),
        "--runs",
        "3",
        "--model",
        "gemini-3.5-flash-lite",
        "--judge",
        "gemini-3.6-flash",
        "--cases",
        "off-topic,find-changes",
    ]
    assert events[-1]["code"] == 0


def test_s10_ac10_plan_runs_the_same_command_with_plan(tmp_path: Path) -> None:
    body = client(project(tmp_path)).get("/api/evals/plan?cases=off-topic&runs=1").json()
    assert body["type"] == "plan"
    assert body["args"][-1] == "--plan"
    assert "gemini-3.8-flash" in body["args"]  # the default model when none is picked
    assert body["args"][body["args"].index("--judge") + 1] == "gemini-3.5-flash-lite"  # D-111


def test_s10_ac10_no_workspace_or_no_cases(tmp_path: Path) -> None:
    assert client(project(tmp_path), workspace=False).get("/api/evals/plan").status_code == 409
    other = tmp_path / "other"
    other.mkdir()
    web = client(project(other, cases=False))
    assert web.get("/api/evals").json()["has_cases"] is False
    assert web.post("/api/evals/run", json={}, headers=PAGE).status_code == 404


async def test_s10_ac10_stop_ends_the_eval_and_one_runs_at_a_time(tmp_path: Path) -> None:
    root = project(tmp_path)
    args = command(
        root / "evals" / "cases" / "cloudco.toml",
        root / "out",
        cases=["slow"],
        runs=1,
        model="m",
        judge="m",
        models=["m"],
    )
    process = EvalProcess()
    await process.start(root, args)
    follow = process.follow()
    first = await anext(follow)
    assert first["type"] == "eval_started"
    assert process.running
    with pytest.raises(EvalError, match="already running"):
        await process.start(root, args)
    assert process.stop() is True
    rest = [event async for event in follow]
    assert rest[0] == {"type": "eval_finished", "stop_reason": "Stopped by you."}
    assert rest[-1] == {"type": "exit", "code": 1}
    assert not process.running
    assert process.stop() is False


async def test_s10_a_reloaded_page_follows_the_running_eval_from_the_start(tmp_path: Path) -> None:
    """D-119: the server reads the eval itself; a page that comes back sees every event so far."""
    root = project(tmp_path)
    args = command(
        root / "evals" / "cases" / "cloudco.toml",
        root / "out",
        cases=["slow"],
        runs=1,
        model="m",
        judge="m",
        models=["m"],
    )
    process = EvalProcess()
    await process.start(root, args)
    await asyncio.sleep(0.5)  # the first page went away; the eval goes on
    again = process.follow()
    assert (await anext(again))["type"] == "eval_started"  # from the start
    process.stop()
    assert [e async for e in again][-1]["type"] == "exit"


async def test_s10_stop_ends_even_an_eval_that_ignores_it(tmp_path: Path) -> None:
    """D-119: if the eval doesn't end within the grace period after Stop, it is ended for it."""
    root = project(tmp_path)
    (root / "evals" / "run.py").write_text(
        "import json, signal, sys, time\n"
        "signal.signal(signal.SIGTERM, lambda *_: None)  # pretend to be stuck\n"
        "print(json.dumps({'type': 'eval_started'}), flush=True)\n"
        "time.sleep(60)\n"
    )
    args = command(
        root / "evals" / "cases" / "cloudco.toml",
        root / "out",
        cases=[],
        runs=1,
        model="m",
        judge="m",
        models=["m"],
    )
    process = EvalProcess(stop_grace_seconds=0.3)
    await process.start(root, args)
    follow = process.follow()
    await anext(follow)
    process.stop()
    events = await asyncio.wait_for(_all(follow), timeout=10)
    assert events[-1]["type"] == "exit"
    assert not process.running


async def _all(follow: Any) -> list[dict[str, Any]]:
    return [e async for e in follow]


def test_s10_the_page_can_ask_to_follow_the_running_eval(tmp_path: Path) -> None:
    web = client(project(tmp_path))
    assert web.get("/api/evals/follow").status_code == 409  # nothing running
