"""Claude as a second provider (S09-AC10 to AC14; D-102 to D-104).

The person pays for Claude, so nothing here calls Anthropic: a stand-in for the SDK records
what would be sent and answers with replies shaped like the Messages API's.
"""

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from agentic_harness.anthropic_model import AnthropicModel, from_message, to_messages
from agentic_harness.config import CLAUDE_SMALL_MODEL, Secret, Settings, load_settings
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.model import GeminiModel, ModelError, make_model
from agentic_harness.pricing import load_prices
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.tools.registry import tool
from agentic_harness.workspace import Workspace

KEY = "test-claude-key-not-real"
CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
THINKING = {"type": "thinking", "thinking": "", "signature": "c2lnLWNsYXVkZQ=="}


class Reply:
    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    def model_dump(self, **_: Any) -> dict[str, Any]:
        return self.data


class RecordingClaude:
    """Stands in for anthropic.AsyncAnthropic: records requests, plays back replies."""

    def __init__(self, replies: list[dict[str, Any]], error: Exception | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.replies = replies
        self.error = error
        self.messages = SimpleNamespace(create=self._create)

    async def _create(self, **kwargs: Any) -> Reply:
        self.sent.append(kwargs)
        if self.error:
            raise self.error
        return Reply(self.replies.pop(0))


def reply(content: list[dict[str, Any]], stop: str, **usage: int) -> dict[str, Any]:
    base = {"input_tokens": 100, "output_tokens": 20}
    return {
        "model": "claude-haiku-5-5",
        "content": content,
        "stop_reason": stop,
        "usage": base | usage,
    }


def claude(replies: list[dict[str, Any]], effort: str | None = None, **kw: Any) -> AnthropicModel:
    settings = Settings(model="claude-haiku-5-5", thinking=effort, anthropic_key=Secret(KEY))
    return AnthropicModel(settings, client=RecordingClaude(replies, **kw))


@tool(risk="read")
def find(item: str) -> str:
    """Find a record."""
    return f"found {item}"


# ── AC11: the steps translate both ways ─────────────────────────────────────────────


def test_s09_ac11_steps_become_claude_messages() -> None:
    steps = [
        {"type": "user_input", "content": [{"type": "text", "text": "Find X"}]},
        {"type": "thought", "provider": "anthropic", "block": THINKING},
        {"type": "function_call", "id": "toolu_1", "name": "find", "arguments": {"item": "X"}},
        {
            "type": "function_result",
            "name": "find",
            "call_id": "toolu_1",
            "result": [{"type": "text", "text": "found X"}],
            "is_error": True,
        },
        {"type": "model_output", "content": [{"type": "text", "text": "Done."}]},
        {"type": "user_input", "content": [{"type": "text", "text": "Thanks"}]},
    ]
    messages = to_messages(steps)
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant", "user"]
    assert messages[1]["content"][0] == THINKING  # Claude's own thinking, exactly as sent
    assert messages[1]["content"][1] == {
        "type": "tool_use",
        "id": "toolu_1",
        "name": "find",
        "input": {"item": "X"},
    }
    result = messages[2]["content"][0]
    assert (result["type"], result["tool_use_id"], result["is_error"]) == (
        "tool_result",
        "toolu_1",
        True,
    )


def test_s09_ac11_a_gemini_thought_is_left_out_for_claude_and_back() -> None:
    gemini_thought = {"type": "thought", "signature": "Z2VtaW5p", "summary": []}
    steps = [
        {"type": "user_input", "content": [{"type": "text", "text": "Hi"}]},
        gemini_thought,
        {"type": "model_output", "content": [{"type": "text", "text": "Hello"}]},
    ]
    sent = to_messages(steps)
    assert sent[1]["content"] == [{"type": "text", "text": "Hello"}]  # no Gemini thought


async def test_s09_ac11_gemini_never_sees_claudes_thinking() -> None:
    from tests.unit.test_model import RecordingSdk  # the Gemini stand-in

    sdk = RecordingSdk()
    steps = [
        {"type": "user_input", "content": [{"type": "text", "text": "Hi"}]},
        {"type": "thought", "provider": "anthropic", "block": THINKING},
        {"type": "model_output", "content": [{"type": "text", "text": "Hello"}]},
    ]
    await GeminiModel(Settings(), client=sdk).create("s", steps, [])
    assert all(s.get("provider") != "anthropic" for s in sdk.sent[0]["input"])


def test_s09_ac11_a_claude_reply_becomes_steps_and_usage() -> None:
    data = reply(
        [
            THINKING,
            {"type": "text", "text": "Let me look."},
            {"type": "tool_use", "id": "toolu_9", "name": "find", "input": {"item": "Y"}},
        ],
        "tool_use",
        cache_read_input_tokens=400,
        cache_creation_input_tokens=50,
    )
    out = from_message(data, "claude-haiku-5-5")
    assert out.status == "requires_action"
    assert [s["type"] for s in out.steps] == ["thought", "model_output", "function_call"]
    assert out.steps[0] == {"type": "thought", "provider": "anthropic", "block": THINKING}
    assert out.tool_calls[0]["arguments"] == {"item": "Y"}
    assert out.usage == {
        "total_input_tokens": 550,
        "total_cached_tokens": 400,
        "total_cache_write_tokens": 50,
        "total_output_tokens": 20,
    }
    assert from_message(reply([], "max_tokens"), "m").status == "incomplete"
    assert from_message(reply([], "refusal"), "m").status == "refused"


# ── AC10 / AC12: requests, effort, cost ─────────────────────────────────────────────


async def test_s09_ac12_effort_maps_to_output_config_and_auto_sends_nothing() -> None:
    answer = reply([{"type": "text", "text": "ok"}], "end_turn")
    high = claude([answer], effort="high")
    await high.create(
        "be brief", [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}], []
    )
    sent = high._client.sent[0]
    assert sent["output_config"] == {"effort": "high"}
    assert sent["system"] == "be brief"
    assert sent["model"] == "claude-haiku-5-5"
    assert "thinking" not in sent  # adaptive thinking is these models' default
    auto = claude([dict(answer)])
    await auto.create(
        "s", [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}], []
    )
    assert "output_config" not in auto._client.sent[0]


async def test_s09_ac10_tools_are_declared_in_claudes_shape() -> None:
    model = claude([reply([{"type": "text", "text": "ok"}], "end_turn")])
    await model.create(
        "s",
        [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}],
        [find.declaration()],
    )
    declared = model._client.sent[0]["tools"][0]
    assert declared["name"] == "find"
    assert declared["input_schema"]["properties"]["item"]["type"] == "string"


def test_s09_ac12_claude_calls_are_priced_with_cache_reads_and_writes() -> None:
    prices = load_prices()
    usage = {"total_input_tokens": 1_000_000, "total_cached_tokens": 0, "total_output_tokens": 0}
    assert prices.cost("claude-haiku-5-5", usage) == pytest.approx(0.10)
    assert prices.cost("claude-sonnet-5-5", usage) == pytest.approx(2.00)
    read = usage | {"total_cached_tokens": 1_000_000}
    assert prices.cost("claude-sonnet-5-5", read) == pytest.approx(0.20)
    write = usage | {"total_cache_write_tokens": 1_000_000}
    assert prices.cost("claude-sonnet-5-5", write) == pytest.approx(2.50)  # 1.25x input


async def test_s09_ac10_a_run_on_claude_goes_through_the_same_loop() -> None:
    model = claude(
        [
            reply(
                [
                    THINKING,
                    {"type": "tool_use", "id": "toolu_1", "name": "find", "input": {"item": "X"}},
                ],
                "tool_use",
            ),
            reply([{"type": "text", "text": "X is found."}], "end_turn"),
        ]
    )
    result = await Harness(model, Limits(), [find], prices=load_prices()).run("Find X")
    assert result.outcome == "completed"
    assert result.answer == "X is found."
    second = model._client.sent[1]["messages"]
    assert second[1]["content"][0] == THINKING  # thinking passed back unchanged
    assert second[2]["content"][0]["content"][0]["text"] == "found X"
    assert result.usd > 0


async def test_s09_ac10_errors_are_named_and_the_key_never_shows() -> None:
    class RateLimitedError(Exception):
        def __init__(self) -> None:
            super().__init__("rate limited")
            self.status_code = 429
            self.body = {"error": {"message": f"Rate limited for key {KEY}"}}

    model = claude([], error=RateLimitedError())
    with pytest.raises(ModelError) as caught:
        await model.create(
            "s", [{"type": "user_input", "content": [{"type": "text", "text": "hi"}]}], []
        )
    assert str(caught.value).startswith("Claude 429:")
    assert KEY not in str(caught.value)


def test_s09_ac10_a_claude_name_gets_the_claude_client() -> None:
    settings = Settings(model="claude-sonnet-5-5", anthropic_key=Secret(KEY))
    assert type(make_model(settings)).__name__ == "AnthropicModel"
    assert isinstance(
        make_model(Settings(model="gemini-3.5-flash-lite", api_key=Secret("g"))), GeminiModel
    )


# ── AC10 / AC14: the page offers Claude only with its key; the key stays secret ──────


def page(tmp_path: Path, settings: Settings, built: list[Settings]) -> TestClient:
    def factory(s: Settings) -> Any:
        built.append(s)
        return GeminiModel(s, client=object())  # never called

    app = create_app(
        settings,
        project_root=tmp_path,
        workspace=Workspace.load(CLOUDCO),
        trace_dir=tmp_path,
        model_factory=factory,
    )
    return TestClient(app, base_url="http://127.0.0.1")


def test_s09_ac10_claude_is_offered_only_when_its_key_is_set(tmp_path: Path) -> None:
    without = page(tmp_path, Settings(api_key=Secret("g")), []).get("/api/health").json()
    assert not any(m.startswith("claude-") for m in without["models"])
    with_key = (
        page(tmp_path, Settings(api_key=Secret("g"), anthropic_key=Secret(KEY)), [])
        .get("/api/health")
        .json()
    )
    assert {"claude-haiku-5-5", "claude-sonnet-5-5"} <= set(with_key["models"])
    assert with_key["claude_small_model"] == CLAUDE_SMALL_MODEL  # the pane shows helpers' model
    assert without["claude_small_model"] is None
    refused = page(tmp_path, Settings(api_key=Secret("g")), []).post(
        "/api/run", headers=PAGE_HEADER, json={"task": "hi", "model": "claude-sonnet-5-5"}
    )
    assert refused.status_code == 400
    assert "ANTHROPIC_API_KEY" in refused.json()["detail"]


def test_s09_ac13_a_claude_runs_small_calls_use_haiku(tmp_path: Path) -> None:
    built: list[Settings] = []
    web = page(tmp_path, Settings(anthropic_key=Secret(KEY)), built)
    web.post(
        "/api/run",
        headers=PAGE_HEADER,
        json={"task": "hi", "profile": "sales", "model": "claude-sonnet-5-5"},
    )
    names = [s.model for s in built]
    assert names[0] == "claude-sonnet-5-5"  # the run itself
    assert set(names[1:]) == {CLAUDE_SMALL_MODEL}  # helper, check, summary, title: Haiku


def test_s09_ac14_the_claude_key_is_read_from_its_own_name(tmp_path: Path) -> None:
    env = tmp_path / ".env"
    env.write_text("")
    settings = load_settings(env, {"ANTHROPIC_API_KEY": KEY})
    assert settings.has_anthropic_key
    assert repr(settings.anthropic_key) == "***"
    assert not settings.has_key  # it is not a Gemini key


def test_s09_ac14_no_live_test_calls_claude() -> None:
    """The person pays for Claude: `make live` must never name a Claude model (D-104)."""
    live = Path(__file__).resolve().parents[1] / "live"
    named = [p.name for p in live.glob("*.py") if "claude-" in p.read_text()]
    assert named == []
