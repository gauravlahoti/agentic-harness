"""What an eval will do and roughly cost, before it starts (S10-AC10).

Part of the evals. The Run dialog shows this so nothing is spent by surprise: how many agent
runs, about how many judge calls, which models, and the cap. It imports no DeepEval and
calls no model, so it answers in a moment.

Does not: run or score anything.
"""

import json
import re
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from agentic_harness.config import CLAUDE_PREFIX, CLAUDE_SMALL_MODEL, EVAL_JUDGE_MODEL
from agentic_harness.pricing import Prices
from evals.cases import Case

JUDGE_MODEL = EVAL_JUDGE_MODEL  # the default; the Run dialog can pick another (D-111)
FALLBACK_JUDGE = CLAUDE_SMALL_MODEL  # only with a Claude key; the person pays (D-104)
FALLBACK_AGENT = CLAUDE_SMALL_MODEL  # the agent, when Gemini runs out mid-eval (D-116)
DEFAULT_CAP_USD = 3.00  # a safety net for a runaway eval; the models you pick set the cost (D-113)
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
    if case.multi_turn:
        calls += len(CONVERSATION) * 2
    return calls


CAUTIOUS_REPLIES_PER_TURN = 4  # model calls per agent turn, for the free-limit meter
SECONDS_PER_TEST = 60  # one test, agent + judging, before any eval has been timed (D-118)
RECENT_EVALS = 5  # how many past evals the projection learns from
DEFAULT_FOLDER = Path(".agentic-harness") / "evals"  # results, when --out isn't given
RESULT_FILE = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")


def measured(folder: Path) -> dict[str, Any] | None:
    """Real averages from your last evals, or None before any has recorded tokens (D-117).

    Agent: tokens in, tokens out and model replies per turn. Judge: tokens per call.
    Results saved before D-117 carry no tokens and are skipped.
    """
    files = sorted((f for f in folder.glob("*.json") if RESULT_FILE.match(f.stem)), reverse=True)
    turns: list[dict[str, Any]] = []
    judged = [0, 0, 0]  # calls, tokens in, tokens out
    used = 0
    timed = [0.0, 0]  # seconds, test runs
    for path in files[:RECENT_EVALS]:
        try:
            result = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        found = [
            t
            for case in result.get("cases", [])
            for run in case.get("runs", [])
            for t in run.get("turns", [])
            if t.get("replies")
        ]
        judge = result.get("judge") or {}
        if not found and not judge.get("calls"):
            continue
        used += 1
        runs = sum(len(case.get("runs", [])) for case in result.get("cases", []))
        if runs and result.get("seconds"):
            timed[0] += float(result["seconds"])
            timed[1] += runs
        turns += found
        judged[0] += int(judge.get("calls") or 0)
        judged[1] += int(judge.get("tokens_in") or 0)
        judged[2] += int(judge.get("tokens_out") or 0)
    if not used:
        return None

    def mean(key: str) -> int:
        return round(sum(int(t[key]) for t in turns) / len(turns))

    return {
        "agent": (mean("tokens_in"), mean("tokens_out"), mean("replies")) if turns else None,
        "judge": (judged[1] // judged[0], judged[2] // judged[0]) if judged[0] else None,
        "seconds_per_test": timed[0] / timed[1] if timed[1] else None,
        "evals": used,
    }


def project(
    est: dict[str, Any],
    model: str,
    judge: str,
    fallback: str | None,
    prices: Prices,
    seen: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """What a run will cost, per role, and what the person pays (D-117).

    Gemini's free tier bills nothing, so a Gemini role costs the person $0 while the quota
    lasts; its list price shows what it would cost on a paid key. A Claude role is paid from
    the first call. At most, the fallback (Claude Haiku) does every Gemini turn and call
    (D-116). Token counts are your last evals' averages, or cautious numbers before any.
    """
    seen = seen or {}
    a_in, a_out, a_replies = seen.get("agent") or (*AGENT_TURN_TOKENS, CAUTIOUS_REPLIES_PER_TURN)
    j_in, j_out = seen.get("judge") or JUDGE_CALL_TOKENS
    turns, calls = int(est["agent_runs"]), int(est["judge_calls"])

    def usd(name: str, n: int, tokens_in: int, tokens_out: int) -> float:
        usage = {"total_input_tokens": tokens_in, "total_output_tokens": tokens_out}
        return n * prices.cost(name, usage)

    def paid(name: str) -> bool:
        return name.startswith(CLAUDE_PREFIX)

    agent_list = usd(model, turns, a_in, a_out)
    judge_list = usd(judge, calls, j_in, j_out)
    low = (agent_list if paid(model) else 0.0) + (judge_list if paid(judge) else 0.0)
    high, backup = low, None
    if fallback:
        backup_agent = 0.0 if paid(model) else usd(fallback, turns, a_in, a_out)
        backup_judge = 0.0 if paid(judge) else usd(fallback, calls, j_in, j_out)
        high = low + backup_agent + backup_judge
        backup = {
            "model": fallback,
            "agent_usd": round(backup_agent, 4),
            "judge_usd": round(backup_judge, 4),
        }
    return {
        "agent": {
            "model": model,
            "turns": turns,
            "calls": turns * a_replies,
            "usd_list": round(agent_list, 4),
            "paid": paid(model),
            "free_per_day": None if paid(model) else prices.free_per_day(model),
        },
        "judge": {
            "model": judge,
            "calls": calls,
            "usd_list": round(judge_list, 4),
            "paid": paid(judge),
            "free_per_day": None if paid(judge) else prices.free_per_day(judge),
        },
        "fallback": backup,
        "low": round(low, 4),
        "high": round(high, 4),
        "basis": "measured" if seen.get("agent") or seen.get("judge") else "cautious",
        "from_evals": int(seen.get("evals") or 0),
        # how long: past evals' seconds per test, else a cautious minute each (D-118)
        "seconds": round(
            int(est.get("test_runs") or 0) * (seen.get("seconds_per_test") or SECONDS_PER_TEST)
        ),
    }


def estimate(cases: Sequence[Case], runs: int) -> dict[str, Any]:
    return {
        "test_runs": runs * len(cases),
        "agent_runs": runs * sum(len(c.turns) for c in cases),
        "judge_calls": runs * sum(judge_calls(c) for c in cases),
    }
