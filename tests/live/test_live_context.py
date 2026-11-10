"""CloudCo context on real Gemini (S02-AC8, S02-AC11). Runs only with ``make live``.

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

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
pytestmark = pytest.mark.live


async def test_s02_ac11_answer_follows_cloudco_format(tmp_path: Path) -> None:
    settings = load_settings()
    events: list[Event] = []
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_seconds=120),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=tmp_path,
        secrets=[settings.require_key()],
    )
    harness.subscribe(events.append)
    result = await harness.run("ShopCo wants 25% off and unlimited liability. Can we agree?")

    assert result.outcome == "completed", result.reason
    for heading in ("Summary", "Needs a human decision", "Sources"):
        assert heading in result.answer
    assert "CFO" in result.answer  # 25% sits in the CFO's band (standard-terms §2)
    # S02-AC8: every call carried the same prompt.
    prompt_ids = {e.data["prompt_id"] for e in events if e.type == "model_called"}
    assert prompt_ids == {harness.prompt_id}
