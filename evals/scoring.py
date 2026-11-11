"""Score one run of a case: 3 code metrics + 8 DeepEval metrics (S10-AC4, AC5; D-109, D-114).

Part of the evals. Which metric applies where:

- **Agent layers, every turn the loop ran** (a turn the scope guard stopped has no plan,
  tools or steps to judge): PlanAdherence, ArgumentCorrectness, TaskCompletion,
  StepEfficiency. A conversation's score is the mean of its turns; it passes only if every
  turn passes. TaskCompletion on the last turn is told what a correct result is (the case's
  ``expected_outcome``), and fails in code if a required word is missing.
- **Whole conversation**: KnowledgeRetention, ConversationCompleteness, RoleAdherence and
  TopicAdherence for multi-turn cases. (TurnFaithfulness was dropped, D-118.)
- **Code**: tool correctness always; guardrails (one turn) or guardrails across turns.

Each metric is measured on its own (``metric.a_measure``), so its score, reason, judge and
cost are its own. A metric that errors (say, the judge's JSON doesn't parse) is **Not
Scored**, and one with nothing to grade is **Not Applicable**: both are shown with their reason
and neither fails the case (D-118). ``JudgeUnavailableError`` stops the whole eval.

Does not: run the agent (``evals/runner.py`` does) or write files.
"""

import asyncio
import json
from collections.abc import Callable, Sequence
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
METRIC_SECONDS = 300.0  # one metric, all its judge calls; past this it's Not Scored (D-119)


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
    }
    return kinds[metric](**common)


async def measure(metric: str, test_case: Any, judge: Judge, **options: Any) -> Score:
    instance = build(metric, judge, **options)
    judge.start()
    try:
        await asyncio.wait_for(instance.a_measure(test_case, _show_indicator=False), METRIC_SECONDS)
    except JudgeUnavailableError:
        raise
    except TimeoutError:  # the judge never finished this metric: Not Scored, eval goes on
        used, usd = judge.taken()
        why = f"The judge didn't answer in {METRIC_SECONDS / 60:g} min."
        return Score(metric, None, False, "", used, usd, why, status="not_scored")
    except Exception as error:  # the judge failed, not the agent: Not Scored (D-118)
        used, usd = judge.taken()
        why = f"{type(error).__name__}: {error}"[:300]
        return Score(metric, None, False, "", used, usd, why, status="not_scored")
    used, usd = judge.taken()
    score = None if instance.score is None else float(instance.score)
    return settle(
        Score(metric, score, bool(instance.success), str(instance.reason or ""), used, usd)
    )


# DeepEval's words when a conversation gives it nothing to grade (for example every turn was
# refused before the loop): that is Not Applicable, not a score of 0.
NOTHING_TO_GRADE = ("no question-answer pairs", "nothing to evaluate", "no turns to evaluate")


def settle(score: Score) -> Score:
    if any(words in score.reason.lower() for words in NOTHING_TO_GRADE):
        score.status = "not_applicable"
    return score


def combine(metric: str, turns: list[tuple[int, Score]], many: bool) -> Score:
    """Per-turn scores → one score: the mean; passed only if every turn passed."""
    numbers = [s.score for _, s in turns if s.score is not None]
    reason = "\n".join((f"Turn {n}: " if many else "") + (s.reason or s.error) for n, s in turns)
    counted = [s for _, s in turns if s.counted]
    return Score(
        metric,
        mean(numbers) if numbers else None,
        all(s.passed for s in counted),
        reason,
        list(dict.fromkeys(name for _, s in turns for name in s.judge)),
        sum(s.usd for _, s in turns),
        "; ".join(s.error for _, s in turns if s.error),
        # scored if any turn was; otherwise whatever the turns were (Not Scored first)
        status="scored"
        if counted
        else (
            "not_scored" if any(s.status == "not_scored" for _, s in turns) else "not_applicable"
        ),
    )


def code_scores(case: Case, views: Sequence[RunView]) -> list[Score]:
    rules = (
        guardrails(case, views, "guardrails_turns") if case.multi_turn else guardrails(case, views)
    )
    return [tool_correctness(case, views), rules]


Progress = Callable[[str, str, int, int], None]  # (started | finished, metric, index, of)


async def judged_scores(
    case: Case,
    views: Sequence[RunView],
    judge: Judge,
    *,
    role: str,
    topics: list[str],
    progress: Progress = lambda *_: None,
) -> list[Score]:
    """Every judged metric for one run; ``progress`` hears each one start and finish."""
    scores: list[Score] = []
    ran = [(n, v) for n, v in enumerate(views, 1) if v.loop_ran]
    many = len(views) > 1
    todo = [*(PER_TURN if ran else ()), *(CONVERSATION if case.multi_turn else ())]
    for index, metric in enumerate(todo, 1):
        progress("started", metric, index, len(todo))
        scores.append(await one_metric(metric, case, views, ran, many, judge, role, topics))
        progress("finished", metric, index, len(todo))
    return scores


async def one_metric(
    metric: str,
    case: Case,
    views: Sequence[RunView],
    ran: list[tuple[int, RunView]],
    many: bool,
    judge: Judge,
    role: str,
    topics: list[str],
) -> Score:
    if metric in CONVERSATION:
        return await measure(
            metric, conversation(views, role, case.expected_outcome), judge, topics=topics
        )
    # an agent-layer metric: every turn the loop ran
    per_turn: list[tuple[int, Score]] = []
    for n, view in ran:
        task = None
        if metric == "task_completion" and n == len(views):
            task = f"{view.task}\nA correct result: {case.expected_outcome}"
        per_turn.append(
            (n, await measure(metric, llm_test_case(view, task), judge, task=task, topics=topics))
        )
    score = combine(metric, per_turn, many)
    if metric == "task_completion" and (missing := missing_words(case, views)):
        score.passed = False
        score.status = "scored"  # a missing required word is a real fail, judged or not
        score.reason += f"\n✗ the answer leaves out: {', '.join(missing)}"
    return score
