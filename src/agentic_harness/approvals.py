"""``ask_human``: the model chooses to pause and ask a person (S06-AC9; D-89).

Harness part: guardrails (the other half of human in the loop). A gate rule *forces* a
pause before an action; this tool lets the model ask when something it needs is missing,
such as which customer. The loop answers it through the same approval channel the page's
cards use, so there is one pause mechanism, one timeout and one card style.

A workspace turns it on with ``ask_human = true`` in ``workspace.toml``.

Does not: run anything itself. The loop intercepts the call, because only the loop can wait
for a person (and keep that wait out of the run's time limit).
"""

from typing import Annotated

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
