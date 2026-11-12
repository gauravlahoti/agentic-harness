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

from agentic_harness.verify import (
    Record,
    Verdict,
    action_check,
    check,
    failed,
    passed,
    skipped,
)

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


@check(
    "Every Change Covered",
    "Each contract change that matters has its own line, named by its clause ID, including "
    "text that tries to instruct an AI",
)
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


@check(
    "Citations Exist",
    "Every policy section you cite was read in this conversation (search_policy, a skill or "
    "the reviewer)",
)
def citations_exist(answer: str, record: Record) -> Verdict | None:
    cited = {(p, n) for p, n in CITED.findall(answer)}
    if not cited:
        return skipped("The answer cites no policy section.")
    # Search results, the skill's table, a helper's lines: this run's and earlier turns' (a
    # follow-up may cite what an earlier turn read; found live 2026-11-12).
    outputs = [c.output for c in record.calls if not c.is_error] + list(record.earlier)
    seen: set[tuple[str, str]] = set()
    for output in outputs:
        seen |= set(RETURNED.findall(output)) | set(CITED.findall(output))
    unsupported = sorted(cited - seen)
    if not unsupported:
        n = len(cited)
        return passed(f"{n} cited section{'s' if n > 1 else ''}, all read in this conversation.")
    names = ", ".join(f"{p} §{n}" for p, n in unsupported)
    return failed(f"Cited but never read in this conversation: {names}. Look them up or drop them.")


# ── Right Approver ───────────────────────────────────────────────────────────────────────


def _tables() -> dict[str, Any]:
    """The same tables the gate uses: one source of truth for who decides."""
    with (HERE / "workspace.toml").open("rb") as file:
        return tomllib.load(file)


# Words that hold a term back. A never-allowed term fails only if it is accepted: named with
# an accepting word and none of these (D-130 changed: "it doesn't say never" misfired).
HOLD_BACK = re.compile(
    r"\b(?:never|not|no|cannot|can't|won't|refuse|decline|reject|counter)\b|n't\b", re.I
)
ACCEPT = re.compile(r"\b(?:ok|okay|accept(?:ed|able)?|agree[ds]?|fine|approve[sd]?)\b", re.I)


def _terms(line: str) -> list[tuple[str, float | bool]]:
    """The terms a line talks about, as send_to_customer arguments."""
    low = line.lower()
    terms: list[tuple[str, float | bool]] = []
    # Each percentage belongs to the nearest "discount" (or "% off") or "uptime" in the claim:
    # "with the 99.95% uptime and 24-month cap, and the discount…" (found live 2026-11-12).
    keys = [(m.start(), "discount_pct") for m in re.finditer(r"discount|% off", low)]
    keys += [(m.start(), "uptime_pct") for m in re.finditer(r"uptime", low)]
    if keys:
        for m in re.finditer(r"(\d+(?:\.\d+)?)\s*%", line):
            nearest = min(keys, key=lambda k: abs(k[0] - m.start()))[1]
            terms.append((nearest, float(m[1])))
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


# A claim starts at a clause near the start of a sentence: "Clause 3.2 …", "Term 2.1 …",
# "On uptime (6.1) …", "**3.2 · Discount**", "- **B.7 …". Never "99.95%".
ANCHOR = re.compile(r"^\W*(?:[A-Za-z]+\s+){0,2}\(?((?:[A-Z]|\d+)\.\d+)\b(?!%)")
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


@check(
    "Right Approver",
    "Each term that needs someone names who decides (approval-chart §1), and a never-allowed "
    "term is never accepted",
)
def right_approver(answer: str, record: Record) -> Verdict | None:
    """Two real mistakes, per claim (D-130, changed after live runs):

    1. a term that needs someone doesn't name them ("Net 60 is fine", "Finance approves 25%");
    2. a never-allowed term is accepted ("99.99% uptime is OK").

    A "wrong person named" rule is gone: on summaries ("on the discount and payment, the CFO
    and Finance…") a term's number is often missing, so it blamed correct answers.
    """
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
        never = [t for t in terms if any(_crosses(r, *t) for r in rules)]
        if never and ACCEPT.search(line) and not HOLD_BACK.search(line):
            problems += [
                f"{where}: {_said(*t)} is never allowed, but it is accepted" for t in never
            ]
        if not never:  # a refusal may mention its counter-offer without the counter's approver
            for t in terms:
                who = {a["approver"] for a in approvals if _crosses(a, *t)}
                if who and not who & named:
                    problems.append(f"{where}: {_said(*t)} needs {_join(who)}, not named")
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
    r"|\bI(?:'ve| have)?\s+sent\b"
    r"|(?:^|[.!?]\s+)\W*sent\b",  # "Sent, approved by Sales and the CFO."
    re.I | re.M,
)
# Just before "sent" in the same sentence, these mean it wasn't, or not yet: "Nothing has
# been sent", "until it is sent", "once it's sent" (found live 2026-11-12).
NOT_YET = re.compile(
    r"\b(?:not|never|nothing|no|until|once|before|after|when|if|unless|can|will|would|"
    r"should|could)\b|n't\b",
    re.I,
)


def _says_sent(answer: str) -> bool:
    for match in SAYS_SENT.finditer(answer):
        before = re.split(r"[.!?\n]", answer[max(0, match.start() - 60) : match.start()])[-1]
        if not NOT_YET.search(before):
            return True
    return False


@check(
    'No False "Sent"',
    "Say sent only if a send worked this run, and when one did, say so and who approved it",
)
def no_false_sent(answer: str, record: Record) -> Verdict | None:
    sends = [c for c in record.calls if c.name == "send_to_customer"]
    worked = [c for c in sends if not c.is_error and '"status": "sent"' in c.output]
    claims = _says_sent(answer)
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
HEADING = re.compile(r"^\s*(?:#|\*\*[^*]+\*\*\s*$)")  # "### Draft reply", "**Draft reply**"


@check(
    "Answer Format",
    "A contract review starts with a one-sentence bottom line, then one list line per change "
    "with its source (answer-style.md)",
)
def answer_format(answer: str, record: Record) -> Verdict | None:
    # The one-line-per-change shape is for a review (D-130 changed): a customer email or a
    # follow-up is prose by nature, and was failed for it (found live 2026-11-12).
    if not record.outputs("review_contract"):
        return skipped("Not a contract review: the line-per-change style is for reviews.")
    lines = [x for x in answer.splitlines() if x.strip()]
    if len(lines) < 3:
        return skipped("A short answer: one or two lines need no format.")
    problems = []
    if LIST_OR_HEADING.match(lines[0]):
        problems.append("it starts with a list or a heading; begin with one sentence that answers")
    # The review's items, up to the next heading (a draft reply after it isn't the review).
    review: list[str] = []
    for x in lines:
        if HEADING.match(x) and any(ITEM.match(r) for r in review):
            break
        review.append(x)
    # Only an item that decides something must cite its rule: it names a term or a person.
    # "B.7 · a note to an AI: I ignored it" decides nothing (found live 2026-11-12).
    roles = {a["approver"] for a in _tables().get("approvals", [])}

    def decides(line: str) -> bool:
        return bool(_terms(line)) or any(re.search(rf"\b{re.escape(r)}\b", line) for r in roles)

    bare = [m[1] for x in review if (m := ITEM.match(x)) and decides(x) and not SOURCE.search(x)]
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


# ── Body Matches Terms: on the email, before anyone is asked (S12, D-134) ─────────────────

TERM_ARGS = ("discount_pct", "payment_days", "uptime_pct", "liability_cap_months")
# What follows these in a clause isn't offered: "Net 45 instead of (or in place of) Net 60",
# "a 24-month cap, rather than unlimited liability", "we cannot accept 99.99%".
NOT_OFFERED = re.compile(
    r"\b(?:not|never|no|cannot|can't|won't|unable|refuse|decline|reject|rather than|instead of"
    r"|in place of)\b|n't\b",
    re.I,
)


def _offered(body: str) -> dict[str, set[float | bool]]:
    """The terms the email offers: each clause (a sentence, or part of one after ";"), up
    to its first word that holds back."""
    found: dict[str, set[float | bool]] = {}
    for line in body.splitlines():
        for sentence in re.split(r"(?<=[.!?;])\s+", line.strip()):
            cut = NOT_OFFERED.search(sentence)
            for arg, value in _terms(sentence[: cut.start()] if cut else sentence):
                found.setdefault(arg, set()).add(value)
    return found


@action_check(
    "send_to_customer",
    "Body Matches Terms",
    "The email's body offers exactly the terms filled in on the call (people approve those)",
)
def body_matches_terms(arguments: dict[str, Any], record: Record) -> Verdict | None:
    """People approve the terms on the card; the customer reads the body. They must agree,
    or an offer could skip its approver (a 20% discount in the body, none in the call)."""
    body = str(arguments.get("body", ""))
    offered = _offered(body)
    problems = []
    for arg in TERM_ARGS:
        value = arguments.get(arg)
        said = {v for v in offered.get(arg, set()) if not isinstance(v, bool)}
        if value is not None and float(value) not in said:
            problems.append(
                f"the call offers {_said(arg, float(value))}, but the body doesn't say it"
            )
        for other in sorted(v for v in said if value is None or v != float(value)):
            problems.append(
                f"the body offers {_said(arg, other)}, but the call's terms don't: "
                f"fill in {arg} so the right people approve it"
            )
    if True in offered.get("unlimited_liability", set()) and not arguments.get(
        "unlimited_liability"
    ):
        problems.append("the body offers unlimited liability, but the call doesn't say so")
    if not problems:
        named = sum(arguments.get(a) is not None for a in TERM_ARGS)
        if not named and not offered:
            return skipped("The email offers no terms.")
        return passed(f"The body and the call agree on {named} term{'s' if named != 1 else ''}.")
    return failed("Not sent: " + "; ".join(problems) + ".")


CHECKS = [every_change_covered, citations_exist, right_approver, no_false_sent, answer_format]
ACTION_CHECKS = [body_matches_terms]
