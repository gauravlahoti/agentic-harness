"""The model boundary: one interface and the Gemini client (S01-AC2, S01-AC3).

Harness part: the model. The loop only ever calls ``create(system, steps, tools)``.
Steps are plain dicts in Gemini's own format, kept exactly as received (D-05, D-22).

GeminiModel: stateless (``store=False``, the whole history every call, never
``previous_interaction_id``; D-04), no hidden SDK calls (D-29).
Every answer comes from a real Gemini model; there is no fake model (D-32).

Does not: run tools, count cost, or decide when to stop. The loop does.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from agentic_harness.config import Settings

Step = dict[str, Any]

MAX_ATTEMPTS = 2  # one retry for a blip; a busy model fails fast instead of waiting minutes


class ModelError(RuntimeError):
    """The model could not answer (overloaded, bad request, no credit, timeout…)."""


@dataclass(frozen=True, slots=True)
class ModelReply:
    """One model reply. ``steps`` are exactly what the model sent."""

    steps: list[Step]
    status: str
    usage: dict[str, Any] = field(default_factory=dict)
    model: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelReply":
        return cls(
            steps=list(data.get("steps", [])),
            status=str(data.get("status", "")),
            usage=dict(data.get("usage", {})),
            model=str(data.get("model", "")),
        )

    @property
    def tool_calls(self) -> list[Step]:
        """Gemini has no "tool_use" stop reason: a reply asks for tools by containing them."""
        return [step for step in self.steps if step.get("type") == "function_call"]

    @property
    def text(self) -> str:
        return "".join(
            part.get("text", "")
            for step in self.steps
            if step.get("type") == "model_output"
            for part in step.get("content", [])
            if part.get("type") == "text"
        )


@runtime_checkable
class ModelClient(Protocol):
    """Anything the loop can talk to. One method; ``name`` is used for pricing."""

    name: str

    async def create(self, system: str, steps: Sequence[Step], tools: Sequence[Step]) -> ModelReply:
        """Send the full history; return the model's next reply."""
        ...


class GeminiModel:
    """Gemini through the Interactions API, stateless."""

    def __init__(self, settings: Settings, *, client: Any = None) -> None:
        self.name = settings.model
        self._secret = settings.api_key.reveal() if settings.api_key else ""
        self._client = client or _make_client(settings)

    async def create(self, system: str, steps: Sequence[Step], tools: Sequence[Step]) -> ModelReply:
        request: dict[str, Any] = {
            "model": self.name,
            "store": False,  # we own the history (D-04)
            "automatic_continuation": False,  # no hidden extra calls (D-29)
            "system_instruction": system,
            "input": list(steps),
        }
        if tools:
            request["tools"] = list(tools)
        try:
            reply = await self._client.aio.interactions.create(**request)
        except Exception as error:  # every SDK failure becomes one named error for the loop
            raise ModelError(self._describe(error)) from error
        return ModelReply.from_dict(reply.model_dump(mode="json", exclude_none=True))

    def _describe(self, error: Exception) -> str:
        text = f"{type(error).__name__}: {error}"
        if self._secret:
            text = text.replace(self._secret, "***")
        return text[:500]


def _make_client(settings: Settings) -> Any:
    """Build the SDK client. Imported here so offline code never loads the SDK."""
    from google import genai
    from google.genai import types

    http = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=MAX_ATTEMPTS))
    if settings.backend == "agent_platform":
        return genai.Client(
            vertexai=True, project=settings.project, location=settings.location, http_options=http
        )
    return genai.Client(api_key=settings.require_key(), http_options=http)
