"""Tools: a name, a description, a JSON schema, a risk, and the Python function behind it.

Harness part: actions. The model only ever sees the declaration (name, description,
parameters); it never gets the function, the risk or the ``ctx``. Tools are usually made
with ``@tool`` (registry.py), which builds this record from the function itself (D-43).

``ToolContext`` is what the harness hands a tool that asks for ``ctx`` (D-48): the run's
ID, the workspace folder, and the only two ways a tool may write a file. Every write
goes through it, so it is checked in one place and announced as a ``file_saved`` event.

Does not: run tools (registry.call_tool does), or know any workspace's tools by name.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from agentic_harness.limits import Budget

Risk = Literal["read", "write", "action"]
RISKS: tuple[Risk, ...] = ("read", "write", "action")

# A plain file name: no folders, no leading dot (so no ".env", no "../").
FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}")


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    risk: Risk  # required (D-44): guardrails gate on it without knowing the tool
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    function: Callable[..., Any] = field(default=lambda: None, repr=False)
    # Which harness part acts when this tool runs: "tool" for actions, "context" for
    # built-ins that only read context (load_skill). The page colours lines by it.
    part: str = "tool"
    takes_ctx: bool = False  # the function has a ``ctx`` parameter the harness fills in

    def declaration(self) -> dict[str, Any]:
        """What Gemini is shown: its function-tool format."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


def _no_events(type_: str, **data: Any) -> None:
    """The default listener: nobody is watching (tests, scripts)."""


@dataclass(frozen=True, slots=True)
class ToolContext:
    """What a tool may know about its run, and the only way it may write a file."""

    run_id: str
    root: Path  # the workspace folder
    readable: tuple[str, ...] = ()  # folders read_file may open (D-46)
    emit: Callable[..., None] = _no_events
    call_id: str = ""  # which tool call is running, so the page can tie a file to it
    budget: Budget | None = None  # the run's budget: a helper gets a slice of it (S04)
    # Who approved this call, in order: {"approver", "rule", "at", "note"}. A tool that leaves
    # a record (an outbox file) can write it down (S06-AC10).
    approvals: tuple[dict[str, str], ...] = ()
    # Which profile is asking, so a tool can leave out what that profile must not see, in
    # code rather than by asking the model (D-106). Helpers get their caller's profile.
    profile: str | None = None

    @property
    def task_dir(self) -> Path:
        return self.root / "tasks" / self.run_id  # drafts of this run (D-47)

    @property
    def outbox(self) -> Path:
        return self.root / "outbox"  # where actions land; never real email

    def save_task_file(self, name: str, text: str) -> str:
        return self._save(self.task_dir, name, text, folder="tasks")

    def save_outbox_file(self, name: str, text: str) -> str:
        return self._save(self.outbox, name, text, folder="outbox")

    def _save(self, folder_path: Path, name: str, text: str, *, folder: str) -> str:
        if not FILE_NAME.fullmatch(name) or ".." in name:
            raise ValueError(f"Bad file name {name!r}: use a plain file name like 'draft.md'.")
        folder_path.mkdir(parents=True, exist_ok=True)
        file = folder_path / name
        file.write_text(text)
        relative = file.relative_to(self.root).as_posix()
        # The page shows a file card from this event; the model only gets the path (D-53).
        self.emit("file_saved", path=relative, folder=folder, text=text, call_id=self.call_id)
        return relative
