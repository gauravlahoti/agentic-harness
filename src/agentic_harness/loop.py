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
import hashlib
import time
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentic_harness.events import Event, EventBus, Listener
from agentic_harness.gate import ApprovalRequest, Gate
from agentic_harness.limits import Budget, Limits
from agentic_harness.model import ModelClient, ModelError, Step
from agentic_harness.pricing import Prices
from agentic_harness.scope import Scope, ScopeCheck
from agentic_harness.tools import Tool, ToolContext
from agentic_harness.tools.registry import call_tool

# Domain-free on purpose: the workspace adds who the agent is (S02).
# Measured live (D-30): "use the tools when they help" made a small model call tools it
# didn't need; asking it to answer directly cut needless calls from 5/5 to 1/5.
SYSTEM_PROMPT = (
    "You are an agent running on a harness. Answer directly when you already know the answer. "
    "Call a tool only when the task needs something that tool provides, such as live data or "
    "an action; never call a tool just to be thorough. When you have the answer, reply in "
    "plain text."
)

Outcome = Literal["completed", "stopped", "failed"]

# A person's answer to an approval request: (approved, note). The server and CLI supply one.
Approver = Callable[[ApprovalRequest], Awaitable[tuple[bool, str]]]
APPROVAL_TIMEOUT = 600.0  # seconds; no answer counts as "no" (D-79)
SCOPE_CHECK_SECONDS = 15.0  # the scope check is small; a stuck one must not hold the run


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
        context: dict[str, Any] | None = None,
        root: Path | None = None,
        readable: Sequence[str] = (),
        off: dict[str, list[str]] | None = None,
        gate: Gate | None = None,
        approver: Approver | None = None,
        scope: Scope | None = None,
        scope_check: ScopeCheck | None = None,
    ) -> None:
        self.model, self.limits, self.prices, self.system = model, limits, prices, system
        self.root, self.readable = root, tuple(readable)  # the workspace folder tools may use
        self.off = off or {}  # what was switched off for this harness (D-72)
        self.gate = gate  # what this profile may use, see, never do, and must ask for (S05)
        self.approver = approver  # who answers "may I?"; none means no (D-79)
        self.scope, self.scope_check = scope, scope_check  # stay on the job (D-81)
        self.context = context or {}  # what was loaded into the prompt, for the page (S02)
        # Same text on every call (S02-AC8); each call carries this ID to prove it.
        self.prompt_id = hashlib.sha256(system.encode()).hexdigest()[:12]
        self.tools = {tool.name: tool for tool in tools}
        self._bus = EventBus()

    def visible_tools(self) -> list[Tool]:
        """The tools the model is told about. A gated-out tool is hidden *and* blocked."""
        tools = list(self.tools.values())
        return self.gate.visible(tools) if self.gate else tools

    def subscribe(self, listener: Listener) -> None:
        self._bus.subscribe(listener)

    async def run(self, task: str) -> RunResult:
        run = _Run(self._bus)
        budget = Budget(self.limits)
        declarations = [tool.declaration() for tool in self.visible_tools()]
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
            context=self.context,
            off=self.off,
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

        # The scope guard runs once, before the loop: off-topic tasks never start (D-81).
        if self.scope_check is not None:
            try:
                async with asyncio.timeout(min(SCOPE_CHECK_SECONDS, budget.seconds_left())):
                    verdict = await self.scope_check(task)
            except Exception as error:  # a busy check must not block real work
                run.emit("scope_checked", in_scope=True, reason="", usd=0.0, error=f"{error}"[:300])
            else:
                budget.charge(verdict.usd)
                run.emit(
                    "scope_checked",
                    in_scope=verdict.in_scope,
                    reason=verdict.reason,
                    usd=verdict.usd,
                )
                if not verdict.in_scope:
                    return finish(
                        "stopped", "outside_scope", self.scope.refusal if self.scope else ""
                    )

        while (limit := budget.exceeded()) is None:
            budget.count_step()
            run.emit(
                "model_called", step=budget.steps, history=len(steps), prompt_id=self.prompt_id
            )
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
            steps.extend([await self._run_tool(call, run, budget) for call in calls])

        return finish("stopped", limit)

    async def _run_tool(self, call: Step, run: "_Run", budget: Budget) -> Step:
        name, arguments = call.get("name", ""), call.get("arguments") or {}
        call_id = call.get("id")
        tool = self.tools.get(name)
        part, risk = (tool.part, tool.risk) if tool else ("tool", "")
        run.emit(
            "tool_started", call_id=call_id, name=name, arguments=arguments, part=part, risk=risk
        )
        guard: dict[str, Any] = {}  # what the gate did, for the page and the trace
        if tool is None:
            output, is_error = f"Unknown tool: {name}", True
        else:
            # The gate decides before anything runs (S05): ① profile, ② never rules, ③ a person.
            decision = self.gate.check(name, arguments) if self.gate else None
            if decision and decision.kind == "block":
                guard["blocked"] = {
                    "rule": decision.rule,
                    "label": decision.label,
                    "because": decision.because,
                }
                output = (
                    f"Blocked by the harness: {decision.label} ({decision.because}). "
                    "This can't be done or approved; tell the person instead of retrying."
                )
                is_error = True
            else:
                approved, note = True, ""
                if decision and decision.kind == "ask":
                    approved, note = await self._ask(
                        run, call_id or "", name, arguments, decision.because, budget
                    )
                    guard["approval"] = {"approved": approved, "note": note}
                if not approved:
                    output = "A person rejected this, so it was not done" + (
                        f": {note}" if note else "."
                    )
                    is_error = True
                else:
                    # A fresh context per call: it knows the call, so a file can be tied to it.
                    ctx = None
                    if self.root is not None:
                        ctx = ToolContext(
                            run.id, self.root, self.readable, run.emit, call_id or "", budget
                        )
                    result = await call_tool(tool, arguments, ctx)  # never raises (S03-AC8)
                    output, is_error = result.output, result.is_error
                    if self.gate and not is_error:
                        seen = self.gate.inspect(output)  # ④ hide fields, ⑤ flag instructions
                        output = seen.output
                        if seen.hidden:
                            guard["hidden"] = seen.hidden
                        if seen.flags:
                            guard["flags"] = seen.flags
        run.emit(
            "tool_finished",
            call_id=call_id,
            name=name,
            output=output,
            is_error=is_error,
            part=part,
            risk=risk,
            **guard,
        )
        result_step: Step = {
            "type": "function_result",
            "name": name,
            "call_id": call_id,
            "result": [{"type": "text", "text": output}],
        }
        if is_error:
            result_step["is_error"] = True
        return result_step

    async def _ask(
        self,
        run: "_Run",
        call_id: str,
        name: str,
        arguments: dict[str, Any],
        because: str,
        budget: Budget,
    ) -> tuple[bool, str]:
        """Pause for a person. The wait is not run time: it doesn't count toward the limit."""
        run.emit(
            "approval_requested", call_id=call_id, name=name, arguments=arguments, because=because
        )
        started = budget.elapsed()
        if self.approver is None:
            approved, note = False, "no one is here to approve it"
        else:
            request = ApprovalRequest(run.id, call_id, name, dict(arguments), because)
            try:
                approved, note = await asyncio.wait_for(self.approver(request), APPROVAL_TIMEOUT)
            except TimeoutError:
                approved, note = False, "no answer in 10 minutes"
        budget.exclude(budget.elapsed() - started)
        run.emit("approval_decided", call_id=call_id, name=name, approved=approved, note=note)
        return approved, note


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
