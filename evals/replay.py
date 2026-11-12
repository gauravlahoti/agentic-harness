"""Hand a saved run to DeepEval as a trace and as test cases, with no model calls (S10-AC3).

Part of the evals; D-110. DeepEval's trajectory metrics (TaskCompletion, StepEfficiency,
PlanAdherence) read the run as a tree of spans: ``{name, type, input, output, children}``.
Usually DeepEval builds that tree while the agent runs (``@observe``). Our harness already
saved the run, so we replay it: ``traces.Span`` → the same dict shape, attached to the test
case. The judge then sees every model step, every tool call and the sub-agent's work, and
nothing has to run again.

- ``llm_test_case``: one run (one turn) → ``LLMTestCase`` with the trace and tools called.
- ``conversation``: all turns of a case → ``ConversationalTestCase``; each answer carries
  what that turn's tools returned as its retrieval context.

Tool results are cut to ``OUTPUT_CAP`` characters: the judge needs what was found, not
every word of a contract, and each character costs.

**The judge's copy is cleaned (D-118).** The first full eval showed two ways the raw trace
misled the judge:

- ``load_skill`` is how the agent reads its plan, but the judge counted it as an extra step
  "before the plan". Its output (the skill text) moves into the agent's input as the plan.
- A helper's work was saved both as its own agent and as the ``delegate_task`` call that
  started it, so the judge saw "the reviewer ran twice". The helper now sits inside its call.

Does not: call DeepEval's metrics (``evals/scoring.py`` does) or a model.
"""

from collections.abc import Sequence
from typing import Any

from evals.traces import RunView, Span

OUTPUT_CAP = 3000


def cut(value: Any) -> Any:
    if isinstance(value, str) and len(value) > OUTPUT_CAP:
        return value[:OUTPUT_CAP] + f" … [{len(value) - OUTPUT_CAP} more characters]"
    return value


READS_PLAN = "load_skill"  # reading the plan: not a step of it
STARTS_HELPER = "delegate_task"  # the call a helper's work belongs under


def trace_dict(span: Span, *, for_judge: bool = False) -> dict[str, Any]:
    """A Span tree → DeepEval's trace dict (the shape ``create_nested_spans_dict`` makes)."""
    node: dict[str, Any] = {"name": span.name, "type": span.kind}
    children = list(span.children)
    plan = ""
    if for_judge:
        skill = "\n\n".join(
            str(c.output) for c in children if c.kind == "tool" and c.name == READS_PLAN
        )
        # The plan is the agent's own to-do list when it wrote one (D-155): graded against
        # the skill's text, it lost marks for merging or reordering the skill's steps.
        own = written_plan(children)
        if own:
            plan = f"The plan (the to-do list it wrote with write_plan):\n{own}"
            if skill:
                plan += f"\n\nThe skill it followed, for reference:\n{skill}"
        elif skill:
            plan = f"The plan (the skill it loaded):\n{skill}"
        # Reading the skill and updating the to-do list are bookkeeping, not steps of the
        # task (D-156): the judge counted them as wasted or "unplanned" steps.
        children = nest_helpers(
            [
                b
                for c in children
                if c.name not in BOOKKEEPING and (b := unbooked(c)).output != "updates its notes"
            ]
        )
    given = span.input
    if plan:
        given = f"{span.input}\n\n{plan}"
    if given not in (None, "", {}):
        node["input"] = cut(given)
    if span.output not in (None, ""):
        node["output"] = cut(span.output)
    node["children"] = [trace_dict(child, for_judge=for_judge) for child in children]
    return node


WRITES_PLAN = "write_plan"
BOOKKEEPING = (READS_PLAN, WRITES_PLAN)


def unbooked(span: Span) -> Span:
    """A model step's "calls [...]" without the bookkeeping calls; dropped if nothing is left."""
    text = span.output
    if span.kind != "llm" or not isinstance(text, str) or not text.startswith("calls ["):
        return span
    names = [n.strip(" '\"") for n in text[len("calls [") : -1].split(",") if n.strip()]
    kept = [n for n in names if n not in BOOKKEEPING]
    return Span(span.kind, span.name, span.input, f"calls {kept}" if kept else "updates its notes")


def written_plan(children: Sequence[Span]) -> str:
    """The last to-do list the agent wrote, one numbered line per item, with its status."""
    plans = [c.input for c in children if c.kind == "tool" and c.name == WRITES_PLAN]
    items = plans[-1].get("items") if plans and isinstance(plans[-1], dict) else None
    if not isinstance(items, list):
        return ""
    return "\n".join(
        f"{n}. {i.get('text', '')} [{i.get('status', '')}]"
        + (f" ({i['note']})" if i.get("note") else "")
        for n, i in enumerate(items, 1)
        if isinstance(i, dict)
    )


def nest_helpers(children: list[Span]) -> list[Span]:
    """Move each helper's agent span inside the delegate_task call that started it."""
    kept: list[Span] = []
    waiting: list[Span] = []  # helpers seen since the last delegate_task
    for child in children:
        if child.kind == "agent":
            waiting.append(child)
            continue
        if child.kind == "tool" and child.name == STARTS_HELPER and waiting:
            child = Span(child.kind, child.name, child.input, child.output, [*waiting])
            waiting = []
        kept.append(child)
    return kept + waiting  # a helper with no call left (shouldn't happen) stays visible


def llm_test_case(view: RunView, task: str | None = None) -> Any:
    """One run → an LLMTestCase carrying its trace. ``task`` overrides what success means."""
    from deepeval.test_case import LLMTestCase, ToolCall

    case = LLMTestCase(
        input=task or view.task,
        actual_output=view.answer or "(no answer)",
        tools_called=[
            ToolCall(name=t.name, input_parameters=t.arguments, output=cut(t.output))
            for t in view.tools
            if t.name != READS_PLAN
        ],
    )
    case._trace_dict = trace_dict(view.root, for_judge=True)  # what the trajectory metrics read
    return case


def conversation(views: Sequence[RunView], role: str, expected_outcome: str = "") -> Any:
    """All turns of a case → a ConversationalTestCase (user, assistant, user, …)."""
    from deepeval.test_case import ConversationalTestCase, ToolCall, Turn

    turns: list[Any] = []
    for view in views:
        found = [cut(t.output) for t in view.tools if t.completed and t.output]
        turns.append(Turn(role="user", content=view.task))
        turns.append(
            Turn(
                role="assistant",
                content=view.answer or "(no answer)",
                retrieval_context=found or None,
                tools_called=[
                    ToolCall(name=t.name, input_parameters=t.arguments) for t in view.tools
                ]
                or None,
            )
        )
    return ConversationalTestCase(
        turns=turns, chatbot_role=role, expected_outcome=expected_outcome or None
    )
