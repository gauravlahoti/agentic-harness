"""``create_harness``: the one call that wires a harness together (S01-AC12).

Harness part: the entry point. The CLI and the web server both use it, the
same way a framework gives you one call. Here every argument is a module we
wrote, so each line can be explained.

It also answers "what would a run get?" for the page's Harness pane
(``describe_harness``), from the same pieces, so the two can't drift (D-68).

Does not: read settings or files itself; the caller passes everything in.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_harness.approvals import ask_human_tool
from agentic_harness.context import build_context
from agentic_harness.gate import Gate
from agentic_harness.limits import Limits
from agentic_harness.loop import Approver, Harness
from agentic_harness.memory import SessionStore, load_notes, note_path, save_note_tool
from agentic_harness.model import ModelClient
from agentic_harness.planning import PLAN_TOOL, plan_tool
from agentic_harness.pricing import Prices, load_prices
from agentic_harness.scope import scope_check
from agentic_harness.skills import Skill, load_skill_tool
from agentic_harness.subagents import (
    MAX_CHILD_STEPS,
    MONEY_SLICE,
    TIME_SLICE,
    SubAgent,
    child_system,
    delegate_tool,
)
from agentic_harness.tools import Tool
from agentic_harness.tools.builtin import builtin_tools
from agentic_harness.trace import TraceWriter
from agentic_harness.trimming import ModelSummarizer
from agentic_harness.verify import PLAN_CHECK, Check
from agentic_harness.workspace import Workspace, WorkspaceError

DEFAULT_MEMORY_DIR = Path(".agentic-harness")  # sessions and notes live under it (S07)
DEFAULT_TRACE_DIR = Path(".agentic-harness") / "traces"  # git-ignored

ModelFactory = Callable[[str], ModelClient]  # model name → a client for it (D-62)


@dataclass(frozen=True, slots=True)
class Off:
    """What the person switched off for one run. It can only remove (D-70)."""

    tools: tuple[str, ...] = ()
    skills: tuple[str, ...] = ()
    subagents: tuple[str, ...] = ()
    checks: tuple[str, ...] = ()  # answer checks switched off (S11)

    def summary(self) -> dict[str, list[str]]:
        return {
            "tools": list(self.tools),
            "skills": list(self.skills),
            "subagents": list(self.subagents),
            "checks": list(self.checks),
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
    approver: Approver | None = None,
    memory_dir: Path | None = DEFAULT_MEMORY_DIR,
    small_model: str | None = None,
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
    gate = workspace.gate(profile)  # what this profile may use, see, never do, must ask (S05)
    notes_file = (
        note_path(memory_dir, workspace.name, profile) if memory_dir and workspace.notes else None
    )
    # Notes are read once, here: the prompt is the same for every call of the task (D-92).
    notes = load_notes(notes_file) if notes_file else ""
    context = build_context(
        workspace,
        profile,
        skip_skills=off.skills,
        notes=notes,
        not_allowed=not_allowed_prompt(workspace, gate),
    )

    # The workspace's own tools, then the built-ins it asked for (D-45), minus switched off.
    available = _tools(workspace, off)
    helpers = (
        [] if not delegation else [a for a in workspace.subagents if a.name not in off.subagents]
    )
    # While someone can delegate, the delegate-only tools belong to the helpers (D-59).
    tools = [t for t in available.values() if not (helpers and t.name in workspace.delegate_only)]
    if context.skills:
        tools.append(load_skill_tool(context.skills))  # built in: reads a skill on demand
    if notes_file is not None:
        tools.append(save_note_tool(notes_file))  # the agent keeps notes for next time (D-92)
    if workspace.ask_human:
        tools.append(ask_human_tool())  # the model may pause to ask a person (D-89)
    if workspace.plan and PLAN_TOOL not in off.tools:
        tools.append(plan_tool())  # the main agent may keep a to-do list; helpers don't (S11)
    if helpers:
        models = {
            a.name: _helper_model(a, model, model_factory, prices, small_model) for a in helpers
        }

        def make_child(agent: SubAgent, child_limits: Limits) -> Harness:
            # Only its declared tools that are still on and that its caller may use;
            # never delegate_task (D-58). Same gate as its caller (S05-AC8).
            own = [available[n] for n in agent.tools if n in available and gate.allows(n)]
            return Harness(
                models[agent.name],
                child_limits,
                own,
                prices=prices,
                system=child_system(agent),
                context={"subagent": agent.name, "instructions": agent.source},
                root=workspace.path,
                readable=workspace.readable,
                gate=gate,
                profile=profile,  # the caller's: a helper sees no more than it (D-106)
            )

        tools.append(delegate_tool(helpers, make_child))
    _check_unique(tools)
    check = None
    if workspace.scope:  # one small call per task, before the loop (D-81)
        check_model = model
        wanted = small_model or workspace.scope.model
        if wanted and wanted != model.name and model_factory:
            prices.for_model(wanted)
            check_model = model_factory(wanted)
        check = scope_check(workspace.scope, check_model, prices)
    summarizer = None
    if workspace.window is not None:  # one small call, only when pruning is not enough (D-93)
        small = model
        wanted = small_model or workspace.summary_model
        if wanted and wanted != model.name and model_factory:
            prices.for_model(wanted)
            small = model_factory(wanted)
        summarizer = ModelSummarizer(small, prices.cost)
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
        gate=gate,
        approver=approver,
        scope=workspace.scope,
        scope_check=check,
        window=workspace.window,
        summarizer=summarizer,
        profile=profile,
        checks=[c for c in all_checks(workspace) if c.name not in off.checks],  # VERIFY (S11)
        retries=workspace.verify_retries,
    )
    if trace_dir is not None:
        harness.subscribe(TraceWriter(trace_dir, secrets))
    return harness


def all_checks(workspace: Workspace) -> list[Check]:
    """The harness's own Plan Complete (only with a plan tool), then the workspace's."""
    return [*([PLAN_CHECK] if workspace.plan else []), *workspace.checks]


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
        "tool": {t.name for t in [*workspace.tools, *builtin_tools(workspace.builtins)]}
        | ({PLAN_TOOL} if workspace.plan else set()),
        "skill": {s.name for s in workspace.skills(profile)},
        "sub-agent": {a.name for a in workspace.subagents},
        "check": {c.name for c in all_checks(workspace)},
    }
    for kind, names in (
        ("tool", off.tools),
        ("skill", off.skills),
        ("sub-agent", off.subagents),
        ("check", off.checks),
    ):
        if unknown := [n for n in names if n not in known[kind]]:
            raise WorkspaceError(
                f"Can't switch off {kind} {unknown[0]!r}: this workspace has none."
            )
    return off


def _helper_model(
    agent: SubAgent,
    parent: ModelClient,
    factory: ModelFactory | None,
    prices: Prices,
    small_model: str | None = None,
) -> ModelClient:
    # ``small_model`` pins every helper to one model, e.g. Claude Haiku on a Claude run (D-103).
    wanted = small_model or agent.model
    if not wanted or wanted == parent.name or factory is None:
        return parent
    prices.for_model(wanted)  # a helper's model needs a price too, checked now
    return factory(wanted)


def not_allowed_prompt(workspace: Workspace, gate: Gate) -> str:
    """What this profile can't do, and the one sentence to say when asked (D-105).

    The tools are hidden from the model (D-75), so without this it improvises: a found-live
    answer explained approvals and repeated terms instead of a plain no.
    """
    tools = [*workspace.tools, *builtin_tools(workspace.builtins)]
    blocked = [t for t in tools if not gate.allows(t.name)]
    if not blocked:
        return ""
    lines = []
    for t in blocked:
        does = " ".join(t.description.split()).split(". ")[0].rstrip(".")  # first sentence
        can = [p.label for p in workspace.profiles if t.name in (p.tools or ())]
        who = f" {' or '.join(can)} can." if can else ""
        lines.append(f'- {does}: reply only "{gate.label} can\'t do that here.{who}"')
    return (
        f"## Not available to {gate.label}\n\n"
        "If you are asked for one of these, reply with that one sentence and stop: no details "
        "of the work, no drafts, no workarounds.\n" + "\n".join(lines)
    )


def harness_tools(workspace: Workspace, skills: Sequence[Skill]) -> list[Tool]:
    """The tools the harness itself adds for this workspace, as the model sees them.
    Same conditions as ``create_harness``; ``delegate_task`` is shown with the helpers."""
    found: list[Tool] = []
    if skills:
        found.append(load_skill_tool(skills))
    if workspace.notes:
        found.append(save_note_tool(Path("notes.md")))  # only its declaration is read
    if workspace.ask_human:
        found.append(ask_human_tool())
    if workspace.plan:
        found.append(plan_tool())
    return found


def describe_harness(
    workspace: Workspace,
    profile: str | None,
    limits: Limits | None = None,
    memory_dir: Path | None = None,
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
        # Guardrails in three parts (S05): Permissions, Never allowed, Human in the loop.
        "guardrails": {
            **workspace.gate(profile).summary(tools),
            "scope": (
                {"covers": workspace.scope.covers, "refusal": workspace.scope.refusal}
                if workspace.scope
                else None
            ),
            "writes": ["tasks/<run-id>/", "outbox/"],
            "protected": [
                "workspace.toml",
                *(f.path for f in context.files),
                *(d.replace("{profile}", profile or "") for d in workspace.skill_dirs),
            ],
        },
        "memory": {
            "notes_on": workspace.notes,
            # Newest first, as the agent will see them at the start of its next task.
            "notes": list(
                reversed(load_notes(note_path(memory_dir, workspace.name, profile)).splitlines())
            )
            if memory_dir and workspace.notes
            else [],
            "conversations": len(SessionStore(memory_dir, workspace.name).list(profile))
            if memory_dir
            else 0,
            "trimming": None
            if workspace.window is None
            else {
                "window": workspace.window.tokens,
                "prune_at": workspace.window.prune_at,
                "summarize_at": workspace.window.summarize_at,
                "keep_recent": workspace.window.keep_recent,
            },
        },
        # Plan and Verify (S11): what the harness does before an answer reaches the person.
        "verify": {
            "plan_on": workspace.plan,
            "retries": workspace.verify_retries,
            "checks": [
                {
                    "name": c.name,
                    "label": c.label,
                    "description": c.description,
                    "source": "built-in" if c is PLAN_CHECK else "workspace",
                }
                for c in all_checks(workspace)
            ],
        },
        "context": {
            "files": context.summary()["files"],
            "prompt_tokens": context.summary()["prompt_tokens"],
        },
        "skills": context.summary()["skills"],
        # The harness's own tools (S11): the model sees them like any other (load_skill,
        # save_note, ask_human, update_plan). Only update_plan can be switched off.
        "harness_tools": [
            {
                "name": t.name,
                "risk": t.risk,
                "description": t.description,
                "switchable": t.name == PLAN_TOOL,
            }
            for t in harness_tools(workspace, context.skills)
        ],
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
