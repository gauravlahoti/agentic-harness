"""Skills: the open SKILL.md format, read strictly, loaded on demand (S02-AC4, AC5; D-35, D-36)."""

from pathlib import Path

import pytest

from agentic_harness.skills import Skill, SkillError, find_skills, load_skill_tool, read_skill


def write(root: Path, folder: str, text: str) -> Path:
    path = root / folder / "SKILL.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


GOOD = (
    "---\nname: review-notes\ndescription: Review notes step by step.\n---\n\n# Steps\n1. Read.\n"
)


def test_s02_ac5_reads_name_description_and_body(tmp_path: Path) -> None:
    skill = read_skill(write(tmp_path, "review-notes", GOOD), root=tmp_path)
    assert skill.name == "review-notes"
    assert skill.description == "Review notes step by step."
    assert skill.body.startswith("# Steps")
    assert skill.source == "review-notes/SKILL.md"


def test_s02_ac5_quoted_values_are_fine(tmp_path: Path) -> None:
    text = "---\nname: \"review-notes\"\ndescription: 'Quoted.'\n---\nBody\n"
    assert read_skill(write(tmp_path, "review-notes", text), root=tmp_path).description == "Quoted."


@pytest.mark.parametrize(
    ("folder", "text", "problem"),
    [
        ("review-notes", "no frontmatter\n", "frontmatter"),
        ("review-notes", "---\nname: review-notes\n", "frontmatter"),
        ("other-name", GOOD, "folder"),
        ("Bad_Name", "---\nname: Bad_Name\ndescription: x\n---\n", "lowercase"),
        ("review-notes", "---\nname: review-notes\n---\nBody\n", "description"),
        ("review-notes", "---\nname: review-notes\ndescription: x\nversion: 2\n---\n", "version"),
        ("review-notes", "---\nname: review-notes\ndescription: " + "x" * 1100 + "\n---\n", "1024"),
        ("review-notes", "---\nname: review-notes\ndescription: x\n  nested: y\n---\n", "line"),
    ],
)
def test_s02_ac5_bad_skills_are_rejected_clearly(
    tmp_path: Path, folder: str, text: str, problem: str
) -> None:
    with pytest.raises(SkillError, match=problem):
        read_skill(write(tmp_path, folder, text), root=tmp_path)


def test_s02_ac5_find_skills_in_folders(tmp_path: Path) -> None:
    write(tmp_path, "shared/one", "---\nname: one\ndescription: First.\n---\n")
    write(tmp_path, "shared/two", "---\nname: two\ndescription: Second.\n---\n")
    (tmp_path / "shared" / "not-a-skill").mkdir()
    skills = find_skills([tmp_path / "shared", tmp_path / "missing"], root=tmp_path)
    assert [s.name for s in skills] == ["one", "two"]


def test_s02_ac5_the_same_name_twice_is_an_error(tmp_path: Path) -> None:
    write(tmp_path, "a/one", "---\nname: one\ndescription: A.\n---\n")
    write(tmp_path, "b/one", "---\nname: one\ndescription: B.\n---\n")
    with pytest.raises(SkillError, match="twice"):
        find_skills([tmp_path / "a", tmp_path / "b"], root=tmp_path)


def skills_for_tool() -> list[Skill]:
    return [
        Skill("one", "First.", "skills/one/SKILL.md", "Do one."),
        Skill("two", "Second.", "skills/two/SKILL.md", "Do two."),
    ]


def test_s02_ac4_load_skill_returns_the_full_text() -> None:
    tool = load_skill_tool(skills_for_tool())
    assert tool.name == "load_skill"
    assert tool.part == "context"  # shown as a CONTEXT line, not a TOOL line
    text = tool.function(name="two")
    assert "Do two." in text
    assert "skills/two/SKILL.md" in text  # so the answer can cite it in Sources


def test_s02_ac4_load_skill_offers_only_visible_skills() -> None:
    tool = load_skill_tool(skills_for_tool())
    assert tool.parameters["properties"]["name"]["enum"] == ["one", "two"]
    with pytest.raises(SkillError, match="three"):
        tool.function(name="three")
