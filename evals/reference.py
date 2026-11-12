"""Reference-based metrics: the run compared with the golden case's known answer (D-161).

Part of the evals. The usual terms (DeepEval's docs and most of the field): a metric is
**reference-based** when it reads ground truth (an expected output, expected tools), and
**reference-free** when it reads only the input and the actual output.
Online evals can only be reference-free: live, nobody knows the right answer. Offline, the
golden set does, so most offline metrics should use it:

- **Step Efficiency** (code): the agent's tool calls, not counting bookkeeping
  (``write_plan``, ``load_skill``), within the case's ``max_steps``.
- **Context Relevancy** (code): the share of its tool calls that the case expects or allows
  (``expected_tools`` + ``allowed_tools``). Offline it's reference-based; online the
  reference-free judge version is used.
- **Answer Correctness**, **Answer Relevancy** and, for a conversation, **Conversation
  Completeness** (one judge call per run): the answers against ``reference_answer`` (or the
  ``expected_outcome`` when a case has none).

Does not: run the agent, or score the reference-free metrics (``evals/scoring.py``).
"""

from collections.abc import Sequence
from typing import Any

from agentic_harness.online_evals import Metric, read_judge
from evals.cases import Case
from evals.checks import Score
from evals.traces import RunView

BOOKKEEPING = ("write_plan", "load_skill")
PASS_AT = 0.7
DEFAULT_ALLOWED = 2  # extra calls a case without max_steps may make beyond its expected tools

ANSWER_CORRECTNESS = Metric(
    "answer_correctness",
    "Answer Correctness",
    "The answer reaches the reference answer's decision",
    "judge",
)
ANSWER_RELEVANCY = Metric(
    "answer_relevancy", "Answer Relevancy", "It covers what the reference covers", "judge"
)
CONVERSATION_COMPLETENESS = Metric(
    "conversation_completeness",
    "Conversation Completeness",
    "The conversation ends where the golden case says it should",
    "judge",
)
ASK = {
    "answer_correctness": "does the final ANSWER reach the same decision as the REFERENCE "
    "(same yes/no, same person who decides, same counter-offer, nothing sent when the "
    "reference says nothing is sent)? Wording, order and length don't matter; a wrong or "
    "missing decision does",
    "answer_relevancy": "does the final ANSWER cover every point the REFERENCE covers, and "
    "nothing off the subject? Extra helpful detail is fine",
    "conversation_completeness": "does the whole CONVERSATION end where the EXPECTED OUTCOME "
    "says it should? A refusal the expected outcome asks for is complete, even if the "
    "person wanted something else",
}
SYSTEM_NOTE = (
    "You compare an AI assistant's answer with a known right answer for a test. Be literal: "
    "judge only against the REFERENCE and EXPECTED OUTCOME given. Reply with only JSON."
)


def _steps(views: Sequence[RunView]) -> list[str]:
    """The main agent's real tool calls (a helper's calls are inside its delegate_task)."""
    return [t.name for v in views for t in v.tools if not t.agent and t.name not in BOOKKEEPING]


def step_efficiency(case: Case, views: Sequence[RunView]) -> Score:
    calls = _steps(views)
    budget = case.max_steps or len(case.expected_tools) + DEFAULT_ALLOWED
    if not any(v.loop_ran for v in views):
        return Score(
            "step_efficiency", None, True, "The agent never started.", status="not_applicable"
        )
    used = len(calls)
    score = 1.0 if used <= budget else budget / used
    names = ", ".join(calls) or "none"
    why = f"{used} tool call{'s' if used != 1 else ''} ({names}); budget {budget}."
    return Score("step_efficiency", score, used <= budget, why)


def context_relevancy(case: Case, views: Sequence[RunView], allowed: Sequence[str]) -> Score:
    fine = {*case.expected_tools, *case.allowed_tools, *allowed}
    calls = [t.name for v in views for t in v.tools if t.name not in BOOKKEEPING]
    if not calls:
        return Score(
            "context_relevancy", None, True, "No tool was called.", status="not_applicable"
        )
    off = [n for n in calls if n not in fine]
    score = 1 - len(off) / len(calls)
    why = f"{len(calls) - len(off)} of {len(calls)} calls fetched what the case expects" + (
        f"; not needed: {', '.join(sorted(set(off)))}." if off else "."
    )
    return Score("context_relevancy", score, score >= PASS_AT, why)


def prompt(case: Case, views: Sequence[RunView], metrics: Sequence[Metric]) -> str:
    asks = "\n".join(f"- {m.name}: {ASK[m.name]}." for m in metrics)
    shape = ", ".join(f'"{m.name}": {{"score": 0.0, "reason": "one sentence"}}' for m in metrics)
    talk = "\n".join(f"PERSON: {v.task}\nASSISTANT: {v.answer or '(no answer)'}" for v in views)
    reference = case.reference_answer or case.expected_outcome
    return "\n\n".join(
        [
            f"Score each from 0 to 1.\n{asks}",
            f"Reply with JSON only, in this shape:\n{{{shape}}}",
            f"CONVERSATION:\n{talk}",
            f"REFERENCE (a right final answer):\n{reference}",
            f"EXPECTED OUTCOME:\n{case.expected_outcome}",
        ]
    )


async def judged(case: Case, views: Sequence[RunView], judge: Any) -> list[Score]:
    """One judge call for the reference-based judged metrics of one run."""
    if not any(v.loop_ran and v.answer for v in views):
        return []
    metrics = [ANSWER_CORRECTNESS, ANSWER_RELEVANCY]
    if case.multi_turn:
        metrics.append(CONVERSATION_COMPLETENESS)
    judge.start()
    try:
        text = await judge.a_generate(SYSTEM_NOTE + "\n\n" + prompt(case, views, metrics))
        found = read_judge(metrics, str(text))
        error = ""
    except Exception as problem:  # Not Scored with the reason, never a failed case (D-118)
        found, error = {}, f"{type(problem).__name__}: {problem}"[:300]
    names, usd = judge.taken()
    scores = []
    for n, m in enumerate(metrics):
        r = found.get(m.name)
        if r is None or r.status == "not_scored":
            why = r.reason if r else f"The judge failed: {error}"
            scores.append(
                Score(
                    m.name,
                    None,
                    True,
                    why,
                    names,
                    usd if n == 0 else 0.0,
                    error,
                    status="not_scored",
                )
            )
        else:
            scores.append(
                Score(
                    m.name, r.score, r.status == "passed", r.reason, names, usd if n == 0 else 0.0
                )
            )
    return scores
