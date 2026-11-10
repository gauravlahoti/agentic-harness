"""The scope guard on real Gemini (S05-AC14). Runs only with ``make live``.

Off-topic questions are refused before the loop; real CloudCo questions are not.
"""

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


async def run(task: str, tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = load_settings()
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_steps=8, max_seconds=120),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=tmp_path,
        secrets=[settings.require_key()],
        model_factory=lambda name: GeminiModel(replace(settings, model=name)),
        delegation=False,
    )
    return await harness.run(task)


@pytest.mark.parametrize(
    "task", ["What is the prime minister of India?", "Write me a poem about the sea."]
)
async def test_s05_ac14_off_topic_is_refused_before_the_loop(task: str, tmp_path: Path) -> None:
    result = await run(task, tmp_path)
    assert (result.outcome, result.reason, result.model_calls) == ("stopped", "outside_scope", 0)
    assert "Contract Agent" in result.answer


async def test_s05_ac14_real_questions_still_get_answered(tmp_path: Path) -> None:
    result = await run("Can we promise ShopCo 99.99% uptime?", tmp_path)
    assert result.outcome == "completed", result.reason
