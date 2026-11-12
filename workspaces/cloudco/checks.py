"""CloudCo's answer checks: run by the harness's VERIFY step before you see an answer (S11-AC8).

Not part of the harness: ``workspace.toml`` names this file under ``[verify]``; the harness
runs whatever ``CHECKS`` lists and knows none of these words. Each check is plain code
(D-126): free, exact, the same every time. It returns passed, failed (with a reason the
agent can act on) or None when there is nothing to check.

- Every Change Covered  each contract change that matters gets a line in the answer
- Citations Exist       every policy section the answer cites came back from a tool
- Right Approver        the decider named for a term matches CloudCo's approval tables
- No False "Sent"       says sent only if a send worked, and says so when one did

All of CloudCo is made up.
"""

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from agentic_harness.verify import Record, Verdict, check, failed, passed

HERE = Path(__file__).resolve().parent
NUMBER = re.compile(r"\d+(?:\.\d+)?")


# ── Every Change Covered ─────────────────────────────────────────────────────────────────


def _edits(record: Record) -> list[dict[str, str]]:
    """Every edit review_contract returned (the agent's or its helper's), by clause."""
    found: dict[str, dict[str, str]] = {}
    for output in record.outputs("review_contract"):
        try:
            data = json.loads(output)
        except ValueError:
            continue
        for edit in data.get("edits", []) if isinstance(data, dict) else []:
            found.setdefault(str(edit.get("clause")), edit)
    return list(found.values())


def matters(edit: dict[str, str]) -> bool:
    """A change that matters: its numbers change, or a sentence is added or removed.
    "thirty (30)" → "30" and "shall" → "will" are wording only."""
    removed, added = edit.get("removed", ""), edit.get("added", "")
    if not removed.strip() or not added.strip():
        return True
    return sorted(NUMBER.findall(removed)) != sorted(NUMBER.findall(added))


def mentions(answer: str, clause: str) -> bool:
    """ "2.1" in the answer, but not inside "12.1", "2.11" or "99.95"."""
    return re.search(rf"(?<![\w.]){re.escape(clause)}(?![\w]|\.\d)", answer) is not None


@check("Every Change Covered", "Each contract change that matters has a line in the answer")
def every_change_covered(answer: str, record: Record) -> Verdict | None:
    changes = [e for e in _edits(record) if matters(e)]
    if not changes:
        return None  # no contract was reviewed in this run
    missing = [e for e in changes if not mentions(answer, e["clause"])]
    if not missing:
        return passed(f"All {len(changes)} changes that matter are in the answer.")
    named = ", ".join(f"{e['clause']} ({e.get('title', '')})" for e in missing)
    return failed(f"These changes have no line in the answer: {named}.")


# ── Citations Exist ──────────────────────────────────────────────────────────────────────

CITED = re.compile(r"(standard-terms|approval-chart)\s*§\s*(\d+)")
RETURNED = re.compile(r'"policy":\s*"([a-z-]+)",\s*"section":\s*"§(\d+)"')


@check("Citations Exist", "Every policy section the answer cites came back from a tool")
def citations_exist(answer: str, record: Record) -> Verdict | None:
    cited = {(p, n) for p, n in CITED.findall(answer)}
    if not cited:
        return None
    seen: set[tuple[str, str]] = set()
    for call in record.calls:
        if not call.is_error:  # search_policy's JSON, the skill's table, a helper's lines
            seen |= set(RETURNED.findall(call.output)) | set(CITED.findall(call.output))
    unsupported = sorted(cited - seen)
    if not unsupported:
        return passed(f"All {len(cited)} cited sections were read this run.")
    names = ", ".join(f"{p} §{n}" for p, n in unsupported)
    return failed(f"Cited but never read this run: {names}. Look them up or drop them.")


# ── Right Approver ───────────────────────────────────────────────────────────────────────


def _tables() -> dict[str, Any]:
    """The same tables the gate uses: one source of truth for who decides."""
    with (HERE / "workspace.toml").open("rb") as file:
        return tomllib.load(file)


NEVER_WORDS = re.compile(r"\b(never|not allowed|can't|cannot|can not|refuse|decline|no)\b", re.I)


def _terms(line: str) -> list[tuple[str, float | bool]]:
    """The terms a line talks about, as send_to_customer arguments."""
    low = line.lower()
    terms: list[tuple[str, float | bool]] = []
    percents = [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)\s*%", line)]
    discount, uptime = "discount" in low or "% off" in low, "uptime" in low
    if discount != uptime:  # both on one line: too ambiguous to check
        arg = "discount_pct" if discount else "uptime_pct"
        terms += [(arg, p) for p in percents]
    terms += [("payment_days", float(n)) for n in re.findall(r"\bnet\s*(\d+)", low)]
    if "liabilit" in low:
        terms += [
            ("liability_cap_months", float(n)) for n in re.findall(r"(\d+)[\s-]*months?", low)
        ]
        if "unlimited" in low:
            terms.append(("unlimited_liability", True))
    return terms


def _crosses(rule: dict[str, Any], arg: str, value: float | bool) -> bool:
    if rule.get("arg") != arg:
        return False
    if "above" in rule:
        return not isinstance(value, bool) and value > float(rule["above"])
    return bool(value == rule.get("equals"))


@check("Right Approver", "Each term's decider matches CloudCo's approval chart")
def right_approver(answer: str, record: Record) -> Verdict | None:
    tables = _tables()
    approvals, rules = tables.get("approvals", []), tables.get("rules", [])
    roles = {a["approver"] for a in approvals}
    problems, checked = [], 0
    for line in (x.strip() for x in answer.splitlines()):
        terms = _terms(line)
        if not terms:
            continue
        checked += 1
        never = any(_crosses(r, arg, v) for r in rules for arg, v in terms)
        deciders = {a["approver"] for a in approvals for arg, v in terms if _crosses(a, arg, v)}
        named = {r for r in roles if re.search(rf"\b{re.escape(r)}\b", line)}
        short = line[:80]
        if never and not NEVER_WORDS.search(line):
            problems.append(f'"{short}": this term is never allowed; say so')
        elif not never and deciders and not named & deciders:
            problems.append(
                f'"{short}": needs {" and ".join(sorted(deciders))} (approval-chart §1)'
            )
        if wrong := named - deciders - {"Sales"}:  # Sales approves every send (§3)
            problems.append(
                f'"{short}": {", ".join(sorted(wrong))} does not decide this; '
                f"{' and '.join(sorted(deciders)) or 'Sales'} does"
            )
    if not checked:
        return None
    if problems:
        return failed("; ".join(problems) + ".")
    return passed(f"The deciders on {checked} line{'s' if checked > 1 else ''} match the chart.")


# ── No False "Sent" ──────────────────────────────────────────────────────────────────────

SAYS_SENT = re.compile(
    r"\b(?:has|have|was|were|is|it's)\s+(?:now\s+|been\s+)*(?:sent|emailed|delivered)\b"
    r"|\bI(?:'ve| have)?\s+sent\b",
    re.I,
)
NOT_SENT = re.compile(
    r"\b(?:not|n't|never)\s+(?:yet\s+|been\s+)*(?:sent|emailed|delivered)\b", re.I
)


@check('No False "Sent"', "Says sent only if a send worked this run, and says so when one did")
def no_false_sent(answer: str, record: Record) -> Verdict | None:
    sends = [c for c in record.calls if c.name == "send_to_customer"]
    worked = [c for c in sends if not c.is_error and '"status": "sent"' in c.output]
    claims = SAYS_SENT.search(answer) is not None and not NOT_SENT.search(answer)
    if not sends and not claims:
        return None
    if claims and not worked:
        return failed("The answer says it was sent, but no send worked this run.")
    if worked and not claims:
        who = json.loads(worked[-1].output).get("approved_by", [])
        return failed(
            "The message was sent"
            + (f" (approved by {', '.join(who)})" if who else "")
            + ": tell the person it was sent and who approved it."
        )
    return passed("What the answer says about sending matches what happened.")


CHECKS = [every_change_covered, citations_exist, right_approver, no_false_sent]
