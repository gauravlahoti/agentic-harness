"""The model boundary (S01-AC2, S01-AC3, S01-AC4).

One interface for any model; Gemini gets the whole history with store=False;
FakeModel replays real recorded replies.
"""

import inspect
from collections.abc import Callable
from types import SimpleNamespace
from typing import Any

import pytest

from agentic_harness.config import Secret, Settings
from agentic_harness.model import FakeModel, GeminiModel, ModelClient, ModelError, ModelReply

Recorded = Callable[[str], dict[str, Any]]
HISTORY = [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}]


class FakeSdkReply:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self.data


class FakeSdk:
    """Stands in for google.genai.Client: records exactly what GeminiModel sends."""

    def __init__(self, reply: dict[str, Any] | None = None, error: Exception | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.reply, self.error = reply, error
        self.aio = SimpleNamespace(interactions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> FakeSdkReply:
        self.sent.append(kwargs)
        if self.error:
            raise self.error
        return FakeSdkReply(self.reply or {})


def test_s01_ac2_model_client_has_one_method() -> None:
    methods = [
        name
        for name, member in vars(ModelClient).items()
        if inspect.isfunction(member) and not name.startswith("_")
    ]
    assert methods == ["create"]
    assert list(inspect.signature(ModelClient.create).parameters) == [
        "self",
        "system",
        "steps",
        "tools",
    ]


def test_s01_ac2_both_models_fit_the_interface(recorded: Recorded) -> None:
    gemini = GeminiModel(Settings(), client=FakeSdk())
    fake = FakeModel([recorded("01_text")])
    for model in (gemini, fake):
        assert isinstance(model, ModelClient)


async def test_s01_ac3_gemini_sends_full_history_stateless(recorded: Recorded) -> None:
    sdk = FakeSdk(reply=recorded("01_text"))
    model = GeminiModel(Settings(model="gemini-test"), client=sdk)
    tools = [{"type": "function", "name": "t", "description": "d", "parameters": {}}]
    await model.create("be brief", HISTORY, tools)
    sent = sdk.sent[0]
    assert sent["store"] is False
    assert "previous_interaction_id" not in sent
    assert sent["input"] == HISTORY  # the whole history, every time
    assert sent["system_instruction"] == "be brief"
    assert sent["tools"] == tools
    assert sent["model"] == "gemini-test"
    assert sent["automatic_continuation"] is False  # D-29: no hidden extra calls


async def test_s01_ac3_no_tools_means_no_tools_field(recorded: Recorded) -> None:
    sdk = FakeSdk(reply=recorded("01_text"))
    await GeminiModel(Settings(), client=sdk).create("s", HISTORY, [])
    assert "tools" not in sdk.sent[0]


async def test_s01_ac3_api_errors_become_model_errors_without_the_key() -> None:
    key = "AIza-secret-for-test"
    sdk = FakeSdk(error=RuntimeError(f"503 high demand (key {key})"))
    model = GeminiModel(Settings(api_key=Secret(key)), client=sdk)
    with pytest.raises(ModelError) as error:
        await model.create("s", HISTORY, [])
    assert "503 high demand" in str(error.value)
    assert key not in str(error.value)


def test_s01_ac3_live_model_needs_a_key() -> None:
    from agentic_harness.config import MissingKeyError

    with pytest.raises(MissingKeyError):
        GeminiModel(Settings())


async def test_s01_ac4_fake_replays_recorded_replies_in_order(recorded: Recorded) -> None:
    fake = FakeModel([recorded("02_tool_call"), recorded("03_tool_round_trip")])
    first = await fake.create("s", HISTORY, [])
    second = await fake.create("s", HISTORY, [])
    assert first.status == "requires_action"
    assert [c["name"] for c in first.tool_calls] == ["get_time"]
    assert second.status == "completed"
    assert "UTC" in second.text
    assert fake.name == "gemini-3.5-flash-lite"  # taken from the recording


async def test_s01_ac4_fake_records_what_it_was_sent(recorded: Recorded) -> None:
    fake = FakeModel([recorded("01_text")])
    await fake.create("system text", HISTORY, [])
    assert fake.requests == [{"system": "system text", "steps": HISTORY, "tools": []}]


async def test_s01_ac4_fake_runs_out_loudly(recorded: Recorded) -> None:
    fake = FakeModel([recorded("01_text")])
    await fake.create("s", HISTORY, [])
    with pytest.raises(ModelError, match="no scripted reply"):
        await fake.create("s", HISTORY, [])


def test_s01_ac4_reply_reads_text_and_calls(recorded: Recorded) -> None:
    reply = ModelReply.from_dict(recorded("04_two_calls"))
    assert [c["arguments"]["timezone"] for c in reply.tool_calls] == ["UTC", "Asia/Tokyo"]
    assert reply.text == ""
    assert ModelReply.from_dict(recorded("01_text")).text == "Hello there friend."
