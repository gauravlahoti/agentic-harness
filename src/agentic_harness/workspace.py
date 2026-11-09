"""Workspaces: the folder that turns the harness into one particular agent (D-26).

Harness part: loading. In S01 a workspace gives two things: its tools
(``tools.py`` with a ``TOOLS`` list) and, optionally, a recorded run for
Fake mode (``fake_replies.json``). S02 adds ``workspace.toml``, memory files
and skills.

Does not: know any workspace by name. It loads whatever folder it is given.
"""

import importlib.util
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentic_harness.tools import Tool


class WorkspaceError(ValueError):
    """The workspace folder is missing something or declares it wrongly."""


@dataclass(frozen=True, slots=True)
class Workspace:
    path: Path
    name: str
    tools: tuple[Tool, ...] = ()
    fake_replies: tuple[dict[str, Any], ...] = ()

    @classmethod
    def load(cls, path: Path) -> "Workspace":
        path = Path(path).resolve()
        if not path.is_dir():
            raise WorkspaceError(f"Workspace {path} is not a folder.")
        return cls(
            path=path,
            name=path.name,
            tools=_load_tools(path / "tools.py"),
            fake_replies=_load_fake_replies(path / "fake_replies.json"),
        )


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


def _load_fake_replies(file: Path) -> tuple[dict[str, Any], ...]:
    if not file.exists():
        return ()
    replies = json.loads(file.read_text())
    if not isinstance(replies, list):
        raise WorkspaceError(f"{file} must be a list of recorded Gemini replies.")
    return tuple(replies)
