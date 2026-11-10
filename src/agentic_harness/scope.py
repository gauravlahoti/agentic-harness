"""The scope guard: keep the agent on its job (S05-AC14; D-81).

Harness part: guardrails. A workspace may declare ``[scope]`` in ``workspace.toml``:
what the agent ``covers`` and its polite ``refusal``. The harness then adds two layers:

1. a Scope section in the system prompt, so the agent knows its job;
2. an input check before the loop: one small model call reads the task and answers
   IN or OUT. OUT ends the run with the refusal, before any tool or loop step.

If the check itself fails (a busy model), the run goes on: layer 1 still applies, and a
503 must never block real work.

Does not: know any domain (the words come from the workspace) or judge answers.
"""

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from agentic_harness.model import ModelClient
from agentic_harness.pricing import Prices


@dataclass(frozen=True, slots=True)
class Scope:
    covers: str  # what the agent helps with, in plain words
    refusal: str  # what it says to anything else
    model: str | None = None  # the check's model; None: the run's model


@dataclass(frozen=True, slots=True)
class Verdict:
    in_scope: bool
    reason: str
    usd: float = 0.0


ScopeCheck = Callable[[str], Awaitable[Verdict]]


def scope_prompt(scope: Scope) -> str:
    """Layer 1: the Scope section of the system prompt."""
    # No refusal text here. The input check (layer 2) has already let this task in; given a
    # ready-made refusal, a small model copied it for short, vague requests that were plainly
    # part of the job (found live). The prompt says what the job is and how to handle vagueness.
    return (
        "## Scope\n\n"
        f"You help with: {scope.covers}\n"
        "Requests about this work are in scope, even short or vague ones: use your tools, "
        "or ask for what is missing (for example, which record). Politely decline only tasks "
        "that are clearly about something else, even if you know the answer."
    )


CHECK_PROMPT = (
    "You decide whether a request is inside an assistant's scope. You do not answer it.\n"
    "The assistant only helps with: {covers}\n"
    "Reply with IN or OUT, a colon, and a reason of a few words. Greetings, questions "
    "about what the assistant can do, and the person's preferences about how it should "
    "answer them (format, length, tone) are IN."
)


def parse_verdict(text: str) -> tuple[bool, str]:
    """'OUT: weather' → (False, 'weather'). Anything unclear counts as IN (D-81)."""
    match = re.match(r"\W*(IN|OUT)\b\W*(.*)", text.strip(), re.I | re.S)
    if not match:
        return True, text.strip()[:200]
    return match[1].upper() == "IN", match[2].strip()[:200]


def scope_check(scope: Scope, model: ModelClient, prices: Prices) -> ScopeCheck:
    """Layer 2: one small call per task, before the loop."""

    async def check(task: str) -> Verdict:
        steps = [{"type": "user_input", "content": [{"type": "text", "text": task}]}]
        reply = await model.create(CHECK_PROMPT.format(covers=scope.covers), steps, [])
        in_scope, reason = parse_verdict(reply.text)
        return Verdict(in_scope, reason, prices.cost(model.name, reply.usage))

    return check
