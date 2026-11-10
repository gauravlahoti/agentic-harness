"""Permissions on real Gemini (S05-AC11). Runs only with ``make live``.

The same question as Sales and as Engineering must give two different, correct answers:
Sales sees the deal's value; Engineering is told it is hidden and never learns it.
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
QUESTION = "What is the annual value of ShopCo's current deal? Give the number."
pytestmark = pytest.mark.live


async def ask(profile: str, tmp_path: Path) -> str:
    settings = load_settings()
    harness = create_harness(
        GeminiModel(settings),
        Limits(max_steps=8, max_seconds=120),
        Workspace.load(CLOUDCO),
        profile=profile,
        trace_dir=tmp_path,
        secrets=[settings.require_key()],
        model_factory=lambda name: GeminiModel(replace(settings, model=name)),
        delegation=False,
    )
    result = await harness.run(QUESTION)
    assert result.outcome == "completed", result.reason
    return result.answer


async def test_s05_ac11_two_profiles_two_answers(tmp_path: Path) -> None:
    sales = await ask("sales", tmp_path)
    engineering = await ask("engineering", tmp_path)
    assert "480,000" in sales or "480000" in sales, sales
    assert "480,000" not in engineering
    assert "480000" not in engineering
    told = ("hidden", "not available", "access", "cannot see", "can't see")  # "not for you"
    assert any(word in engineering.lower() for word in told), engineering
