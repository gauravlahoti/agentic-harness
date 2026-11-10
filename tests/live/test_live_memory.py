"""Memory on real Gemini (S07-AC10, S07-AC11). Runs only with ``make live``.

Round 2 starts from round 1's saved steps, exactly as the server does it, and must recall
what round 1 decided. A topic title must be short and non-empty.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from agentic_harness.api import create_harness
from agentic_harness.config import load_settings
from agentic_harness.limits import Limits
from agentic_harness.memory import SessionStore, make_title
from agentic_harness.model import GeminiModel
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
pytestmark = pytest.mark.live


def harness(tmp_path: Path):  # type: ignore[no-untyped-def]
    settings = load_settings()
    return create_harness(
        GeminiModel(settings),
        Limits(max_steps=10, max_seconds=180),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=tmp_path / "traces",
        secrets=[settings.require_key()],
        model_factory=lambda name: GeminiModel(replace(settings, model=name)),
        delegation=False,
        memory_dir=tmp_path / "memory",
    )


async def test_s07_ac10_round_two_recalls_round_one(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "memory", "cloudco")
    session = store.create("sales")
    first = await harness(tmp_path).run(
        "ShopCo asks for a 20% discount. Who has to approve that? One sentence.",
        record=lambda steps: store.append_steps(session.id, "sales", steps),
    )
    assert first.outcome == "completed", first.reason
    saved = store.load(session.id, "sales").steps
    second = await harness(tmp_path).run(
        "Which role did you just say decides that? Answer in one word, no tools.",
        history=saved,
    )
    assert second.outcome == "completed", second.reason
    assert "CFO" in second.answer, second.answer


async def test_s07_ac11_a_real_model_titles_a_conversation(tmp_path: Path) -> None:
    settings = load_settings()
    title = await make_title(
        GeminiModel(replace(settings, model="gemini-3.5-flash-lite")),
        "What did ShopCo change in contract CT-2207, and what can I agree to?",
    )
    assert 3 <= len(title) <= 48
    assert "\n" not in title
    assert not title.endswith(".")


async def test_s07_ac4_a_preference_is_kept_and_used_next_time(tmp_path: Path) -> None:
    """Found live: "I like all my responses in bullets" must be saved, then followed."""
    first = await harness(tmp_path).run("I like all my responses in bullets.")
    assert first.outcome == "completed", first.reason
    notes = (tmp_path / "memory" / "notes" / "cloudco" / "sales.md").read_text()
    assert "bullet" in notes.lower(), notes
    second = await harness(tmp_path).run("Who approves a 20% discount, and why?")
    assert second.outcome == "completed", second.reason
    assert any(line.lstrip().startswith(("-", "*", "•")) for line in second.answer.splitlines())
