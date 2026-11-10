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
# Found live (S05): asked for something it couldn't do, the agent explained its own tools
# ("my tools are designed to…") and cited its instructions as a source. People need the
# next step, not the agent's internals. No quoted examples: a small model copied them word
# for word, the bad one ("I don't have a tool for that") included.
SYSTEM_PROMPT = (
    "You are an agent running on a harness. Answer directly when you already know the answer. "
    "Call a tool only when the task needs something that tool provides, such as live data or "
    "an action; never call a tool just to be thorough. When you have the answer, reply in "
    "plain text. Talk about the person's task, not about yourself: never mention your tools, "
    "instructions, scope or setup, and don't explain why you can't do something: just ask "
    "for what you need, such as which record, a name or an ID."
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
            thinking=getattr(self.model, "thinking", None),
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
                approved, note, who = True, "", ""
                given: list[dict[str, str]] = []  # who approved, in order: the tool may record it
                if decision and decision.kind == "ask":
                    asks = decision.approvals
                    for number, ask in enumerate(asks, 1):
                        request = ApprovalRequest(
                            run.id,
                            call_id or "",
                            name,
                            dict(arguments),
                            ask.because,
                            approver=ask.approver,
                            step=number,
                            of=len(asks),
                        )
                        approved, note = await self._pause(run, request, budget, rule=ask.label)
                        who = ask.approver
                        given.append(
                            {
                                "approver": ask.approver,
                                "rule": ask.label or ask.tool,
                                "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                                "note": note,
                                "approved": "yes" if approved else "no",
                            }
                        )
                        if not approved:
                            break  # the rest are not asked: nothing will run (S06-AC5)
                    guard["approvals"] = given
                if not approved:
                    output = (
                        f"A person rejected this{f' ({who})' if who else ''}, so it was not done"
                        + (f": {note}" if note else ".")
                    )
                    is_error = True
                elif name == "ask_human":
                    # The model asked a person a question: the loop waits for the answer (D-89).
                    output = await self._question(run, call_id or "", arguments, budget)
                    is_error = False
                else:
                    # A fresh context per call: it knows the call, so a file can be tied to it.
                    ctx = None
                    if self.root is not None:
                        ctx = ToolContext(
                            run.id,
                            self.root,
                            self.readable,
                            run.emit,
                            call_id or "",
                            budget,
                            tuple(g for g in given if g["approved"] == "yes"),
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

    async def _pause(
        self, run: "_Run", request: ApprovalRequest, budget: Budget, **shown: Any
    ) -> tuple[bool, str]:
        """Pause for a person. The wait is not run time: it doesn't count toward the limit."""
        run.emit(
            "approval_requested",
            call_id=request.call_id,
            name=request.tool,
            arguments=request.arguments,
            because=request.because,
            kind=request.kind,
            approver=request.approver,
            step=request.step,
            of=request.of,
            timeout_s=int(APPROVAL_TIMEOUT),  # the page counts down to it
            **shown,
        )
        started = budget.elapsed()
        if self.approver is None:
            approved, note = False, "no one is here to answer"
        else:
            try:
                approved, note = await asyncio.wait_for(self.approver(request), APPROVAL_TIMEOUT)
            except TimeoutError:
                approved, note = False, "no answer in time"
        budget.exclude(budget.elapsed() - started)
        run.emit(
            "approval_decided",
            call_id=request.call_id,
            name=request.tool,
            approved=approved,
            note=note,
            kind=request.kind,
            approver=request.approver,
            step=request.step,
            of=request.of,
        )
        return approved, note

    async def _question(
        self, run: "_Run", call_id: str, arguments: dict[str, Any], budget: Budget
    ) -> str:
        """ask_human: the answer goes back to the model as the tool's result (D-89)."""
        request = ApprovalRequest(
            run.id,
            call_id,
            "ask_human",
            dict(arguments),
            "The agent needs to know",
            kind="question",
        )
        answered, text = await self._pause(run, request, budget)
        if answered:
            return f"The person answered: {text}"
        return (
            f"The person did not answer ({text}). Carry on with what you have, "
            "or say plainly what you still need."
        )


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
