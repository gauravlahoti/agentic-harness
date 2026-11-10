"""Claude as a second model provider, behind the same boundary as Gemini (S09; D-102).

Harness part: the model. The loop speaks one step format (Gemini's: ``user_input``,
``model_output``, ``thought``, ``function_call``, ``function_result``). This class turns
those steps into Claude's Messages API shape and turns Claude's reply back into steps, so
the loop, tools, gate and approvals don't know which provider answered.

    user_input                        → user message, text block
    model_output / function_call      → assistant message: text / tool_use blocks
    thought (from Claude)             → the thinking block, exactly as Claude sent it
    thought (from Gemini)             → left out: one provider can't read the other's
    function_result                   → user message, tool_result blocks

Effort maps to ``output_config.effort`` (Auto sends nothing: the model's own default).
Thinking stays on (adaptive): on these models effort is the control, not a budget.
Retries are off, as for Gemini (D-42): a 429 is a clear error, never a hidden sleep.

The person pays for Claude (D-104): tests use a recorded stand-in for the SDK, never the API.

Does not: run tools, count cost, or decide when to stop. The loop does.
"""

from collections.abc import Sequence
from typing import Any

from agentic_harness.config import Settings
from agentic_harness.model import ModelError, ModelReply, Step

PROVIDER = "anthropic"
MAX_TOKENS = 16_000  # per reply; non-streaming stays well inside the SDK's timeout
STOP_TO_STATUS = {
    "end_turn": "completed",
    "stop_sequence": "completed",
    "tool_use": "requires_action",
    "max_tokens": "incomplete",
    "pause_turn": "requires_action",
    "refusal": "refused",  # the loop ends the run with this named reason
}


class AnthropicModel:
    """Claude through the Messages API, stateless: the whole history every call."""

    def __init__(self, settings: Settings, *, client: Any = None) -> None:
        self.name = settings.model
        self.thinking = settings.thinking  # low | medium | high, or None for the default
        self._secret = settings.anthropic_key.reveal() if settings.anthropic_key else ""
        self._client = client or _make_client(settings)

    async def create(self, system: str, steps: Sequence[Step], tools: Sequence[Step]) -> ModelReply:
        request: dict[str, Any] = {
            "model": self.name,
            "max_tokens": MAX_TOKENS,
            "system": system,
            "messages": to_messages(steps),
            # Cache the stable start (tools, system, earlier turns): cheaper on every
            # follow-up call. Writes cost 1.25x and are priced as such (pricing.py).
            "cache_control": {"type": "ephemeral"},
        }
        if tools:
            request["tools"] = [to_tool(t) for t in tools]
        if self.thinking:
            request["output_config"] = {"effort": self.thinking}
        try:
            reply = await self._client.messages.create(**request)
        except Exception as error:  # every SDK failure becomes one named error for the loop
            raise ModelError(self._describe(error)) from error
        return from_message(reply.model_dump(mode="json", exclude_none=True), self.name)

    def _describe(self, error: Exception) -> str:
        code = getattr(error, "status_code", None)
        body = getattr(error, "body", None)
        said = body.get("error", {}).get("message") if isinstance(body, dict) else None
        text = (
            f"Claude {code}: {said or error}"
            if code
            else f"Claude: {type(error).__name__}: {error}"
        )
        if self._secret:
            text = text.replace(self._secret, "***")
        return text[:500]


def to_tool(declaration: Step) -> dict[str, Any]:
    """A tool as the loop declares it (Gemini's shape) → Claude's tool definition."""
    return {
        "name": declaration["name"],
        "description": declaration.get("description", ""),
        "input_schema": declaration.get("parameters") or {"type": "object", "properties": {}},
    }


def to_messages(steps: Sequence[Step]) -> list[dict[str, Any]]:
    """The loop's steps → Claude's alternating user / assistant messages."""
    messages: list[dict[str, Any]] = []

    def add(role: str, block: dict[str, Any]) -> None:
        if messages and messages[-1]["role"] == role:
            messages[-1]["content"].append(block)  # same speaker: one message
        else:
            messages.append({"role": role, "content": [block]})

    for step in steps:
        kind = step.get("type")
        if kind == "user_input":
            text = "".join(p.get("text", "") for p in step.get("content", []))
            add("user", {"type": "text", "text": text})
        elif kind == "model_output":
            text = "".join(p.get("text", "") for p in step.get("content", []))
            if text:
                add("assistant", {"type": "text", "text": text})
        elif kind == "thought":
            if step.get("provider") == PROVIDER and isinstance(step.get("block"), dict):
                add("assistant", step["block"])  # exactly as Claude sent it
            # A Gemini thought can't be read by Claude: left out (D-102).
        elif kind == "function_call":
            add(
                "assistant",
                {
                    "type": "tool_use",
                    "id": step.get("id", ""),
                    "name": step.get("name", ""),
                    "input": step.get("arguments") or {},
                },
            )
        elif kind == "function_result":
            text = "".join(p.get("text", "") for p in step.get("result", []))
            block: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": step.get("call_id", ""),
                "content": [{"type": "text", "text": text}],
            }
            if step.get("is_error"):
                block["is_error"] = True
            add("user", block)
    return messages


def from_message(data: dict[str, Any], model: str) -> ModelReply:
    """Claude's reply → the loop's steps, its status, and usage in the loop's terms."""
    steps: list[Step] = []
    for block in data.get("content", []):
        kind = block.get("type")
        if kind in ("thinking", "redacted_thinking"):
            # Kept whole, signature and all: Claude needs it back unchanged next call.
            steps.append({"type": "thought", "provider": PROVIDER, "block": block})
        elif kind == "text":
            steps.append(
                {"type": "model_output", "content": [{"type": "text", "text": block["text"]}]}
            )
        elif kind == "tool_use":
            steps.append(
                {
                    "type": "function_call",
                    "id": block["id"],
                    "name": block["name"],
                    "arguments": block.get("input") or {},
                }
            )
    usage = data.get("usage", {})
    read = int(usage.get("cache_read_input_tokens") or 0)
    written = int(usage.get("cache_creation_input_tokens") or 0)
    plain = int(usage.get("input_tokens") or 0)
    return ModelReply(
        steps=steps,
        status=STOP_TO_STATUS.get(str(data.get("stop_reason")), str(data.get("stop_reason"))),
        usage={
            # Everything the model read this call, as Gemini reports it, and how much was
            # served from the cache (cheap) or written to it (dearer).
            "total_input_tokens": plain + read + written,
            "total_cached_tokens": read,
            "total_cache_write_tokens": written,
            "total_output_tokens": int(usage.get("output_tokens") or 0),  # includes thinking
        },
        model=str(data.get("model") or model),
    )


def _make_client(settings: Settings) -> Any:
    """Build the SDK client. Imported here so offline code never loads the SDK."""
    import anthropic

    # No SDK retries (D-42): a rate limit must surface as a clear error at once.
    return anthropic.AsyncAnthropic(api_key=settings.require_anthropic_key(), max_retries=0)
