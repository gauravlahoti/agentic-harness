"""ONLINE EVALS: score every live answer on quality, after the person sees it (D-148, D-149).

Harness part: evaluation. Three layers look at an answer, each with its own job:

    verification (verify.py)   before the answer · blocks · code only · mistakes that harm
    online evals (this file)   after every live answer · never blocks · code + one judge call
    offline evals (evals/)     the golden set, before a change ships · a report

The metrics, the same everywhere a workspace runs:

- Groundedness       each claim is supported by what the tools returned      LLM as Judge
- Hallucination      every ID, %, amount, date and number is in the context  Code
- Context Relevancy  what the agent fetched was relevant to the question     LLM as Judge
- Answer Relevancy   the answer covers every part of what was asked          LLM as Judge
- Style & Format     follows the workspace's style guide                     LLM as Judge
- plus the workspace's own code metrics (``METRICS`` in its checks file), e.g. Citations.

The four judged metrics come back from **one** judge call, in one JSON reply (D-149):
DeepEval's metrics make 3 to 10 calls each, too slow and costly for every answer.

Does not: retry, block, or send anything back to the model (that is verification's job).
A judge that fails or replies badly gives "Not Scored" with the reason; the code metrics
still count. Knows no workspace: its ID pattern and style guide come from workspace.toml.
"""

import asyncio
import contextlib
import json
import re
from collections.abc import Collection, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from agentic_harness.model import ModelClient
from agentic_harness.pricing import Prices
from agentic_harness.verify import Check, Record, run_checks

GradedBy = Literal["code", "judge"]
Status = Literal["passed", "failed", "skipped", "not_scored"]
PASS_AT = 0.7  # a judged score at or above this passes (same as the offline judge metrics)
JUDGE_SECONDS = 60.0  # one judge call; past this the judged metrics are Not Scored
CONTEXT_CHARS = 20_000  # what the judge reads of the tool outputs, at most
OUTPUT_CHARS = 6_000  # of any one tool output
# A record ID: capitals, a dash, digits ("CUS-0042"). A workspace may give its own pattern.
DEFAULT_IDS = r"\b[A-Z]{2,6}-\d{2,}(?:-\d+)*\b"
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
# A number with what's around it: "$12,000", "25%", "Net 60", "99.95". Not inside a word.
NUMBER = re.compile(
    r"(?<![\w.,])([$€£]\s?)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(\s?%| percent)?(?![\w])"
)
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)


@dataclass(frozen=True, slots=True)
class Metric:
    name: str  # the switch's id: "groundedness"
    label: str  # Title Case: "Groundedness"
    description: str  # one sentence: what it checks
    graded_by: GradedBy

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "label": self.label,
            "description": self.description,
            "graded_by": self.graded_by,
        }


GROUNDEDNESS = Metric(
    "groundedness",
    "Groundedness",
    "Each claim in the answer is supported by what the tools returned",
    "judge",
)
HALLUCINATION = Metric(
    "hallucination",
    "Hallucination",
    "Every ID, %, amount, date and number in the answer appears in what the tools returned "
    "or in the question",
    "code",
)
CONTEXT_RELEVANCY = Metric(
    "context_relevancy",
    "Context Relevancy",
    "What the agent fetched was relevant to the question: not off-topic, not far too much",
    "judge",
)
ANSWER_RELEVANCY = Metric(
    "answer_relevancy",
    "Answer Relevancy",
    "The answer addresses every part of what was asked, with the detail asked for",
    "judge",
)
STYLE_FORMAT = Metric(
    "style_format", "Style & Format", "The answer follows the workspace's style guide", "judge"
)
# What the judge is asked, per metric (in the prompt, so one call grades them all).
ASK = {
    "groundedness": "the share of the ANSWER's factual claims that the CONTEXT supports. List "
    'each claim it does not support in "unsupported" (short quotes). No factual claims: 1',
    "context_relevancy": "whether the tools the agent called fetched what the QUESTION needs "
    "(1: every record or document fetched was needed; 0: none was). Tools return whole records, "
    "so unused fields of a needed record don't lower it; the agent's own instructions "
    "(load_skill) and to-do notes (write_plan) don't count either way",
    "answer_relevancy": "whether the ANSWER addresses every part of the QUESTION, with the "
    "detail asked for (1: fully; lower for each part missed or answered only in name)",
    "style_format": "how well the ANSWER follows the STYLE GUIDE (1: fully)",
}


@dataclass(frozen=True, slots=True)
class Score:
    name: str
    label: str
    graded_by: GradedBy
    status: Status  # "skipped": nothing to grade; "not_scored": the judge failed. Neither counts
    score: float | None
    reason: str
    unsupported: tuple[str, ...] = ()  # the claims or facts it could not find

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "graded_by": self.graded_by,
            "status": self.status,
            "score": None if self.score is None else round(self.score, 3),
            "reason": self.reason,
            "unsupported": list(self.unsupported),
        }


@dataclass(frozen=True, slots=True)
class Scored:
    results: list[Score]
    usd: float = 0.0
    judge: str = ""  # the model that judged, "" when no call was made
    error: str = ""


@dataclass(slots=True)
class OnlineEvals:
    """The metrics a workspace switched on, and the model that judges them."""

    judge: ModelClient
    prices: Prices
    ids: str = DEFAULT_IDS  # the workspace's record-ID pattern
    style: str = ""  # the style guide's text; "" means no Style & Format metric
    workspace_metrics: Sequence[Check] = ()  # code metrics from the workspace's checks file
    off: Collection[str] = field(default_factory=tuple)  # metric names switched off

    def metrics(self) -> list[Metric]:
        return listed(self.workspace_metrics, bool(self.style), self.off)

    async def score(self, question: str, answer: str, record: Record, before: str = "") -> Scored:
        """Every switched-on metric for one answer. Never raises for a judge problem."""
        wanted = {m.name for m in self.metrics()}
        found: dict[str, Score] = {}
        if HALLUCINATION.name in wanted:
            found[HALLUCINATION.name] = hallucination(
                answer, context_text(record) + "\n" + question + "\n" + before, self.ids
            )
        checks = [c for c in self.workspace_metrics if c.name in wanted]
        for r in run_checks(checks, answer, record):
            status: Status = "not_scored" if r.status == "error" else r.status
            value = {"passed": 1.0, "failed": 0.0}.get(r.status)
            found[r.name] = Score(r.name, r.label, "code", status, value, r.message)

        judged = [m for m in self.metrics() if m.graded_by == "judge"]
        context = context_blocks(record)
        if not context:  # nothing was fetched: there's nothing to be grounded in
            for m in (GROUNDEDNESS, CONTEXT_RELEVANCY):
                if m.name in wanted:
                    found[m.name] = _skip(m, "No tool was called, so there is no context.")
            needs = (GROUNDEDNESS.name, CONTEXT_RELEVANCY.name)
            judged = [m for m in judged if m.name not in needs]
        usd, judge, error = 0.0, "", ""
        if judged:
            prompt = judge_prompt(judged, question, answer, context, self.style, before)
            steps = [{"type": "user_input", "content": [{"type": "text", "text": prompt}]}]
            judge = self.judge.name
            try:
                async with asyncio.timeout(JUDGE_SECONDS):
                    reply = await self.judge.create(JUDGE_SYSTEM, steps, [])
                usd = self.prices.cost(self.judge.name, reply.usage)
                found |= read_judge(judged, reply.text)
            except Exception as problem:  # busy, timed out, out of quota: Not Scored, said why
                error = f"{type(problem).__name__}: {problem}"[:300]
                for m in judged:
                    found[m.name] = Score(
                        m.name, m.label, "judge", "not_scored", None, f"The judge failed: {error}"
                    )
        order = [m.name for m in self.metrics()]
        return Scored([found[n] for n in order if n in found], usd, judge, error)


def listed(
    workspace_metrics: Sequence[Check], style: bool, off: Collection[str] = ()
) -> list[Metric]:
    """In the order the page shows them: the harness's, the workspace's, style last."""
    own = [Metric(c.name, c.label, c.description, "code") for c in workspace_metrics]
    every = [GROUNDEDNESS, HALLUCINATION, CONTEXT_RELEVANCY, ANSWER_RELEVANCY, *own]
    every += [STYLE_FORMAT] if style else []
    return [m for m in every if m.name not in off]


def _skip(m: Metric, why: str) -> Score:
    return Score(m.name, m.label, m.graded_by, "skipped", None, why)


# ── Hallucination: code ─────────────────────────────────────────────────────────────────


def facts(answer: str, ids: str = DEFAULT_IDS) -> list[tuple[str, str]]:
    """The checkable facts in an answer, as (kind, text): IDs, dates, %, amounts and whole
    numbers of two or more digits. Plain decimals ("3.2") are left out: they are section
    numbers far more often than values. Single digits are left out: counts and list steps."""
    found: list[tuple[str, str]] = []
    rest = answer
    for kind, pattern in (("id", re.compile(ids)), ("date", DATE)):
        for match in pattern.finditer(rest):
            found.append((kind, match[0]))
        rest = pattern.sub(" ", rest)
    for match in NUMBER.finditer(rest):
        money, whole, decimal, percent = match.groups()
        if percent:
            found.append(("percent", whole + (decimal or "")))
        elif money:
            found.append(("amount", whole + (decimal or "")))
        elif not decimal and len(whole.replace(",", "")) >= 2:
            found.append(("number", whole))
    return list(dict.fromkeys(found))


def _value(text: str) -> str:
    """ "12,000" and "12000.0" are the same number."""
    number = text.replace(",", "")
    return number.rstrip("0").rstrip(".") if "." in number else number.lstrip("0") or "0"


def hallucination(answer: str, context: str, ids: str = DEFAULT_IDS) -> Score:
    """Every fact in the answer must appear in the context. A % must appear as a %."""
    m = HALLUCINATION
    found = facts(answer, ids)
    if not found:
        return _skip(m, "No IDs, dates or numbers in the answer to check.")
    numbers, percents = set(), set()
    for match in NUMBER.finditer(DATE.sub(" ", context)):
        _, whole, decimal, percent = match.groups()
        value = _value(whole + (decimal or ""))
        numbers.add(value)
        if percent:
            percents.add(value)
    # IDs' digits count too ("thirty (30) days" is in; "CT-2207" makes 2207 known).
    numbers |= {_value(d) for d in re.findall(r"\d+", context)}
    missing = []
    for kind, text in found:
        if kind in ("id", "date"):
            ok = text in context
        elif kind == "percent":
            # Data often stores a percent as a plain number ("percent": 99.98). A decimal
            # is rarely there by chance; a whole number ("20") still needs its % (D-159).
            ok = _value(text) in percents or ("." in text and _value(text) in numbers)
        else:
            ok = _value(text) in numbers
        if not ok:
            missing.append(text + ("%" if kind == "percent" else ""))
    share = 1 - len(missing) / len(found)
    if missing:
        return Score(
            m.name,
            m.label,
            "code",
            "failed",
            share,
            f"{len(missing)} of {len(found)} facts appear in no tool result: {', '.join(missing)}.",
            tuple(missing),
        )
    why = f"All {len(found)} facts found in tool results."
    return Score(m.name, m.label, "code", "passed", 1.0, why)


# ── The judge: one call, four metrics ───────────────────────────────────────────────────

JUDGE_SYSTEM = (
    "You grade one answer from an AI assistant. Be strict and literal: judge only against "
    "what is given in the message, never your own knowledge. Reply with only JSON."
)


def context_blocks(record: Record) -> list[str]:
    """What the tools returned, this turn and earlier ones, each cut to a fair share."""
    # A failed or refused call counts too: "the CFO rejected the send" is grounded in it
    # (found in the eval of 2026-11-12: dropped, a true answer looked made up; D-154).
    blocks = [
        f"[{c.name}{' · failed' if c.is_error else ''}] {c.output[:OUTPUT_CHARS]}"
        for c in record.calls
    ]
    blocks += [f"[earlier turn] {text[:OUTPUT_CHARS]}" for text in record.earlier]
    return blocks


def context_text(record: Record) -> str:
    return "\n".join(c.output for c in record.calls) + "\n".join(record.earlier)


def judge_prompt(
    metrics: Sequence[Metric],
    question: str,
    answer: str,
    context: Sequence[str],
    style: str = "",
    before: str = "",
) -> str:
    asks = "\n".join(f"- {m.name}: {ASK[m.name]}." for m in metrics)
    shape = ", ".join(
        f'"{m.name}": {{"score": 0.0, "reason": "one sentence"'
        + (', "unsupported": []' if m.name == GROUNDEDNESS.name else "")
        + "}"
        for m in metrics
    )
    text = "\n\n".join(context)
    cut = len(text) > CONTEXT_CHARS
    parts = [
        f"Grade the ANSWER below. Every score is from 0 to 1.\n{asks}",
        f"Reply with JSON only, in this shape:\n{{{shape}}}",
    ]
    if before:
        parts.append(f"EARLIER IN THE CONVERSATION:\n{before}")
    parts.append(f"QUESTION:\n{question}")
    if any(m.name in (GROUNDEDNESS.name, CONTEXT_RELEVANCY.name) for m in metrics):
        note = " (cut short: judge only what is here)" if cut else ""
        parts.append(f"CONTEXT (what the tools returned){note}:\n{text[:CONTEXT_CHARS]}")
    if any(m.name == STYLE_FORMAT.name for m in metrics) and style:
        parts.append(f"STYLE GUIDE:\n{style}")
    parts.append(f"ANSWER:\n{answer}")
    return "\n\n".join(parts)


def salvage(metrics: Sequence[Metric], body: str) -> dict[str, Any] | None:
    """Each metric's object read on its own, when the whole reply isn't valid JSON. Found
    live (Flash-Lite): one object left open, so the next metric sat inside it, and all four
    were lost. One slip should cost one metric at most."""
    data: dict[str, Any] = {}
    for m in metrics:
        match = re.search(rf'"{m.name}"\s*:\s*\{{\s*"score"\s*:\s*([\d.]+)', body)
        if not match:
            continue
        rest = body[match.end() :]
        reason = re.match(r'\s*,\s*"reason"\s*:\s*"((?:[^"\\]|\\.)*)"', rest)
        listed = re.match(r'[^{}]*?"unsupported"\s*:\s*(\[[^\]]*\])', rest)
        row: dict[str, Any] = {"score": float(match[1])}
        if reason:
            row["reason"] = json.loads(f'"{reason[1]}"')
        if listed:
            with contextlib.suppress(ValueError):
                row["unsupported"] = json.loads(listed[1])
        data[m.name] = row
    return data or None


def _find(data: Any, name: str) -> Any:
    """A metric's object, even nested inside another's (a judge slip seen live)."""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get(name), dict):
        return data[name]
    return next((f for v in data.values() if (f := _find(v, name)) is not None), None)


def read_judge(metrics: Sequence[Metric], text: str) -> dict[str, Score]:
    """The judge's JSON → one Score per metric. A missing or broken one is Not Scored."""
    body = FENCE.sub("", text.strip())
    start, end = body.find("{"), body.rfind("}")
    try:
        data = json.loads(body[start : end + 1]) if start != -1 and end > start else None
    except ValueError:
        data = salvage(metrics, body)
    found: dict[str, Score] = {}
    for m in metrics:
        row = _find(data, m.name)
        raw = row.get("score") if isinstance(row, dict) else None
        if not isinstance(row, dict) or not isinstance(raw, int | float) or isinstance(raw, bool):
            why = (
                "The judge gave no score for it."
                if data is not None
                else (f"The judge's reply was not JSON: {text.strip()[:120]!r}")
            )
            found[m.name] = Score(m.name, m.label, "judge", "not_scored", None, why)
            continue
        value = min(1.0, max(0.0, float(raw)))
        unsupported = row.get("unsupported") if m.name == GROUNDEDNESS.name else None
        found[m.name] = Score(
            m.name,
            m.label,
            "judge",
            "passed" if value >= PASS_AT else "failed",
            value,
            str(row.get("reason", "")).strip()[:400],
            tuple(str(u)[:200] for u in unsupported) if isinstance(unsupported, list) else (),
        )
    return found
