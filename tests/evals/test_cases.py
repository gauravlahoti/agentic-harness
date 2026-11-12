"""S10-AC1: golden cases load and validate; a bad case names its field."""

from pathlib import Path

import pytest

from evals.cases import CaseError, load_suite

ROOT = Path(__file__).resolve().parents[2]
CLOUDCO = ROOT / "evals" / "cases" / "cloudco.toml"


def test_s10_ac1_cloudco_has_16_valid_cases() -> None:
    suite = load_suite(CLOUDCO)
    assert len(suite.cases) == 20
    assert suite.workspace == (ROOT / "workspaces" / "cloudco").resolve()
    ids = [c.id for c in suite.cases]
    assert len(set(ids)) == 20
    multi = [c.id for c in suite.cases if c.multi_turn]
    assert len(multi) == 6  # + agree-then-draft (D-165)
    assert "follow-up-in-scope" in multi


CORE = {
    "single": [
        "find-changes",
        "discount-needs-cfo",
        "uptime-never",
        "injection-flagged",
        "deal-value-hidden",
        "off-topic",
        "review-then-confirm",
    ],
    "multi": ["follow-up-in-scope", "cfo-no-holds", "round-2-memory"],
}


def test_s10_ac1_the_core_set_mixes_single_and_multi_turn_cases() -> None:
    """The Run dialog's default: a few of each, enough to score all 11 metrics once."""
    cases = load_suite(CLOUDCO).cases
    assert [c.id for c in cases if c.core and not c.multi_turn] == CORE["single"]
    assert [c.id for c in cases if c.core and c.multi_turn] == CORE["multi"]
    groups = {c.group for c in cases if c.core}
    assert groups >= {"Sales Review", "Approvals", "Never Rules", "Injection", "Scope"}


def test_s10_ac1_fields_come_through() -> None:
    case = next(c for c in load_suite(CLOUDCO).cases if c.id == "send-cfo-rejects")
    assert case.profile == "sales"
    assert case.approvals == {"CFO": "reject", "Sales": "approve", "Engineering": "approve"}
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
        (('group = "G"', 'group = "G"\ncore = "yes"'), "core"),
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
    assert len(suite.pick(None)) == 20
    with pytest.raises(CaseError, match="no-such"):
        suite.pick(["no-such"])


SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "per", "the", "to"}


def is_title_case(name: str) -> bool:
    """Every word capitalised, small words lowercase unless first (CLAUDE.md, UI text casing)."""
    words = [w for part in name.split() for w in part.split("-")]
    return all(
        w[0].isupper() or (i > 0 and w in SMALL) or not w[0].isalpha() for i, w in enumerate(words)
    )


def test_ui_names_are_title_case() -> None:
    import json

    catalog = json.loads((ROOT / "evals" / "catalog.json").read_text())
    names = [m["name"] for m in catalog["metrics"].values()]
    names += [t["title"] for t in catalog["tables"]] + [t["subtitle"] for t in catalog["tables"]]
    names += [r["name"] for t in catalog["tables"] for r in t["rows"]]
    names += [c.group for c in load_suite(CLOUDCO).cases]
    assert [n for n in names if not is_title_case(n)] == []
    assert not is_title_case("Plan adherence")  # the check itself catches sentence case
