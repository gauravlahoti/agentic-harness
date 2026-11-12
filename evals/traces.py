"""Read a saved run (its trace file) into what the checks and DeepEval need (S10-AC3).

Part of the evals. The harness already writes every event of a run to
``<trace_dir>/<run_id>.jsonl``: model replies, tool calls with their arguments and results,
what the gate did, approvals, the scope check, and a sub-agent's events tagged with its
``agent_id``. This file turns that list into:

- ``RunView``: the task, the answer, numbers, the scope verdict, every tool use (main agent
  and helpers), every approval asked;
- ``Span``: the run as a tree (agent → model steps, tools, a helper as a nested agent),
  which ``evals/replay.py`` hands to DeepEval as the trace.

Does not: call a model, or change the trace.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ToolUse:
    name: str
    arguments: dict[str, Any]
    output: str
    is_error: bool  # failed, blocked by a rule, or rejected by a person: it did not happen
    agent: str = ""  # "" for the main agent, else the helper's name
    blocked: str = ""  # the never-rule that stopped it
    approvals: tuple[dict[str, str], ...] = ()  # who was asked, and their answer
    flagged: bool = False  # the gate found instruction-like text in its result

    @property
    def completed(self) -> bool:
        return not self.is_error


@dataclass(slots=True)
class Span:
    kind: str  # agent | llm | tool
    name: str
    input: Any = None
    output: Any = None
    children: list["Span"] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RunView:
    run_id: str
    task: str
    answer: str
    outcome: str
    reason: str
    model: str
    profile: str
    model_calls: int
    usd: float
    seconds: float
    scope_in: bool | None  # None: no scope check ran
    scope_reason: str
    tools: tuple[ToolUse, ...]
    asked: tuple[tuple[str, bool], ...]  # (approver role, approved) for every approval
    root: Span
    # Every model reply in the run, helpers included: what the eval cost panel learns from.
    tokens_in: int = 0
    tokens_out: int = 0  # thinking counts as output, as it is billed
    replies: int = 0
    # The online evals' scores for this answer (D-148): the same metrics, offline (D-151).
    online: tuple[dict[str, Any], ...] = ()
    online_usd: float = 0.0
    online_judge: str = ""

    @property
    def loop_ran(self) -> bool:
        """False when the scope guard stopped the task before any model call."""
        return self.model_calls > 0


def read_events(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def read_run(path: Path) -> RunView:
    """One run's trace file → a RunView. Helper events nest under their agent."""
    events = read_events(path)
    if not events or events[0].get("type") != "run_started":
        raise ValueError(f"{path.name} is not a run trace.")
    first = events[0]["data"]
    root = Span("agent", "agent", input=first.get("task", ""))
    helpers: dict[str, Span] = {}
    started: dict[str, dict[str, Any]] = {}  # call_id → its tool_started data
    tools: list[ToolUse] = []
    asked: list[tuple[str, bool]] = []
    scope_in: bool | None = None
    scope_reason = ""
    finished: dict[str, Any] = {}
    online: dict[str, Any] = {}
    tokens_in = tokens_out = replies = 0

    for event in events[1:]:
        kind, data = event.get("type"), event.get("data", {})
        helper_id = data.get("agent_id")
        parent = helpers.get(helper_id, root) if helper_id else root
        if kind == "run_started" and helper_id:
            helpers[helper_id] = Span("agent", data.get("agent", "helper"), data.get("task", ""))
            root.children.append(helpers[helper_id])
        elif kind == "run_finished":
            if helper_id:
                if helper_id in helpers:
                    helpers[helper_id].output = data.get("answer", "")
            else:
                finished = data
        elif kind == "scope_checked" and not helper_id:
            scope_in, scope_reason = bool(data.get("in_scope")), str(data.get("reason", ""))
        elif kind == "model_replied":
            usage = data.get("usage") or {}
            tokens_in += int(usage.get("total_input_tokens") or 0)
            tokens_out += int(usage.get("total_output_tokens") or 0)
            tokens_out += int(usage.get("total_thought_tokens") or 0)
            replies += 1
            text = data.get("text") or ""
            calls = data.get("tool_calls") or []
            parent.children.append(
                Span("llm", f"model step {data.get('step')}", output=text or f"calls {calls}")
            )
        elif kind == "tool_started":
            started[str(data.get("call_id"))] = data
        elif kind == "tool_finished":
            arguments = started.get(str(data.get("call_id")), {}).get("arguments") or {}
            use = ToolUse(
                name=str(data.get("name", "")),
                arguments=dict(arguments),
                output=str(data.get("output", "")),
                is_error=bool(data.get("is_error")),
                agent=str(data.get("agent", "")) if helper_id else "",
                blocked=str((data.get("blocked") or {}).get("rule", "")),
                approvals=tuple(data.get("approvals") or ()),
                flagged=bool(data.get("flags")),
            )
            tools.append(use)
            parent.children.append(Span("tool", use.name, use.arguments, use.output))
        elif kind == "online_evals_finished" and not helper_id:
            online = data
        elif kind == "approval_decided" and data.get("kind", "approval") == "approval":
            asked.append((str(data.get("approver", "")), bool(data.get("approved"))))

    root.output = finished.get("answer", "")
    context = first.get("context") or {}
    return RunView(
        run_id=str(events[0].get("run_id", path.stem)),
        task=str(first.get("task", "")),
        answer=str(finished.get("answer", "")),
        outcome=str(finished.get("outcome", "")),
        reason=str(finished.get("reason", "")),
        model=str(first.get("model", "")),
        profile=str(context.get("profile") or ""),
        model_calls=int(finished.get("model_calls") or 0),
        usd=float(finished.get("usd") or 0.0),
        seconds=float(finished.get("seconds") or 0.0),
        scope_in=scope_in,
        scope_reason=scope_reason,
        tools=tuple(tools),
        asked=tuple(asked),
        root=root,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        replies=replies,
        online=tuple(online.get("results") or ()),
        online_usd=float(online.get("usd") or 0.0),
        online_judge=str(online.get("judge") or ""),
    )
