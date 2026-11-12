"""VERIFY: check the agent's answer before the person sees it (S11-AC6, AC7; D-125 to D-127).

Harness part: the loop (self-verification). Guardrails ask "is this allowed?" before a tool
runs; verification asks "is this correct?" after the model drafts its answer:

    draft → run every check on (answer, this run's tool calls)
          → all pass: finish
          → a failure, retries left: send the failures back as a note, loop again
          → a failure, none left: finish, marked "Not verified"

A check is a plain function the workspace writes in its ``checks.py`` (D-125): it gets the
answer and a ``Record`` of what the tools returned, and says passed, failed, or nothing to
check (``None``). The harness adds one of its own, "Plan Complete". Code, not a model
(D-126): free, exact, and the same every time.

Does not: know any workspace's checks, call a model, or decide what an answer should say.
"""

import importlib.util
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agentic_harness.planning import Item, unfinished

# The start of every note the harness puts in the conversation. The model reads it as the
# harness speaking; the scope check and the page skip it as not the person's words.
NOTE_PREFIX = "[Harness check]"


@dataclass(frozen=True, slots=True)
class Call:
    """One tool call of this run, as the tools answered it (after the gate)."""

    name: str
    arguments: dict[str, Any]
    output: str
    is_error: bool
    agent: str = ""  # "" for the main agent, else the helper's name


@dataclass(frozen=True, slots=True)
class Record:
    """What a check may look at: every call of the run, the plan, who asked, and what tools
    returned in earlier turns of the conversation (a follow-up may rely on them)."""

    calls: tuple[Call, ...] = ()
    plan: tuple[Item, ...] | None = None
    profile: str | None = None
    earlier: tuple[str, ...] = ()  # tool outputs from earlier turns, as saved (not trimmed)

    def outputs(self, name: str) -> list[str]:
        """What a tool returned, for each call that worked, in order."""
        return [c.output for c in self.calls if c.name == name and not c.is_error]


@dataclass(frozen=True, slots=True)
class Verdict:
    ok: bool
    message: str
    applies: bool = True  # False: nothing to check in this answer (shown, never counted)


def passed(message: str) -> Verdict:
    return Verdict(True, message)


def failed(message: str) -> Verdict:
    return Verdict(False, message)


def skipped(message: str) -> Verdict:
    """Nothing to check this time, and why: "Nothing was sent this run"."""
    return Verdict(True, message, applies=False)


CheckFn = Callable[[str, Record], Verdict | None]  # None = skipped, no reason given


@dataclass(frozen=True, slots=True)
class Check:
    name: str  # the function's name: the pane's switch uses it
    label: str  # Title Case, for people: "Right Approver"
    description: str  # one sentence: what passes
    fn: CheckFn


def check(label: str, description: str) -> Callable[[CheckFn], Check]:
    """``@check("Right Approver", "…")`` turns a function into a Check."""

    def wrap(fn: CheckFn) -> Check:
        return Check(fn.__name__, label, description, fn)

    return wrap


Status = Literal["passed", "failed", "error", "skipped"]


@dataclass(frozen=True, slots=True)
class Result:
    name: str
    label: str
    status: Status  # "error": the check broke; "skipped": nothing to check. Neither is sent back
    message: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "label": self.label,
            "status": self.status,
            "message": self.message,
        }


@check("Plan Complete", "If a plan was written, every item is done or skipped with a reason")
def plan_complete(answer: str, record: Record) -> Verdict | None:
    if record.plan is None:
        return skipped("No plan was made: the agent treated the task as simple.")
    left = unfinished(record.plan)
    if not left:
        n = len(record.plan)
        return passed(f"{n} item{'s' if n > 1 else ''}, all finished.")
    names = "; ".join(i.text for i in left)
    return failed(
        f"{len(left)} plan item{'s' if len(left) > 1 else ''} still open: {names}. "
        "Finish them, or mark them skipped with a reason."
    )


PLAN_CHECK = plan_complete


# ── Checks on an action, before it runs (S12, D-134) ─────────────────────────────────────

ActionFn = Callable[[dict[str, Any], Record], Verdict | None]


@dataclass(frozen=True, slots=True)
class ActionCheck:
    """A check on one tool's call, before anyone is asked to approve it and before it runs.
    It reads the call's arguments (an email's body and its terms, say). A failure stops the
    call and tells the model why; a person never sees an action that failed one."""

    name: str
    label: str
    description: str
    tool: str  # the tool it guards
    fn: ActionFn


def action_check(tool: str, label: str, description: str) -> Callable[[ActionFn], ActionCheck]:
    """``@action_check("send_message", "Body Matches Terms", "…")``."""

    def wrap(fn: ActionFn) -> ActionCheck:
        return ActionCheck(fn.__name__, label, description, tool, fn)

    return wrap


def run_action_checks(
    checks: Sequence[ActionCheck], tool: str, arguments: dict[str, Any], record: Record
) -> list[Result]:
    """The checks that guard this tool, in order. Same statuses as answer checks."""
    results = []
    for c in (c for c in checks if c.tool == tool):
        try:
            verdict = c.fn(arguments, record)
        except Exception as error:  # a broken check must not block a good action
            results.append(Result(c.name, c.label, "error", f"{type(error).__name__}: {error}"))
            continue
        if verdict is None or not verdict.applies:
            why = verdict.message if verdict else "Nothing to check for this call."
            results.append(Result(c.name, c.label, "skipped", why))
        else:
            results.append(
                Result(c.name, c.label, "passed" if verdict.ok else "failed", verdict.message)
            )
    return results


def run_checks(checks: Sequence[Check], answer: str, record: Record) -> list[Result]:
    """Every switched-on check, in order, so the page can account for each one. A check that
    doesn't apply is "skipped" with its reason. A check that raises is an error, not a
    failure: a bug in a check must not make the model rewrite a good answer."""
    results = []
    for c in checks:
        try:
            verdict = c.fn(answer, record)
        except Exception as error:
            results.append(Result(c.name, c.label, "error", f"{type(error).__name__}: {error}"))
            continue
        if verdict is None or not verdict.applies:
            why = verdict.message if verdict else "Nothing to check in this answer."
            results.append(Result(c.name, c.label, "skipped", why))
            continue
        status: Status = "passed" if verdict.ok else "failed"
        results.append(Result(c.name, c.label, status, verdict.message))
    return results


def feedback(failures: Sequence[Result]) -> str:
    """The note sent back to the model: what failed, in the checks' own words."""
    lines = "\n".join(f"- {r.label}: {r.message}" for r in failures)
    return (
        f"{NOTE_PREFIX} Your answer did not pass these checks:\n{lines}\n"
        "Fix them with what you already have; call a tool only if the fix needs a fact you "
        "don't have yet. Then give your full answer again, written for the person: don't "
        "mention these checks or your earlier draft."
    )


def load_checks(file: Path) -> tuple[tuple[Check, ...], tuple[ActionCheck, ...]]:
    """A workspace's ``CHECKS`` (on answers) and ``ACTION_CHECKS`` (on a tool's call, S12),
    imported by path (workspaces are not packages)."""
    from agentic_harness.workspace import WorkspaceError  # here: workspace imports this file

    if not file.is_file():
        raise WorkspaceError(f"[verify] checks: {file.name} not found in the workspace.")
    spec = importlib.util.spec_from_file_location(f"workspace_checks_{file.parent.name}", file)
    if spec is None or spec.loader is None:
        raise WorkspaceError(f"Cannot import {file}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    checks = getattr(module, "CHECKS", None)
    if not isinstance(checks, list | tuple) or not all(isinstance(c, Check) for c in checks):
        raise WorkspaceError(f"{file} must define CHECKS as a list of @check functions.")
    actions = getattr(module, "ACTION_CHECKS", [])
    if not isinstance(actions, list | tuple) or not all(
        isinstance(c, ActionCheck) for c in actions
    ):
        raise WorkspaceError(f"{file}: ACTION_CHECKS must be a list of @action_check functions.")
    names = [c.name for c in [*checks, *actions]]
    if PLAN_CHECK.name in names or len(set(names)) != len(names):
        raise WorkspaceError(f"{file}: check names must be unique (and not {PLAN_CHECK.name}).")
    return tuple(checks), tuple(actions)
