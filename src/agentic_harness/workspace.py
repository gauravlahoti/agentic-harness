"""Workspaces: the folder that turns the harness into one particular agent (S02-AC1, AC3, AC6).

Harness part: loading. A workspace may have a ``workspace.toml`` (read by the
harness, never shown to the model) naming its memory files, skill folders, tools
file, built-in tools, readable folders and profiles. ``{profile}`` in a path picks the
active profile's file or folder (D-39). Without ``workspace.toml`` a folder still loads, with
just its ``tools.py`` (D-41).

Does not: know any workspace by name, or build the prompt (context.py does).
"""

import importlib.util
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_harness.skills import Skill, find_skills
from agentic_harness.subagents import DEFAULT_MAX_WORDS, SubAgent
from agentic_harness.tools import Tool
from agentic_harness.tools.builtin import BUILTINS

PROFILE = "{profile}"
NAME = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")  # sub-agent names, like skill names
DEFAULT_BUDGET = 2000  # tokens per memory file (D-38)


class WorkspaceError(ValueError):
    """The workspace folder is missing something or declares it wrongly."""


@dataclass(frozen=True, slots=True)
class Profile:
    id: str
    label: str


@dataclass(frozen=True, slots=True)
class MemoryFile:
    path: str  # relative to the workspace, as shown on the page
    text: str


@dataclass(frozen=True, slots=True)
class Workspace:
    path: Path
    name: str  # the folder's name
    title: str = ""  # what the page shows; the folder's name if not set
    owner: str = ""
    tools: tuple[Tool, ...] = ()
    memory: tuple[str, ...] = ()
    skill_dirs: tuple[str, ...] = ()
    profiles: tuple[Profile, ...] = ()
    memory_budget_tokens: int = DEFAULT_BUDGET
    domain_words: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    builtins: tuple[str, ...] = ()  # built-in tools it asks for (D-45)
    readable: tuple[str, ...] = ()  # folders read_file may open (D-46)
    subagents: tuple[SubAgent, ...] = ()  # helpers delegate_task can start (D-55)
    delegate_only: tuple[str, ...] = ()  # tools only helpers get while delegating (D-59)

    @classmethod
    def load(cls, path: Path) -> "Workspace":
        path = Path(path).resolve()
        if not path.is_dir():
            raise WorkspaceError(f"Workspace {path} is not a folder.")
        config = _read_toml(path / "workspace.toml")
        profiles = config.get("profiles", {})
        if not isinstance(profiles, dict):
            raise WorkspaceError("workspace.toml: [profiles] must be a table of profiles.")
        builtins = _texts(config, "builtins")
        if unknown := [name for name in builtins if name not in BUILTINS]:
            known = ", ".join(BUILTINS)
            raise WorkspaceError(
                f"workspace.toml: unknown built-in {unknown[0]!r} (there are: {known})."
            )
        tools = _load_tools(path / (_text(config, "tools") or "tools.py"))
        subagents = _subagents(path, config.get("subagents", {}), tools, builtins)
        delegate_only = _texts(config, "delegate_only")
        helper_tools = {name for agent in subagents for name in agent.tools}
        if stray := [name for name in delegate_only if name not in helper_tools]:
            raise WorkspaceError(
                f"workspace.toml: delegate_only lists {stray[0]!r}, no helper's tool."
            )
        return cls(
            path=path,
            name=path.name,
            title=_text(config, "name") or path.name,
            owner=_text(config, "owner"),
            tools=tools,
            memory=_texts(config, "memory"),
            skill_dirs=_texts(config, "skills"),
            profiles=tuple(
                Profile(id=key, label=_text(value, "label") or key)
                for key, value in profiles.items()
            ),
            memory_budget_tokens=int(config.get("memory_budget_tokens", DEFAULT_BUDGET)),
            domain_words=_texts(config, "domain_words"),
            examples=_texts(config, "examples"),
            builtins=builtins,
            readable=_texts(config, "readable"),
            subagents=subagents,
            delegate_only=delegate_only,
        )

    def check_profile(self, profile: str | None) -> str | None:
        """The profile to use: the one asked for, or the first listed. Unknown → error."""
        ids = [p.id for p in self.profiles]
        if profile is None:
            return ids[0] if ids else None
        if profile not in ids:
            known = ", ".join(ids) or "none"
            raise WorkspaceError(f"Unknown profile {profile!r} (this workspace has: {known}).")
        return profile

    def memory_files(self, profile: str | None) -> list[MemoryFile]:
        """The memory files for this profile, in the order workspace.toml lists them."""
        files = []
        for pattern in self.memory:
            relative = _fill(pattern, profile)
            if relative is None:
                continue
            file = self.path / relative
            if not file.is_file():
                if PROFILE in pattern:
                    continue  # this profile has no file of its own: fine
                raise WorkspaceError(f"Memory file {relative} is listed but missing.")
            files.append(MemoryFile(path=relative, text=file.read_text()))
        return files

    def skills(self, profile: str | None) -> list[Skill]:
        """The skills this profile can see: only its own folders (S02-AC6)."""
        folders = [self.path / rel for p in self.skill_dirs if (rel := _fill(p, profile))]
        return find_skills(folders, root=self.path)


def _fill(pattern: str, profile: str | None) -> str | None:
    if PROFILE not in pattern:
        return pattern
    return None if profile is None else pattern.replace(PROFILE, profile)


def _read_toml(file: Path) -> dict[str, Any]:
    if not file.exists():
        return {}
    try:
        return tomllib.loads(file.read_text())
    except tomllib.TOMLDecodeError as error:
        raise WorkspaceError(f"workspace.toml: {error}") from None


def _text(config: dict[str, Any], key: str) -> str:
    value = config.get(key, "")
    if not isinstance(value, str):
        raise WorkspaceError(f"workspace.toml: {key} must be text.")
    return value


def _texts(config: dict[str, Any], key: str) -> tuple[str, ...]:
    value = config.get(key, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise WorkspaceError(f"workspace.toml: {key} must be a list of text.")
    return tuple(value)


def _load_tools(file: Path) -> tuple[Tool, ...]:
    if not file.exists():
        return ()
    # Import the workspace's own file by path: workspaces are not installed packages.
    spec = importlib.util.spec_from_file_location(f"workspace_tools_{file.parent.name}", file)
    if spec is None or spec.loader is None:
        raise WorkspaceError(f"Cannot import {file}.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tools = getattr(module, "TOOLS", None)
    if not isinstance(tools, list | tuple) or not all(isinstance(t, Tool) for t in tools):
        raise WorkspaceError(f"{file} must define TOOLS as a list of Tool objects.")
    return tuple(tools)


def _subagents(
    root: Path, table: Any, tools: tuple[Tool, ...], builtins: tuple[str, ...]
) -> tuple[SubAgent, ...]:
    """Read ``[subagents.<name>]``. Each helper may use only read-only tools (D-58)."""
    if not isinstance(table, dict):
        raise WorkspaceError("workspace.toml: [subagents] must be a table of helpers.")
    risks = {t.name: t.risk for t in tools} | {n: BUILTINS[n].risk for n in builtins}
    agents = []
    for name, config in table.items():
        where = f"workspace.toml: sub-agent {name!r}"
        if not NAME.fullmatch(name):
            raise WorkspaceError(f"{where}: use lowercase words and hyphens.")
        if not isinstance(config, dict):
            raise WorkspaceError(f"{where} must be a table.")
        instructions = _text(config, "instructions")
        file = root / instructions
        if not instructions or not file.is_file():
            raise WorkspaceError(f"{where}: instructions file {instructions!r} is missing.")
        agent_tools = _texts(config, "tools")
        for tool_name in agent_tools:
            if tool_name not in risks:
                raise WorkspaceError(f"{where}: unknown tool {tool_name!r}.")
            if risks[tool_name] != "read":
                raise WorkspaceError(
                    f"{where}: {tool_name} has risk {risks[tool_name]}; helpers may only read."
                )
        max_words = config.get("max_words", DEFAULT_MAX_WORDS)
        if not isinstance(max_words, int) or isinstance(max_words, bool) or max_words < 1:
            raise WorkspaceError(f"{where}: max_words must be a whole number above zero.")
        agents.append(
            SubAgent(
                name=name,
                description=_text(config, "description") or name,
                instructions=file.read_text(),
                source=instructions,
                tools=agent_tools,
                model=_text(config, "model") or None,
                max_words=max_words,
            )
        )
    return tuple(agents)
