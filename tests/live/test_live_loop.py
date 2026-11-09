"""A real tool round trip on Gemini (S01-AC14). Runs only with ``make live``: needs a key.

Uses the configured model (HARNESS_MODEL). On the free tier a busy model can return
503 "high demand"; the run then fails with a named reason instead of hanging.
"""

from pathlib import Path

import pytest

from agentic_harness.api import create_harness
from agentic_harness.config import load_settings
from agentic_harness.events import Event
from agentic_harness.limits import Limits
from agentic_harness.model import GeminiModel
from agentic_harness.workspace import Workspace

HELLO = Path(__file__).resolve().parents[2] / "workspaces" / "hello"
pytestmark = pytest.mark.live


async def test_s01_ac14_real_tool_round_trip_keeps_signatures(tmp_path: Path) -> None:
    settings = load_settings()
    key = settings.require_key()
    events: list[Event] = []
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_seconds=90),
        Workspace.load(HELLO),
        trace_dir=tmp_path,
        secrets=[key],
    )
    harness.subscribe(events.append)
    result = await harness.run("What time is it in UTC right now? Use the tool.")

    assert result.outcome == "completed", result.reason
    assert result.model_calls >= 2
    assert any(e.type == "tool_finished" and not e.data["is_error"] for e in events)
    replies = [e for e in events if e.type == "model_replied"]
    assert all(any("signature" in s for s in r.data["steps"]) for r in replies)
    assert key not in (tmp_path / f"{result.run_id}.jsonl").read_text()
