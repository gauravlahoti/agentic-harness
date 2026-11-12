"""CloudCo's text checks on real answers from live runs (S11-AC8, AC14; D-130).

The answers in ``tests/fixtures/answers/`` are copied from today's traces (Claude Sonnet and
Haiku, 2026-11-12). Each verdict below was decided by reading the answer against CloudCo's
approval chart, not by running the check. Two false failures in a row (a paragraph read as one
claim, then a list item cut into sentences) are why this exists: a change that flips any
verdict here fails the test.
"""

from pathlib import Path

import pytest

from agentic_harness.verify import Record
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2]
ANSWERS = ROOT / "tests" / "fixtures" / "answers"
CHECKS = {c.name: c for c in Workspace.load(ROOT / "workspaces" / "cloudco").checks}

# answer → (Right Approver passes?, Answer Format passes?)
EXPECTED = {
    # Its counter-offer gives 99.95% uptime only the CFO; 99.95% needs Engineering. One
    # paragraph per clause, no list (written before answer-style.md existed).
    "sonnet-094743-draft": (False, False),
    # Every decider right; has a list (the counter-offer terms).
    "sonnet-094743-final": (True, True),
    # Every decider right; all paragraphs.
    "haiku-100604-draft": (True, False),
    "haiku-100604-final": (True, False),
    # "Clause 3.2 raises the discount… That needs the CFO.": right, across two sentences.
    "haiku-101534-draft": (True, False),
    # Your run: one list item per clause, all right; B.7 makes no decision, so needs no source.
    "haiku-101534-final": (True, True),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_s11_ac8_ac14_checks_agree_with_a_person_on_real_answers(name: str) -> None:
    text = (ANSWERS / f"{name}.md").read_text()
    approver, form = EXPECTED[name]
    got = CHECKS["right_approver"].fn(text, Record())
    assert got is not None
    assert got.ok is approver, f"Right Approver on {name}: {got.message}"
    got = CHECKS["answer_format"].fn(text, Record())
    assert got is not None
    assert got.ok is form, f"Answer Format on {name}: {got.message}"


def test_s11_ac8_the_real_catch_names_the_missing_approver() -> None:
    text = (ANSWERS / "sonnet-094743-draft.md").read_text()
    got = CHECKS["right_approver"].fn(text, Record())
    assert got is not None
    assert "99.95% uptime needs Engineering" in got.message
