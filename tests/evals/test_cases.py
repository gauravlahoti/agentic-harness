"""S10-AC1: golden cases load and validate; a bad case names its field."""

from pathlib import Path

import pytest

from evals.cases import CaseError, load_suite

ROOT = Path(__file__).resolve().parents[2]
CLOUDCO = ROOT / "evals" / "cases" / "cloudco.toml"


def test_s10_ac1_cloudco_has_16_valid_cases() -> None:
    suite = load_suite(CLOUDCO)
    assert len(suite.cases) == 16
    assert suite.workspace == (ROOT / "workspaces" / "cloudco").resolve()
    ids = [c.id for c in suite.cases]
    assert len(set(ids)) == 16
    multi = [c.id for c in suite.cases if c.multi_turn]
    assert len(multi) == 5
    assert "follow-up-in-scope" in multi


def test_s10_ac1_fields_come_through() -> None:
    case = next(c for c in load_suite(CLOUDCO).cases if c.id == "send-cfo-rejects")
    assert case.profile == "sales"
    assert case.approvals == {"CFO": "reject", "Sales": "approve"}
    assert case.expect_approval == ("CFO",)
    assert case.key_args == {"send_to_customer": {"discount_pct": 20}}
    assert case.never_call == ("send_to_customer",)
    assert case.scope == "in"
    off = next(c for c in load_suite(CLOUDCO).cases if c.id == "off-topic")
    assert off.scope == "out"


def _write(tmp_path: Path, body: str) -> Path:
    (tmp_path / "ws").mkdir(exist_ok=True)
    (tmp_path / "ws" / "workspace.toml").write_text('name = "ws"\n')
    path = tmp_path / "cases.toml"
    path.write_text('workspace = "ws"\n' + body)
    return path


GOOD = """
[[case]]
id = "a"
group = "G"
profile = "sales"
turns = ["hello"]
expected_outcome = "says hi"
"""


def test_s10_ac1_a_minimal_case_loads(tmp_path: Path) -> None:
    suite = load_suite(_write(tmp_path, GOOD))
    assert suite.cases[0].turns == ("hello",)
    assert suite.cases[0].approvals == {}


@pytest.mark.parametrize(
    ("change", "field"),
    [
        (('turns = ["hello"]', "turns = []"), "turns"),
        (('profile = "sales"', 'profile = ""'), "profile"),
        (('expected_outcome = "says hi"', ""), "expected_outcome"),
        (('id = "a"', 'id = "Bad ID"'), "id"),
        (('group = "G"', 'group = "G"\nscope = "maybe"'), "scope"),
        (('group = "G"', 'group = "G"\napprovals = { CFO = "perhaps" }'), "approvals"),
        (('group = "G"', 'group = "G"\nmust_include = "2.1"'), "must_include"),
        (('group = "G"', 'group = "G"\nexpect_flaged = true'), "expect_flaged"),
    ],
)
def test_s10_ac1_a_bad_case_names_its_field(
    tmp_path: Path, change: tuple[str, str], field: str
) -> None:
    body = GOOD.replace(*change)
    with pytest.raises(CaseError, match=field):
        load_suite(_write(tmp_path, body))


def test_s10_ac1_duplicate_ids_and_missing_workspace_are_named(tmp_path: Path) -> None:
    with pytest.raises(CaseError, match="twice"):
        load_suite(_write(tmp_path, GOOD + GOOD))
    path = tmp_path / "nows.toml"
    path.write_text('workspace = "nowhere"\n' + GOOD)
    with pytest.raises(CaseError, match="workspace"):
        load_suite(path)


def test_s10_ac1_pick_cases_by_id() -> None:
    suite = load_suite(CLOUDCO)
    assert [c.id for c in suite.pick(["off-topic", "find-changes"])] == [
        "off-topic",
        "find-changes",
    ]
    assert len(suite.pick(None)) == 16
    with pytest.raises(CaseError, match="no-such"):
        suite.pick(["no-such"])
