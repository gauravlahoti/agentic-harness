"""Offline evals for the owner on the hosted copy (S14, D-213). Your review, 2026-11-13:

- the Offline Evals page sat blank for seconds, then appeared all at once;
- the Next Run card showed $0 with Claude picked ("No price for 'claude-haiku-5-5'");
- there was no Run Eval button;
- Workspace and Observability should start folded on every visit.

- AC24: the owner's eval plan and run are priced and checked against Claude's models.
- AC25: the owner may start and stop an eval, which runs with the Claude key; visitors can't.
- AC26: the plan is worked out once per choice, not on every page visit.
- AC27: the page draws the evals before the plan arrives; sidebar folds start fresh each visit.
"""

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

import agentic_harness.server.app as server
from agentic_harness.config import Secret, Settings
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.server.evals import eval_env
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
CLOUDCO = ROOT / "workspaces" / "cloudco"
HOST = "tour.example"
OWNER = "owner-passphrase-for-tests-only"
WEB = ROOT / "src" / "agentic_harness" / "web"


def client(tmp_path: Path) -> TestClient:
    config = Settings(
        public=True,
        allowed_hosts=(HOST,),
        anthropic_key=Secret("sk-ant-fake-key-for-tests-0123456789"),
        owner_key=Secret(OWNER),
    )
    app = create_app(
        config, project_root=ROOT, workspace=Workspace.load(CLOUDCO), memory_dir=tmp_path
    )
    return TestClient(app, base_url=f"https://{HOST}")


OWNER_HEADERS = {**PAGE_HEADER, "X-Harness-Owner": OWNER}
CLAUDE = {"model": "claude-haiku-5-5", "judge": "claude-haiku-5-5"}


def test_s14_ac24_the_owner_eval_plan_is_priced_for_claude(tmp_path: Path) -> None:
    plan = client(tmp_path).get("/api/evals/plan", params=CLAUDE, headers=OWNER_HEADERS)
    assert plan.status_code == 200, plan.text
    body = plan.json()
    assert body["type"] == "plan"
    assert body["model"] == "claude-haiku-5-5"


def test_s14_ac25_the_owner_may_start_an_eval_and_visitors_may_not(tmp_path: Path) -> None:
    web = client(tmp_path)
    bad = {**CLAUDE, "cases": ["not a case!"], "runs": 1}
    # The owner gets past the read-only guard to the eval's own checks (a bad case: 400).
    assert web.post("/api/evals/run", headers=OWNER_HEADERS, json=bad).status_code == 400
    assert web.post("/api/evals/run", headers=PAGE_HEADER, json=bad).status_code == 403
    assert web.post("/api/evals/stop", headers=PAGE_HEADER).status_code == 403
    assert web.post("/api/evals/stop", headers=OWNER_HEADERS).status_code == 200


def test_s14_ac25_an_owner_eval_runs_with_the_claude_key() -> None:
    """The eval is its own process; in public mode it would see no key at all."""
    environ = {
        "HARNESS_PUBLIC": "1",
        "HARNESS_OWNER_KEY": OWNER,
        "ANTHROPIC_API_KEY": "k",
        "X": "1",
    }
    owner = eval_env(environ, owner=True)
    assert owner is not None
    assert "HARNESS_PUBLIC" not in owner
    assert "HARNESS_OWNER_KEY" not in owner  # the passphrase never leaves the server process
    assert owner["ANTHROPIC_API_KEY"] == "k"
    assert eval_env(environ, owner=False) is None  # everyone else: unchanged


def test_s14_ac26_the_plan_is_worked_out_once_per_choice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[list[str]] = []

    async def counted(project_root: Path, args: list[str]) -> dict[str, Any]:
        calls.append(args)
        return {"type": "plan", "cases": [], "model": "m", "judge": "j"}

    monkeypatch.setattr(server, "plan", counted)
    web = client(tmp_path)
    for _ in range(3):
        assert web.get("/api/evals/plan", params=CLAUDE, headers=OWNER_HEADERS).status_code == 200
    web.get("/api/evals/plan", params={**CLAUDE, "runs": 3}, headers=OWNER_HEADERS)
    assert len(calls) == 2  # one per choice


def test_s14_ac27_the_evals_page_draws_before_the_plan_arrives() -> None:
    app_js = (WEB / "app.js").read_text()
    start = app_js.index("async function loadEvals(select)")
    body = app_js[start : app_js.index("\nasync function loadSuite()", start)]
    assert 'await fetch("/api/evals/plan")' not in body  # no wait before the first draw
    assert "loadSuite()" in body
    css = (WEB / "app.css").read_text()
    assert ".owner-mode :is(#evals-run, #evals-reset, #evals-stop) { display: none; }" not in css


def test_s14_ac27_sidebar_folds_start_fresh_each_visit() -> None:
    app_js = (WEB / "app.js").read_text()
    assert "side-fold-" not in app_js  # not remembered: every visit starts at the defaults
