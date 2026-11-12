"""``write_plan``: the agent's to-do list for one task (S11-AC1, AC2, AC5; D-121, D-122).

Harness part: the loop (task decomposition). The model decides *whether* a task needs a
plan and *what* the steps are; the harness gives it one tool to write them down, keeps
the newest list in run state, and won't let the run end quietly with items open (the
"Plan Complete" check in verify.py).

One tool rewrites the whole list each time (D-122), so a status change can ride along
with a real tool call in the same reply, and the newest copy is always one result in the
history (trimming never stubs it: D-123).

Does not: run anything. The loop intercepts the call, like ``ask_human``, because only the
loop holds run state. Nor does it keep the plan after the task: a plan belongs to one task,
not to long-term memory.
"""

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any, Literal, cast

from agentic_harness.tools import Tool

PLAN_TOOL = "write_plan"
Status = Literal["open", "doing", "done", "skipped"]
STATUSES: tuple[Status, ...] = ("open", "doing", "done", "skipped")
BOXES = {"open": "[ ]", "doing": "[>]", "done": "[x]", "skipped": "[-]"}

# The model reads this to decide when to plan (D-121): light questions must not plan.
DESCRIPTION = (
    "Write or update your to-do list for this task. Use it when the task has 3 or more "
    "distinct parts (for example: look something up, review it, then send a reply), or the "
    "person asks two or more things in one message (for example: is X a customer, and if so"
    " pull its record); answer a single simple question directly, with no plan. Send the "
    "whole list every time. Mark an item doing when you start it and done when it is "
    "finished; you can update the list in the same reply as another tool call. If an item "
    "turns out to be unnecessary, mark it skipped and say why in its note. Finish every "
    "item before you give your final answer. When you follow a skill's steps for such a "
    "task, write them here first: the skill is the recipe, this list is your progress on "
    "it."
)


@dataclass(frozen=True, slots=True)
class Item:
    text: str
    status: Status = "open"
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


class PlanError(ValueError):
    """The model's list can't be used; the message tells it what to fix."""


def plan_tool() -> Tool:
    """The declaration the model sees. Its function never runs: the loop answers it."""
    item = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "One step, in a few words"},
            "status": {"type": "string", "enum": list(STATUSES)},
            "note": {"type": "string", "description": "Why it was skipped (needed for skipped)"},
        },
        "required": ["text", "status"],
    }
    # No minItems/maxItems or defaults: Gemini declarations don't take them (gemini-api-notes).
    parameters = {
        "type": "object",
        "properties": {"items": {"type": "array", "items": item, "description": "The whole list"}},
        "required": ["items"],
    }
    return Tool(
        name=PLAN_TOOL,
        description=DESCRIPTION,
        risk="read",  # it changes nothing outside the run
        parameters=parameters,
        function=_outside_a_run,
        part="plan",
    )


def _outside_a_run(**_: Any) -> str:
    return "No plan was kept: write_plan only works inside a run."


def read_items(arguments: Mapping[str, Any]) -> list[Item]:
    """The model's arguments as items. Every problem is named, so one retry can fix them all."""
    rows = arguments.get("items")
    if not isinstance(rows, list) or not rows:
        raise PlanError("items must be a non-empty list of {text, status, note}.")
    items, problems = [], []
    for number, row in enumerate(rows, 1):
        row = row if isinstance(row, dict) else {}
        text = str(row.get("text", "")).strip()
        status = row.get("status")
        note = str(row.get("note", "") or "").strip()
        if not text:
            problems.append(f"item {number} needs text")
        if status not in STATUSES:
            problems.append(f"item {number}: status must be one of {', '.join(STATUSES)}")
        elif status == "skipped" and not note:
            problems.append(f"item {number} is skipped: give the reason in its note")
        items.append(Item(text, cast(Status, status), note))
    if problems:
        raise PlanError("The plan was not saved: " + "; ".join(problems) + ".")
    return items


def unfinished(items: Sequence[Item]) -> list[Item]:
    """Open or in progress. Skipped with a reason counts as finished (D-124)."""
    return [i for i in items if i.status in ("open", "doing")]


def show(items: Sequence[Item]) -> str:
    """What the model gets back: the whole list, so the newest copy is in its history."""
    done = sum(i.status in ("done", "skipped") for i in items)
    lines = [f"Plan saved ({done} of {len(items)} done):"]
    for i in items:
        lines.append(f"{BOXES[i.status]} {i.text}" + (f" ({i.note})" if i.note else ""))
    if unfinished(items):  # found live: the agent answered with items still open
        lines.append("Mark every item done, or skipped with why, before your final answer.")
    return "\n".join(lines)


def latest_plan(steps: Sequence[Mapping[str, Any]]) -> list[Item] | None:
    """The newest plan the harness accepted, rebuilt from saved steps (S11-AC2).

    Used to show an old conversation's plan; a Resume (S09) gets it the same way.
    """
    accepted = {
        s.get("call_id")
        for s in steps
        if s.get("type") == "function_result"
        and s.get("name") == PLAN_TOOL
        and not s.get("is_error")
    }
    for step in reversed(steps):
        if (
            step.get("type") == "function_call"
            and step.get("name") == PLAN_TOOL
            and step.get("id") in accepted
        ):
            try:
                return read_items(step.get("arguments") or {})
            except PlanError:
                return None
    return None
