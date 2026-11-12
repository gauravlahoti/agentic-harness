"""CloudCo's text checks on real answers from live runs (S11-AC8, AC14; D-130).

The answers in ``tests/fixtures/answers/`` are copied from the 2026-11-12 traces (Claude
Sonnet and Haiku). Each verdict below was decided by reading the answer against CloudCo's
approval chart, not by running the check. The checks failed correct answers again and again
(a paragraph read as one claim, a list item cut into sentences, "wrong person named" on a
sentence without the term's number, a customer email asked for sources, "Nothing has been
sent" read as "sent"): a change that flips any verdict here fails the test.
"""

import json
from pathlib import Path

import pytest

from agentic_harness.verify import Call, Record
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2]
ANSWERS = ROOT / "tests" / "fixtures" / "answers"
CHECKS = {c.name: c for c in Workspace.load(ROOT / "workspaces" / "cloudco").checks}

# A run that reviewed a contract (Answer Format, which needed it, became the online Style &
# Format metric, D-150: its human verdicts are dropped here).
REVIEWED = Record((Call("review_contract", {}, json.dumps({"edits": []}), False),))

# answer → (reviewed in that run?, and passes: Right Approver, No False "Sent")
EXPECTED = {
    # Its counter-offer gives 99.95% uptime only the CFO; 99.95% needs Engineering.
    "sonnet-094743-draft": (True, False, True),
    "sonnet-094743-final": (True, True, True),
    # Every decider right.
    "haiku-100604-draft": (True, True, True),
    "haiku-100604-final": (True, True, True),
    # "Clause 3.2 raises the discount… That needs the CFO.": right, across two sentences.
    "haiku-101534-draft": (True, True, True),
    # One list item per clause, all right.
    "haiku-101534-final": (True, True, True),
    # "Term 2.1 …", "Discount 3.2 …": each sentence starts a claim; all right.
    "haiku-103134-draft": (True, True, True),
    "haiku-103134-final": (True, True, True),
    # A follow-up ("send it asap"). Its plan: "with the 99.95% uptime and 24-month cap… held
    # for the CFO and Finance": Engineering, who approves 99.95%, is missing.
    "haiku-103432-draft": (False, False, True),
    "haiku-103432-final": (False, True, True),
    # "I can't give approvals": who decides each, all right.
    "haiku-103508-draft": (False, True, True),
    "haiku-103508-final": (False, True, True),
    # A customer email draft ([PENDING: CFO approval]) and "Nothing has been sent".
    "haiku-103528-draft": (False, True, True),
    "haiku-103528-final": (False, True, True),
}


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_s11_ac8_ac14_checks_agree_with_a_person_on_real_answers(name: str) -> None:
    text = (ANSWERS / f"{name}.md").read_text()
    reviewed, *verdicts = EXPECTED[name]
    record = REVIEWED if reviewed else Record()
    for check, expected in zip(("right_approver", "no_false_sent"), verdicts, strict=True):
        got = CHECKS[check].fn(text, record)
        assert got is not None
        assert got.ok is expected, f"{CHECKS[check].label} on {name}: {got.message}"


@pytest.mark.parametrize("name", ["sonnet-094743-draft", "haiku-103432-draft"])
def test_s11_ac8_the_real_catches_name_the_missing_approver(name: str) -> None:
    text = (ANSWERS / f"{name}.md").read_text()
    got = CHECKS["right_approver"].fn(text, Record())
    assert got is not None
    assert "99.95% uptime needs Engineering" in got.message
