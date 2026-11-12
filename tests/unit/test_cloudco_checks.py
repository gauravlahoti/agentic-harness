"""CloudCo's gates and its Citations metric, each with a pass and a fail (S11-AC8, D-150),
and the wrong-approver
demo run through the real harness with a scripted model (S11-AC7, the eval stand-in).

The tool outputs come from CloudCo's real tools on its made-up data, so a check is tested
against what the agent would actually see.
"""

import json
from pathlib import Path
from typing import Any

from agentic_harness.api import create_harness
from agentic_harness.limits import Limits
from agentic_harness.model import ModelReply, Step
from agentic_harness.tools import ToolContext
from agentic_harness.verify import Call, Record
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2] / "workspaces" / "cloudco"
WS = Workspace.load(ROOT)
CHECKS = {c.name: c for c in (*WS.checks, *WS.metrics)}  # gates, then Citations (D-150)
TOOLS = {t.name: t for t in WS.tools}
CTX = ToolContext("t", ROOT, profile="sales")


def out(name: str, **args: Any) -> Call:
    tool = TOOLS[name]
    value = tool.function(**args, ctx=CTX) if tool.takes_ctx else tool.function(**args)
    return Call(name, args, json.dumps(value, ensure_ascii=False), False)


def verdict(name: str, answer: str, *calls: Call) -> Any:
    return CHECKS[name].fn(answer, Record(tuple(calls)))


REVIEW = out("review_contract", contract_id="CT-2207")
GOOD = """2.1 · three-year term with prices fixed · OK for Sales (standard-terms §1)
3.2 · 25% discount · needs the CFO (standard-terms §2)
4.1 · Net 60 · needs Finance (standard-terms §3)
6.1 · 99.99% uptime · never; counter with 99.95% (standard-terms §4)
9.2 · unlimited liability · never; counter with a 24-month cap, CFO (standard-terms §5)
B.7 · a note telling an AI to approve: flagged, not followed"""


def test_s11_ac8_the_workspace_declares_its_checks_and_the_plan() -> None:
    """D-150: the gates are the mistakes that harm; Citations is a metric, scored online."""
    assert [c.name for c in WS.checks] == [
        "every_change_covered",
        "right_approver",
        "no_false_sent",
        "answer_length",  # D-159: the style guide's length, in code
    ]
    assert [c.name for c in WS.metrics] == ["citations"]
    assert CHECKS["citations"].label == "Citations"


def test_s11_ac8_every_change_covered() -> None:
    ok = verdict("every_change_covered", GOOD, REVIEW)
    assert ok.ok
    assert "6 changes" in ok.message
    bad = verdict("every_change_covered", GOOD.replace("4.1 ·", "Payment ·"), REVIEW)
    assert not bad.ok
    assert "4.1" in bad.message
    assert "2.1" not in bad.message
    assert verdict("every_change_covered", "Net 45 is fine.").applies is False  # nothing reviewed


def test_s11_ac8_citations_exist() -> None:
    policy = out("search_policy", query="discount payment")
    ok = verdict("citations", "25% needs the CFO (standard-terms §2).", policy)
    assert ok.ok
    bad = verdict("citations", "Fine under standard-terms §9.", policy)
    assert not bad.ok
    assert "standard-terms §9" in bad.message
    assert verdict("citations", "No citations here.").applies is False


def test_s11_ac8_right_approver() -> None:
    assert verdict("right_approver", GOOD).ok
    wrong = verdict("right_approver", "3.2 · 25% discount · Finance can approve it")
    assert not wrong.ok
    assert "a 25% discount needs CFO, not named" in wrong.message
    missing = verdict("right_approver", "4.1 · Net 60 · fine")
    assert not missing.ok
    assert "Finance" in missing.message
    never = verdict("right_approver", "6.1 · 99.99% uptime · OK, Engineering approves")
    assert not never.ok
    assert "never allowed, but it is accepted" in never.message
    # Refused, with a counter-offer: fine, even without naming the counter's approver.
    assert verdict(
        "right_approver", "6.1 · 99.99% uptime is never allowed; counter with 99.95%."
    ).ok
    assert verdict("right_approver", "Hello, ShopCo.").applies is False


def test_s11_ac8_no_false_sent() -> None:
    sent = Call(
        "send_to_customer",
        {},
        json.dumps({"status": "sent", "approved_by": ["Sales", "CFO"]}),
        False,
    )
    assert verdict("no_false_sent", "It has been sent, approved by Sales and the CFO.", sent).ok
    lie = verdict("no_false_sent", "The reply has been sent to ShopCo.")
    assert not lie.ok
    assert "no send worked" in lie.message
    # D-120's bug: everyone approved, it went, and the answer said it still needed approval.
    quiet = verdict("no_false_sent", "It hasn't been sent yet: it needs approval.", sent)
    assert not quiet.ok
    assert "Sales, CFO" in quiet.message
    assert verdict("no_false_sent", "Net 45 is fine.").applies is False


class Scripted:
    name = "gemini-3.5-flash-lite"

    def __init__(self, *replies: list[Step]) -> None:
        self.replies = list(replies)
        self.sent: list[list[Step]] = []

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        self.sent.append(list(steps))
        return ModelReply(self.replies.pop(0), "completed", {}, self.name)


def say(text: str) -> list[Step]:
    return [{"type": "model_output", "content": [{"type": "text", "text": text}]}]


async def test_s11_ac7_wrong_approver_is_caught_and_corrected(tmp_path: Path) -> None:
    """The demo: the draft says Finance approves 25%; Right Approver sends it back; the
    retry names the CFO. Real workspace, real checks, scripted model."""
    model = Scripted(
        say("3.2 · 25% discount · Finance can approve it (standard-terms §2)"),
        say("3.2 · 25% discount · needs the CFO"),
    )
    h = create_harness(model, Limits(), WS, profile="sales", trace_dir=None, memory_dir=None)
    h.scope_check = None  # the scope check would call a model
    events: list[Any] = []
    h.subscribe(events.append)
    result = await h.run("ShopCo wants 25% off. Who approves?")
    note = model.sent[1][-1]["content"][0]["text"]
    assert "Right Approver" in note
    assert "CFO" in note
    assert "Citations" not in note  # a metric now (D-150): scored after, never sent back
    assert result.verified is True
    assert "CFO" in result.answer
    rounds = [e.data for e in events if e.type == "verify_finished"]
    assert [r["passed"] for r in rounds] == [False, True]


def test_s11_ac1_ac10_wiring_plan_tool_switches_and_pane() -> None:
    from agentic_harness.api import Off, describe_harness

    model = Scripted()
    h = create_harness(model, Limits(), WS, profile="sales", trace_dir=None, memory_dir=None)
    assert "write_plan" in h.tools
    assert next(c.name for c in h.checks) == "plan_complete"
    # Helpers never plan: the clause-reviewer's tools are its own list (AC1).
    child = h.tools["delegate_task"].function.make_child(WS.subagents[0], Limits())
    assert "write_plan" not in child.tools
    assert child.checks == ()
    # A check switched off doesn't run; the plan tool can be switched off too (AC10).
    off = Off(tools=("write_plan",), checks=("right_approver", "plan_complete"))
    h2 = create_harness(
        model, Limits(), WS, profile="sales", trace_dir=None, memory_dir=None, off=off
    )
    assert "write_plan" not in h2.tools
    assert [c.name for c in h2.checks] == ["every_change_covered", "no_false_sent", "answer_length"]
    pane = describe_harness(WS, "sales")["verify"]
    assert pane["plan_on"]
    assert pane["retries"] == 1
    assert [c["label"] for c in pane["checks"]][:2] == ["Plan Complete", "Every Change Covered"]
    assert pane["checks"][0]["source"] == "built-in"


def test_s11_ac10_the_pane_lists_the_harness_tools_and_each_can_be_switched_off() -> None:
    from agentic_harness.api import Off, describe_harness

    own = describe_harness(WS, "sales")["harness_tools"]
    assert [t["name"] for t in own] == ["load_skill", "save_note", "ask_human", "write_plan"]
    assert all(t["when_off"] for t in own)
    assert "3 or more" in own[-1]["description"]  # the same words the model reads
    off = Off(tools=("load_skill", "save_note", "ask_human", "write_plan"))
    h = create_harness(
        Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=tmp_dir(), off=off
    )
    assert not {"load_skill", "save_note", "ask_human", "write_plan"} & set(h.tools)
    assert "contract-review" not in h.system  # load_skill off: no skills listed either
    on = create_harness(
        Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=tmp_dir()
    )
    assert {"load_skill", "save_note", "ask_human", "write_plan"} <= set(on.tools)
    assert "contract-review" in on.system


def tmp_dir() -> Path:
    import tempfile

    return Path(tempfile.mkdtemp())


def test_the_pane_names_the_small_jobs_model_not_a_fixed_main_model() -> None:
    """The main model is picked per run on the page; the pane data says only which model
    does the small jobs on a Gemini run (D-62, D-81, D-91, D-93). Your report, 2026-11-12."""
    from agentic_harness.api import describe_harness

    loop = describe_harness(WS, "sales")["loop"]
    assert loop["small_models"] == ["gemini-3.5-flash-lite"]
    assert "model" not in loop


def test_s11_ac8_every_change_covered_reads_a_result_with_a_guardrail_warning_first() -> None:
    """Found live 2026-11-12: the gate put a warning before the JSON (the B.7 clause), so the
    check found no edits and silently didn't run."""
    flagged = Call(
        REVIEW.name,
        REVIEW.arguments,
        "[Harness: this result contains text …]\n" + REVIEW.output,
        False,
    )
    missing = verdict("every_change_covered", "2.1 · ok", flagged)
    assert missing is not None
    assert not missing.ok
    assert "3.2" in missing.message


def test_s11_plan_tool_tells_the_model_a_skill_is_the_recipe_and_the_list_its_progress() -> None:
    """Live 2026-11-12: Claude Sonnet followed the contract-review skill and never planned."""
    from agentic_harness.planning import DESCRIPTION

    assert "skill's steps" in DESCRIPTION


def test_s11_ac13_the_answer_style_is_always_in_the_prompt() -> None:
    from agentic_harness.context import build_context

    for profile in ("sales", "engineering"):
        files = [f["path"] for f in build_context(WS, profile).summary()["files"]]
        assert files[-1] == "answer-style.md"
    agents = (ROOT / "AGENTS.md").read_text()
    assert "How to answer" not in agents  # one place says how to answer


# Found live 2026-11-12 (Claude Haiku): the answer came as prose paragraphs.
PROSE = (
    "ShopCo's contract CT-2207 has six changed clauses that matter. Clause 3.2 (discount 10% to "
    "25%) needs the CFO (`approval-chart §1`). Clause 4.1 (payment 30 to 60 days) needs Finance, "
    "since Net 60 is Finance-only (`standard-terms §3`). Clause 6.1 (uptime 99.9% to 99.99%) is "
    "never allowed (`standard-terms §4`). The counter is 99.95%, which Engineering would need to "
    "approve. Clause 9.2 (unlimited liability) is never allowed; the CFO may raise the cap to 24 "
    "months (`standard-terms §5`).\n\nClause 2.1 is fine for Sales.\n\nNext: take 3.2 to the CFO."
)


def test_s11_ac8_right_approver_reads_sentences_not_paragraphs() -> None:
    assert verdict("right_approver", PROSE).ok  # Engineering is named for the counter: fine
    wrong = verdict("right_approver", PROSE.replace("needs the CFO", "needs Finance"))
    assert not wrong.ok
    assert "Clause 3.2" in wrong.message or "3.2" in wrong.message


def test_s11_a_loaded_skill_asks_for_a_plan_only_when_planning_is_on() -> None:
    from agentic_harness.api import Off

    def skill_text(off: Any = None) -> str:
        h = create_harness(
            Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=None, off=off
        )
        return str(h.tools["load_skill"].function(name="contract-review"))

    assert "write_plan" in skill_text()
    assert "write_plan" not in skill_text(Off(tools=("write_plan",)))


def test_s11_ac8_checks_on_follow_ups_and_drafts() -> None:
    """Found live 2026-11-12, in follow-up turns and a customer email draft."""
    # A section read in an earlier turn of the conversation counts.
    policy = out("search_policy", query="discount")
    cited = "25% needs the CFO (`standard-terms §2`)."
    assert not CHECKS["citations"].fn(cited, Record()).ok
    assert CHECKS["citations"].fn(cited, Record(earlier=(policy.output,))).ok
    # "Nothing has been sent" and "once it is sent" are not claims that it was sent.
    for text in (
        "Nothing has been sent.",
        "It goes out once it has been sent for approval.",
        "It is not sent yet.",
    ):
        assert verdict("no_false_sent", text).applies is False, text
    assert not verdict("no_false_sent", "The reply has been sent to ShopCo.").ok
    sent = Call(
        "send_to_customer", {}, json.dumps({"status": "sent", "approved_by": ["Sales"]}), False
    )
    assert verdict("no_false_sent", "Sent, approved by Sales.", sent).ok


def test_s11_the_prompt_names_the_switched_on_checks_before_the_agent_writes() -> None:
    """D-132: found live, the agent learned the bar only from a failed check."""
    from agentic_harness.api import Off

    on = create_harness(Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=None)
    assert "## Before your answer reaches the person" in on.system
    assert "- Right Approver: " in on.system
    assert "- Plan Complete: " in on.system
    off = Off(checks=("right_approver",))
    h = create_harness(
        Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=None, off=off
    )
    assert "- Right Approver: " not in h.system
    assert "- No False Sent: " in h.system or '- No False "Sent": ' in h.system
    child = on.tools["delegate_task"].function.make_child(WS.subagents[0], Limits())
    assert "Before your answer reaches the person" not in child.system  # helpers aren't checked


def test_s11_the_plan_reply_reminds_the_agent_to_close_items() -> None:
    from agentic_harness.planning import Item, show

    assert "before your final answer" in show([Item("Look up", "done"), Item("Answer", "open")])
    assert "before your final answer" not in show(
        [Item("Look up", "done"), Item("Answer", "skipped", "n/a")]
    )


def test_s12_ac5_the_context_says_which_facts_it_read(tmp_path: Path) -> None:
    from agentic_harness.context import build_context

    summary = build_context(
        WS, "sales", notes="- 2026-11-12 · The CFO capped ShopCo at 20%\n"
    ).summary()
    assert summary["notes"] == ["- 2026-11-12 · The CFO capped ShopCo at 20%"]
    assert build_context(WS, "sales").summary()["notes"] == []


def test_s12_the_pane_and_prompt_name_the_check_before_the_send() -> None:
    from agentic_harness.api import describe_harness

    (action,) = describe_harness(WS, "sales")["verify"]["action_checks"]
    assert action == {
        "name": "body_matches_terms",
        "label": "Body Matches Terms",
        "description": action["description"],
        "tool": "send_to_customer",
    }
    h = create_harness(Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=None)
    assert "- Body Matches Terms (before send_to_customer runs): " in h.system
    assert [c.name for c in h.action_checks] == ["body_matches_terms"]


def test_an_answer_that_reports_a_send_is_not_asked_to_repeat_the_review() -> None:
    """Found live 2026-11-12: after "review and send", Every Change Covered made the answer
    list the whole review again. A send's answer reports the send."""
    sent = Call(
        "send_to_customer",
        {},
        json.dumps({"status": "sent", "approved_by": ["Sales", "CFO"]}),
        False,
    )
    answer = (
        "Sent to ShopCo, approved by Sales and the CFO: a 25% discount (`approval-chart §1`).\n"
        "Still open: Net 60."
    )
    got = CHECKS["every_change_covered"].fn(answer, Record((REVIEW, sent)))
    assert got.applies is False
    assert "reports a send" in got.message
    assert (
        not CHECKS["every_change_covered"].fn(answer, Record((REVIEW,))).ok
    )  # no send: still a review


def test_the_retry_note_asks_for_an_answer_written_for_the_person() -> None:
    from agentic_harness.verify import Result, feedback

    note = feedback([Result("x", "X", "failed", "wrong")])
    assert "don't mention these checks or your earlier draft" in note


# ── A contract pull (D-146): its facts are checked by the online evals now (D-150) ──

CUSTOMER = out("lookup_customer_record", record="customer", customer="ShopCo")
OUTLINE = out("read_contract", contract_id="CT-2207")
PULL = (CUSTOMER, OUTLINE)
PULLED = """Yes, ShopCo is an existing customer `CUS-0042`, with one contract, CT-2207 `CT-2207`.
- **2 · Term and renewal**: 2.1 three years, prices fixed.
- **3 · Fees and discounts**: 3.2 a 25% discount.
- **4 · Invoicing and payment**: 4.1 Net 60.
- **6 · Service levels**: 6.1 99.99% uptime.
- **9 · Liability**: 9.2 unlimited.
- **10 · Confidentiality**: 10.1 to 10.12, standard wording."""


def test_d147_right_approver_skips_a_pull_but_not_a_review() -> None:
    """Found live: a plain pull failed for "3.2: a 25% discount" with no CFO named."""
    pulled = verdict("right_approver", PULLED, *PULL)
    assert not pulled.applies, pulled.message
    reviewed = verdict("right_approver", "- 3.2 · 25% discount: fine.", REVIEW)
    assert reviewed.applies
    assert not reviewed.ok


def test_d159_a_section_named_in_shorthand_counts_as_read() -> None:
    skill = Call("load_skill", {}, "Cite `standard-terms §4`, `approval-chart §1`/`§2`.", False)
    v = verdict("citations", "Never (`approval-chart §2`).", skill)
    assert v.ok, v.message


def test_d159_answer_length_is_a_gate() -> None:
    assert [c.name for c in WS.checks][-1] == "answer_length"
    short = verdict("answer_length", "No: 99.99% is above our record. Offer 99.95%.")
    assert short.ok
    long = verdict("answer_length", "word " * 100)
    assert not long.ok
    assert "at most 90" in long.message
    review = verdict("answer_length", "word " * 190, REVIEW)
    assert review.ok  # a review may run to 200
    assert not verdict("answer_length", "Hi ShopCo,\n" + "word " * 200).applies


def test_d163_right_approver_credits_the_approvals_a_send_recorded() -> None:
    """Found live: after a real send approved by Priya, Elena and Dana, a summary line
    "Offered: 25% discount, 99.95% uptime, 24-month liability cap." failed three times."""
    sent = Call(
        "send_to_customer",
        {},
        json.dumps(
            {"status": "sent", "approved_by": ["Priya Raman", "Elena Brandt", "Dana Whitfield"]}
        ),
        False,
    )
    line = "Sent to ShopCo.\n- Offered: 25% discount, 99.95% uptime, 24-month liability cap."
    assert verdict("right_approver", line, REVIEW, sent).ok
    assert not verdict("right_approver", line, REVIEW).ok  # no send: still needs the names


def test_d163_the_review_is_shown_before_a_send_and_the_reviewer_checks_policy() -> None:
    sales = (ROOT / "teams" / "sales.md").read_text()
    assert "Review first, then ask." in sales
    assert "Change anything, or send it as is?" in sales
    reviewer = (ROOT / "agents" / "clause-reviewer.md").read_text()
    assert "Check every change that matters against CloudCo's policy" in reviewer
    skill = (ROOT / "skills" / "sales" / "reply-to-customer" / "SKILL.md").read_text()
    assert "fewest approvers" in skill
