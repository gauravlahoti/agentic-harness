"""The judge: the model DeepEval's metrics ask, through our own model clients (S10-AC5; D-111).

Part of the evals. DeepEval lets you plug in any model as a ``DeepEvalBaseLLM``. Ours wraps
the harness's own ``ModelClient`` (Gemini or Claude), so the judge gets the same things
every run gets: the key only from ``config.py``, no hidden retries (D-42), and real costs
from ``pricing.toml``.

- The judge starts on Gemini Flash-Lite (free tier).
- A 429 (out of quota) or 503 (busy) switches it, for the rest of the eval, to Claude Haiku,
  but only if a Claude key is there (the person pays for Claude, D-104).
- Every other error, or no fallback, raises ``JudgeUnavailableError``: the eval stops and says why.
- ``start()`` / ``taken()`` bracket one metric, so each score names the model(s) that judged
  it and what that cost.

DeepEval's metrics ask for JSON matching a schema; the reply is parsed into that schema.

Does not: decide scores (DeepEval's metric prompts do), or retry.
"""

import asyncio
import re
from collections.abc import Callable
from typing import Any

from deepeval.models import DeepEvalBaseLLM

from agentic_harness.model import ModelClient, ModelError
from agentic_harness.pricing import Prices

BUSY = re.compile(r"\b(429|503)\b")
SYSTEM = (
    "You are an evaluation judge. Follow the instructions in the message exactly. "
    "When asked for JSON, reply with only that JSON, no other text."
)
FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.S)


class JudgeUnavailableError(RuntimeError):
    """No model can judge right now; the eval stops with this message."""


def busy(error: Exception) -> bool:
    """A 429 or 503: the model is out of quota or overloaded, not a bad request."""
    code = getattr(error.__cause__, "status_code", None)
    return code in (429, 503) or bool(BUSY.search(str(error)))


def parse(text: str, schema: Any) -> Any:
    """The judge's text → the pydantic schema DeepEval asked for."""
    body = FENCE.sub("", text.strip())
    start, end = body.find("{"), body.rfind("}")
    if start == -1 or end < start:
        raise ValueError(f"The judge did not reply with JSON: {text[:120]!r}")
    return schema.model_validate_json(body[start : end + 1])


RETRY_NOTE = (
    "\n\nYour last reply did not match the JSON schema asked for. Reply with that JSON only, "
    "with every field in the exact shape asked (lists as lists)."
)


class Judge(DeepEvalBaseLLM):  # type: ignore[misc]  # DeepEval is untyped here (pyproject)
    def __init__(
        self,
        primary: ModelClient,
        prices: Prices,
        fallback: Callable[[], ModelClient] | None = None,
    ) -> None:
        self._primary = primary
        self._active = primary
        self.first = primary.name  # the judge the eval started with
        self._fallback = fallback
        self._prices = prices
        self.switched = ""  # why the judge moved to the fallback, if it did
        self.usd = 0.0  # everything the judge cost in this eval
        self.by_model: dict[str, float] = {}  # per model: Claude is paid, Gemini may be free
        # what the cost panel learns from (D-117): calls made and tokens used
        self.calls = 0
        self.tokens_in = 0
        self.tokens_out = 0
        self._used: list[str] = []
        self._spent = 0.0
        super().__init__(model=primary.name)

    # DeepEvalBaseLLM's interface
    def load_model(self, *args: Any, **kwargs: Any) -> "Judge":
        return self

    def get_model_name(self, *args: Any, **kwargs: Any) -> str:
        return self._active.name

    async def a_generate(self, prompt: str, schema: Any = None) -> Any:
        text = await self._ask(prompt)
        if schema is None:
            return text
        try:
            return parse(text, schema)
        except ValueError:  # pydantic's ValidationError is a ValueError too
            # A reply in the wrong shape is usually a one-off: ask once more, then give up
            # (the metric shows Not Scored, D-118).
            return parse(await self._ask(prompt + RETRY_NOTE), schema)

    def generate(self, prompt: str, schema: Any = None) -> Any:
        # The evals always call ``a_measure``; this sync path exists for DeepEval's interface.
        return asyncio.run(self.a_generate(prompt, schema))

    # One metric at a time: who judged it, and what it cost
    def start(self) -> None:
        self._used, self._spent = [], 0.0

    def taken(self) -> tuple[list[str], float]:
        return list(dict.fromkeys(self._used)), self._spent

    @property
    def current(self) -> str:
        """The model judging now (DeepEval's base class owns ``name``)."""
        return self._active.name

    async def _ask(self, prompt: str) -> str:
        steps = [{"type": "user_input", "content": [{"type": "text", "text": prompt}]}]
        try:
            reply = await self._active.create(SYSTEM, steps, [])
        except ModelError as error:
            if self._active is not self._primary or not busy(error):
                raise JudgeUnavailableError(f"The judge failed: {error}") from error
            if self._fallback is None:
                raise JudgeUnavailableError(
                    f"The judge is out of quota ({error}) and there is no Claude key for "
                    "the fallback judge."
                ) from error
            self._active = self._fallback()
            self.switched = f"{self._primary.name} → {self._active.name}: {str(error)[:200]}"
            try:
                reply = await self._active.create(SYSTEM, steps, [])
            except ModelError as second:
                raise JudgeUnavailableError(f"The fallback judge failed too: {second}") from second
        cost = self._prices.cost(self._active.name, reply.usage)
        self.calls += 1
        self.tokens_in += int(reply.usage.get("total_input_tokens") or 0)
        self.tokens_out += int(reply.usage.get("total_output_tokens") or 0)
        self.tokens_out += int(reply.usage.get("total_thought_tokens") or 0)
        self._used.append(self._active.name)
        self._spent += cost
        self.usd += cost
        self.by_model[self._active.name] = self.by_model.get(self._active.name, 0.0) + cost
        return reply.text
