"""Score one run of a case: 3 code metrics + 9 DeepEval metrics (S10-AC4, AC5; D-109, D-114).

Part of the evals. Which metric applies where:

- **Agent layers, every turn the loop ran** (a turn the scope guard stopped has no plan,
  tools or steps to judge): PlanAdherence, ArgumentCorrectness, TaskCompletion,
  StepEfficiency. A conversation's score is the mean of its turns; it passes only if every
  turn passes. TaskCompletion on the last turn is told what a correct result is (the case's
  ``expected_outcome``), and fails in code if a required word is missing.
- **Whole conversation**: TurnFaithfulness whenever a tool returned something;
  KnowledgeRetention, ConversationCompleteness, RoleAdherence and TopicAdherence for
  multi-turn cases.
- **Code**: tool correctness always; guardrails (one turn) or guardrails across turns.

Each metric is measured on its own (``metric.a_measure``), so its score, reason, judge and
cost are its own. A metric that errors (say, the judge's JSON doesn't parse) fails with the
error shown; ``JudgeUnavailableError`` stops the whole eval.

Does not: run the agent (``evals/runner.py`` does) or write files.
"""

import json
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from statistics import mean
from typing import Any

from evals.cases import Case
from evals.checks import Score, guardrails, missing_words, tool_correctness
from evals.judge import Judge, JudgeUnavailableError
from evals.plan import CONVERSATION, PER_TURN
from evals.replay import conversation, llm_test_case
from evals.traces import RunView

CATALOG = Path(__file__).with_name("catalog.json")


@cache
def catalog() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(CATALOG.read_text())
    return data


def threshold(metric: str) -> float:
    return float(catalog()["metrics"][metric]["threshold"])


def build(metric: str, judge: Judge, *, task: str | None = None, topics: list[str]) -> Any:
    """The DeepEval metric object for one of our metric IDs."""
    from deepeval import metrics as m

    common: dict[str, Any] = {
        "model": judge,
        "threshold": threshold(metric),
        "async_mode": True,
        "include_reason": True,
    }
    if metric == "task_completion":
        return m.TaskCompletionMetric(task=task, **common)
    if metric == "topic_adherence":
        return m.TopicAdherenceMetric(relevant_topics=topics, **common)
    kinds = {
        "plan_adherence": m.PlanAdherenceMetric,
        "argument_correctness": m.ArgumentCorrectnessMetric,
        "step_efficiency": m.StepEfficiencyMetric,
        "knowledge_retention": m.KnowledgeRetentionMetric,
        "conversation_completeness": m.ConversationCompletenessMetric,
        "role_adherence": m.RoleAdherenceMetric,
        "turn_faithfulness": m.TurnFaithfulnessMetric,
    }
    return kinds[metric](**common)


async def measure(metric: str, test_case: Any, judge: Judge, **options: Any) -> Score:
    instance = build(metric, judge, **options)
    judge.start()
    try:
        await instance.a_measure(test_case, _show_indicator=False)
    except JudgeUnavailableError:
        raise
    except Exception as error:  # a broken reply fails this metric, not the eval
        used, usd = judge.taken()
        return Score(metric, None, False, "", used, usd, f"{type(error).__name__}: {error}"[:300])
    used, usd = judge.taken()
    score = None if instance.score is None else float(instance.score)
    return Score(metric, score, bool(instance.success), str(instance.reason or ""), used, usd)


def combine(metric: str, turns: list[tuple[int, Score]], many: bool) -> Score:
    """Per-turn scores → one score: the mean; passed only if every turn passed."""
    numbers = [s.score for _, s in turns if s.score is not None]
    reason = "\n".join((f"Turn {n}: " if many else "") + (s.reason or s.error) for n, s in turns)
    return Score(
        metric,
        mean(numbers) if numbers else None,
        all(s.passed for _, s in turns),
        reason,
        list(dict.fromkeys(name for _, s in turns for name in s.judge)),
        sum(s.usd for _, s in turns),
        "; ".join(s.error for _, s in turns if s.error),
    )


def code_scores(case: Case, views: Sequence[RunView]) -> list[Score]:
    rules = (
        guardrails(case, views, "guardrails_turns") if case.multi_turn else guardrails(case, views)
    )
    return [tool_correctness(case, views), rules]


async def judged_scores(
    case: Case, views: Sequence[RunView], judge: Judge, *, role: str, topics: list[str]
) -> list[Score]:
    scores: list[Score] = []
    ran = [(n, v) for n, v in enumerate(views, 1) if v.loop_ran]
    many = len(views) > 1
    for metric in PER_TURN if ran else ():
        per_turn: list[tuple[int, Score]] = []
        for n, view in ran:
            task = None
            if metric == "task_completion" and n == len(views):
                task = f"{view.task}\nA correct result: {case.expected_outcome}"
            per_turn.append(
                (
                    n,
                    await measure(
                        metric, llm_test_case(view, task), judge, task=task, topics=topics
                    ),
                )
            )
        score = combine(metric, per_turn, many)
        if metric == "task_completion" and (missing := missing_words(case, views)):
            score.passed = False
            score.reason += f"\n✗ the answer leaves out: {', '.join(missing)}"
        scores.append(score)
    convo = conversation(views, role, case.expected_outcome)
    if any(t.completed and t.output for v in views for t in v.tools):
        scores.append(await measure("turn_faithfulness", convo, judge, topics=topics))
    if case.multi_turn:
        for metric in CONVERSATION:
            scores.append(await measure(metric, convo, judge, topics=topics))
    return scores
