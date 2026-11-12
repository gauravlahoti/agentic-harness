"""Body Matches Terms on the real emails of the S06 to S11 runs (S12-AC2; D-134).

People approve the terms on the card; the customer reads the body. The six emails in
``tests/fixtures/emails/`` are copied from the outbox, and each verdict was decided by
reading the body against its "Offered terms", not by running the check.
"""

import re
from pathlib import Path
from typing import Any

import pytest

from agentic_harness.verify import Record
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2]
EMAILS = ROOT / "tests" / "fixtures" / "emails"
CHECK = {c.name: c for c in Workspace.load(ROOT / "workspaces" / "cloudco").action_checks}[
    "body_matches_terms"
]


def call_of(text: str) -> dict[str, Any]:
    """The send_to_customer arguments that produced this email: its body and offered terms."""
    body = text.split("\n\n", 1)[1].split("\nOffered terms:")[0]
    terms = text.split("Offered terms:")[1].split("\n\n")[0]
    arguments: dict[str, Any] = {"body": body}
    for pattern, arg in (
        (r"Discount: (\d+)%", "discount_pct"),
        (r"Payment: Net (\d+)", "payment_days"),
        (r"Uptime: ([\d.]+)%", "uptime_pct"),
        (r"Liability cap: (\d+) months", "liability_cap_months"),
    ):
        if m := re.search(pattern, terms):
            arguments[arg] = float(m[1])
    return arguments


EXPECTED = {
    "20261110-145208-8fb80f": True,
    # "we are reviewing a liability cap of 24 months": a number the CFO never approved.
    "20261111-000506-f67c30": False,
    # "Net 45 in place of Net 60", "99.95% … rather than 99.99%": only the first is offered.
    "20261112-025715-f48159": True,
    "20261112-030552-c5c48b": True,
    "20261112-105145-dc0739": True,
    "20261112-105910-fdba50": True,
}


@pytest.mark.parametrize("stem", sorted(EXPECTED))
def test_s12_ac2_body_matches_terms_on_real_emails(stem: str) -> None:
    text = (EMAILS / f"{stem}-to-CUS-0042.md").read_text()
    got = CHECK.fn(call_of(text), Record())
    assert got is not None
    assert got.ok is EXPECTED[stem], got.message


def test_s12_ac2_the_real_catch_names_the_unapproved_term() -> None:
    text = (EMAILS / "20261111-000506-f67c30-to-CUS-0042.md").read_text()
    got = CHECK.fn(call_of(text), Record())
    assert got is not None
    assert "a 24-month liability cap, but the call's terms don't" in got.message


def test_s12_ac2_a_body_that_says_another_number_fails() -> None:
    body = "We can offer a 20% discount and Net 45."
    got = CHECK.fn({"body": body, "discount_pct": 15, "payment_days": 45}, Record())
    assert got is not None
    assert not got.ok
    assert "the call offers a 15% discount, but the body doesn't say it" in got.message
    assert "the body offers a 20% discount" in got.message
    # A refusal in the body isn't an offer.
    ok = CHECK.fn(
        {"body": "We can't accept 99.99% uptime; we can offer 99.95% uptime.", "uptime_pct": 99.95},
        Record(),
    )
    assert ok is not None
    assert ok.ok, ok.message
