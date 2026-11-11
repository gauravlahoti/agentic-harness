"""What an eval will do and roughly cost, before it starts (S10-AC10).

Part of the evals. The Run dialog shows this so nothing is spent by surprise: how many agent
runs, about how many judge calls, which models, and the cap. It imports no DeepEval and
calls no model, so it answers in a moment.

Does not: run or score anything.
"""

from collections.abc import Sequence
from typing import Any

from agentic_harness.config import CLAUDE_PREFIX, CLAUDE_SMALL_MODEL
from agentic_harness.pricing import Prices
from evals.cases import Case

JUDGE_MODEL = "gemini-3.5-flash-lite"  # free tier, the most quota (D-111)
FALLBACK_JUDGE = CLAUDE_SMALL_MODEL  # only with a Claude key; the person pays (D-104)
FALLBACK_AGENT = CLAUDE_SMALL_MODEL  # the agent, when Gemini runs out mid-eval (D-116)
DEFAULT_CAP_USD = 0.50  # an eval's own money limit, agent + judge (S10-AC6)
RUNS = (1, 3)  # 1 while building; 3 for pass^3 (D-112)
# Cautious tokens for the cost estimate. Agent turn: above the 90th percentile of 115 saved
# runs (about 10k in, 1k out). Judge call: DeepEval's prompt plus the trace (outputs capped).
AGENT_TURN_TOKENS = (15_000, 1_500)
JUDGE_CALL_TOKENS = (3_000, 400)

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


def cost_range(
    est: dict[str, Any], model: str, fallback: str | None, prices: Prices
) -> dict[str, float]:
    """What the person pays, at least and at most (USD).

    Gemini's free tier bills nothing, so a Gemini eval costs $0 while the quota lasts. At
    most, the fallback (Claude Haiku) does every agent turn and every judge call (D-116).
    """

    def each(name: str, tokens: tuple[int, int]) -> float:
        usage = {"total_input_tokens": tokens[0], "total_output_tokens": tokens[1]}
        return prices.cost(name, usage)

    def agent(name: str) -> float:
        return float(est["agent_runs"]) * each(name, AGENT_TURN_TOKENS)

    low = agent(model) if model.startswith(CLAUDE_PREFIX) else 0.0  # a Claude agent always pays
    high = low
    if fallback:
        high = (low or agent(fallback)) + est["judge_calls"] * each(fallback, JUDGE_CALL_TOKENS)
    return {"low": round(low, 4), "high": round(high, 4)}


def estimate(cases: Sequence[Case], runs: int) -> dict[str, Any]:
    return {
        "agent_runs": runs * sum(len(c.turns) for c in cases),
        "judge_calls": runs * sum(judge_calls(c) for c in cases),
    }
