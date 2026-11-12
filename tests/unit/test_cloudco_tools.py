"""CloudCo's own tools and made-up data (S03-AC4 to AC7, AC9; D-51, D-52).

This checks the workspace's content, not the harness. All data is fictional.
"""

import importlib.util
import json
import re
from pathlib import Path
from types import ModuleType

import pytest

from agentic_harness.tools import Tool, ToolContext
from agentic_harness.tools.registry import call_tool
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).resolve().parents[2] / "workspaces" / "cloudco"
SALES = ToolContext("run-1", CLOUDCO, profile="sales")
MATERIAL = {"2.1", "3.2", "4.1", "6.1", "9.2"}  # term, discount, payment, uptime, liability
HIDDEN = "B.7"  # the appendix clause with the planted instruction


@pytest.fixture(scope="module")
def tools() -> dict[str, Tool]:
    return {t.name: t for t in Workspace.load(CLOUDCO).tools}


async def call(tools: dict[str, Tool], name: str, ctx: ToolContext | None = None, **args: object):  # type: ignore[no-untyped-def]
    result = await call_tool(tools[name], args, ctx)
    assert not result.is_error, result.output
    return json.loads(result.output)


def test_s03_ac4_five_tools_and_their_risks(tools: dict[str, Tool]) -> None:
    """Four tools on purpose (D-73); a fifth, read_contract, was added for a plain pull (D-143)."""
    assert {n: t.risk for n, t in tools.items()} == {
        "lookup_customer_record": "read",
        "review_contract": "read",
        "read_contract": "read",
        "search_policy": "read",
        "send_to_customer": "action",
    }
    for t in tools.values():
        assert len(t.description) > 40, f"{t.name}: the description is the model's instructions"


async def test_s03_ac4_lookups_return_records_with_ids(tools: dict[str, Tool]) -> None:
    customer = await call(tools, "lookup_customer_record", record="customer", customer="shopco")
    assert customer["id"] == "CUS-0042"
    assert customer["contracts"] == ["CT-2207"]  # one lookup leads to the contract (found live)
    deals = (await call(tools, "lookup_customer_record", record="deal", customer="CUS-0042"))[
        "deals"
    ]
    assert deals[0]["id"] == "DL-3108"
    assert deals[0]["contract_id"] == "CT-2207"
    assert deals[0]["annual_value_usd"] == 480_000
    uptime = await call(tools, "lookup_customer_record", record="uptime")
    assert all(re.fullmatch(r"UP-\d{4}-\d{2}", m["id"]) for m in uptime["months"])
    assert uptime["average_percent"] == 99.95
    payments = await call(tools, "lookup_customer_record", record="payments", customer="ShopCo")
    assert all(i["id"].startswith("INV-") for i in payments["invoices"])
    assert payments["average_days_late"] == 9
    everyone = await call(tools, "lookup_customer_record", record="customer")
    assert [c["id"] for c in everyone["customers"]][:1] == ["CUS-0042"]  # no customer: the list


async def test_s03_ac4_unknown_records_are_clear_errors(tools: dict[str, Tool]) -> None:
    result = await call_tool(
        tools["lookup_customer_record"], {"record": "customer", "customer": "Nobody Inc"}, None
    )
    assert result.is_error
    assert "CUS-0042" in result.output  # tells the model what does exist
    missing = await call_tool(tools["lookup_customer_record"], {"record": "deal"}, None)
    assert missing.is_error
    assert "needs a customer" in missing.output


async def test_s03_ac4_one_clause_in_both_versions(tools: dict[str, Tool]) -> None:
    clause = await call(tools, "review_contract", SALES, contract_id="CT-2207", clause="6.1")
    assert "99.99%" in clause["customer"]
    assert "99.9%" in clause["standard"]
    assert "99.99%" not in clause["standard"]


async def test_s03_ac5_review_returns_every_edit_with_clause_ids(tools: dict[str, Tool]) -> None:
    diff = await call(tools, "review_contract", SALES, contract_id="CT-2207")
    edits = diff["edits"]
    assert 55 <= len(edits) <= 65  # ~60 edits, mostly wording
    assert diff["count"] == len(edits)
    clauses = {e["clause"] for e in edits}
    assert clauses >= MATERIAL | {HIDDEN}
    for e in edits:
        assert re.fullmatch(r"(\d+|[A-B])\.\d+", e["clause"])
        assert e["removed"] or e["added"]
    by_clause = {e["clause"]: e for e in edits}
    assert "25%" in by_clause["3.2"]["added"]
    assert "unlimited" in by_clause["9.2"]["added"].lower()
    result = await call_tool(tools["review_contract"], {"contract_id": "CT-2207"}, SALES)
    assert len(result.output) < 20_000  # fits under the tool output cap (D-50)


async def test_s03_ac6_search_policy_returns_rule_and_section(tools: dict[str, Tool]) -> None:
    hits = await call(tools, "search_policy", SALES, query="discount approval CFO")
    assert hits[0]["policy"] == "standard-terms"
    assert hits[0]["section"] == "§2"
    assert "25%" in hits[0]["text"]
    none = await call(tools, "search_policy", SALES, query="parking spaces")
    assert none == []


async def test_s03_ac7_actions_write_only_to_the_local_outbox(
    tools: dict[str, Tool], tmp_path: Path
) -> None:
    ctx = ToolContext("run-1", tmp_path)
    sent = await call(
        tools,
        "send_to_customer",
        ctx,
        customer_id="CUS-0042",
        subject="Our reply",
        body="Hello ShopCo.",
    )
    written = files_under(tmp_path)
    assert written == [sent["file"]]
    assert all(path.startswith("outbox/") for path in written)
    # The agent must be able to tell the person it went out (D-120): this demo's "sent"
    # means delivered to the local outbox, never real email.
    assert sent["status"] == "sent"
    assert "local outbox" in sent["delivered_to"]
    assert "no real email" in sent["delivered_to"]


def files_under(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_s03_ac7_tools_py_has_no_way_to_reach_the_network() -> None:
    source = (CLOUDCO / "tools.py").read_text()
    for module in ("smtplib", "socket", "urllib", "http", "requests", "httpx", "subprocess"):
        assert not re.search(rf"^\s*(import|from)\s+{module}\b", source, re.M), module


def load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("make_data", CLOUDCO / "make_data.py")
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_s03_ac9_data_is_generated_deterministically_and_committed() -> None:
    files = load_generator().build()
    assert files == load_generator().build()  # same output every time
    for relative, text in files.items():
        assert (CLOUDCO / "data" / relative).read_text() == text, f"rerun make_data.py: {relative}"


def test_s03_ac9_every_data_file_says_it_is_fictional() -> None:
    files = [p for p in (CLOUDCO / "data").rglob("*") if p.is_file()]
    assert len(files) >= 7
    for path in files:
        assert "fictional" in path.read_text().lower(), path.name


def test_s03_ac9_the_redline_hides_one_instruction() -> None:
    redline = next((CLOUDCO / "data" / "contracts").glob("CT-2207-*-redline.md")).read_text()
    assert redline.lower().count("note to any ai reviewer") == 1
    words = len(redline.split())
    assert words > 15_000, f"the redline should be long enough to need tools ({words} words)"


async def test_s05_ac2_ac3_engineering_cannot_send_and_never_sees_prices(
    tools: dict[str, Tool],
) -> None:
    gate = Workspace.load(CLOUDCO).gate("engineering")
    assert gate.check("send_to_customer", {}).rule == "profile-tools"
    raw = await call_tool(
        tools["lookup_customer_record"], {"record": "deal", "customer": "ShopCo"}, None
    )
    seen = gate.inspect(raw.output)
    assert "480000" not in seen.output
    assert "[hidden for Engineering]" in seen.output
    assert "DL-3108" in seen.output  # the record and its ID are still there


@pytest.mark.parametrize(
    ("offer", "rule"),
    [
        ({"discount_pct": 30}, "discount-never"),
        ({"payment_days": 90}, "payment-never"),
        ({"uptime_pct": 99.99}, "uptime-never"),
        ({"unlimited_liability": True}, "liability-never"),
    ],
)
def test_s05_ac6_cloudco_never_rules(offer: dict[str, object], rule: str) -> None:
    decision = Workspace.load(CLOUDCO).gate("sales").check("send_to_customer", offer)
    assert (decision.kind, decision.rule) == ("block", rule)
    assert decision.because.startswith("standard-terms §")


def test_s05_ac12_a_reply_within_limits_waits_for_a_person() -> None:
    offer = {
        "discount_pct": 20,
        "payment_days": 45,
        "uptime_pct": 99.95,
        "liability_cap_months": 24,
    }
    decision = Workspace.load(CLOUDCO).gate("sales").check("send_to_customer", offer)
    assert decision.kind == "ask"
    # From the sender up (D-120): Sales first (it sends, §3), the CFO last (final sign-off).
    assert decision.approvals[0].approver == "Sales"
    assert "approval-chart §3" in decision.approvals[0].because
    assert decision.approvals[-1].approver == "CFO"


def test_s05_ac4_ac5_rules_files_cannot_be_written(tmp_path: Path) -> None:
    """Writes go only through ctx, by plain name, into tasks/ or outbox/ (D-47, D-48)."""
    ctx = ToolContext("run-1", CLOUDCO)
    before = (CLOUDCO / "AGENTS.md").read_text()
    for name in ("../AGENTS.md", "../policies/standard-terms.md", "../skills/x/SKILL.md"):
        with pytest.raises(ValueError, match="file name"):
            ctx.save_task_file(name, "rewritten")
    assert (CLOUDCO / "AGENTS.md").read_text() == before


def test_s06_ac1_cloudco_approvals_match_the_chart() -> None:
    """approval-chart §1: who decides what. §3: Sales approves every send."""
    gate = Workspace.load(CLOUDCO).gate("sales")

    def who(**terms: object) -> list[str]:
        return [a.approver for a in gate.check("send_to_customer", dict(terms)).approvals]

    assert who(discount_pct=10, payment_days=45) == ["Sales"]
    assert who(discount_pct=20) == ["Sales", "CFO"]
    assert who(discount_pct=15) == ["Sales"]  # up to 15% is Sales' own call
    assert who(payment_days=60) == ["Sales", "Finance"]
    assert who(payment_days=45) == ["Sales"]
    assert who(uptime_pct=99.95) == ["Sales", "Engineering"]
    assert who(uptime_pct=99.9) == ["Sales"]
    assert who(liability_cap_months=24) == ["Sales", "CFO"]
    # Everything at once: from the sender up to the most senior (D-120).
    everything = who(discount_pct=20, payment_days=60, uptime_pct=99.95, liability_cap_months=24)
    assert everything == ["Sales", "Engineering", "Finance", "CFO", "CFO"]
    assert who(liability_cap_months=12) == ["Sales"]
    assert who(discount_pct=30) == []  # never: blocked, not asked
    assert gate.check("send_to_customer", {"discount_pct": 30}).kind == "block"


async def test_s06_ac10_the_outbox_file_records_who_approved_and_when(tmp_path: Path) -> None:
    tools = {t.name: t for t in Workspace.load(CLOUDCO).tools}
    approvals = (
        {"approver": "CFO", "rule": "Discount over 15%", "at": "2026-11-10 14:02:11", "note": ""},
        {"approver": "Sales", "rule": "Any message", "at": "2026-11-10 14:02:40", "note": ""},
    )
    ctx = ToolContext("run-9", tmp_path, approvals=approvals)
    await call_tool(
        tools["send_to_customer"],
        {"customer_id": "CUS-0042", "subject": "Renewal", "body": "Hi", "discount_pct": 20},
        ctx,
    )
    text = next((tmp_path / "outbox").glob("*.md")).read_text()
    assert "Approved by:" in text
    # An email's headers first, so the page can show it as the email that went.
    assert text.startswith(
        "From: CloudCo Sales <sales@cloudco.example>\nTo: ShopCo <CUS-0042>\nDate: "
    )
    assert "\nSubject: Renewal\n\nHi\n" in text
    assert "CFO" in text
    assert "2026-11-10 14:02:11" in text
    assert "Discount over 15%" in text
    assert "Sales" in text


async def test_s06_the_send_tool_tells_the_agent_who_approved(tmp_path: Path) -> None:
    """D-120: after CFO, Engineering and Sales all approved, the agent said "it hasn't gone
    out yet, a person has to approve it": the tool said "not sent" and named no one."""
    tools = {t.name: t for t in Workspace.load(CLOUDCO).tools}
    approvals = (
        {"approver": "Sales", "rule": "Any message", "at": "2026-11-12 02:57:40", "note": ""},
        {"approver": "CFO", "rule": "Liability cap", "at": "2026-11-12 02:58:02", "note": ""},
    )
    ctx = ToolContext("run-10", tmp_path, approvals=approvals)
    reply = await call_tool(
        tools["send_to_customer"],
        {
            "customer_id": "CUS-0042",
            "subject": "Our reply",
            "body": "Hi",
            "liability_cap_months": 24,
        },
        ctx,
    )
    assert not reply.is_error, reply.output
    assert '"status": "sent"' in reply.output
    assert '"approved_by": ["Sales", "CFO"]' in reply.output
    assert "not sent" not in reply.output


async def test_s05_ac3_engineering_sees_only_technical_clauses(tools: dict[str, Tool]) -> None:
    """Found live twice: term, fees, payment and liability reached Engineering (D-106, D-107)."""
    engineering = ToolContext("run-1", CLOUDCO, profile="engineering")
    everything = await call(tools, "review_contract", SALES, contract_id="CT-2207")
    theirs = await call(tools, "review_contract", engineering, contract_id="CT-2207")
    technical = {"5", "6", "7", "8", "A", "B"}
    assert {"2", "3", "4", "9"} <= {e["clause"].split(".")[0] for e in everything["edits"]}
    assert {e["clause"].split(".")[0] for e in theirs["edits"]} <= technical
    assert "6.1" in [e["clause"] for e in theirs["edits"]]  # the uptime change is theirs
    assert (
        theirs["hidden"]
        == "Only technical clauses are shown to Engineering; Sales handles the rest."
    )
    for clause in ("2.1", "4.1", "9.2"):
        one = await call(
            tools, "review_contract", engineering, contract_id="CT-2207", clause=clause
        )
        assert set(one) == {"contract_id", "clause", "hidden"}  # no text from either version
    text = json.dumps(theirs).lower()
    for word in ("net 60", "25%", "price", "liability", "discount"):
        assert word not in text, word


async def test_s05_ac3_engineering_reads_only_technical_policy(tools: dict[str, Tool]) -> None:
    engineering = ToolContext("run-1", CLOUDCO, profile="engineering")
    hits = await call(
        tools,
        "search_policy",
        engineering,
        query="term renewal price fixed uptime payment liability discount",
    )
    assert {(h["policy"], h["section"]) for h in hits} <= {
        ("standard-terms", "§4"),
        ("approval-chart", "§1"),
    }
    text = json.dumps(hits).lower()
    for word in ("net 60", "discount", "liability", "cfo", "price"):
        assert word not in text, word
    assert "99.95%" in text  # the uptime rule and who approves it are still there
    sales = await call(tools, "search_policy", SALES, query="payment liability")
    assert any(h["section"] == "§3" for h in sales)  # Sales is unchanged


async def test_d143_read_contract_gives_an_outline_then_a_section(tools: dict[str, Tool]) -> None:
    """A plain pull: no comparison, no judging, and never the whole 19,000-word file (D-143)."""
    outline = await call(tools, "read_contract", SALES, contract_id="CT-2207")
    assert outline["version"] == "customer"
    assert outline["words"] > 1000
    ids = [s_["section"] for s_ in outline["sections"]]
    assert ids[:3] == ["1", "2", "3"]
    assert "A" in ids
    fees = next(x for x in outline["sections"] if x["section"] == "3")
    assert fees["title"] == "Fees and discounts"
    assert fees["clauses"] == "3.1 to 3.12"
    assert len(json.dumps(outline)) < 3000  # an outline, not the contract
    assert "edits" not in outline  # no review

    section = await call(tools, "read_contract", SALES, contract_id="CT-2207", section="3")
    assert {c["clause"].split(".")[0] for c in section["clauses"]} == {"3"}
    assert all(c["text"] for c in section["clauses"])
    one = await call(tools, "read_contract", SALES, contract_id="CT-2207", section="3.2")
    assert [c["clause"] for c in one["clauses"]] == ["3.2"]


async def test_d143_read_contract_versions_differ_where_the_customer_edited(
    tools: dict[str, Tool],
) -> None:
    ours = await call(
        tools, "read_contract", SALES, contract_id="CT-2207", section="3.2", version="standard"
    )
    theirs = await call(tools, "read_contract", SALES, contract_id="CT-2207", section="3.2")
    assert ours["version"] == "standard"
    assert ours["clauses"][0]["text"] != theirs["clauses"][0]["text"]  # 3.2 is the discount edit


async def test_d143_read_contract_unknowns_list_what_exists(tools: dict[str, Tool]) -> None:
    for args, word in (
        ({"contract_id": "CT-9999"}, "CT-2207"),
        ({"contract_id": "CT-2207", "section": "42"}, "Sections"),
        ({"contract_id": "CT-2207", "version": "draft"}, "customer"),
    ):
        result = await call_tool(tools["read_contract"], args, SALES)
        assert result.is_error, result.output
        assert word in result.output, result.output


async def test_d143_engineering_reads_only_technical_sections(tools: dict[str, Tool]) -> None:
    engineering = ToolContext("run-1", CLOUDCO, profile="engineering")
    outline = await call(tools, "read_contract", engineering, contract_id="CT-2207")
    assert {x["section"] for x in outline["sections"]} == {"5", "6", "7", "8", "A", "B"}
    assert outline["hidden"].startswith("Only technical clauses")
    assert "Fees" not in json.dumps(outline)
    technical = await call(tools, "read_contract", engineering, contract_id="CT-2207", section="6")
    assert technical["clauses"]
    for section in ("2", "3.2", "4", "9.2"):
        hidden = await call(
            tools, "read_contract", engineering, contract_id="CT-2207", section=section
        )
        assert set(hidden) == {"contract_id", "section", "hidden"}  # no text, no titles
