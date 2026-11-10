"""The system prompt: who the agent works for and how its teams work (S02-AC2, AC4, AC7, AC8).

Harness part: context. Built once per run, in a fixed order (D-37):

    harness base prompt → memory files (AGENTS.md, then the profile's team file) → skill list

Memory files go in whole, on every call, so each has a size budget (D-38).
Skills go in as one line each; ``load_skill`` reads the rest (D-36). The same
order and text on every call lets Gemini cache the start of the prompt; the
``prompt_id`` proves in the trace that it never changed.

Does not: read files itself (workspace.py does) or talk to the model.
"""

import hashlib
import math
from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from agentic_harness.loop import SYSTEM_PROMPT
from agentic_harness.scope import scope_prompt
from agentic_harness.skills import Skill
from agentic_harness.workspace import MemoryFile, Workspace

SKILLS_HEADER = (
    "## Skills\n"
    "Before doing a task one of these covers, read it with load_skill and follow it. "
    "Cite the skill's source path in your answer."
)


def estimate_tokens(text: str) -> int:
    """A rough count: about four characters per token (D-38)."""
    return math.ceil(len(text) / 4)


@dataclass(frozen=True, slots=True)
class Context:
    profile: str | None
    system: str
    prompt_id: str
    files: tuple[MemoryFile, ...]
    skills: tuple[Skill, ...]
    warnings: tuple[str, ...]

    def summary(self) -> dict[str, Any]:
        """What the page and the trace show about the context (never the full text)."""
        return {
            "profile": self.profile,
            "files": [{"path": f.path, "tokens": estimate_tokens(f.text)} for f in self.files],
            "skills": [
                {"name": s.name, "description": s.description, "source": s.source}
                for s in self.skills
            ],
            "prompt_tokens": estimate_tokens(self.system),
            "prompt_id": self.prompt_id,
            "warnings": list(self.warnings),
        }


def build_context(
    workspace: Workspace, profile: str | None, *, skip_skills: Collection[str] = ()
) -> Context:
    files = workspace.memory_files(profile)
    # A switched-off skill is not even listed: the model can't ask for it (D-70).
    skills = [s for s in workspace.skills(profile) if s.name not in skip_skills]

    parts = [SYSTEM_PROMPT]
    if workspace.scope:
        parts.append(scope_prompt(workspace.scope))  # what the agent is for (D-81)
    parts += [f"## From {f.path}\n\n{f.text.strip()}" for f in files]
    if skills:
        lines = [f"- {s.name}: {s.description} ({s.source})" for s in skills]
        parts.append(SKILLS_HEADER + "\n" + "\n".join(lines))
    system = "\n\n".join(parts) + "\n"

    budget = workspace.memory_budget_tokens
    warnings = tuple(
        f"{f.path} is about {estimate_tokens(f.text)} tokens, over the {budget}-token budget: "
        "it is sent on every call."
        for f in files
        if estimate_tokens(f.text) > budget
    )
    prompt_id = hashlib.sha256(system.encode()).hexdigest()[:12]
    return Context(profile, system, prompt_id, tuple(files), tuple(skills), warnings)
