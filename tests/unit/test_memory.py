"""Conversations that last (S07-AC1, AC2, AC3, AC11; D-90, D-91).

A conversation is one append-only file of exact steps. These tests use a scripted model
and the real store on a temp folder; no Gemini is called.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.memory import (
    CANCELLED,
    SessionStore,
    Turn,
    fallback_title,
    make_title,
)
from agentic_harness.model import ModelError, ModelReply, Step
from agentic_harness.pricing import load_prices
from agentic_harness.tools.registry import tool

ASK = {"type": "user_input", "content": [{"type": "text", "text": "Which customers?"}]}
THOUGHT = {"type": "thought", "signature": "c2lnbmF0dXJl", "summary": [{"text": "hmm"}]}
CALL = {"type": "function_call", "id": "c1", "name": "find", "arguments": {"item": "x"}}
RESULT = {
    "type": "function_result",
    "name": "find",
    "call_id": "c1",
    "result": [{"type": "text", "text": "found"}],
}
ANSWER = {"type": "model_output", "content": [{"type": "text", "text": "Three."}]}


def store(tmp_path: Path) -> SessionStore:
    return SessionStore(tmp_path, "demo")


def test_s07_ac1_a_conversation_is_saved_step_by_step_exactly(tmp_path: Path) -> None:
    s = store(tmp_path)
    session = s.create("sales")
    s.append_steps(session.id, "sales", [ASK, THOUGHT, CALL])
    s.append_steps(session.id, "sales", [RESULT, ANSWER])
    again = s.load(session.id, "sales")
    assert again.steps == [ASK, THOUGHT, CALL, RESULT, ANSWER]  # byte for byte, signature too
    lines = (tmp_path / "sessions" / "demo" / "sales" / f"{session.id}.jsonl").read_text()
    assert [json.loads(line)["kind"] for line in lines.splitlines()] == ["session"] + ["step"] * 5


def test_s07_ac1_a_crash_mid_line_loses_only_that_line(tmp_path: Path) -> None:
    s = store(tmp_path)
    session = s.create("sales")
    s.append_steps(session.id, "sales", [ASK, ANSWER])
    file = tmp_path / "sessions" / "demo" / "sales" / f"{session.id}.jsonl"
    with file.open("a") as out:
        out.write('{"kind": "step", "step": {"type": "mod')  # the process died here
    assert s.load(session.id, "sales").steps == [ASK, ANSWER]


def test_s07_ac3_an_unfinished_tool_call_is_marked_cancelled_not_rerun(tmp_path: Path) -> None:
    s = store(tmp_path)
    session = s.create("sales")
    s.append_steps(session.id, "sales", [ASK, THOUGHT, CALL])  # the server stopped here
    steps = s.load(session.id, "sales").steps
    assert steps[:3] == [ASK, THOUGHT, CALL]
    last = steps[-1]
    assert (last["type"], last["call_id"], last["name"]) == ("function_result", "c1", "find")
    assert last["result"][0]["text"] == CANCELLED
    assert last["is_error"] is True


def test_s07_ac2_the_list_is_per_profile_newest_first_with_titles(tmp_path: Path) -> None:
    s = store(tmp_path)
    first = s.create("sales")
    s.set_title(first.id, "sales", "ShopCo uptime question")
    s.append_steps(first.id, "sales", [ASK, ANSWER])
    s.finish_turn(
        first.id, "sales", Turn("Which customers?", "Three.", "completed", 0.01, 2.0, "r1")
    )
    second = s.create("sales")
    s.set_title(second.id, "sales", "Discount limits")
    other = s.create("engineering")
    s.set_title(other.id, "engineering", "Not yours")
    listed = s.list("sales")
    assert [item.title for item in listed] == ["Discount limits", "ShopCo uptime question"]
    assert listed[1].turns == 1
    assert [item.title for item in s.list("engineering")] == ["Not yours"]
    assert s.list("nobody") == []


def test_s07_ac2_a_conversation_can_be_opened_and_deleted(tmp_path: Path) -> None:
    s = store(tmp_path)
    session = s.create("sales")
    s.set_title(session.id, "sales", "A topic")
    s.finish_turn(session.id, "sales", Turn("Hi", "Hello", "completed", 0.0, 1.0, "r1"))
    opened = s.load(session.id, "sales")
    assert opened.title == "A topic"
    assert [(t.task, t.answer) for t in opened.turns] == [("Hi", "Hello")]
    s.delete(session.id, "sales")
    assert s.list("sales") == []
    with pytest.raises(KeyError):
        s.load(session.id, "sales")


def test_s07_a_conversation_id_cannot_walk_out_of_the_folder(tmp_path: Path) -> None:
    s = store(tmp_path)
    for bad in ("../x", "a/b", "..", "", "x" * 80):
        with pytest.raises(KeyError):
            s.load(bad, "sales")


def test_s07_ac11_title_falls_back_to_the_first_words() -> None:
    assert fallback_title(
        "What did ShopCo change in contract CT-2207 and what can I agree to?"
    ) == ("What did ShopCo change in contract")
    assert fallback_title("   ") == "New conversation"
    assert len(fallback_title("x" * 200)) <= 48


class ScriptedModel:
    """Answers from a list; remembers what it was sent."""

    name = "gemini-3.5-flash-lite"

    def __init__(self, replies: Sequence[list[Step]], fail: Exception | None = None) -> None:
        self.replies = list(replies)
        self.sent: list[list[Step]] = []
        self.fail = fail

    async def create(self, system: str, steps: Sequence[Step], tools: Sequence[Step]) -> ModelReply:
        self.sent.append(list(steps))
        if self.fail:
            raise self.fail
        usage = {"total_input_tokens": 100, "total_output_tokens": 10}
        return ModelReply(self.replies.pop(0), "completed", usage, self.name)


async def test_s07_ac11_title_comes_from_a_small_model_call() -> None:
    model = ScriptedModel(
        [
            [
                {
                    "type": "model_output",
                    "content": [{"type": "text", "text": '"ShopCo discount review."\n'}],
                }
            ]
        ]
    )
    title = await make_title(model, "Can ShopCo have 25% off?")
    assert title == "ShopCo discount review"  # no quotes, no full stop
    assert "25% off" in str(model.sent[0])


async def test_s07_ac11_a_failed_title_call_is_not_an_error() -> None:
    model = ScriptedModel([], fail=RuntimeError("503"))
    assert await make_title(model, "Can ShopCo have 25% off?") == "Can ShopCo have 25% off?"


@tool(risk="read")
def find(item: str) -> str:
    """Find a thing."""
    return "found"


def harness(model: ScriptedModel) -> Harness:
    return Harness(model, Limits(), [find], prices=load_prices())


async def test_s07_ac1_a_follow_up_sends_the_history_and_records_every_step() -> None:
    model = ScriptedModel(
        [
            [THOUGHT, CALL],
            [ANSWER],
            [{"type": "model_output", "content": [{"type": "text", "text": "Round two."}]}],
        ]
    )
    recorded: list[Step] = []
    h = harness(model)
    first = await h.run("Which customers?", record=recorded.extend)
    assert first.outcome == "completed"
    assert [s["type"] for s in recorded] == [
        "user_input",
        "thought",
        "function_call",
        "function_result",
        "model_output",
    ]
    second = await h.run("And their uptime?", history=recorded)
    assert second.outcome == "completed"
    assert model.sent[-1][:5] == recorded  # round one, exactly as it was
    assert model.sent[-1][-1]["content"][0]["text"] == "And their uptime?"


async def test_s07_a_run_that_never_got_a_reply_leaves_nothing_in_the_history() -> None:
    model = ScriptedModel([], fail=ModelError("boom"))
    recorded: list[Step] = []
    result = await harness(model).run("Hi", record=recorded.extend)
    assert result.outcome == "failed"
    assert recorded == []  # a question with no reply would be a dangling turn


def _unused(_: Any) -> None:  # keeps the Any import honest for type checkers
    return None
