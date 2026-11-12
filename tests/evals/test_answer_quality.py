"""Offline Evals score Answer Quality with the online evals' own results (D-148, D-151).

The harness scores each answer while the agent runs; the eval reads those scores from the
run's trace, so a metric means the same thing on a live answer and on a golden case.
"""

import json
from pathlib import Path

from evals.scoring import ANSWER_QUALITY, catalog, quality_scores
from evals.traces import read_run


def trace(tmp_path: Path, name: str, results: list[dict[str, object]]) -> Path:
    events = [
        {"type": "run_started", "run_id": name, "data": {"task": "q", "model": "m"}},
        {"type": "run_finished", "data": {"answer": "a", "outcome": "completed"}},
        {
            "type": "online_evals_finished",
            "data": {"results": results, "usd": 0.0004, "judge": "gemini-3.5-flash-lite"},
        },
    ]
    path = tmp_path / f"{name}.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events))
    return path


def row(name: str, status: str, score: float | None, graded_by: str = "judge") -> dict[str, object]:
    return {"name": name, "status": status, "score": score, "reason": "r", "graded_by": graded_by}


def test_d151_offline_reads_the_online_scores_from_the_trace(tmp_path: Path) -> None:
    one = read_run(
        trace(
            tmp_path,
            "t1",
            [
                row("groundedness", "passed", 0.9),
                row("hallucination", "failed", 0.5, "code"),
                row("citations", "skipped", None, "code"),
            ],
        )
    )
    two = read_run(trace(tmp_path, "t2", [row("groundedness", "passed", 0.7)]))
    scores = {s.metric: s for s in quality_scores([one, two])}
    assert scores["groundedness"].score == 0.8  # the mean over the two turns
    assert scores["groundedness"].passed
    assert scores["groundedness"].judge == ["gemini-3.5-flash-lite"]
    assert scores["groundedness"].usd == 0.0008  # one judge call per answer, counted once
    assert scores["hallucination"].judge == []  # code: no judge
    assert not scores["hallucination"].passed
    assert scores["citations"].status == "not_applicable"
    assert "answer_relevancy" not in scores  # no turn had it


def test_d151_the_table_says_code_or_llm_as_judge_for_every_metric() -> None:
    data = catalog()
    listed = [m for t in data["tables"] for r in t["rows"] for m in r["metrics"]]
    assert set(ANSWER_QUALITY) <= set(listed)
    assert {data["metrics"][m]["kind"] for m in listed} == {"code", "judge"}
    quality = next(t for t in data["tables"] if t["id"] == "quality")
    assert (quality["title"], quality["subtitle"]) == ("Answer Quality", "Same as Online")


def test_d155_plan_adherence_grades_the_plan_the_agent_wrote() -> None:
    """Found in the eval of 2026-11-12: graded against the skill's text, 5 of 7 cases failed
    Plan Adherence for merging or reordering the skill's steps in their own plan."""
    from evals.replay import trace_dict
    from evals.traces import Span

    skill = Span(
        "tool", "load_skill", {"name": "contract-review"}, "1. Look up 2. Review 3. Answer"
    )
    first = {"items": [{"text": "Look up ShopCo", "status": "doing"}]}
    last = {
        "items": [
            {"text": "Look up ShopCo", "status": "done"},
            {"text": "Answer", "status": "done"},
        ]
    }
    root = Span(
        "agent",
        "agent",
        "Review CT-2207",
        children=[
            skill,
            Span("tool", "write_plan", first, "saved"),
            Span("tool", "write_plan", last, "saved"),
        ],
    )
    given = trace_dict(root, for_judge=True)["input"]
    assert "with write_plan):\n1. Look up ShopCo [done]\n2. Answer [done]" in given
    assert "The skill it followed, for reference:\n1. Look up 2. Review 3. Answer" in given
    no_plan = Span("agent", "agent", "q", children=[skill])
    assert "The plan (the skill it loaded):" in trace_dict(no_plan, for_judge=True)["input"]


def test_d156_bookkeeping_is_not_a_step_for_the_judge() -> None:
    """Found in the eval of 2026-11-12: write_plan updates and load_skill counted as wasted
    or unplanned steps (Step Efficiency, Plan Adherence)."""
    from evals.replay import trace_dict
    from evals.traces import Span

    root = Span(
        "agent",
        "agent",
        "q",
        children=[
            Span("llm", "model step 1", output="calls ['load_skill', 'write_plan']"),
            Span("tool", "write_plan", {"items": [{"text": "Look up", "status": "done"}]}, "ok"),
            Span("llm", "model step 2", output="calls ['write_plan', 'lookup_customer_record']"),
            Span("tool", "lookup_customer_record", {"record": "customer"}, "CUS-0042"),
        ],
    )
    kids = trace_dict(root, for_judge=True)["children"]
    # a step that only did bookkeeping is gone; a mixed one keeps its real call (D-160)
    assert [k["name"] for k in kids] == ["model step 2", "lookup_customer_record"]
    assert kids[0]["output"] == "calls ['lookup_customer_record']"


def test_d158_three_metrics_are_reported_and_never_fail_a_run() -> None:
    from evals.scoring import decides

    for metric in ("plan_adherence", "knowledge_retention"):
        assert not decides(metric)
        assert "D-158" in catalog()["metrics"][metric]["note"]
    assert decides("conversation_completeness")  # reference-based now, so it decides (D-161)
    assert decides("task_completion")
    assert decides("groundedness")


def test_d160_the_judge_sees_why_a_draft_was_rewritten(tmp_path: Path) -> None:
    events = [
        {"type": "run_started", "run_id": "r", "data": {"task": "q", "model": "m"}},
        {"type": "model_replied", "data": {"step": 1, "text": "long draft"}},
        {
            "type": "verify_finished",
            "data": {"retrying": True, "results": [{"label": "Answer Length", "status": "failed"}]},
        },
        {"type": "model_replied", "data": {"step": 2, "text": "short answer"}},
        {"type": "run_finished", "data": {"answer": "short answer", "outcome": "completed"}},
    ]
    path = tmp_path / "r.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in events))
    names = [c.name for c in read_run(path).root.children]
    assert names == ["model step 1", "harness check", "model step 2"]
    assert "Answer Length" in str(read_run(path).root.children[1].output)


def test_reference_based_metrics_are_the_ones_that_use_the_golden_case() -> None:
    based = {k for k, m in catalog()["metrics"].items() if m["reference"]}
    assert based == {
        "tool_correctness",
        "task_completion",
        "guardrails",
        "guardrails_turns",
        "step_efficiency",
        "conversation_completeness",
        "context_relevancy",
        "answer_relevancy",
        "answer_correctness",
    }
    # Groundedness, Hallucination, Citations and Style stay reference-free: same online and off.
    for m in ("groundedness", "hallucination", "citations", "style_format"):
        assert not catalog()["metrics"][m]["reference"]


def _view(tools: list[tuple[str, str]], answer: str = "a") -> object:
    from evals.traces import RunView, Span, ToolUse

    uses = tuple(
        ToolUse(name=n, arguments={}, output="o", is_error=False, agent=a) for n, a in tools
    )
    return RunView(
        "r",
        "q",
        answer,
        "completed",
        "",
        "m",
        "sales",
        2,
        0.0,
        1.0,
        True,
        "",
        uses,
        (),
        Span("agent", "agent"),
    )


def test_d161_step_efficiency_is_code_against_the_cases_budget() -> None:
    from evals.cases import Case
    from evals.reference import step_efficiency

    case = Case("c", "g", "sales", ("q",), "o", max_steps=2)
    ok = step_efficiency(case, [_view([("write_plan", ""), ("lookup", ""), ("search", "")])])
    assert ok.passed  # plan updates don't count
    over = step_efficiency(case, [_view([("a", ""), ("b", ""), ("c", ""), ("d", "")])])
    assert not over.passed
    assert over.score == 0.5


def test_d161_context_relevancy_offline_compares_with_the_expected_tools() -> None:
    from evals.cases import Case
    from evals.reference import context_relevancy

    case = Case(
        "c",
        "g",
        "sales",
        ("q",),
        "o",
        expected_tools=("review_contract",),
        allowed_tools=("search_policy",),
    )
    good = context_relevancy(case, [_view([("review_contract", ""), ("search_policy", "h")])], ())
    assert good.passed
    assert good.score == 1.0
    bad = context_relevancy(
        case,
        [_view([("review_contract", ""), ("send_to_customer", ""), ("read_contract", "")])],
        (),
    )
    assert not bad.passed
    assert "send_to_customer" in bad.reason


async def test_d161_one_reference_judge_call_scores_correctness_and_relevancy() -> None:
    from evals.cases import Case
    from evals.reference import judged

    class StandIn:
        def __init__(self) -> None:
            self.prompts: list[str] = []

        def start(self) -> None: ...

        def taken(self) -> tuple[list[str], float]:
            return ["claude-haiku-5-5"], 0.001

        async def a_generate(self, prompt: str, schema: object = None) -> str:
            self.prompts.append(prompt)
            return json.dumps(
                {
                    "answer_correctness": {"score": 0.9, "reason": "Same decision."},
                    "answer_relevancy": {"score": 0.5, "reason": "Misses the counter."},
                }
            )

    judge = StandIn()
    case = Case("c", "g", "sales", ("q",), "o", reference_answer="No: the CFO decides.")
    scores = {s.metric: s for s in await judged(case, [_view([("x", "")])], judge)}
    assert len(judge.prompts) == 1
    assert "REFERENCE (a right final answer):\nNo: the CFO decides." in judge.prompts[0]
    assert scores["answer_correctness"].passed
    assert not scores["answer_relevancy"].passed
    assert "conversation_completeness" not in scores  # one turn: no conversation metric
    assert scores["answer_correctness"].usd == 0.001
    assert scores["answer_relevancy"].usd == 0.0  # one call, counted once


def test_d161_golden_cases_carry_a_reference_and_a_budget() -> None:
    from evals.cases import load_suite

    suite = load_suite(Path("evals/cases/cloudco.toml"))
    for case in (c for c in suite.cases if c.core):
        assert case.reference_answer, case.id
        assert case.max_steps is not None, case.id
        assert "search_policy" in case.allowed_tools


def test_d162_a_test_passes_on_critical_metrics_and_80_percent() -> None:
    from evals.checks import Score
    from evals.scoring import verdict

    def s(metric: str, ok: bool) -> Score:
        return Score(metric, 1.0 if ok else 0.0, ok, "")

    many = [s("tool_correctness", True), s("task_completion", True), s("guardrails", True)]
    many += [s(m, True) for m in ("groundedness", "hallucination", "citations", "style_format")]
    assert verdict([*many, s("context_relevancy", True), s("step_efficiency", False)]) == (
        True,
        8,
        9,
    )
    assert not verdict([*many, s("guardrails_turns", False)])[0]  # a critical miss fails it
    half = [s("task_completion", True), s("style_format", False), s("groundedness", False)]
    assert not verdict(half)[0]  # 1 of 3 is under 80%
    assert verdict([s("plan_adherence", False), *many])[0]  # reported only: never counts
