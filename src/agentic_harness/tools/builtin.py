"""Built-in tools: the harness's own, for any workspace that asks for them (S03-AC2).

Harness part: actions. A workspace opts in with ``builtins = [...]`` (D-45).
- ``read_file`` opens files only inside the folders the workspace lists as ``readable``;
  ``.env`` and ``workspace.toml`` never, even if listed (D-46).
- ``write_file`` saves a draft into this run's own folder, ``tasks/<run-id>/`` (D-47).
``load_skill`` is built in too, but lives in skills.py and is added whenever there are skills.

Does not: write anywhere else, run commands, or reach the network.
"""

from collections.abc import Iterable
from typing import Annotated

from agentic_harness.tools import Tool, ToolContext
from agentic_harness.tools.registry import tool

NEVER_READ = {".env", "workspace.toml"}  # secrets, and the config the model must not see


@tool(risk="read")
def read_file(
    path: Annotated[
        str, "A path inside the workspace, e.g. 'policies/terms.md', or a folder to list it"
    ],
    ctx: ToolContext,
) -> str:
    """Read a text file from the workspace, or list a folder's files.
    Use it when you need a document's exact words. Only some folders are open to you;
    an error will say which."""
    folders = [(ctx.root / name).resolve() for name in ctx.readable]
    target = (ctx.root / path).resolve()  # resolve() follows "..", and links, to the real place
    allowed = any(target == folder or target.is_relative_to(folder) for folder in folders)
    if not allowed or target.name in NEVER_READ or target.name.startswith(".env"):
        open_to_you = ", ".join(f"{name}/" for name in ctx.readable) or "none"
        raise PermissionError(f"{path} is not readable. Folders open to you: {open_to_you}")
    if target.is_dir():
        files = sorted(p for p in target.rglob("*") if p.is_file() and not p.name.startswith("."))
        return "\n".join(p.relative_to(ctx.root.resolve()).as_posix() for p in files)
    if not target.is_file():
        raise FileNotFoundError(f"No such file: {path}")
    return target.read_text()


@tool(risk="write")
def write_file(
    name: Annotated[str, "A plain file name, e.g. 'reply-draft.md'"],
    text: Annotated[str, "The full text to save"],
    ctx: ToolContext,
) -> dict[str, str]:
    """Save a draft (for example a reply or a summary) in this task's folder, where people
    can open it. Use it when the task asks you to write or draft something.
    It never sends anything."""
    return {"saved": ctx.save_task_file(name, text)}


BUILTINS: dict[str, Tool] = {t.name: t for t in (read_file, write_file)}


def builtin_tools(names: Iterable[str]) -> list[Tool]:
    """The built-ins a workspace asked for, in its order. Unknown names are an error."""
    tools = []
    for name in names:
        if name not in BUILTINS:
            raise ValueError(f"Unknown built-in tool {name!r} (there are: {', '.join(BUILTINS)}).")
        tools.append(BUILTINS[name])
    return tools
