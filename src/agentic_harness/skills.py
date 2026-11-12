"""Skills: how a team does one task, in the open SKILL.md format (S02-AC4, AC5).

Harness part: context. A skill is a folder with a SKILL.md file: a short
frontmatter (name, description) and a body of steps. Only the name and the
description go into the prompt; the built-in ``load_skill`` tool returns the
body when the model needs it (D-36).

The frontmatter reader is tiny and strict on purpose (D-35): one ``key: value``
line each for ``name`` and ``description``, nothing else. Our runtime has no
YAML package, and a clear error beats a silently misread skill.

Does not: know any workspace's skills, or decide which skills a profile sees
(workspace.py does).
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from agentic_harness.planning import PLAN_TOOL
from agentic_harness.tools import Tool

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")  # Agent Skills format: lowercase-hyphen
MAX_NAME = 64
MAX_DESCRIPTION = 1024
KEYS = ("name", "description")


class SkillError(ValueError):
    """A SKILL.md file that doesn't follow the format, or a skill that isn't there."""


@dataclass(frozen=True, slots=True)
class Skill:
    name: str
    description: str
    source: str  # path relative to the workspace, so answers can cite it
    body: str


def read_skill(file: Path, root: Path) -> Skill:
    """Read and check one SKILL.md file."""
    where = file.relative_to(root).as_posix()
    lines = file.read_text().splitlines()
    if not lines or lines[0].strip() != "---" or "---" not in [x.strip() for x in lines[1:]]:
        raise SkillError(f"{where}: must start with a frontmatter block between '---' lines.")
    end = 1 + [x.strip() for x in lines[1:]].index("---")
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep or line[:1].isspace():
            raise SkillError(f"{where}: each frontmatter line must be 'key: value' ({line!r}).")
        key = key.strip()
        if key not in KEYS:
            raise SkillError(
                f"{where}: unknown frontmatter key {key!r}; only name and description."
            )
        fields[key] = value.strip().strip("'\"")

    name, description = fields.get("name", ""), fields.get("description", "")
    folder = file.parent.name
    if not NAME.match(name) or len(name) > MAX_NAME:
        raise SkillError(f"{where}: name {name!r} must be lowercase words joined by '-'.")
    if name != folder:
        raise SkillError(f"{where}: name {name!r} must match its folder {folder!r}.")
    if not description:
        raise SkillError(f"{where}: a description is required.")
    if len(description) > MAX_DESCRIPTION:
        raise SkillError(f"{where}: description is over {MAX_DESCRIPTION} characters.")
    body = "\n".join(lines[end + 1 :]).strip()
    return Skill(name=name, description=description, source=where, body=body)


def find_skills(folders: Iterable[Path], root: Path) -> list[Skill]:
    """Every skill inside these folders (a skill = a subfolder with SKILL.md), in order."""
    skills: list[Skill] = []
    seen: dict[str, str] = {}
    for folder in folders:
        if not folder.is_dir():
            continue  # a profile without its own skills folder simply has none
        for entry in sorted(folder.iterdir()):
            if not (entry / "SKILL.md").is_file():
                continue
            skill = read_skill(entry / "SKILL.md", root)
            if skill.name in seen:
                raise SkillError(
                    f"Skill {skill.name!r} appears twice: {seen[skill.name]}, {skill.source}."
                )
            seen[skill.name] = skill.source
            skills.append(skill)
    return skills


SKILL_TOOL = "load_skill"  # trimming keeps its results whole: they are instructions (S11)

# Added after a skill's steps when the agent can keep a plan (S11). Found live: Sonnet and
# Haiku both followed the skill and never planned; the skill is the recipe, the plan the progress.
PLAN_HINT = (
    f"\n\n---\nBefore you start, write these steps as your plan with {PLAN_TOOL}, then mark "
    "each one done as you finish it."
)


def load_skill_tool(skills: Sequence[Skill], *, plan: bool = False) -> Tool:
    """The built-in tool that hands the model a skill's full steps (D-36). With ``plan``, it
    also asks the agent to copy the steps into its plan (D-121 changed)."""
    by_name = {skill.name: skill for skill in skills}

    def load_skill(name: str) -> str:
        skill = by_name.get(name)
        if skill is None:
            raise SkillError(f"No skill named {name!r} for this profile.")
        text = f"# Skill: {skill.name}\nSource: {skill.source}\n\n{skill.body}"
        return text + (PLAN_HINT if plan else "")

    return Tool(
        name=SKILL_TOOL,
        description="Read the full steps of one of your skills before doing that task.",
        risk="read",
        parameters={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "enum": list(by_name),
                    "description": "The skill's name, as listed in your instructions.",
                }
            },
            "required": ["name"],
        },
        function=load_skill,
        part="context",
    )
