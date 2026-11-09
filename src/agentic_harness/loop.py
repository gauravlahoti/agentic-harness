"""The loop: ask the model, run the tools it asks for, send results back, repeat (S01).

Harness part: the loop, the heart of the harness. Every later stage wraps
one of these lines:

    steps = [user_input(task)]                 # the history we own
    while no limit is exceeded:                # stop rules
        reply = model.create(system, steps, tools)
        steps += reply.steps                   # exactly as received
        if reply has no function calls: done
        steps += [run each tool, in order]     # results go back together

Gemini has no "tool_use" stop reason: a reply asks for tools by containing
``function_call`` steps (status ``requires_action``, seen live).

Does not: talk to Gemini directly (model.py), price tokens (pricing.py), or
write files (listeners such as trace.py do). It only emits events.
"""

import asyncio
import inspect
import json
import time
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from agentic_harness.events import Event, EventBus, Listener
from agentic_harness.limits import Budget, Limits
from agentic_harness.model import ModelClient, ModelError, Step
from agentic_harness.pricing import Prices
from agentic_harness.tools import Tool

# Domain-free on purpose: the workspace adds who the agent is (S02).
SYSTEM_PROMPT = (
    "You are an agent running on a harness. Use the tools you are given when they help. "
    "When you have the answer, reply in plain text."
)

Outcome = Literal["completed", "stopped", "failed"]


@dataclass(frozen=True, slots=True)
class RunResult:
    run_id: str
    outcome: Outcome
    reason: str  # "answered", "step_limit", "output_limit", "model_error: …", …
    answer: str
    steps: list[Step] = field(repr=False)
    model_calls: int
    usd: float
    seconds: float


def user_input(text: str) -> Step:
    return {"type": "user_input", "content": [{"type": "text", "text": text}]}


class Harness:
    def __init__(
        self,
        model: ModelClient,
        limits: Limits,
        tools: Sequence[Tool],
        *,
        prices: Prices,
        system: str = SYSTEM_PROMPT,
    ) -> None:
        self.model, self.limits, self.prices, self.system = model, limits, prices, system
        self.tools = {tool.name: tool for tool in tools}
        self._bus = EventBus()

    def subscribe(self, listener: Listener) -> None:
        self._bus.subscribe(listener)

    async def run(self, task: str) -> RunResult:
        run = _Run(self._bus)
        budget = Budget(self.limits)
        declarations = [tool.declaration() for tool in self.tools.values()]
        steps: list[Step] = [user_input(task)]
        run.emit(
            "run_started",
            task=task,
            model=self.model.name,
            tools=list(self.tools),
            limits={
                "max_steps": self.limits.max_steps,
                "max_usd": self.limits.max_usd,
                "max_seconds": self.limits.max_seconds,
            },
        )

        def finish(outcome: Outcome, reason: str, answer: str = "") -> RunResult:
            result = RunResult(
                run.id,
                outcome,
                reason,
                answer,
                steps,
                budget.steps,
                budget.usd,
                round(budget.elapsed(), 3),
            )
            run.emit(
                "run_finished",
                outcome=outcome,
                reason=reason,
                answer=answer,
                model_calls=budget.steps,
                usd=budget.usd,
                seconds=result.seconds,
            )
            return result

        while (limit := budget.exceeded()) is None:
            budget.count_step()
            run.emit("model_called", step=budget.steps, history=len(steps))
            try:
                # The time limit also covers waiting for the model.
                async with asyncio.timeout(budget.seconds_left()):
                    reply = await self.model.create(self.system, steps, declarations)
            except TimeoutError:
                return finish("stopped", "time_limit")
            except ModelError as error:
                return finish("failed", f"model_error: {error}")

            usd = self.prices.cost(self.model.name, reply.usage)
            budget.charge(usd)
            steps.extend(reply.steps)  # exactly as received: thought signatures live here
            calls = reply.tool_calls
            run.emit(
                "model_replied",
                step=budget.steps,
                status=reply.status,
                usage=reply.usage,
                usd=usd,
                text=reply.text,
                tool_calls=[c.get("name") for c in calls],
                steps=reply.steps,
            )

            if reply.status == "incomplete":
                return finish("stopped", "output_limit", reply.text)
            if reply.status == "completed" and not calls:
                return finish("completed", "answered", reply.text)
            if reply.status not in ("completed", "requires_action") or not calls:
                # Anything we don't understand ends the run loudly, never a silent loop.
                return finish("failed", f"unexpected_status: {reply.status}")

            # Run every call in order, then send all results back together.
            steps.extend([await self._run_tool(call, run) for call in calls])

        return finish("stopped", limit)

    async def _run_tool(self, call: Step, run: "_Run") -> Step:
        name, arguments = call.get("name", ""), call.get("arguments") or {}
        run.emit("tool_started", call_id=call.get("id"), name=name, arguments=arguments)
        tool = self.tools.get(name)
        is_error = True
        if tool is None:
            output = f"Unknown tool: {name}"
        else:
            try:
                value = tool.function(**arguments)
                if inspect.isawaitable(value):
                    value = await value
                output = value if isinstance(value, str) else json.dumps(value, default=str)
                is_error = False
            except Exception as error:  # a broken tool is news for the model, not a crash
                output = f"{type(error).__name__}: {error}"
        run.emit(
            "tool_finished", call_id=call.get("id"), name=name, output=output, is_error=is_error
        )
        result: Step = {
            "type": "function_result",
            "name": name,
            "call_id": call.get("id"),
            "result": [{"type": "text", "text": output}],
        }
        if is_error:
            result["is_error"] = True
        return result


class _Run:
    """Numbers the events of one run and sends them to the listeners."""

    def __init__(self, bus: EventBus) -> None:
        self.id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
        self._bus = bus
        self._seq = 0

    def emit(self, type_: str, **data: Any) -> None:
        self._seq += 1
        self._bus.emit(
            Event(type=type_, run_id=self.id, seq=self._seq, time=time.time(), data=data)
        )
