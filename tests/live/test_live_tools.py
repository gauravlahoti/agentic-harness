"""CloudCo tools on real Gemini (S03-AC11). Runs only with ``make live``.

Asks the story's question and checks the agent found all 5 changes that matter, each
with its clause ID. Which model: HARNESS_MODEL (Flash-Lite has the most free quota).
"""

import re
from pathlib import Path

import pytest

from agentic_harness.api import create_harness
from agentic_harness.config import load_settings
from agentic_harness.events import Event
from agentic_harness.limits import Limits
from agentic_harness.model import GeminiModel
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
MATERIAL = ("2.1", "3.2", "4.1", "6.1", "9.2")  # term, discount, payment, uptime, liability
pytestmark = pytest.mark.live


async def test_s03_ac11_finds_all_five_changes_with_ids(tmp_path: Path) -> None:
    settings = load_settings()
    events: list[Event] = []
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_steps=12, max_seconds=180),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=tmp_path,
        secrets=[settings.require_key()],
    )
    harness.subscribe(events.append)
    result = await harness.run("What did ShopCo change in CT-2207, and what can I agree to?")

    assert result.outcome == "completed", result.reason
    used = [e.data["name"] for e in events if e.type == "tool_started"]
    assert "compare_to_standard" in used

    def cited(clause: str) -> bool:  # "2.1" as a whole ID, not inside "12.1" or "2.10"
        return re.search(rf"(?<![\d.]){re.escape(clause)}(?!\d)", result.answer) is not None

    missing = [c for c in MATERIAL if not cited(c)]
    assert missing == [], f"clause IDs missing from the answer: {missing}\n\n{result.answer}"
