"""Sub-agents and switches (S04-AC1, AC3 to AC6, AC8, AC12; D-55 to D-61, D-64, D-70).

A throwaway workspace with one helper is enough: the harness is checked against the
*shape* of a sub-agent, never against CloudCo's. Running a child end to end needs a real
model, so that part is proven live (D-65); here we test the pieces around it.
"""

import textwrap
from pathlib import Path

import pytest

from agentic_harness.api import Off, create_harness, describe_harness
from agentic_harness.config import Settings
from agentic_harness.events import Event
from agentic_harness.limits import Budget, Limits
from agentic_harness.loop import RunResult
from agentic_harness.model import GeminiModel, ModelClient
from agentic_harness.subagents import (
    MAX_CHILD_STEPS,
    cap_words,
    child_limits,
    result_text,
    tag_events,
)
from agentic_harness.workspace import Workspace, WorkspaceError

TOOLS = '''
from agentic_harness.tools import ToolContext
from agentic_harness.tools.registry import tool

@tool(risk="read")
def look(item: str) -> str:
    """Look at one item."""
    return item

@tool(risk="read")
def scan(item: str) -> str:
    """Scan a big document."""
    return item

@tool(risk="action")
def poke(item: str) -> str:
    """Change something."""
    return item

TOOLS = [look, scan, poke]
'''

TOML = """
name = "Test Agent"
skills = ["skills"]
delegate_only = ["scan"]

[subagents.helper]
description = "Reads big documents and returns a short summary."
instructions = "agents/helper.md"
tools = ["look", "scan"]
model = "gemini-3.5-flash-lite"
max_words = 50
"""


def make(tmp_path: Path, toml: str = TOML) -> Workspace:
    (tmp_path / "tools.py").write_text(TOOLS)
    (tmp_path / "workspace.toml").write_text(textwrap.dedent(toml))
    (tmp_path / "agents").mkdir(exist_ok=True)
    (tmp_path / "agents" / "helper.md").write_text("HELPER-INSTRUCTIONS: list each finding.\n")
    skill = tmp_path / "skills" / "do-it" / "SKILL.md"
    skill.parent.mkdir(parents=True, exist_ok=True)
    skill.write_text("---\nname: do-it\ndescription: How to do it.\n---\nSteps.\n")
    return Workspace.load(tmp_path)


def model(name: str = "gemini-3.6-flash") -> ModelClient:
    return GeminiModel(Settings(model=name), client=object())  # built, never called


def harness(ws: Workspace, **kwargs: object):  # type: ignore[no-untyped-def]
    built: list[str] = []

    def factory(name: str) -> ModelClient:
        built.append(name)
        return model(name)

    h = create_harness(model(), Limits(), ws, trace_dir=None, model_factory=factory, **kwargs)  # type: ignore[arg-type]
    return h, built


def test_s04_ac1_subagents_come_from_workspace_toml(tmp_path: Path) -> None:
    ws = make(tmp_path)
    [helper] = ws.subagents
    assert helper.name == "helper"
    assert helper.tools == ("look", "scan")
    assert helper.model == "gemini-3.5-flash-lite"
    assert helper.max_words == 50
    assert "HELPER-INSTRUCTIONS" in helper.instructions
    assert helper.source == "agents/helper.md"
    assert ws.delegate_only == ("scan",)


def test_s04_ac1_the_harness_has_none_built_in(tmp_path: Path) -> None:
    plain = Workspace.load(tmp_path)
    assert plain.subagents == ()
    h = create_harness(model(), Limits(), plain, trace_dir=None)
    assert "delegate_task" not in h.tools


@pytest.mark.parametrize(
    ("change", "problem"),
    [
        ('instructions = "agents/helper.md"', 'instructions = "agents/missing.md"'),
        ("[subagents.helper]", "[subagents.Bad_Name]"),
        ('tools = ["look", "scan"]', 'tools = ["look", "nope"]'),
        ("max_words = 50", 'max_words = "short"'),
        ('delegate_only = ["scan"]', 'delegate_only = ["look", "poke"]'),
    ],
)
def test_s04_ac1_bad_declarations_are_clear_errors(
    tmp_path: Path, change: str, problem: str
) -> None:
    with pytest.raises(WorkspaceError):
        make(tmp_path, TOML.replace(change, problem))


def test_s04_ac3_helpers_may_only_read(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="read"):
        make(tmp_path, TOML.replace('tools = ["look", "scan"]', 'tools = ["look", "poke"]'))


def test_s04_ac3_ac4_the_child_gets_only_its_declared_tools(tmp_path: Path) -> None:
    h, built = harness(make(tmp_path))
    child = h.tools["delegate_task"].function.make_child(make(tmp_path).subagents[0], Limits())  # type: ignore[attr-defined]
    assert sorted(child.tools) == ["look", "scan"]  # no poke, no load_skill, no delegate_task
    assert "HELPER-INSTRUCTIONS" in child.system
    assert child.model.name == "gemini-3.5-flash-lite"
    assert built == ["gemini-3.5-flash-lite"]  # its own model (D-62)


def test_s04_ac4_a_child_cannot_declare_delegate_task(tmp_path: Path) -> None:
    toml = TOML.replace('tools = ["look", "scan"]', 'tools = ["look", "delegate_task"]')
    with pytest.raises(WorkspaceError, match="delegate_task"):
        make(tmp_path, toml)


def test_s04_ac1_delegate_task_lists_the_helpers(tmp_path: Path) -> None:
    h, _ = harness(make(tmp_path))
    tool = h.tools["delegate_task"]
    assert tool.parameters["properties"]["agent"]["enum"] == ["helper"]
    assert tool.parameters["required"] == ["agent", "brief"]
    assert "Reads big documents" in tool.description
    assert tool.risk == "read"


def test_s04_ac5_delegate_only_tools_leave_the_parent(tmp_path: Path) -> None:
    on, _ = harness(make(tmp_path))
    assert "scan" not in on.tools  # only the helper reads the big document (D-59)
    off, _ = harness(make(tmp_path), delegation=False)
    assert "delegate_task" not in off.tools
    assert "scan" in off.tools  # delegation off: the parent does it itself


def test_s04_ac5_the_child_gets_a_slice_of_what_is_left() -> None:
    now = [0.0]
    budget = Budget(Limits(max_steps=25, max_usd=1.0, max_seconds=120), clock=lambda: now[0])
    limits = child_limits(budget)
    assert (limits.max_usd, limits.max_seconds, limits.max_steps) == (0.25, 60.0, MAX_CHILD_STEPS)
    budget.charge(0.6)
    now[0] = 80.0
    limits = child_limits(budget)
    assert limits.max_usd == pytest.approx(0.1)
    assert limits.max_seconds == pytest.approx(20.0)  # half of the 40 s left
    budget.charge(1.0)  # nothing left: still a valid (tiny) limit, so the child stops at once
    assert child_limits(budget).max_usd > 0


def result(outcome: str, reason: str, answer: str = "", text: str = "") -> RunResult:
    steps = [{"type": "model_output", "content": [{"type": "text", "text": text}]}] if text else []
    return RunResult("child-1", outcome, reason, answer, steps, 3, 0.01, 4.0)  # type: ignore[arg-type]


def test_s04_ac5_out_of_budget_gives_a_partial_answer_and_the_reason() -> None:
    text = result_text(result("stopped", "time_limit", text="Found 3 so far."), "helper", 50)
    assert "helper stopped early: time_limit" in text
    assert "Found 3 so far." in text
    empty = result_text(result("failed", "model_error: Gemini 429"), "helper", 50)
    assert "model_error: Gemini 429" in empty
    assert "no answer" in empty


def test_s04_ac6_the_result_is_cut_at_the_word_limit() -> None:
    long = " ".join(f"w{i}" for i in range(80))
    assert cap_words(long, 50).endswith("[cut: 30 more words]")
    assert len(cap_words(long, 50).split()) == 50 + 4  # + "[cut: 30 more words]"
    assert cap_words("short answer", 50) == "short answer"
    assert result_text(result("completed", "answered", answer=long), "helper", 50) == cap_words(
        long, 50
    )


def test_s04_ac8_child_events_are_tagged() -> None:
    seen: list[tuple[str, dict[str, object]]] = []
    listener = tag_events(lambda type_, **data: seen.append((type_, data)), "parent-1", "helper")
    listener(Event("tool_started", "child-1", 3, 0.0, {"name": "look", "call_id": "c9"}))
    assert seen == [
        (
            "tool_started",
            {
                "name": "look",
                "call_id": "c9",
                "agent_id": "child-1",
                "parent_id": "parent-1",
                "agent": "helper",
            },
        )
    ]


def test_s04_ac12_switches_remove_tools_skills_and_helpers(tmp_path: Path) -> None:
    ws = make(tmp_path)
    h, _ = harness(ws, off=Off(tools=("look",)))
    assert "look" not in h.tools
    child = h.tools["delegate_task"].function.make_child(ws.subagents[0], Limits())  # type: ignore[attr-defined]
    assert sorted(child.tools) == ["scan"]  # off means off for helpers too
    h, _ = harness(ws, off=Off(skills=("do-it",)))
    assert "load_skill" not in h.tools
    assert "do-it" not in h.system
    h, _ = harness(ws, off=Off(subagents=("helper",)))
    assert "delegate_task" not in h.tools
    assert "scan" in h.tools  # the delegate-only tool comes back
    assert h.off == {"tools": [], "skills": [], "subagents": ["helper"]}


def test_s04_ac12_unknown_names_are_refused(tmp_path: Path) -> None:
    ws = make(tmp_path)
    for off in (Off(tools=("nope",)), Off(skills=("nope",)), Off(subagents=("nope",))):
        with pytest.raises(WorkspaceError, match="nope"):
            harness(ws, off=off)


def test_s04_ac11_describe_harness_matches_what_runs(tmp_path: Path) -> None:
    ws = make(tmp_path)
    info = describe_harness(ws, None)
    assert [s["name"] for s in info["skills"]] == ["do-it"]
    tools = {t["name"]: t for t in info["tools"]}
    assert tools["poke"]["risk"] == "action"
    assert tools["scan"]["delegate_only"] is True
    assert tools["look"]["parameters"]["required"] == ["item"]
    assert info["subagents"][0]["name"] == "helper"
    assert info["subagents"][0]["tools"] == ["look", "scan"]


def test_s04_ac11_pane_sections_follow_the_harness_parts(tmp_path: Path) -> None:
    info = describe_harness(make(tmp_path), None, Limits(max_steps=9, max_usd=0.5, max_seconds=60))
    loop = info["loop"]
    assert (loop["max_steps"], loop["max_usd"], loop["max_seconds"]) == (9, 0.5, 60)
    assert loop["helper_slice"] == {"time": 0.5, "money": 0.25, "max_steps": MAX_CHILD_STEPS}
    assert loop["prompt_id"]
    guard = info["guardrails"]
    assert guard["allowed"] == ["look", "scan", "poke"]  # no profile: every tool
    assert guard["never"] == []
    assert guard["approvals"] == []
    assert "workspace.toml" in guard["protected"]
    assert info["memory"] == {"notes_on": False, "notes": [], "conversations": 0}


def test_s04_ac8_only_the_main_agents_finish_ends_the_page_stream() -> None:
    """Found live: a helper's run_finished closed the stream and cancelled the parent."""
    from agentic_harness.server.runs import ends_stream

    assert ends_stream({"type": "run_finished", "data": {"outcome": "completed"}})
    helper = {"type": "run_finished", "data": {"outcome": "completed", "agent_id": "c1"}}
    assert not ends_stream(helper)
    assert not ends_stream({"type": "model_called", "data": {}})


def test_s05_ac8_a_helper_never_has_more_rights_than_its_caller(tmp_path: Path) -> None:
    toml = TOML + '\n[profiles.narrow]\nlabel = "Narrow"\ntools = ["look", "scan"]\n'
    toml += '\n[profiles.tiny]\nlabel = "Tiny"\ntools = ["scan"]\n'
    ws = make(tmp_path, toml)
    h, _ = harness(ws, profile="tiny")
    child = h.tools["delegate_task"].function.make_child(ws.subagents[0], Limits())  # type: ignore[attr-defined]
    assert sorted(child.tools) == ["scan"]  # declared look+scan, but Tiny may only use scan
    assert child.gate is not None
    assert child.gate.label == "Tiny"  # the same gate as its caller
    narrow, _ = harness(ws, profile="narrow")
    assert "poke" not in [t.name for t in narrow.visible_tools()]
