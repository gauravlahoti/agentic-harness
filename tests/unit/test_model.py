"""The model boundary (S01-AC2, S01-AC3): one interface; Gemini gets the whole history.

These tests check the *request we build*, not the model's answers. A stand-in for the
SDK's network call records exactly what GeminiModel sends. How well the agent answers is
for the evals (S08), against real Gemini.
"""

import inspect
from types import SimpleNamespace
from typing import Any

import pytest

from agentic_harness.config import MissingKeyError, Secret, Settings
from agentic_harness.model import GeminiModel, ModelClient, ModelError, ModelReply

HISTORY = [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}]
REPLY = {
    "status": "completed",
    "model": "gemini-test",
    "steps": [{"type": "model_output", "content": [{"type": "text", "text": "Hello."}]}],
}


class SdkReply:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self.data


class RecordingSdk:
    """Stands in for google.genai.Client's network call and records what was sent."""

    def __init__(self, error: Exception | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.error = error
        self.aio = SimpleNamespace(interactions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs: Any) -> SdkReply:
        self.sent.append(kwargs)
        if self.error:
            raise self.error
        return SdkReply(REPLY)


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
    assert isinstance(GeminiModel(Settings(), client=RecordingSdk()), ModelClient)


async def test_s01_ac3_gemini_sends_full_history_stateless() -> None:
    sdk = RecordingSdk()
    model = GeminiModel(Settings(model="gemini-test"), client=sdk)
    tools = [{"type": "function", "name": "t", "description": "d", "parameters": {}}]
    reply = await model.create("be brief", HISTORY, tools)
    sent = sdk.sent[0]
    assert sent["store"] is False
    assert "previous_interaction_id" not in sent
    assert sent["input"] == HISTORY  # the whole history, every time
    assert sent["system_instruction"] == "be brief"
    assert sent["tools"] == tools
    assert sent["model"] == "gemini-test"
    assert sent["automatic_continuation"] is False  # D-29: no hidden extra calls
    assert reply.text == "Hello."


async def test_s01_ac3_no_tools_means_no_tools_field() -> None:
    sdk = RecordingSdk()
    await GeminiModel(Settings(), client=sdk).create("s", HISTORY, [])
    assert "tools" not in sdk.sent[0]


async def test_s01_ac3_api_errors_become_model_errors_without_the_key() -> None:
    key = "test-value-not-a-real-key"
    sdk = RecordingSdk(error=RuntimeError(f"503 high demand (key {key})"))
    model = GeminiModel(Settings(api_key=Secret(key)), client=sdk)
    with pytest.raises(ModelError) as error:
        await model.create("s", HISTORY, [])
    assert "503 high demand" in str(error.value)
    assert key not in str(error.value)


def test_s01_ac3_live_model_needs_a_key() -> None:
    with pytest.raises(MissingKeyError):
        GeminiModel(Settings())


def test_s01_ac3_reply_reads_text_and_tool_calls() -> None:
    reply = ModelReply.from_dict(
        {
            "status": "requires_action",
            "steps": [
                {"type": "thought", "signature": "abc"},
                {"type": "function_call", "id": "c1", "name": "t", "arguments": {}},
                {"type": "function_call", "id": "c2", "name": "t", "arguments": {}},
            ],
        }
    )
    assert [c["id"] for c in reply.tool_calls] == ["c1", "c2"]
    assert reply.text == ""
