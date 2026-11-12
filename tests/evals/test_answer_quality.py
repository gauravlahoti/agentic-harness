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
    assert [k["name"] for k in kids] == ["model step 1", "model step 2", "lookup_customer_record"]
    assert kids[0]["output"] == "updates its notes"
    assert kids[1]["output"] == "calls ['lookup_customer_record']"


def test_d158_three_metrics_are_reported_and_never_fail_a_run() -> None:
    from evals.scoring import decides

    for metric in ("plan_adherence", "conversation_completeness", "knowledge_retention"):
        assert not decides(metric)
        assert "D-158" in catalog()["metrics"][metric]["note"]
    assert decides("task_completion")
    assert decides("groundedness")
