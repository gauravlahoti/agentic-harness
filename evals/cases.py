"""Golden cases: load a workspace's eval file and check every field (S10-AC1).

Part of the evals (not the harness). A case says who asks what (profile, turns) and what a
correct run looks like: the tools it must call, the words its answer must and must not
contain, who must approve, which never-rule must fire. ``evals/checks.py`` checks those in
code; ``expected_outcome`` goes to the judge.

A typo must fail loudly, not silently skip a check, so unknown fields are errors and every
error names the case and the field.

Does not: run anything, or know any workspace (the file names its own).
"""

import re
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Literal

ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
DECISIONS = ("approve", "reject")
TEXT_LISTS = (
    "expected_tools",
    "must_include",
    "must_not_include",
    "never_call",
    "expect_approval",
    "expect_blocked",
    "allowed_tools",
)
KNOWN = {
    "id",
    "group",
    "profile",
    "turns",
    "expected_outcome",
    "key_args",
    "scope",
    "approvals",
    "expect_flagged",
    "core",
    "reference_answer",
    "max_steps",
    *TEXT_LISTS,
}


class CaseError(ValueError):
    """A golden case (or the file) is wrong; the message names the case and the field."""


@dataclass(frozen=True, slots=True)
class Case:
    id: str
    group: str
    profile: str
    turns: tuple[str, ...]
    expected_outcome: str
    expected_tools: tuple[str, ...] = ()
    key_args: dict[str, dict[str, Any]] = field(default_factory=dict)
    must_include: tuple[str, ...] = ()  # in the last answer
    must_not_include: tuple[str, ...] = ()  # in any answer
    never_call: tuple[str, ...] = ()  # must never run to completion
    scope: Literal["in", "out"] = "in"
    approvals: dict[str, str] = field(default_factory=dict)  # role → approve | reject
    expect_approval: tuple[str, ...] = ()
    expect_blocked: tuple[str, ...] = ()
    expect_flagged: bool = False
    core: bool = False  # in the Run dialog's default set: a few cases that score every metric
    # Reference-based metrics (D-161): a right final answer, a step budget, and tools that are
    # fine to call beyond expected_tools (the file's own allowed_tools are added to each case).
    reference_answer: str = ""
    max_steps: int | None = None
    allowed_tools: tuple[str, ...] = ()

    @property
    def multi_turn(self) -> bool:
        return len(self.turns) > 1


@dataclass(frozen=True, slots=True)
class Suite:
    path: Path
    workspace: Path
    cases: tuple[Case, ...]

    def pick(self, ids: list[str] | None) -> list[Case]:
        """The cases asked for, in the order asked; all of them for None."""
        if not ids:
            return list(self.cases)
        by_id = {c.id: c for c in self.cases}
        if unknown := [i for i in ids if i not in by_id]:
            raise CaseError(f"No case named {unknown[0]!r} in {self.path.name}.")
        return [by_id[i] for i in ids]


def load_suite(path: Path) -> Suite:
    """Read a cases file; raise CaseError naming the first wrong field."""
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise CaseError(f"{path.name}: {error}") from None
    workspace = (path.parent / str(data.get("workspace", ""))).resolve()
    if not data.get("workspace") or not (workspace / "workspace.toml").is_file():
        raise CaseError(f"{path.name}: 'workspace' must point to a folder with workspace.toml.")
    shared = data.get("allowed_tools", [])
    if not isinstance(shared, list) or not all(isinstance(t, str) for t in shared):
        raise CaseError(f"{path.name}: allowed_tools must be a list of tool names.")
    cases = tuple(
        replace(c, allowed_tools=(*c.allowed_tools, *shared))
        for c in (_case(raw, n) for n, raw in enumerate(data.get("case", []), 1))
    )
    seen: set[str] = set()
    for case in cases:
        if case.id in seen:
            raise CaseError(f"Case id {case.id!r} is used twice.")
        seen.add(case.id)
    return Suite(path, workspace, cases)


def _case(raw: dict[str, Any], number: int) -> Case:
    name = str(raw.get("id", f"#{number}"))

    def fail(key: str, why: str) -> CaseError:
        return CaseError(f"Case {name!r}: {key} {why}")

    if unknown := sorted(set(raw) - KNOWN):
        raise fail(unknown[0], "is not a known field.")
    if not isinstance(raw.get("id"), str) or not ID.match(raw["id"]):
        raise fail("id", "must be lowercase letters, digits and dashes.")
    for key in ("group", "profile", "expected_outcome"):
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise fail(key, "must be a non-empty string.")
    turns = raw.get("turns")
    if not isinstance(turns, list) or not turns or not all(isinstance(t, str) for t in turns):
        raise fail("turns", "must be a non-empty list of messages.")
    lists: dict[str, tuple[str, ...]] = {}
    for key in TEXT_LISTS:
        value = raw.get(key, [])
        if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
            raise fail(key, "must be a list of strings.")
        lists[key] = tuple(value)
    scope = raw.get("scope", "in")
    if scope not in ("in", "out"):
        raise fail("scope", 'must be "in" or "out".')
    approvals = raw.get("approvals", {})
    if not isinstance(approvals, dict) or any(v not in DECISIONS for v in approvals.values()):
        raise fail("approvals", 'must map a role to "approve" or "reject".')
    key_args = raw.get("key_args", {})
    if not isinstance(key_args, dict) or not all(isinstance(v, dict) for v in key_args.values()):
        raise fail("key_args", "must map a tool name to its expected arguments.")
    reference = raw.get("reference_answer", "")
    if not isinstance(reference, str):
        raise fail("reference_answer", "must be a string.")
    steps = raw.get("max_steps")
    if steps is not None and (not isinstance(steps, int) or isinstance(steps, bool) or steps < 0):
        raise fail("max_steps", "must be a whole number, 0 or more.")
    flagged = raw.get("expect_flagged", False)
    core = raw.get("core", False)
    for key, value in (("expect_flagged", flagged), ("core", core)):
        if not isinstance(value, bool):
            raise fail(key, "must be true or false.")
    return Case(
        id=raw["id"],
        group=raw["group"],
        profile=raw["profile"],
        turns=tuple(turns),
        expected_outcome=raw["expected_outcome"],
        key_args=key_args,
        scope=scope,
        approvals=dict(approvals),
        expect_flagged=flagged,
        core=core,
        reference_answer=reference,
        max_steps=steps,
        **lists,
    )
