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
