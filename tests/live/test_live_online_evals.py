"""Online evals on real Gemini (D-148, D-149). Runs only with ``make live``.

One real judge call (Flash-Lite) scores a real pull answer on every metric, cheaply.
"""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from agentic_harness.api import create_harness
from agentic_harness.config import load_settings
from agentic_harness.limits import Limits
from agentic_harness.model import GeminiModel
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
pytestmark = pytest.mark.live


async def test_d148_a_real_answer_is_scored_on_every_metric(tmp_path: Path) -> None:
    # Flash-Lite as the agent too: the free tier's bigger daily quota (and fewer 503s).
    settings = replace(load_settings(), model="gemini-3.5-flash-lite")
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_steps=8, max_seconds=180),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=tmp_path,
        secrets=[settings.require_key()],
        model_factory=lambda name: GeminiModel(replace(settings, model=name)),
        delegation=False,
    )
    result = await harness.run("Is ShopCo a customer? If yes, pull its contract details.")
    assert result.outcome == "completed", result.reason
    events = [json.loads(x) for x in (tmp_path / f"{result.run_id}.jsonl").read_text().splitlines()]
    finished = next(e["data"] for e in events if e["type"] == "online_evals_finished")
    by = {r["name"]: r for r in finished["results"]}
    assert set(by) == {
        "groundedness",
        "hallucination",
        "context_relevancy",
        "answer_relevancy",
        "citations",
        "style_format",
    }
    judged = [r for r in by.values() if r["graded_by"] == "judge"]
    assert all(r["status"] in ("passed", "failed") for r in judged), judged  # really scored
    assert finished["judge"] == "gemini-3.5-flash-lite"
    assert finished["usd"] < 0.002
    print(json.dumps(finished, indent=1))  # the real scores, for the record
