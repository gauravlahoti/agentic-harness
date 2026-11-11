"""S10-AC5: the judged metrics run through DeepEval with our judge; 429/503 → Claude Haiku.

No test calls Gemini or Anthropic (S10-AC8): the judge's model is a scripted stand-in, and
the scoring tests use a stand-in judge that fills in whatever schema DeepEval asks for.
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from agentic_harness.model import ModelError
from agentic_harness.pricing import load_prices
from evals.cases import Case
from evals.judge import Judge, JudgeUnavailableError, busy, parse
from evals.plan import estimate, judge_calls
from evals.scoring import code_scores, judged_scores
from evals.traces import read_run
from tests.evals.standins import Scripted, StandInJudge

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "eval_traces"


class Verdict(BaseModel):
    verdict: str
    reason: str


async def test_s10_ac5_judge_parses_json_and_counts_cost() -> None:
    gemini = Scripted("gemini-3.5-flash-lite", ['```json\n{"verdict": "yes", "reason": "ok"}\n```'])
    judge = Judge(gemini, load_prices())
    judge.start()
    out = await judge.a_generate("judge this", schema=Verdict)
    assert out == Verdict(verdict="yes", reason="ok")
    used, usd = judge.taken()
    assert used == ["gemini-3.5-flash-lite"]
    assert usd > 0
    assert judge.usd == usd
    with pytest.raises(ValueError, match="JSON"):
        parse("no json here", Verdict)


async def test_s10_ac5_out_of_quota_switches_to_claude_haiku_for_the_rest() -> None:
    gemini = Scripted("gemini-3.5-flash-lite", [ModelError("Gemini 429: quota exceeded")])
    claude = Scripted("claude-haiku-5-5", ['{"verdict": "no", "reason": "r"}'] * 2)
    judge = Judge(gemini, load_prices(), fallback=lambda: claude)
    judge.start()
    await judge.a_generate("first", schema=Verdict)
    await judge.a_generate("second", schema=Verdict)
    assert judge.current == "claude-haiku-5-5"
    assert "gemini-3.5-flash-lite → claude-haiku-5-5" in judge.switched
    assert gemini.calls == 1
    assert claude.calls == 2
    assert judge.taken()[0] == ["claude-haiku-5-5"]


async def test_s10_ac5_no_fallback_or_other_errors_stop_the_eval() -> None:
    no_key = Judge(
        Scripted("gemini-3.5-flash-lite", [ModelError("Gemini 503: busy")]), load_prices()
    )
    with pytest.raises(JudgeUnavailableError, match="no Claude key"):
        await no_key.a_generate("x")
    bad = Judge(
        Scripted("gemini-3.5-flash-lite", [ModelError("Gemini 400: bad request")]),
        load_prices(),
        fallback=lambda: Scripted("claude-haiku-5-5", ["{}"]),
    )
    with pytest.raises(JudgeUnavailableError, match="400"):
        await bad.a_generate("x")
    assert busy(ModelError("Gemini 429: x"))
    assert not busy(ModelError("Gemini 400: x"))


# ── Scoring with a stand-in judge ───────────────────────────────────────────────────────


def case(**fields: Any) -> Case:
    base: dict[str, Any] = {
        "id": "c",
        "group": "G",
        "profile": "sales",
        "turns": ("t",),
        "expected_outcome": "lists the changes",
    }
    return Case(**{**base, **fields})


async def test_s10_ac5_one_turn_gets_agent_layers_and_faithfulness() -> None:
    view = read_run(FIXTURES / "20261110-235952-d16300.jsonl")
    scores = await judged_scores(
        case(), [view], StandInJudge(), role="Contract Agent", topics=["contracts"]
    )
    names = [s.metric for s in scores]
    assert names == [
        "plan_adherence",
        "argument_correctness",
        "task_completion",
        "step_efficiency",
        "turn_faithfulness",
    ]
    for score in scores:
        assert score.judge == ["stand-in"], score
        assert score.score is not None, score.error


async def test_s10_ac5_conversation_metrics_and_required_words() -> None:
    first = read_run(FIXTURES / "20261111-000506-f67c30.jsonl")
    refused = read_run(FIXTURES / "20261111-010639-4c92e2.jsonl")
    two = case(turns=("a", "b"), must_include=("Priya Raman",))
    scores = {
        s.metric: s
        for s in await judged_scores(
            two, [first, refused], StandInJudge(), role="Contract Agent", topics=["contracts"]
        )
    }
    assert set(scores) >= {
        "knowledge_retention",
        "conversation_completeness",
        "role_adherence",
        "topic_adherence",
        "turn_faithfulness",
    }
    # Only turn 1 ran the loop; the refused turn has no plan or tools to judge.
    assert "Turn 2" not in scores["plan_adherence"].reason
    assert not scores["task_completion"].passed
    assert "leaves out: Priya Raman" in scores["task_completion"].reason
    codes = {s.metric for s in code_scores(two, [first, refused])}
    assert codes == {"tool_correctness", "guardrails_turns"}


def test_s10_ac5_refused_case_needs_no_judge_and_estimates_are_positive() -> None:
    assert judge_calls(case(scope="out")) == 0
    assert judge_calls(case()) > 0
    assert judge_calls(case(turns=("a", "b"))) > judge_calls(case())
    assert estimate([case(), case(turns=("a", "b"))], 3)["agent_runs"] == 9


def test_s10_ac6_cost_to_you_is_a_range_free_tier_to_all_claude() -> None:
    """The cost panel: $0 while Gemini's free tier lasts; at most all-Haiku (D-116, D-117)."""
    from evals.plan import project

    prices = load_prices()
    est = {"agent_runs": 10, "judge_calls": 100}
    flash, lite, haiku_id = "gemini-3.8-flash", "gemini-3.5-flash-lite", "claude-haiku-5-5"
    gemini = project(est, flash, lite, haiku_id, prices)
    assert gemini["low"] == 0.0  # the free tier bills nothing
    # 10 turns x (15k in, 1.5k out) + 100 calls x (3k in, 400 out), at Haiku's price
    haiku = 10 * (15_000 * 0.10 + 1_500 * 0.50) / 1e6 + 100 * (3_000 * 0.10 + 400 * 0.50) / 1e6
    assert gemini["high"] == pytest.approx(haiku, abs=1e-4)
    # each role: what it does, its list price, who pays, its free daily limit
    assert gemini["agent"]["turns"] == 10
    assert gemini["agent"]["paid"] is False
    list_price = 10 * (15_000 * 0.75 + 1_500 * 3.75) / 1e6  # Gemini 3.8 Flash on a paid key
    assert gemini["agent"]["usd_list"] == pytest.approx(list_price, abs=1e-4)
    assert gemini["judge"]["calls"] == 100
    assert gemini["judge"]["free_per_day"] == 500
    assert gemini["fallback"]["model"] == haiku_id
    assert gemini["basis"] == "cautious"
    no_key = project(est, flash, lite, None, prices)
    assert (no_key["low"], no_key["high"], no_key["fallback"]) == (0.0, 0.0, None)
    claude = project(est, haiku_id, lite, haiku_id, prices)
    assert claude["low"] > 0  # a Claude agent is paid from the first turn
    assert claude["agent"]["paid"] is True
    judge = project(est, flash, haiku_id, None, prices)
    assert judge["low"] == judge["high"] > 0  # a Claude judge is paid for every call


def test_s10_ac6_the_projection_learns_from_past_evals(tmp_path: Path) -> None:
    """Once evals have run, their real averages replace the cautious numbers (D-117)."""
    import json

    from evals.plan import measured, project

    assert measured(tmp_path) is None  # nothing run yet
    turn = {"tokens_in": 4_000, "tokens_out": 300, "replies": 3}
    result = {
        "cases": [{"runs": [{"turns": [turn, turn]}]}],
        "judge": {"calls": 10, "tokens_in": 20_000, "tokens_out": 2_000},
    }
    (tmp_path / "20261112-100000-abcdef.json").write_text(json.dumps(result))
    (tmp_path / "20261111-090000-aaaaaa.json").write_text("{}")  # an old result: skipped
    seen = measured(tmp_path)
    assert seen == {"agent": (4_000, 300, 3), "judge": (2_000, 200), "evals": 1}
    plan = project(
        {"agent_runs": 2, "judge_calls": 10},
        "claude-haiku-5-5",
        "claude-haiku-5-5",
        None,
        load_prices(),
        seen,
    )
    assert plan["basis"] == "measured"
    assert plan["from_evals"] == 1
    assert plan["agent"]["calls"] == 6  # 2 turns x 3 replies
    assert plan["low"] == pytest.approx(
        2 * (4_000 * 0.10 + 300 * 0.50) / 1e6 + 10 * (2_000 * 0.10 + 200 * 0.50) / 1e6
    )


async def test_s10_ac6_the_judge_keeps_what_each_model_cost() -> None:
    judge = Judge(
        Scripted("gemini-3.5-flash-lite", [ModelError("Gemini 429: quota"), "{}"]),
        load_prices(),
        fallback=lambda: Scripted("claude-haiku-5-5", ['{"verdict": "yes"}']),
    )
    await judge.a_generate("judge this")
    assert set(judge.by_model) == {"claude-haiku-5-5"}
    assert judge.by_model["claude-haiku-5-5"] == pytest.approx(judge.usd)
