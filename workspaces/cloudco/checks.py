"""CloudCo's answer checks: run by the harness's VERIFY step before you see an answer (S11-AC8).

Not part of the harness: ``workspace.toml`` names this file under ``[verify]``; the harness
runs whatever ``CHECKS`` lists and knows none of these words. Each check is plain code
(D-126): free, exact, the same every time. It returns passed, failed (with a reason the
agent can act on) or skipped (with why there was nothing to check).

- Every Change Covered  each contract change that matters gets a line in the answer
- Citations Exist       every policy section the answer cites came back from a tool
- Right Approver        the decider named for a term matches CloudCo's approval tables
- No False "Sent"       says sent only if a send worked, and says so when one did
- Answer Format         bottom line first; every item line cites a source (answer-style.md)

All of CloudCo is made up.
"""

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from agentic_harness.verify import Record, Verdict, check, failed, passed, skipped

HERE = Path(__file__).resolve().parent
NUMBER = re.compile(r"\d+(?:\.\d+)?")


# ── Every Change Covered ─────────────────────────────────────────────────────────────────


def _edits(record: Record) -> list[dict[str, str]]:
    """Every edit review_contract returned (the agent's or its helper's), by clause."""
    found: dict[str, dict[str, str]] = {}
    for output in record.outputs("review_contract"):
        # The gate may put a warning line first (an instruction found in the text, D-78):
        # read the JSON from its first brace. Found live, 2026-11-12.
        try:
            data, _ = json.JSONDecoder().raw_decode(output[output.find("{") :])
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
        return skipped("No contract was reviewed in this run.")
    missing = [e for e in changes if not mentions(answer, e["clause"])]
    if not missing:
        n = len(changes)
        return passed(f"{n} change{'s' if n > 1 else ''} that matter, all in the answer.")
    named = ", ".join(f"{e['clause']} ({e.get('title', '')})" for e in missing)
    return failed(f"These changes have no line in the answer: {named}.")


# ── Citations Exist ──────────────────────────────────────────────────────────────────────

CITED = re.compile(r"(standard-terms|approval-chart)\s*§\s*(\d+)")
RETURNED = re.compile(r'"policy":\s*"([a-z-]+)",\s*"section":\s*"§(\d+)"')


@check("Citations Exist", "Every policy section the answer cites came back from a tool")
def citations_exist(answer: str, record: Record) -> Verdict | None:
    cited = {(p, n) for p, n in CITED.findall(answer)}
    if not cited:
        return skipped("The answer cites no policy section.")
    seen: set[tuple[str, str]] = set()
    for call in record.calls:
        if not call.is_error:  # search_policy's JSON, the skill's table, a helper's lines
            seen |= set(RETURNED.findall(call.output)) | set(CITED.findall(call.output))
    unsupported = sorted(cited - seen)
    if not unsupported:
        n = len(cited)
        return passed(f"{n} cited section{'s' if n > 1 else ''}, all read this run.")
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
    # "a 24-month cap" is a liability term too (found live: it was missed without "liability").
    if "liabilit" in low or re.search(r"\bcap\b", low):
        months = re.findall(r"(\d+)[\s-]*months?", low)
        terms += [("liability_cap_months", float(n)) for n in months]
        if "unlimited" in low:
            terms.append(("unlimited_liability", True))
    return terms


def _said(arg: str, value: float | bool) -> str:
    """A term in the answer's own words: "99.95% uptime", "Net 60", "a 25% discount"."""
    number = f"{value:g}" if not isinstance(value, bool) else ""
    return {
        "discount_pct": f"a {number}% discount",
        "payment_days": f"Net {number}",
        "uptime_pct": f"{number}% uptime",
        "liability_cap_months": f"a {number}-month liability cap",
        "unlimited_liability": "unlimited liability",
    }[arg]


def _where(unit: str) -> str:
    """Which claim, briefly: its clause if it starts with one, else its first words."""
    found = ANCHOR.match(unit)
    if found:
        return f"Clause {found[1]}"
    words = re.sub(r"[`*]", "", unit).split()
    return f'"{" ".join(words[:6])}…"'


# A claim starts at a clause: "Clause 3.2 …", "**3.2 · Discount**", "- **B.7 …". Not "99.95%".
ANCHOR = re.compile(r"^\W*(?:clause\s+)?((?:[A-Z]|\d+)\.\d+)\b(?!%)", re.I)
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z*`(])")
LIST_LINE = re.compile(r"^(\s*)(?:[-*•]|\d+[.)])\s")


def _units(answer: str) -> list[str]:
    """The answer cut into claims, each about one clause (D-130, changed twice live):

    - a list item is one claim, with its indented lines (its verdict may be a sentence later:
      "**3.2 · Discount**: 10% → 25%. Needs the CFO.");
    - in prose, a claim runs from a sentence that starts at a clause to the next one
      ("Clause 3.2 raises the discount to 25%. That needs the CFO.").
    Whole paragraphs mixed clauses; single sentences split a claim. Both gave false failures.
    """
    units: list[str] = []
    in_item = False
    for line in answer.splitlines():
        if not line.strip():
            in_item = False  # a blank line ends a list item and a paragraph
            continue
        item = LIST_LINE.match(line)
        if item and not item[1]:  # a top-level list item: a new claim
            units.append(line.strip())
            in_item = True
        elif in_item and line[:1].isspace():  # an indented detail of that item
            units[-1] += " " + line.strip()
        else:  # a paragraph: a new claim, then one more at each sentence that starts a clause
            in_item = False
            for number, sentence in enumerate(SENTENCE.split(line.strip())):
                if number == 0 or ANCHOR.match(sentence):
                    units.append(sentence)
                else:
                    units[-1] += " " + sentence
    return units


def _crosses(rule: dict[str, Any], arg: str, value: float | bool) -> bool:
    if rule.get("arg") != arg:
        return False
    if "above" in rule:
        return not isinstance(value, bool) and value > float(rule["above"])
    return bool(value == rule.get("equals"))


def _join(names: set[str]) -> str:
    return " and ".join(sorted(names))


@check("Right Approver", "Each term's decider matches CloudCo's approval chart")
def right_approver(answer: str, record: Record) -> Verdict | None:
    """Per line: a term that is never allowed must be refused; otherwise each term that
    needs someone must name them; and no one may be named who decides none of the terms.
    Sales is always fine to name: Sales approves every send (approval-chart §3)."""
    tables = _tables()
    approvals, rules = tables.get("approvals", []), tables.get("rules", [])
    roles = {a["approver"] for a in approvals}
    problems, checked = [], 0
    # One claim at a time: a list item, or the sentences about one clause (see _units).
    for line in _units(answer):
        terms = list(dict.fromkeys(_terms(line)))  # once each, in order
        if not terms:
            continue
        checked += 1
        where = _where(line)
        named = {r for r in roles if re.search(rf"\b{re.escape(r)}\b", line)}
        needs = {t: {a["approver"] for a in approvals if _crosses(a, *t)} for t in terms}
        never = [t for t in terms if any(_crosses(r, *t) for r in rules)]
        for t in never:
            if not NEVER_WORDS.search(line):
                problems.append(f"{where}: {_said(*t)} is never allowed, and it doesn't say so")
        if not never:  # a refusal line may mention a counter-offer without its approver
            for t, who in needs.items():
                if who and not who & named:
                    problems.append(f"{where}: {_said(*t)} needs {_join(who)}, not named")
        deciders = set().union(*needs.values())
        if wrong := named - deciders - {"Sales"}:
            what = "; ".join(f"{_said(*t)} → {_join(w)}" for t, w in needs.items() if w)
            problems.append(
                f"{where} names {_join(wrong)}, who decides none of its terms"
                + (f" ({what})" if what else "")
            )
    if not checked:
        return skipped("The answer names no discount, payment, uptime or liability term.")
    if problems:
        return failed(". ".join(problems) + ". See approval-chart §1.")
    return passed(
        f"Who decides matches the chart in all {checked} claim{'s' if checked > 1 else ''}."
    )


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
        return skipped("Nothing was sent, and the answer doesn't say it was.")
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


# ── Answer Format ────────────────────────────────────────────────────────────────────────

LIST_OR_HEADING = re.compile(r"^\s*(?:[-*•]\s|\d+[.)]\s|#)")
# An item line: a top-level list line that starts with a bold ID ("- **3.2 · Discount**").
ITEM = re.compile(
    r"^[-*•]\s+\*\*\s*((?:[A-Z]?\d+|[A-Z])\.\d+|[A-Z]{2,}-\d+)\b(?!%)"
)  # not "99.95%"
# A source in backticks: a policy section, a record ID or a path (answer-style.md rule 3).
SOURCE = re.compile(r"`[^`]*(?:§|[A-Z]{2,}-\d+|\.md)[^`]*`")
VERDICT = re.compile(r"\b(?:ok|never|needs?|approves?|decides?)\b", re.I)


@check("Answer Format", "Bottom line first, and every item line cites a source (answer-style.md)")
def answer_format(answer: str, record: Record) -> Verdict | None:
    lines = [x for x in answer.splitlines() if x.strip()]
    if len(lines) < 3:
        return skipped("A short answer: one or two lines need no format.")
    problems = []
    if LIST_OR_HEADING.match(lines[0]):
        problems.append("it starts with a list or a heading; begin with one sentence that answers")
    # Only an item that decides something must cite its rule: it names a term, a role, or a
    # verdict. "B.7 · a note to an AI: I ignored it" decides nothing (found live 2026-11-12).
    roles = {a["approver"] for a in _tables().get("approvals", [])}

    def decides(line: str) -> bool:
        named = any(re.search(rf"\b{re.escape(r)}\b", line) for r in roles)
        return bool(_terms(line)) or named or VERDICT.search(line) is not None

    bare = [m[1] for x in lines if (m := ITEM.match(x)) and decides(x) and not SOURCE.search(x)]
    # Several clauses in paragraphs instead of one line each (found live 2026-11-12).
    clauses = set(re.findall(r"(?<![\w.])(?:[A-Z]|\d+)\.\d+(?![\d%])", answer))
    if len(clauses) >= 3 and not any(LIST_OR_HEADING.match(x) for x in lines):
        problems.append(
            f"it covers {len(clauses)} clauses in paragraphs; put each on its own list line, "
            "starting with its ID in bold"
        )
    if bare:
        problems.append(f"these item lines have no source in backticks: {', '.join(bare)}")
    if problems:
        return failed("The answer doesn't follow the answer style: " + "; ".join(problems) + ".")
    items = sum(bool(ITEM.match(x)) for x in lines)
    return passed(
        "Bottom line first"
        + (f"; every decision among {items} items cites a source." if items else "; no items.")
    )


CHECKS = [every_change_covered, citations_exist, right_approver, no_false_sent, answer_format]
