"""The judge's On/Off switch on the Online Evals page, Off by default (D-167).

Your point (2026-11-12): a judge call on every live answer will hurt the budget. Off, only
the free code metrics run; the switch is kept on the server, so no browser can forget it.
Offline evals and the CLI still judge: create_harness defaults to on. No model is paid.
"""

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from agentic_harness.api import create_harness
from agentic_harness.config import Secret, Settings
from agentic_harness.limits import Limits
from agentic_harness.model import ModelReply
from agentic_harness.online_evals import JUDGE_SYSTEM, OnlineEvals
from agentic_harness.pricing import load_prices
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.verify import Call, Record
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2] / "workspaces"
CLOUDCO = Workspace.load(ROOT / "cloudco")
JS = (Path(__file__).parents[2] / "src" / "agentic_harness" / "web" / "app.js").read_text()
HTML = (Path(__file__).parents[2] / "src" / "agentic_harness" / "web" / "index.html").read_text()


def reply(text: str) -> ModelReply:
    step = {"type": "model_output", "content": [{"type": "text", "text": text}]}
    return ModelReply([step], "completed", {"total_input_tokens": 10}, "gemini-3.5-flash-lite")


class NoJudge:
    """Fails the test if anyone asks it to judge."""

    name = "gemini-3.5-flash-lite"

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        raise AssertionError("the judge was called while it is off")


async def test_d167_judge_off_scores_the_code_metrics_and_makes_no_call() -> None:
    style = CLOUDCO.online.style if CLOUDCO.online else ""
    evals = OnlineEvals(
        NoJudge(),  # type: ignore[arg-type]
        load_prices(),
        style=style,
        workspace_metrics=CLOUDCO.metrics,
        use_judge=False,
    )
    record = Record((Call("lookup_customer_record", {}, "ShopCo CUS-0042", False),))
    scored = await evals.score("Is ShopCo a customer?", "Yes, ShopCo (`CUS-0042`).", record)
    by = {r.name: r for r in scored.results}
    assert by["hallucination"].status == "passed"  # code: still scored, free
    for name in ("groundedness", "context_relevancy", "answer_relevancy", "style_format"):
        assert by[name].status == "skipped", name
        assert "judge is off" in by[name].reason
    assert scored.usd == 0.0
    assert scored.judge == ""


def test_d167_create_harness_judges_by_default_so_offline_evals_are_unchanged() -> None:
    class Idle:
        name = "gemini-3.5-flash-lite"

    def build(**kw: Any) -> Any:
        return create_harness(
            Idle(),  # type: ignore[arg-type]
            Limits(),
            CLOUDCO,
            profile="sales",
            trace_dir=None,
            memory_dir=None,
            **kw,
        )

    assert build().online.use_judge is True
    assert build(online_judge=False).online.use_judge is False


def hello_app(tmp_path: Path, judged: list[str]) -> TestClient:
    hello = shutil.copytree(ROOT / "hello", tmp_path / "hello")
    toml = hello / "workspace.toml"
    toml.write_text(toml.read_text() + "\n[online_evals]\n")

    class Model:
        def __init__(self, settings: Settings) -> None:
            self.name = settings.model

        async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
            if system == JUDGE_SYSTEM:
                judged.append(self.name)
                return reply(json.dumps({"answer_relevancy": {"score": 0.9, "reason": "ok"}}))
            return reply("Hello.")

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=Workspace.load(hello),
        trace_dir=tmp_path / "traces",
        model_factory=Model,
    )
    return TestClient(app, base_url="http://127.0.0.1")


def test_d167_the_switch_starts_off_is_saved_and_needs_the_page(tmp_path: Path) -> None:
    web = hello_app(tmp_path, [])
    assert web.get("/api/online-evals").json()["judge_on"] is False  # no file: off
    assert web.post("/api/online-evals/judge", json={"on": True}).status_code == 403
    assert web.post("/api/online-evals/judge", headers=PAGE_HEADER, json={"on": True}).json() == {
        "judge_on": True
    }
    assert web.get("/api/online-evals").json()["judge_on"] is True
    saved = tmp_path / ".agentic-harness" / "hello" / "online-evals.json"
    assert json.loads(saved.read_text()) == {"judge": True}


def test_d167_page_runs_follow_the_switch(tmp_path: Path) -> None:
    judged: list[str] = []
    web = hello_app(tmp_path, judged)
    web.post("/api/run", headers=PAGE_HEADER, json={"task": "Hi"})
    assert judged == []  # off by default: no judge call
    web.post("/api/online-evals/judge", headers=PAGE_HEADER, json={"on": True})
    web.post("/api/run", headers=PAGE_HEADER, json={"task": "Hi again"})
    assert len(judged) == 1


def test_d167_the_page_has_the_switch_on_the_online_evals_view() -> None:
    online = HTML.split('id="view-online"')[1].split("</section>")[0]
    assert 'id="online-judge"' in online
    assert "/api/online-evals/judge" in JS
    assert "judge off" in JS
