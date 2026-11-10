"""Stand-ins for the eval tests: no test calls Gemini or Anthropic (S10-AC8).

- ``Scripted``: a model client that replies from a list (text, or an error to raise).
- ``Agent``: a model client that plays the CloudCo agent just enough to drive the real
  harness: it passes the scope check (except a World Cup question), looks a customer up,
  or tries to send when asked, then answers.
- ``StandInJudge``: a judge that fills in whatever schema DeepEval asks for.
"""

import types
import typing
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel

from agentic_harness.model import ModelError, ModelReply
from agentic_harness.pricing import load_prices
from evals.judge import Judge

USAGE = {"total_input_tokens": 500, "total_output_tokens": 50}


def text_reply(text: str) -> ModelReply:
    return ModelReply(
        steps=[{"type": "model_output", "content": [{"type": "text", "text": text}]}],
        status="completed",
        usage=dict(USAGE),
    )


def call_reply(name: str, arguments: dict[str, Any], call_id: str) -> ModelReply:
    return ModelReply(
        steps=[{"type": "function_call", "id": call_id, "name": name, "arguments": arguments}],
        status="requires_action",
        usage=dict(USAGE),
    )


class Scripted:
    def __init__(self, name: str, replies: Sequence[str | Exception]) -> None:
        self.name = name
        self.replies = list(replies)
        self.calls = 0

    async def create(self, system: str, steps: Sequence[Any], tools: Sequence[Any]) -> ModelReply:
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return text_reply(reply)


class Agent:
    """Drives the real loop: scope check → one tool call → an answer."""

    def __init__(self, name: str, fail: str = "") -> None:
        self.name = name
        self.fail = fail  # raise this as a ModelError on every agent call

    async def create(self, system: str, steps: Sequence[Any], tools: Sequence[Any]) -> ModelReply:
        last = steps[-1]
        text = "".join(p.get("text", "") for p in last.get("content", []))
        if system.startswith("You decide whether a request"):
            return text_reply("OUT: sports" if "World Cup" in text else "IN: on the job")
        if self.fail:
            raise ModelError(self.fail)
        if last.get("type") == "user_input":
            if "Send" in text:
                arguments = {
                    "customer_id": "CUS-0042",
                    "subject": "Your contract",
                    "body": "We can offer 20%.",
                    "discount_pct": 20,
                }
                return call_reply("send_to_customer", arguments, f"c{len(steps)}")
            return call_reply(
                "lookup_customer_record",
                {"record": "customer", "customer": "ShopCo"},
                f"c{len(steps)}",
            )
        result = "".join(p.get("text", "") for p in last.get("result", []))
        if "rejected" in result:
            return text_reply("Not sent: the CFO rejected the 20% offer.")
        return text_reply("ShopCo (CUS-0042): the account owner is Priya Raman (Sales).")


def factory(fail: str = "") -> Any:
    return lambda name: Agent(name, fail)


def fill(kind: Any) -> Any:
    """A plausible value of any type DeepEval's schemas use."""
    origin = typing.get_origin(kind)
    if origin in (typing.Union, types.UnionType):
        return fill(next(a for a in typing.get_args(kind) if a is not type(None)))
    if origin is typing.Literal:
        return typing.get_args(kind)[0]
    if origin is list:
        return []
    if origin is dict or kind is dict:
        return {}
    if isinstance(kind, type) and issubclass(kind, BaseModel):
        return kind(**{n: fill(f.annotation) for n, f in kind.model_fields.items()})
    return {str: "stand-in", int: 1, float: 1.0, bool: True}.get(kind, "stand-in")


class StandInJudge(Judge):
    """Answers every schema with filled-in values; records each call like the real judge."""

    def __init__(self, fail: Exception | None = None) -> None:
        super().__init__(Scripted("gemini-3.5-flash-lite", []), load_prices())
        self.fail = fail

    async def a_generate(self, prompt: str, schema: Any = None) -> Any:
        if self.fail is not None:
            raise self.fail
        self._used.append("stand-in")
        self.usd += 0.0001
        self._spent += 0.0001
        return fill(schema) if schema is not None else "stand-in"
