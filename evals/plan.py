"""What an eval will do and roughly cost, before it starts (S10-AC10).

Part of the evals. The Run dialog shows this so nothing is spent by surprise: how many agent
runs, about how many judge calls, which models, and the cap. It imports no DeepEval and
calls no model, so it answers in a moment.

Does not: run or score anything.
"""

from collections.abc import Sequence
from typing import Any

from agentic_harness.config import CLAUDE_SMALL_MODEL
from evals.cases import Case

JUDGE_MODEL = "gemini-3.5-flash-lite"  # free tier, the most quota (D-111)
FALLBACK_JUDGE = CLAUDE_SMALL_MODEL  # only with a Claude key; the person pays (D-104)
DEFAULT_CAP_USD = 0.50  # an eval's own money limit, agent + judge (S10-AC6)
RUNS = (1, 3)  # 1 while building; 3 for pass^3 (D-112)

PER_TURN = ("plan_adherence", "argument_correctness", "task_completion", "step_efficiency")
CONVERSATION = (
    "knowledge_retention",
    "conversation_completeness",
    "role_adherence",
    "topic_adherence",
)


def judge_calls(case: Case) -> int:
    """About how many judge calls one run of this case takes."""
    if case.scope == "out":
        return 0  # refused before the loop: nothing for the judge to read
    turns = len(case.turns)
    calls = turns * len(PER_TURN) * 2  # each metric: about two calls per turn
    calls += 2 + 2 * turns  # turn faithfulness: claims, then a verdict per turn
    if case.multi_turn:
        calls += len(CONVERSATION) * 2
    return calls


def estimate(cases: Sequence[Case], runs: int) -> dict[str, Any]:
    return {
        "agent_runs": runs * sum(len(c.turns) for c in cases),
        "judge_calls": runs * sum(judge_calls(c) for c in cases),
    }
