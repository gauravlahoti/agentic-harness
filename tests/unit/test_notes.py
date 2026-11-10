"""Notes that outlast a conversation (S07-AC4; D-92).

The agent saves a short note with ``save_note``; the note is in its prompt from the next
task on, per profile, capped. These tests use a temp folder and a scripted model.
"""

from pathlib import Path

import pytest

from agentic_harness.api import create_harness
from agentic_harness.config import Settings
from agentic_harness.context import build_context
from agentic_harness.gate import Gate
from agentic_harness.limits import Limits
from agentic_harness.memory import NOTES_BUDGET_TOKENS, load_notes, note_path, save_note_tool
from agentic_harness.model import GeminiModel
from agentic_harness.tools.registry import call_tool
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"


async def save(file: Path, text: str) -> str:
    result = await call_tool(save_note_tool(file), {"note": text}, None)
    return result.output


async def test_s07_ac4_a_note_is_saved_as_a_dated_line(tmp_path: Path) -> None:
    file = note_path(tmp_path, "demo", "sales")
    await save(file, "The CFO capped ShopCo at 20%.")
    await save(file, "Finance rejected Net 60: ShopCo pays late.")
    lines = file.read_text().splitlines()
    assert len(lines) == 2
    assert lines[0].startswith("- 20")  # a date first
    assert lines[0].endswith("The CFO capped ShopCo at 20%.")
    assert load_notes(file) == "\n".join(lines)


async def test_s07_ac4_notes_are_per_profile(tmp_path: Path) -> None:
    await save(note_path(tmp_path, "demo", "sales"), "A sales note")
    assert load_notes(note_path(tmp_path, "demo", "engineering")) == ""
    assert "A sales note" in load_notes(note_path(tmp_path, "demo", "sales"))
    assert note_path(tmp_path, "demo", None).name == "_.md"


async def test_s07_ac4_a_note_must_be_short_and_not_empty(tmp_path: Path) -> None:
    file = note_path(tmp_path, "demo", "sales")
    empty = await call_tool(save_note_tool(file), {"note": "   "}, None)
    assert empty.is_error
    long = await call_tool(save_note_tool(file), {"note": "x" * 600}, None)
    assert long.is_error
    assert not file.exists()


def test_s07_ac4_notes_are_capped_and_the_newest_are_kept(tmp_path: Path) -> None:
    file = note_path(tmp_path, "demo", "sales")
    file.parent.mkdir(parents=True)
    lines = [f"- 2026-11-10 · note number {i:04d} " + "y" * 80 for i in range(400)]
    file.write_text("\n".join(lines) + "\n")
    kept = load_notes(file)
    assert len(kept) <= NOTES_BUDGET_TOKENS * 4
    assert "note number 0399" in kept  # the newest survive
    assert "note number 0000" not in kept
    assert all(line.startswith("- 2026") for line in kept.splitlines())  # whole lines only


def test_s07_ac4_notes_go_at_the_end_of_the_prompt() -> None:
    workspace = Workspace.load(CLOUDCO)
    plain = build_context(workspace, "sales").system
    with_notes = build_context(
        workspace, "sales", notes="- 2026-11-10 · The CFO capped ShopCo at 20%."
    )
    assert with_notes.system.startswith(plain.rstrip("\n"))  # the start never changes: caching
    assert with_notes.system.rstrip().endswith("The CFO capped ShopCo at 20%.")
    assert "## Notes from earlier tasks" in with_notes.system
    assert "## Notes" not in plain


async def test_s07_ac4_a_note_reaches_the_next_task_not_the_current_one(tmp_path: Path) -> None:
    workspace = Workspace.load(CLOUDCO)
    model = GeminiModel(Settings(model="gemini-3.5-flash-lite"), client=object())
    first = create_harness(
        model, Limits(), workspace, profile="sales", trace_dir=None, memory_dir=tmp_path
    )
    assert "Notes from earlier tasks" not in first.system
    tool = first.tools["save_note"]
    await call_tool(tool, {"note": "ShopCo pays late: no Net 60."}, None)
    assert "Notes from earlier tasks" not in first.system  # this task's prompt is unchanged
    second = create_harness(
        model, Limits(), workspace, profile="sales", trace_dir=None, memory_dir=tmp_path
    )
    assert "ShopCo pays late: no Net 60." in second.system
    other = create_harness(
        model, Limits(), workspace, profile="engineering", trace_dir=None, memory_dir=tmp_path
    )
    assert "ShopCo pays late" not in other.system  # another profile's notes stay apart


def test_s07_ac4_save_note_is_on_only_when_the_workspace_says_so(tmp_path: Path) -> None:
    model = GeminiModel(Settings(model="gemini-3.5-flash-lite"), client=object())
    on = create_harness(
        model,
        Limits(),
        Workspace.load(CLOUDCO),
        profile="sales",
        trace_dir=None,
        memory_dir=tmp_path,
    )
    assert "save_note" in on.tools
    hello = Workspace.load(CLOUDCO.parent / "hello")
    off = create_harness(model, Limits(), hello, trace_dir=None, memory_dir=tmp_path)
    assert "save_note" not in off.tools


def test_s07_ac4_every_profile_may_save_notes() -> None:
    gate = Gate("Alpha", ("find",))
    assert gate.allows("save_note")  # like load_skill: how the agent works, not a workspace tool


@pytest.mark.parametrize("name", ["save_note"])
def test_s07_save_note_is_a_write_tool_the_page_can_describe(name: str, tmp_path: Path) -> None:
    tool = save_note_tool(tmp_path / "n.md")
    assert tool.name == name
    assert tool.risk == "write"
    assert len(tool.description) > 40


def test_s07_ac4_save_note_covers_the_persons_preferences(tmp_path: Path) -> None:
    """Long-term memory is also personalization: how the person likes answers."""
    assert "how the person likes your answers" in save_note_tool(tmp_path / "n.md").description
