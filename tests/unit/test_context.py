"""Building the system prompt (S02-AC2, AC4, AC7, AC8; D-37, D-38)."""

from pathlib import Path

from agentic_harness.context import build_context, estimate_tokens
from agentic_harness.loop import SYSTEM_PROMPT
from agentic_harness.workspace import Workspace

TOML = """
name = "Test Agent"
memory = ["AGENTS.md", "teams/{profile}.md"]
skills = ["skills/{profile}"]
memory_budget_tokens = 50

[profiles.alpha]
label = "Alpha"
"""


def make(tmp_path: Path, team_text: str = "Alpha rules.") -> Workspace:
    (tmp_path / "workspace.toml").write_text(TOML)
    (tmp_path / "AGENTS.md").write_text("ALWAYS-RULE")
    (tmp_path / "teams").mkdir()
    (tmp_path / "teams" / "alpha.md").write_text(team_text)
    folder = tmp_path / "skills" / "alpha" / "do-it"
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(
        "---\nname: do-it\ndescription: How to do it.\n---\nSECRET-STEP-BODY\n"
    )
    return Workspace.load(tmp_path)


def test_s02_ac2_fixed_order_base_memory_skills(tmp_path: Path) -> None:
    system = build_context(make(tmp_path), "alpha").system
    base = system.index(SYSTEM_PROMPT)
    agents = system.index("ALWAYS-RULE")
    team = system.index("Alpha rules.")
    skills = system.index("do-it: How to do it.")
    assert base < agents < team < skills


def test_s02_ac4_only_skill_names_and_descriptions_in_the_prompt(tmp_path: Path) -> None:
    system = build_context(make(tmp_path), "alpha").system
    assert "do-it: How to do it." in system
    assert "SECRET-STEP-BODY" not in system  # the body arrives only through load_skill
    assert "load_skill" in system


def test_s02_ac2_no_skills_means_no_skill_section(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("Only rules.")
    system = build_context(Workspace.load(tmp_path), None).system
    assert "load_skill" not in system
    assert "Only rules." not in system  # without workspace.toml nothing is a memory file


def test_s02_ac7_a_big_memory_file_gives_a_warning(tmp_path: Path) -> None:
    ctx = build_context(make(tmp_path, team_text="x" * 400), "alpha")  # ~100 tokens > 50
    assert any("teams/alpha.md" in w for w in ctx.warnings)
    sizes = {f["path"]: f["tokens"] for f in ctx.summary()["files"]}
    assert sizes["teams/alpha.md"] == 100
    assert not any("AGENTS.md" in w for w in ctx.warnings)


def test_s02_ac7_estimate_is_characters_over_four() -> None:
    assert estimate_tokens("") == 0
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("abcde") == 2


def test_s02_ac8_the_same_prompt_every_time(tmp_path: Path) -> None:
    ws = make(tmp_path)
    first, second = build_context(ws, "alpha"), build_context(ws, "alpha")
    assert first.system == second.system
    assert first.prompt_id == second.prompt_id
    assert len(first.prompt_id) == 12


def test_s02_ac12_summary_for_the_page(tmp_path: Path) -> None:
    summary = build_context(make(tmp_path), "alpha").summary()
    assert summary["profile"] == "alpha"
    assert [f["path"] for f in summary["files"]] == ["AGENTS.md", "teams/alpha.md"]
    assert summary["skills"] == [
        {"name": "do-it", "description": "How to do it.", "source": "skills/alpha/do-it/SKILL.md"}
    ]
    assert summary["prompt_tokens"] > 0
    assert summary["prompt_id"]
