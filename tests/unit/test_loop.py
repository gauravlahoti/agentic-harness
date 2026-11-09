"""The loop (S01-AC5 … S01-AC10), driven by real recorded Gemini replies."""

import asyncio
import copy
from collections.abc import Callable, Sequence
from typing import Any

import pytest

from agentic_harness.events import Event
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.model import FakeModel, ModelError, ModelReply
from agentic_harness.pricing import Prices
from agentic_harness.tools import Tool

Recorded = Callable[[str], dict[str, Any]]
PRICES = Prices({"gemini-3.5-flash-lite": {"input": 0.30, "output": 2.50, "cached_input": 0.03}})


def time_tool(log: list[str] | None = None) -> Tool:
    def get_time(timezone: str) -> str:
        if log is not None:
            log.append(timezone)
        if "/" in timezone and not timezone.startswith(("Asia/", "Europe/")):
            raise ValueError(f"Unknown time zone: {timezone}")
        return f"2026-11-10T09:30:00 ({timezone})"

    return Tool(
        name="get_time",
        description="Current time in a time zone.",
        parameters={"type": "object", "properties": {"timezone": {"type": "string"}}},
        function=get_time,
    )


def harness(model: Any, tools: Sequence[Tool] = (), **limits: Any) -> tuple[Harness, list[Event]]:
    events: list[Event] = []
    h = Harness(model, Limits(**limits), tools, prices=PRICES)
    h.subscribe(events.append)
    return h, events


# ── AC5 · plain answer ───────────────────────────────────────────────────────


async def test_s01_ac5_plain_answer_is_one_call(recorded: Recorded) -> None:
    model = FakeModel([recorded("01_text")])
    result = await harness(model)[0].run("Say hello")
    assert result.outcome == "completed"
    assert result.model_calls == 1
    assert result.answer == "Hello there friend."


# ── AC6 · tool round trip ────────────────────────────────────────────────────


async def test_s01_ac6_tool_round_trip_is_two_calls(recorded: Recorded) -> None:
    model = FakeModel([recorded("02_tool_call"), recorded("03_tool_round_trip")])
    result = await harness(model, [time_tool()])[0].run("What time is it in UTC?")
    assert result.outcome == "completed"
    assert result.model_calls == 2
    call = ModelReply.from_dict(recorded("02_tool_call")).tool_calls[0]
    sent_result = model.requests[1]["steps"][-1]
    assert sent_result["type"] == "function_result"
    assert sent_result["call_id"] == call["id"]
    assert sent_result["name"] == "get_time"
    assert "09:30" in sent_result["result"][0]["text"]


# ── AC7 · two calls in one reply ─────────────────────────────────────────────


async def test_s01_ac7_two_calls_run_in_order_and_return_together(recorded: Recorded) -> None:
    log: list[str] = []
    model = FakeModel([recorded("04_two_calls"), recorded("03_tool_round_trip")])
    await harness(model, [time_tool(log)])[0].run("Time in UTC and Tokyo?")
    assert log == ["UTC", "Asia/Tokyo"]
    second_request = model.requests[1]["steps"]
    results = [s for s in second_request if s["type"] == "function_result"]
    calls = ModelReply.from_dict(recorded("04_two_calls")).tool_calls
    assert [r["call_id"] for r in results] == [c["id"] for c in calls]
    assert second_request[-2:] == results  # sent together, right after the calls


# ── AC8 · model steps kept exactly ───────────────────────────────────────────


async def test_s01_ac8_model_steps_are_sent_back_unchanged(recorded: Recorded) -> None:
    original = recorded("02_tool_call")
    pristine = copy.deepcopy(original["steps"])
    model = FakeModel([original, recorded("03_tool_round_trip")])
    await harness(model, [time_tool()])[0].run("What time is it in UTC?")
    second_request = model.requests[1]["steps"]
    assert second_request[1 : 1 + len(pristine)] == pristine  # same order, same bytes
    assert any("signature" in step for step in second_request)  # thought signature survived


# ── AC9 · stop rules ─────────────────────────────────────────────────────────


async def test_s01_ac9_step_limit_stops_with_a_reason(recorded: Recorded) -> None:
    # The model keeps asking for tools (as in recording 05); the limit ends it.
    model = FakeModel([recorded("04_two_calls"), recorded("05_two_results")] * 3)
    result = await harness(model, [time_tool()], max_steps=2)[0].run("Loop forever")
    assert result.outcome == "stopped"
    assert result.reason == "step_limit"
    assert result.model_calls == 2


async def test_s01_ac9_cost_limit_stops_with_a_reason(recorded: Recorded) -> None:
    model = FakeModel([recorded("04_two_calls"), recorded("05_two_results")])
    result = await harness(model, [time_tool()], max_usd=0.000_000_1)[0].run("Expensive")
    assert result.outcome == "stopped"
    assert result.reason == "cost_limit"
    assert result.usd > 0


async def test_s01_ac9_time_limit_while_waiting_for_the_model(recorded: Recorded) -> None:
    class SlowModel(FakeModel):
        async def create(self, system: str, steps: Sequence[Any], tools: Sequence[Any]) -> Any:
            await asyncio.sleep(5)
            return await super().create(system, steps, tools)

    result = await harness(SlowModel([recorded("01_text")]), max_seconds=0.2)[0].run("Slow")
    assert result.outcome == "stopped"
    assert result.reason == "time_limit"


async def test_s01_ac9_cost_includes_thought_tokens(recorded: Recorded) -> None:
    reply = recorded("01_text")
    reply["usage"] = {
        "total_input_tokens": 0,
        "total_output_tokens": 0,
        "total_thought_tokens": 1_000_000,
    }
    result = await harness(FakeModel([reply]))[0].run("Think hard")
    assert result.usd == pytest.approx(2.50)


async def test_s01_ac9_output_limit_is_a_named_stop(recorded: Recorded) -> None:
    result = await harness(FakeModel([recorded("08_max_tokens")]))[0].run("List primes")
    assert result.outcome == "stopped"
    assert result.reason == "output_limit"
    assert result.answer.startswith("To list the first 200 prime numbers")


# ── AC10 · unexpected status and errors are loud ─────────────────────────────


@pytest.mark.parametrize("status", ["failed", "cancelled", "in_progress", "something_new"])
async def test_s01_ac10_unexpected_status_is_a_named_error(recorded: Recorded, status: str) -> None:
    reply = recorded("01_text")
    reply["status"] = status
    result = await harness(FakeModel([reply]))[0].run("Hi")
    assert result.outcome == "failed"
    assert result.reason == f"unexpected_status: {status}"
    assert result.model_calls == 1  # no silent retry loop


async def test_s01_ac10_waiting_for_action_without_a_tool_call_is_an_error(
    recorded: Recorded,
) -> None:
    reply = recorded("01_text")
    reply["status"] = "requires_action"
    result = await harness(FakeModel([reply]))[0].run("Hi")
    assert result.outcome == "failed"
    assert result.reason == "unexpected_status: requires_action"


async def test_s01_ac10_model_error_ends_the_run(recorded: Recorded) -> None:
    class BrokenModel(FakeModel):
        async def create(self, system: str, steps: Sequence[Any], tools: Sequence[Any]) -> Any:
            raise ModelError("503 high demand")

    result = await harness(BrokenModel([recorded("01_text")]))[0].run("Hi")
    assert result.outcome == "failed"
    assert result.reason == "model_error: 503 high demand"


async def test_s01_ac10_tool_errors_go_back_to_the_model(recorded: Recorded) -> None:
    model = FakeModel([recorded("06_tool_error_call"), recorded("07_tool_error_reply")])
    result = await harness(model, [time_tool()])[0].run("Time on Mars?")
    assert result.outcome == "completed"
    sent = model.requests[1]["steps"][-1]
    assert sent["is_error"] is True
    assert "Unknown time zone" in sent["result"][0]["text"]


async def test_s01_ac10_unknown_tool_goes_back_as_an_error(recorded: Recorded) -> None:
    model = FakeModel([recorded("02_tool_call"), recorded("03_tool_round_trip")])
    result = await harness(model, tools=[])[0].run("What time is it?")  # get_time not offered
    assert result.outcome == "completed"
    sent = model.requests[1]["steps"][-1]
    assert sent["is_error"] is True
    assert "Unknown tool: get_time" in sent["result"][0]["text"]


async def test_s01_ac10_async_tools_work_too(recorded: Recorded) -> None:
    async def get_time(timezone: str) -> dict[str, str]:
        return {"time": "09:30", "timezone": timezone}

    tool = Tool("get_time", "Time.", {"type": "object"}, get_time)
    model = FakeModel([recorded("02_tool_call"), recorded("03_tool_round_trip")])
    await harness(model, [tool])[0].run("Time?")
    assert '"time": "09:30"' in model.requests[1]["steps"][-1]["result"][0]["text"]


# ── AC11 · events (trace file tested in test_trace.py) ───────────────────────


async def test_s01_ac11_every_step_emits_an_event(recorded: Recorded) -> None:
    model = FakeModel([recorded("02_tool_call"), recorded("03_tool_round_trip")])
    h, events = harness(model, [time_tool()])
    result = await h.run("What time is it in UTC?")
    assert [e.type for e in events] == [
        "run_started",
        "model_called",
        "model_replied",
        "tool_started",
        "tool_finished",
        "model_called",
        "model_replied",
        "run_finished",
    ]
    assert [e.seq for e in events] == list(range(1, 9))
    assert {e.run_id for e in events} == {result.run_id}
    assert events[-1].data["outcome"] == "completed"
    assert events[2].data["steps"] == recorded("02_tool_call")["steps"]  # full steps, for replay
