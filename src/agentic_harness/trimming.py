"""Forgetting on purpose: keep the context under a working window (S07-AC5 to AC8; D-93, D-95).

Harness part: memory. Every call resends the conversation, so it only grows. Three tools,
cheapest first, each used only when the one before is not enough:

  1. cut      a tool result over ~10,000 characters keeps its start and end, plus a marker
  2. prune    past 50% of the window, old tool results become one-line stubs, all at once
              (a batch, so the start of the prompt changes rarely and caching mostly survives)
  3. summarize still past 70% after pruning: one small model call replaces the older turns

The rules that keep Gemini happy (D-95; thought signatures, D-05):
  - the model's own steps (thoughts, calls, answers) are never edited or removed;
  - a call never loses its result (a result may shrink to a stub, never disappear);
  - only whole *earlier* turns are summarized; the current turn is never touched;
  - the summary rides on the current user input, so no two user inputs sit side by side.

What is sent is trimmed; the saved conversation file keeps everything.

Does not: save anything (``memory.py``) or decide when to run (the loop calls ``fit`` before
each model call, with the real input-token count the last reply reported).
"""

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from agentic_harness.model import ModelClient, Step
from agentic_harness.planning import PLAN_TOOL

OUTPUT_LIMIT_CHARS = 10_000
STUB_START = "[cleared to save space"
SUMMARY_PROMPT = (
    "Summarize the earlier part of this conversation for the assistant that is carrying on with "
    "it. Keep decisions, limits, names, IDs and open questions. Be brief: at most 150 words. "
    "Reply with the summary only."
)

Summarize = Callable[[str], Awaitable[str]]


@dataclass(frozen=True, slots=True)
class Window:
    """The working window: small on purpose (D-94), far below the model's real limit."""

    tokens: int = 20_000
    prune_at: float = 0.5
    summarize_at: float = 0.7
    keep_recent: int = 2  # results this new stay whole when pruning

    def __post_init__(self) -> None:
        if not 0 < self.prune_at < self.summarize_at <= 1:
            raise ValueError("Need 0 < prune_at < summarize_at <= 1.")
        if self.tokens < 1000:
            raise ValueError("window_tokens must be at least 1000.")


@dataclass(frozen=True, slots=True)
class Fit:
    steps: list[Step]
    events: list[dict[str, Any]] = field(default_factory=list)


def estimate_tokens(steps: Sequence[Step]) -> int:
    """About 4 characters a token. Used only where the model has not told us the real count."""
    return len(json.dumps(steps, ensure_ascii=False)) // 4


def cut_output(text: str, limit: int = OUTPUT_LIMIT_CHARS) -> str:
    """A big result keeps its start and end; the middle is named as cut (S07-AC5)."""
    if len(text) <= limit:
        return text
    head, tail = text[: int(limit * 0.6)], text[-int(limit * 0.3) :]
    gone = len(text) - len(head) - len(tail)
    return f"{head}\n[… {gone:,} characters cut from the middle; ask for a smaller part …]\n{tail}"


def prune(steps: Sequence[Step], keep_recent: int) -> tuple[list[Step], int]:
    """Old tool results become one-line stubs, except the newest plan (S11-AC3). Nothing else
    changes, nothing is removed."""
    positions = [i for i, s in enumerate(steps) if s.get("type") == "function_result"]
    old = positions[: max(0, len(positions) - keep_recent)]
    # The newest plan stays whole: it is how the agent keeps track in a long run (D-123).
    plans = [i for i in positions if steps[i].get("name") == PLAN_TOOL]
    if plans:
        old = [i for i in old if i != plans[-1]]
    calls = {s.get("id"): s for s in steps if s.get("type") == "function_call"}
    out = list(steps)
    cleared = 0
    for i in old:
        step = steps[i]
        text = _result_text(step)
        if text.startswith(STUB_START):
            continue  # already a stub
        shown = _call_text(calls.get(step.get("call_id")), step.get("name", ""))
        stub = (
            f"{STUB_START}: {shown} returned {len(text):,} characters. Ask again if you need it.]"
        )
        out[i] = {**step, "result": [{"type": "text", "text": stub}]}
        cleared += 1
    return out, cleared


async def fit(steps: list[Step], *, used: int, window: Window, summarize: Summarize | None) -> Fit:
    """Bring the history under the window, cheapest first. ``used`` is the measured fill."""
    if used < window.prune_at * window.tokens:
        return Fit(steps)
    events: list[dict[str, Any]] = []
    before = estimate_tokens(steps)
    pruned, cleared = prune(steps, window.keep_recent)
    if cleared:
        events.append(
            {
                "technique": "prune",
                "cleared": cleared,
                "before": before,
                "after": estimate_tokens(pruned),
            }
        )
    current = pruned
    if summarize is not None and estimate_tokens(pruned) >= window.summarize_at * window.tokens:
        summed = await _summarize(pruned, summarize)
        if summed is not None:
            current, turns = summed
            events.append(
                {
                    "technique": "summarize",
                    "turns": turns,
                    "before": estimate_tokens(pruned),
                    "after": estimate_tokens(current),
                }
            )
    return Fit(current, events)


async def _summarize(steps: list[Step], summarize: Summarize) -> tuple[list[Step], int] | None:
    starts = [i for i, s in enumerate(steps) if s.get("type") == "user_input"]
    if len(starts) < 2:
        return None  # one turn: nothing older to fold away
    now = starts[-1]
    older, current = steps[:now], steps[now:]
    try:
        summary = (await summarize(_render(older))).strip()
    except Exception:  # a busy small model must not stop the run: keep the pruned history
        return None
    if not summary:
        return None
    first = current[0]
    asked = "".join(p.get("text", "") for p in first.get("content", []))
    merged = {
        **first,
        "content": [
            {"type": "text", "text": f"[Earlier in this conversation: {summary}]\n\n{asked}"}
        ],
    }
    return [merged, *current[1:]], len([s for s in older if s.get("type") == "user_input"])


def _render(steps: Sequence[Step]) -> str:
    lines = []
    for s in steps:
        kind = s.get("type")
        if kind == "user_input":
            lines.append("User: " + "".join(p.get("text", "") for p in s.get("content", [])))
        elif kind == "model_output":
            lines.append("Assistant: " + "".join(p.get("text", "") for p in s.get("content", [])))
        elif kind == "function_call":
            lines.append(f"Assistant used {s.get('name')}.")
        elif kind == "function_result":
            lines.append(f"Result of {s.get('name')}: {_result_text(s)[:400]}")
    return "\n".join(lines)


def _result_text(step: Step) -> str:
    return "".join(p.get("text", "") for p in step.get("result", []))


def _call_text(call: Step | None, name: str) -> str:
    args = (call or {}).get("arguments") or {}
    shown = ", ".join(
        f'{k}="{v}"' if isinstance(v, str) else f"{k}={json.dumps(v)}" for k, v in args.items()
    )
    return f"{name}({shown[:80]})"


class ModelSummarizer:
    """One small model call that folds older turns into a few sentences (D-93)."""

    def __init__(self, model: ModelClient, cost: Callable[[str, dict[str, Any]], float]) -> None:
        self.model, self._cost = model, cost
        self.last_usd = 0.0  # the loop charges this to the run's budget after each use

    async def __call__(self, text: str) -> str:
        reply = await self.model.create(
            SUMMARY_PROMPT,
            [{"type": "user_input", "content": [{"type": "text", "text": text}]}],
            [],
        )
        self.last_usd += self._cost(self.model.name, reply.usage)
        return reply.text
