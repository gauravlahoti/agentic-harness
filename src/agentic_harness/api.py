"""``create_harness``: the one call that wires a harness together (S01-AC12).

Harness part: the entry point. The CLI and the web server both use it, the
same way a framework gives you one call. Here every argument is a module we
wrote, so each line can be explained.

It also answers "what would a run get?" for the page's Harness pane
(``describe_harness``), from the same pieces, so the two can't drift (D-68).

Does not: read settings or files itself; the caller passes everything in.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_harness.context import build_context
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.model import ModelClient
from agentic_harness.pricing import Prices, load_prices
from agentic_harness.skills import load_skill_tool
from agentic_harness.subagents import (
    MAX_CHILD_STEPS,
    MONEY_SLICE,
    TIME_SLICE,
    SubAgent,
    child_system,
    delegate_tool,
)
from agentic_harness.tools import RISKS, Tool
from agentic_harness.tools.builtin import builtin_tools
from agentic_harness.trace import TraceWriter
from agentic_harness.workspace import Workspace, WorkspaceError

DEFAULT_TRACE_DIR = Path(".agentic-harness") / "traces"  # git-ignored

ModelFactory = Callable[[str], ModelClient]  # model name → a client for it (D-62)


@dataclass(frozen=True, slots=True)
class Off:
    """What the person switched off for one run. It can only remove (D-70)."""

    tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    subagents: tuple[str, ...] = ()

    def summary(self) -> dict[str, list[str]]:
        return {
            "tools": list(self.tools),
            "skills": list(self.skills),
            "subagents": list(self.subagents),
        }


def create_harness(
    model: ModelClient,
    limits: Limits,
    workspace: Workspace,
    *,
    profile: str | None = None,
    trace_dir: Path | None = DEFAULT_TRACE_DIR,
    secrets: Iterable[str] = (),
    prices: Prices | None = None,
    model_factory: ModelFactory | None = None,
    delegation: bool = True,
    off: Off | None = None,
) -> Harness:
    """A harness for this model, workspace and profile.

    The context (memory files + skill list) is built here, once, before any call (D-37).
    ``off`` removes tools, skills or helpers for this run; ``delegation=False`` removes
    every helper (D-64). Every run is traced unless ``trace_dir`` is None.
    """
    prices = prices or load_prices()
    prices.for_model(model.name)  # no price → fail now, not after the first call (D-25)
    profile = workspace.check_profile(profile)
    off = _check_off(workspace, profile, off or Off())
    context = build_context(workspace, profile, skip_skills=off.skills)

    # The workspace's own tools, then the built-ins it asked for (D-45), minus switched off.
    available = _tools(workspace, off)
    helpers = (
        [] if not delegation else [a for a in workspace.subagents if a.name not in off.subagents]
    )
    # While someone can delegate, the delegate-only tools belong to the helpers (D-59).
    tools = [t for t in available.values() if not (helpers and t.name in workspace.delegate_only)]
    if context.skills:
        tools.append(load_skill_tool(context.skills))  # built in: reads a skill on demand
    if helpers:
        models = {a.name: _helper_model(a, model, model_factory, prices) for a in helpers}

        def make_child(agent: SubAgent, child_limits: Limits) -> Harness:
            # Only its declared tools that are still on; never delegate_task (D-58).
            own = [available[name] for name in agent.tools if name in available]
            return Harness(
                models[agent.name],
                child_limits,
                own,
                prices=prices,
                system=child_system(agent),
                context={"subagent": agent.name, "instructions": agent.source},
                root=workspace.path,
                readable=workspace.readable,
            )

        tools.append(delegate_tool(helpers, make_child))
    _check_unique(tools)
    harness = Harness(
        model,
        limits,
        tools,
        prices=prices,
        system=context.system,
        context=context.summary(),
        root=workspace.path,  # where tools may read (readable) and write (tasks/, outbox/)
        readable=workspace.readable,
        off=off.summary(),
    )
    if trace_dir is not None:
        harness.subscribe(TraceWriter(trace_dir, secrets))
    return harness


def _tools(workspace: Workspace, off: Off) -> dict[str, Tool]:
    tools = [*workspace.tools, *builtin_tools(workspace.builtins)]
    _check_unique(tools)
    return {t.name: t for t in tools if t.name not in off.tools}


def _check_unique(tools: list[Tool]) -> None:
    names = [t.name for t in tools]
    if clash := sorted({n for n in names if names.count(n) > 1}):
        raise WorkspaceError(f"Two tools are named {clash[0]!r}; tool names must be unique.")


def _check_off(workspace: Workspace, profile: str | None, off: Off) -> Off:
    """Every name must exist for this profile: a switch can't invent anything (D-70)."""
    known = {
        "tool": {t.name for t in [*workspace.tools, *builtin_tools(workspace.builtins)]},
        "skill": {s.name for s in workspace.skills(profile)},
        "sub-agent": {a.name for a in workspace.subagents},
    }
    for kind, names in (("tool", off.tools), ("skill", off.skills), ("sub-agent", off.subagents)):
        if unknown := [n for n in names if n not in known[kind]]:
            raise WorkspaceError(
                f"Can't switch off {kind} {unknown[0]!r}: this workspace has none."
            )
    return off


def _helper_model(
    agent: SubAgent, parent: ModelClient, factory: ModelFactory | None, prices: Prices
) -> ModelClient:
    if not agent.model or agent.model == parent.name or factory is None:
        return parent
    prices.for_model(agent.model)  # a helper's model needs a price too, checked now
    return factory(agent.model)


def describe_harness(
    workspace: Workspace, profile: str | None, limits: Limits | None = None
) -> dict[str, Any]:
    """What a run for this profile gets, before any switch (the page's Harness pane).

    Grouped by harness part: context, tools, memory, guardrails, loop (D-67).
    """
    profile = workspace.check_profile(profile)
    limits = limits or Limits()
    context = build_context(workspace, profile)
    builtin_names = set(workspace.builtins)
    tools = [*workspace.tools, *builtin_tools(workspace.builtins)]
    return {
        "profile": profile,
        "loop": {
            "max_steps": limits.max_steps,
            "max_usd": limits.max_usd,
            "max_seconds": limits.max_seconds,
            "stop_rules": ["step_limit", "cost_limit", "time_limit", "output_limit"],
            "helper_slice": {
                "time": TIME_SLICE,
                "money": MONEY_SLICE,
                "max_steps": MAX_CHILD_STEPS,
            },
            "prompt_id": context.prompt_id,
        },
        "guardrails": {
            "risks": {risk: sum(t.risk == risk for t in tools) for risk in RISKS},
            "readable": list(workspace.readable),
            "writes": ["tasks/<run-id>/", "outbox/"],
            "helpers": "read-only tools, cannot delegate (depth 1)",
            "actions_ask_first": False,  # nothing asks a person yet: approvals come in S06
            "planned": [
                {"stage": "S05", "what": "tools and fields per profile, protected files"},
                {"stage": "S06", "what": "a person approves actions before they run"},
            ],
        },
        "memory": {
            "planned": {"stage": "S07", "what": "saved tasks, notes per profile, trimming"},
        },
        "context": {
            "files": context.summary()["files"],
            "prompt_tokens": context.summary()["prompt_tokens"],
        },
        "skills": context.summary()["skills"],
        "tools": [
            {
                "name": t.name,
                "risk": t.risk,
                "description": t.description,
                "parameters": t.parameters,
                "source": "built-in" if t.name in builtin_names else "workspace",
                "delegate_only": t.name in workspace.delegate_only,
            }
            for t in tools
        ],
        # Tools on other servers, reached over MCP. The harness has none: every tool above
        # runs in this process. The pane shows the empty list so the split is visible.
        "remote_tools": [],
        "subagents": [
            {
                "name": a.name,
                "description": a.description,
                "model": a.model,
                "tools": list(a.tools),
                "max_words": a.max_words,
                "source": a.source,
            }
            for a in workspace.subagents
        ],
    }
