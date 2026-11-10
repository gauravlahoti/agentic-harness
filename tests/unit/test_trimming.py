"""Forgetting on purpose (S07-AC5, AC6, AC7, AC8; D-93, D-95).

Cheapest first: cut a big output, stub old tool results, and only if that is not enough,
summarize older turns. The model's own steps are never edited.
"""

from pathlib import Path
from typing import Any

import pytest

from agentic_harness.config import Settings
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.model import GeminiModel, ModelReply, Step
from agentic_harness.pricing import load_prices
from agentic_harness.tools.registry import tool
from agentic_harness.trimming import (
    OUTPUT_LIMIT_CHARS,
    Window,
    cut_output,
    estimate_tokens,
    fit,
    prune,
)


def ask(text: str) -> Step:
    return {"type": "user_input", "content": [{"type": "text", "text": text}]}


def thought(n: int) -> Step:
    return {"type": "thought", "signature": f"sig-{n}", "summary": [{"text": f"thinking {n}"}]}


def call(n: int, name: str = "find", **args: Any) -> Step:
    return {
        "type": "function_call",
        "id": f"c{n}",
        "name": name,
        "arguments": args or {"q": str(n)},
    }


def result(n: int, size: int = 4000, name: str = "find") -> Step:
    text = f"row {n} " + "x" * size
    return {
        "type": "function_result",
        "name": name,
        "call_id": f"c{n}",
        "result": [{"type": "text", "text": text}],
    }


def answer(text: str = "Done.") -> Step:
    return {"type": "model_output", "content": [{"type": "text", "text": text}]}


def long_turn(first: int, rounds: int = 3) -> list[Step]:
    steps: list[Step] = [ask(f"question {first}")]
    for n in range(first, first + rounds):
        steps += [thought(n), call(n), result(n)]
    return [*steps, answer(f"answer {first}")]


def texts(steps: list[Step]) -> list[str]:
    return [p["text"] for s in steps for p in s.get("content", s.get("result", [])) if "text" in p]


# ── AC5: a big output is cut to its start and end ──────────────────────────────────


def test_s07_ac5_a_big_output_keeps_its_start_and_end_with_a_marker() -> None:
    text = "START-" + "m" * 30_000 + "-END"
    cut = cut_output(text)
    assert cut.startswith("START-")
    assert cut.endswith("-END")
    assert "characters cut from the middle" in cut
    assert len(cut) < OUTPUT_LIMIT_CHARS + 300
    assert cut_output("short") == "short"
    assert cut_output("x" * OUTPUT_LIMIT_CHARS) == "x" * OUTPUT_LIMIT_CHARS  # at the limit: whole


@tool(risk="read")
def big() -> str:
    """Return a lot of text."""
    return "A" * 15_000 + "B" * 15_000


async def test_s07_ac5_tool_output_is_cut_before_it_reaches_the_model() -> None:
    from agentic_harness.tools.registry import call_tool

    result = await call_tool(big, {}, None)
    assert result.output.startswith("A")
    assert result.output.endswith("B")
    assert "cut from the middle" in result.output


# ── AC6: old results become one-line stubs, in a batch ─────────────────────────────


def test_s07_ac6_old_results_become_stubs_and_the_recent_ones_stay() -> None:
    steps = long_turn(1, rounds=4)
    pruned, cleared = prune(steps, keep_recent=2)
    results = [s for s in pruned if s["type"] == "function_result"]
    assert cleared == 2
    assert "cleared to save space" in results[0]["result"][0]["text"]
    assert "cleared to save space" in results[1]["result"][0]["text"]
    assert (
        results[2] == steps[[i for i, s in enumerate(steps) if s["type"] == "function_result"][2]]
    )
    assert results[3]["result"][0]["text"].startswith("row 4")
    stub = results[0]["result"][0]["text"]
    assert 'find(q="1")' in stub  # what it was, so the model can ask again
    assert "4,0" in stub or "4,00" in stub  # and how big it was


def test_s07_ac6_pruning_twice_changes_nothing_more() -> None:
    once, _ = prune(long_turn(1, rounds=4), keep_recent=1)
    twice, cleared = prune(once, keep_recent=1)
    assert cleared == 0
    assert twice == once


# ── AC8: the model's steps are never edited, and no call loses its result ──────────


def test_s07_ac8_pruning_never_touches_model_steps_or_removes_a_step() -> None:
    steps = [*long_turn(1, rounds=3), *long_turn(10, rounds=3)]
    pruned, _ = prune(steps, keep_recent=1)
    assert len(pruned) == len(steps)
    for before, after in zip(steps, pruned, strict=True):
        if before["type"] != "function_result":
            assert after == before  # thoughts, calls, answers, user inputs: identical
        else:
            assert after["call_id"] == before["call_id"]  # a call keeps its result
            assert after["name"] == before["name"]


# ── AC6 / AC7: the order of the three techniques ───────────────────────────────────


class Summarizer:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def __call__(self, text: str) -> str:
        self.calls.append(text)
        return "Earlier: ShopCo's discount was capped at 20%."


def big_history() -> list[Step]:
    return [*long_turn(1), *long_turn(10), *long_turn(20), ask("a follow-up question")]


async def test_s07_ac6_below_the_first_line_nothing_happens() -> None:
    steps = long_turn(1, rounds=1)
    window = Window(tokens=100_000)
    summarizer = Summarizer()
    out = await fit(steps, used=estimate_tokens(steps), window=window, summarize=summarizer)
    assert out.steps == steps
    assert out.events == []
    assert summarizer.calls == []


async def test_s07_ac7_past_half_it_prunes_and_does_not_summarize_if_that_was_enough() -> None:
    steps = big_history()
    size = estimate_tokens(steps)
    window = Window(tokens=int(size / 0.55), keep_recent=2)  # past 50%, but pruning will fix it
    summarizer = Summarizer()
    out = await fit(steps, used=size, window=window, summarize=summarizer)
    assert [e["technique"] for e in out.events] == ["prune"]
    assert estimate_tokens(out.steps) < 0.7 * window.tokens
    assert summarizer.calls == []  # AC7: only if still past 70% after pruning


async def test_s07_ac7_still_past_70_percent_after_pruning_summarizes_older_turns() -> None:
    steps = big_history()
    size = estimate_tokens(steps)
    window = Window(tokens=int(size / 4), keep_recent=2)  # pruning alone cannot get under
    summarizer = Summarizer()
    out = await fit(steps, used=size, window=window, summarize=summarizer)
    assert [e["technique"] for e in out.events] == ["prune", "summarize"]
    assert len(summarizer.calls) == 1
    assert "question 1" in summarizer.calls[0]  # it was shown the older turns
    first = out.steps[0]
    assert first["type"] == "user_input"  # the summary rides on the current question
    text = first["content"][0]["text"]
    assert "capped at 20%" in text
    assert text.endswith("a follow-up question")


async def test_s07_ac8_summarizing_replaces_whole_turns_and_the_current_turn_is_untouched() -> None:
    current: list[Step] = [ask("now"), thought(90), call(90), result(90, size=50)]
    steps = [*long_turn(1), *long_turn(10), *current]
    size = estimate_tokens(steps)
    out = await fit(steps, used=size, window=Window(tokens=int(size / 5)), summarize=Summarizer())
    kept = out.steps
    assert kept[1:] == current[1:]  # the model's own steps this turn: identical, signature too
    assert [s["type"] for s in kept] == [
        "user_input",
        "thought",
        "function_call",
        "function_result",
    ]


async def test_s07_one_turn_cannot_be_summarized_away() -> None:
    steps = long_turn(1, rounds=6)
    size = estimate_tokens(steps)
    summarizer = Summarizer()
    out = await fit(steps, used=size, window=Window(tokens=int(size / 5)), summarize=summarizer)
    assert summarizer.calls == []  # nothing older than the current turn to summarize
    assert [e["technique"] for e in out.events] == ["prune"]


async def test_s07_a_failed_summary_leaves_the_pruned_history_alone() -> None:
    async def broken(text: str) -> str:
        raise RuntimeError("503")

    steps = big_history()
    size = estimate_tokens(steps)
    out = await fit(steps, used=size, window=Window(tokens=int(size / 4)), summarize=broken)
    assert [e["technique"] for e in out.events] == ["prune"]
    assert out.steps[-1] == steps[-1]


# ── in the loop ────────────────────────────────────────────────────────────────────


class Scripted:
    name = "gemini-3.5-flash-lite"

    def __init__(self, replies: list[list[Step]], input_tokens: int) -> None:
        self.replies = replies
        self.sent: list[list[Step]] = []
        self.input_tokens = input_tokens

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        self.sent.append(list(steps))
        usage = {"total_input_tokens": self.input_tokens, "total_cached_tokens": 5}
        return ModelReply(self.replies.pop(0), "completed", usage, self.name)


@tool(risk="read")
def find(q: str = "") -> str:
    """Find a thing."""
    return "z" * 6000


async def test_s07_ac6_the_loop_prunes_what_it_sends_and_says_so() -> None:
    replies = [[thought(1), call(1)], [thought(2), call(2)], [thought(3), call(3)], [answer()]]
    model = Scripted(replies, input_tokens=9000)  # 90% of a 10,000-token window
    h = Harness(
        model,
        Limits(),
        [find],
        prices=load_prices(),
        window=Window(tokens=10_000, keep_recent=1),
    )
    events = []
    h.subscribe(events.append)
    result = await h.run("go")
    assert result.outcome == "completed"
    last_sent = model.sent[-1]
    old = [s for s in last_sent if s["type"] == "function_result"]
    assert "cleared to save space" in old[0]["result"][0]["text"]
    assert old[-1]["result"][0]["text"].startswith("z")  # the newest result is whole
    assert [s["signature"] for s in last_sent if s["type"] == "thought"] == [
        "sig-1",
        "sig-2",
        "sig-3",
    ]
    trimmed = [e.data for e in events if e.type == "context_trimmed"]
    assert trimmed
    assert trimmed[0]["technique"] == "prune"
    assert trimmed[0]["after"] < trimmed[0]["before"]
    called = [e.data for e in events if e.type == "model_called"]
    assert called[-1]["window"] == 10_000
    assert called[-1]["fill"] == 9000


async def test_s07_without_a_window_nothing_is_trimmed() -> None:
    replies = [[thought(1), call(1)], [thought(2), call(2)], [answer()]]
    model = Scripted(replies, input_tokens=900_000)
    h = Harness(model, Limits(), [find], prices=load_prices())
    result = await h.run("go")
    assert result.outcome == "completed"
    assert all("cleared" not in str(sent) for sent in model.sent)


def test_s07_window_lines_must_be_in_order() -> None:
    with pytest.raises(ValueError, match="summarize_at"):
        Window(tokens=1000, prune_at=0.8, summarize_at=0.5)


def _unused(_: Path, __: Settings, ___: type[GeminiModel]) -> None:  # keep imports honest
    return None
