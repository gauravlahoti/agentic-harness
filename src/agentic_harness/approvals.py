"""``ask_human``: the model chooses to pause and ask a person (S06-AC9; D-89).

Harness part: guardrails (the other half of human in the loop). A gate rule *forces* a
pause before an action; this tool lets the model ask when something it needs is missing,
such as which customer. The loop answers it through the same approval channel the page's
cards use, so there is one pause mechanism, one timeout and one card style.

A workspace turns it on with ``ask_human = true`` in ``workspace.toml``.

Does not: run anything itself. The loop intercepts the call, because only the loop can wait
for a person (and keep that wait out of the run's time limit).
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Annotated, Any

from agentic_harness.tools import Tool
from agentic_harness.tools.registry import tool


@tool(risk="read")
def ask_human(question: Annotated[str, "One short question for the person you are helping"]) -> str:
    """Ask the person you are helping one short question and wait for their answer.
    Use it only when you cannot go on without something they have not told you (for
    example which record or document they mean). Never use it to check what you can
    look up with your tools, or to ask permission: the harness asks for that itself."""
    # The loop answers this call; if it ever runs, there was no loop to ask for it.
    return "No one was asked: ask_human only works inside a run."


def ask_human_tool() -> Tool:
    return ask_human


# ── What a person needs to decide: the context on an approval card (D-141) ───────────────

ContextFn = Callable[[dict[str, Any]], list[dict[str, Any]]]


@dataclass(frozen=True, slots=True)
class ApprovalContext:
    """A workspace function that tells an approver where each term of a call started: what
    the current agreement says and what the other side asked. The harness only carries its
    rows to the card; it never reads them. Each row: {"arg", "current", "asked", "change",
    "ref"} with "change" one of "up", "down", "same" or "" (compared with "current")."""

    name: str
    tool: str
    fn: ContextFn
    current: str = "Today"  # the card's column titles, in the workspace's own words
    asked: str = "Asked"


def approval_context(
    tool: str, *, current: str = "Today", asked: str = "Asked"
) -> Callable[[ContextFn], ApprovalContext]:
    """``@approval_context("send_message", current="Agreement today", asked="They asked")``."""

    def wrap(fn: ContextFn) -> ApprovalContext:
        return ApprovalContext(fn.__name__, tool, fn, current, asked)

    return wrap


def context_labels(contexts: Sequence[ApprovalContext], tool: str) -> dict[str, str]:
    """The column titles for this tool's card, from the first context that guards it."""
    c = next((c for c in contexts if c.tool == tool), None)
    return {"current": c.current, "asked": c.asked} if c else {}


def context_rows(
    contexts: Sequence[ApprovalContext], tool: str, arguments: dict[str, Any]
) -> list[dict[str, Any]]:
    """Every row for this call. A broken context is left out: it must never block a decision."""
    rows: list[dict[str, Any]] = []
    for c in (c for c in contexts if c.tool == tool):
        try:
            found = c.fn(dict(arguments))
        except Exception:  # the card still shows the call's own terms
            found = []
        rows += [dict(r) for r in found]
    return rows
