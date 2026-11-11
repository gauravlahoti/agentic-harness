"""Reading a workspace (S02-AC1, AC3, AC6; D-39, D-41).

Each test builds a small workspace in a temp folder, so the harness is checked
against the *shape* of a workspace, not against CloudCo's content.
"""

import textwrap
from pathlib import Path

import pytest

from agentic_harness.workspace import Workspace, WorkspaceError

TOML = """
name = "Test Agent"
owner = "TestCo"
memory = ["AGENTS.md", "teams/{profile}.md"]
skills = ["skills/shared", "skills/{profile}"]
tools = "tools.py"
memory_budget_tokens = 500
domain_words = ["widget", "gizmo"]
examples = ["Do the thing", "Do the other thing"]

[profiles.alpha]
label = "Alpha team"

[profiles.beta]
label = "Beta team"
"""


def skill(root: Path, folder: str, name: str, description: str = "Does a thing.") -> None:
    path = root / folder / name / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\nname: {name}\ndescription: {description}\n---\n\nSteps for {name}.\n")


def make(tmp_path: Path, toml: str = TOML) -> Path:
    (tmp_path / "workspace.toml").write_text(textwrap.dedent(toml))
    (tmp_path / "AGENTS.md").write_text("Always be careful.\n")
    (tmp_path / "teams").mkdir()
    (tmp_path / "teams" / "alpha.md").write_text("Alpha rules.\n")
    skill(tmp_path, "skills/shared", "shared-skill")
    skill(tmp_path, "skills/alpha", "alpha-skill")
    skill(tmp_path, "skills/beta", "beta-skill")
    return tmp_path


def test_s02_ac1_reads_workspace_toml(tmp_path: Path) -> None:
    ws = Workspace.load(make(tmp_path))
    assert ws.title == "Test Agent"
    assert ws.owner == "TestCo"
    assert ws.memory == ("AGENTS.md", "teams/{profile}.md")
    assert ws.skill_dirs == ("skills/shared", "skills/{profile}")
    assert [(p.id, p.label) for p in ws.profiles] == [
        ("alpha", "Alpha team"),
        ("beta", "Beta team"),
    ]
    assert ws.memory_budget_tokens == 500
    assert ws.domain_words == ("widget", "gizmo")
    assert ws.examples == ("Do the thing", "Do the other thing")


def test_s02_ac1_toml_is_optional(tmp_path: Path) -> None:
    ws = Workspace.load(tmp_path)  # D-41: an empty folder is a valid (if useless) workspace
    assert ws.title == tmp_path.name
    assert ws.profiles == ()
    assert ws.memory_files(None) == []
    assert ws.skills(None) == []


def test_s02_ac1_wrong_types_are_clear_errors(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text('memory = "AGENTS.md"\n')
    with pytest.raises(WorkspaceError, match="memory"):
        Workspace.load(tmp_path)


def test_s02_ac1_broken_toml_is_a_clear_error(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text("name = \n")
    with pytest.raises(WorkspaceError, match=r"workspace\.toml"):
        Workspace.load(tmp_path)


def test_s02_ac3_profile_picks_its_own_file(tmp_path: Path) -> None:
    ws = Workspace.load(make(tmp_path))
    files = ws.memory_files("alpha")
    assert [f.path for f in files] == ["AGENTS.md", "teams/alpha.md"]
    assert files[1].text == "Alpha rules.\n"


def test_s02_ac3_a_profile_without_its_own_file_just_skips_it(tmp_path: Path) -> None:
    ws = Workspace.load(make(tmp_path))
    assert [f.path for f in ws.memory_files("beta")] == ["AGENTS.md"]


def test_s02_ac3_a_missing_fixed_file_is_an_error(tmp_path: Path) -> None:
    ws = Workspace.load(make(tmp_path))
    (tmp_path / "AGENTS.md").unlink()
    with pytest.raises(WorkspaceError, match=r"AGENTS\.md"):
        ws.memory_files("alpha")


def test_s02_ac3_default_and_unknown_profiles(tmp_path: Path) -> None:
    ws = Workspace.load(make(tmp_path))
    assert ws.check_profile(None) == "alpha"  # first one listed
    assert ws.check_profile("beta") == "beta"
    with pytest.raises(WorkspaceError, match="gamma"):
        ws.check_profile("gamma")
    plain = Workspace.load(tmp_path / "teams")  # no profiles at all
    assert plain.check_profile(None) is None
    with pytest.raises(WorkspaceError):
        plain.check_profile("alpha")


def test_s02_ac6_each_profile_sees_only_its_skill_folders(tmp_path: Path) -> None:
    ws = Workspace.load(make(tmp_path))
    assert [s.name for s in ws.skills("alpha")] == ["shared-skill", "alpha-skill"]
    assert [s.name for s in ws.skills("beta")] == ["shared-skill", "beta-skill"]


def test_s02_ac6_skill_paths_are_relative_for_sources(tmp_path: Path) -> None:
    ws = Workspace.load(make(tmp_path))
    assert ws.skills("alpha")[1].source == "skills/alpha/alpha-skill/SKILL.md"


def test_s03_ac3_builtins_and_readable_folders(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text(
        'builtins = ["read_file", "write_file"]\nreadable = ["docs", "data/sub"]\n'
    )
    ws = Workspace.load(tmp_path)
    assert ws.builtins == ("read_file", "write_file")
    assert ws.readable == ("docs", "data/sub")


def test_s03_ac3_unknown_builtin_is_a_clear_error(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text('builtins = ["run_shell"]\n')
    with pytest.raises(WorkspaceError, match="run_shell"):
        Workspace.load(tmp_path)


def test_s03_ac3_tools_load_from_tools_py_with_the_decorator(tmp_path: Path) -> None:
    (tmp_path / "tools.py").write_text(
        textwrap.dedent(
            '''
            from agentic_harness.tools.registry import tool

            @tool(risk="read")
            def find_widget(widget_id: str) -> dict[str, str]:
                """Find one widget by ID."""
                return {"id": widget_id}

            TOOLS = [find_widget]
            '''
        )
    )
    ws = Workspace.load(tmp_path)
    assert [(t.name, t.risk) for t in ws.tools] == [("find_widget", "read")]


GATED = """
[profiles.alpha]
label = "Alpha"
tools = ["find"]
hide_fields = ["value"]

[profiles.beta]
label = "Beta"

[[rules]]
id = "price-never"
label = "Price above 50"
tool = "send"
arg = "price"
above = 50
because = "terms §2"

[[approvals]]
tool = "send"
because = "chart §3"
"""


GATED_TOOLS = (
    "from agentic_harness.tools.registry import tool\n\n"
    '@tool(risk="read")\ndef find(item: str) -> str:\n    """Find."""\n    return item\n\n'
    '@tool(risk="action")\ndef send(price: int = 0) -> str:\n    """Send."""\n    return "sent"\n\n'
    "TOOLS = [find, send]\n"
)


def test_s05_ac1_profiles_rules_and_approvals_come_from_workspace_toml(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text(GATED)
    (tmp_path / "tools.py").write_text(GATED_TOOLS)
    ws = Workspace.load(tmp_path)
    alpha, beta = ws.profiles
    assert (alpha.tools, alpha.hide_fields) == (("find",), ("value",))
    assert beta.tools is None  # no list: every tool
    gate = ws.gate("alpha")
    assert gate.check("send", {}).rule == "profile-tools"
    assert ws.gate("beta").check("send", {"price": 60}).rule == "price-never"
    assert ws.gate("beta").check("send", {"price": 1}).kind == "ask"


def test_s05_ac1_bad_rules_are_clear_errors(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text(GATED.replace("above = 50", ""))
    (tmp_path / "tools.py").write_text(GATED_TOOLS)
    with pytest.raises(WorkspaceError, match="price-never"):
        Workspace.load(tmp_path)


def test_s06_ac9_ask_human_is_on_only_when_the_workspace_says_so(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text("ask_human = true\n")
    assert Workspace.load(tmp_path).ask_human is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert Workspace.load(plain).ask_human is False


def test_s10_synthetic_data_is_said_by_the_workspace_not_the_harness(tmp_path: Path) -> None:
    """The page tags a workspace's data "Synthetic Data" only when the workspace says so."""
    (tmp_path / "workspace.toml").write_text("synthetic_data = true\n")
    assert Workspace.load(tmp_path).synthetic_data is True
    plain = tmp_path / "plain"
    plain.mkdir()
    assert Workspace.load(plain).synthetic_data is False
    cloudco = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
    assert Workspace.load(cloudco).synthetic_data is True  # its data is all made up


def test_s06_ac1_approvals_take_a_role_a_label_and_a_condition(tmp_path: Path) -> None:
    (tmp_path / "tools.py").write_text(
        "from agentic_harness.tools.registry import tool\n\n"
        "@tool(risk='action')\ndef send(price: int = 0) -> str:\n    'Send.'\n    return 'ok'\n\n"
        "TOOLS = [send]\n"
    )
    (tmp_path / "workspace.toml").write_text(
        """
[[approvals]]
tool = "send"
approver = "Boss"
label = "Price over 20"
arg = "price"
above = 20
because = "chart §1"

[[approvals]]
tool = "send"
approver = "Sales"
because = "chart §3"
"""
    )
    approvals = Workspace.load(tmp_path).approvals
    assert [(a.approver, a.label, a.arg, a.above) for a in approvals] == [
        ("Boss", "Price over 20", "price", 20),
        ("Sales", "", "", None),
    ]
    (tmp_path / "workspace.toml").write_text('[[approvals]]\ntool = "send"\narg = "price"\n')
    with pytest.raises(WorkspaceError, match="needs above or equals"):
        Workspace.load(tmp_path)
