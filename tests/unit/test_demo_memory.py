"""The demo's long-term memory facts for CloudCo (S07; your request, 2026-11-12).

The ``.txt`` files in ``workspaces/cloudco/demo-memory/`` (made-up demo facts; a header line would
load as a fact, so they stay ``.txt``) are copied to ``.agentic-harness/notes/cloudco/``
to seed a demo. They must load as notes, fit the budget, and each profile keeps its own.
"""

from pathlib import Path

from agentic_harness.memory import NOTE_MAX_CHARS, list_notes, load_notes

SEED = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco" / "demo-memory"


def test_demo_facts_load_as_notes_within_the_budget() -> None:
    for profile, count in (("sales", 4), ("engineering", 3)):
        file = SEED / f"{profile}.txt"
        lines = list_notes(file)
        assert len(lines) == count
        assert all(len(line) <= NOTE_MAX_CHARS + 20 for line in lines)
        assert load_notes(file) == "\n".join(lines)  # none dropped by the 2000-token cap


def test_each_profile_keeps_its_own_facts() -> None:
    sales = (SEED / "sales.txt").read_text()
    engineering = (SEED / "engineering.txt").read_text()
    assert "Net 45" in sales
    assert "Net 45" not in engineering
    assert "UP-" in engineering
    assert "UP-" not in sales
