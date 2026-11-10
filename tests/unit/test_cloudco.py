"""CloudCo's context files exist, parse, fit their budget and say they're fictional (S02-AC10).

This checks the workspace's *content*. The harness itself is checked elsewhere against
temp workspaces, so it never depends on CloudCo.
"""

from pathlib import Path

import pytest

from agentic_harness.context import build_context
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"


@pytest.fixture(scope="module")
def cloudco() -> Workspace:
    return Workspace.load(CLOUDCO)


def test_s02_ac10_the_files_are_there(cloudco: Workspace) -> None:
    for relative in (
        "AGENTS.md",
        "teams/sales.md",
        "teams/engineering.md",
        "teams/finance.md",
        "skills/company/contract-review/SKILL.md",
        "skills/sales/reply-to-customer/SKILL.md",
        "skills/engineering/uptime-check/SKILL.md",
        "skills/finance/payment-terms-check/SKILL.md",
        "policies/standard-terms.md",
        "policies/approval-chart.md",
    ):
        assert (CLOUDCO / relative).is_file(), relative
    assert cloudco.title == "Contract Assistant"
    assert [p.id for p in cloudco.profiles] == ["sales", "engineering", "finance", "cfo"]


@pytest.mark.parametrize(
    ("profile", "skills"),
    [
        ("sales", ["contract-review", "reply-to-customer"]),
        ("engineering", ["contract-review", "uptime-check"]),
        ("finance", ["contract-review", "payment-terms-check"]),
        ("cfo", ["contract-review"]),
    ],
)
def test_s02_ac10_each_profile_gets_its_skills(
    cloudco: Workspace, profile: str, skills: list[str]
) -> None:
    assert [s.name for s in cloudco.skills(profile)] == skills


def test_s02_ac10_every_profile_fits_the_memory_budget(cloudco: Workspace) -> None:
    for profile in cloudco.profiles:
        assert build_context(cloudco, profile.id).warnings == ()


def test_s02_ac10_everything_says_it_is_fictional() -> None:
    for file in CLOUDCO.rglob("*.md"):
        assert "ictional" in file.read_text(), (
            f"{file.relative_to(CLOUDCO)} must say it's fictional"
        )


def test_s02_ac11_instructions_ask_for_the_answer_format(cloudco: Workspace) -> None:
    system = build_context(cloudco, "sales").system
    for heading in ("**Summary**", "**Needs a human decision**", "**Sources**"):
        assert heading in system
