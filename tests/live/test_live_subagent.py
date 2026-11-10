"""Sub-agents on real Gemini (S04-AC2, AC6, AC7, AC10, AC13). Runs only with ``make live``.

The same question twice: with the Clause Reviewer (delegation on) and without it. Both must
find the 5 changes that matter; with delegation on, the main agent must never see the raw
diff and should spend fewer tokens of its own.
"""

import re
from dataclasses import replace
from pathlib import Path

import pytest

from agentic_harness.api import Off, create_harness
from agentic_harness.config import load_settings
from agentic_harness.events import Event
from agentic_harness.limits import Limits
from agentic_harness.loop import RunResult
from agentic_harness.model import GeminiModel
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
MATERIAL = ("2.1", "3.2", "4.1", "6.1", "9.2")
TASK = "What did ShopCo change in CT-2207, and what can I agree to?"
pytestmark = pytest.mark.live


async def run(tmp_path: Path, **kwargs: object) -> tuple[RunResult, list[Event]]:
    settings = load_settings()
    events: list[Event] = []
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_steps=12, max_seconds=180),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=tmp_path,
        secrets=[settings.require_key()],
        model_factory=lambda name: GeminiModel(replace(settings, model=name)),
        **kwargs,  # type: ignore[arg-type]
    )
    harness.subscribe(events.append)
    return await harness.run(TASK), events


def missing_clauses(answer: str) -> list[str]:
    return [c for c in MATERIAL if not re.search(rf"(?<![\d.]){re.escape(c)}(?!\d)", answer)]


def parent_tokens(events: list[Event]) -> int:
    total = 0
    for e in events:
        if e.type == "model_replied" and not e.data.get("agent_id"):
            u = e.data["usage"]
            total += u.get("total_input_tokens", 0) + u.get("total_output_tokens", 0)
            total += u.get("total_thought_tokens", 0)
    return total


async def test_s04_ac10_same_findings_fewer_parent_tokens(tmp_path: Path) -> None:
    on, on_events = await run(tmp_path)
    off, off_events = await run(tmp_path, off=Off(subagents=("clause-reviewer",)))

    for result in (on, off):
        assert result.outcome == "completed", result.reason
        assert missing_clauses(result.answer) == [], result.answer

    # AC2: the helper started from an empty history: one message, the brief.
    child_calls = [e for e in on_events if e.type == "model_called" and e.data.get("agent_id")]
    assert child_calls, "the main agent did not delegate"
    assert child_calls[0].data["history"] == 1
    # AC7: the raw diff never reached the main agent's history.
    parent_tools = [s.get("name") for s in on.steps if s.get("type") == "function_result"]
    assert "review_contract" not in parent_tools
    assert "delegate_task" in parent_tools
    # AC6: the helper's result fits its word limit (+ the cut note at most).
    [result] = [s for s in on.steps if s.get("name") == "delegate_task"]
    assert len(result["result"][0]["text"].split()) <= 200 + 5
    # AC13: the run records what was off.
    started = next(e for e in off_events if e.type == "run_started")
    assert started.data["off"]["subagents"] == ["clause-reviewer"]
    # AC10: the main agent's own tokens are lower with a helper doing the reading.
    print(f"parent tokens: on={parent_tokens(on_events)} off={parent_tokens(off_events)}")
    assert parent_tokens(on_events) < parent_tokens(off_events)
