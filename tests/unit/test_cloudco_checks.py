"""CloudCo's four answer checks, each with a pass and a fail (S11-AC8), and the wrong-approver
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
CHECKS = {c.name: c for c in WS.checks}
TOOLS = {t.name: t for t in WS.tools}
CTX = ToolContext("t", ROOT, profile="sales")


def out(name: str, **args: Any) -> Call:
    value = TOOLS[name].function(**args, ctx=CTX)
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


def test_s11_ac8_the_workspace_declares_four_checks_and_the_plan() -> None:
    assert list(CHECKS) == [
        "every_change_covered",
        "citations_exist",
        "right_approver",
        "no_false_sent",
    ]
    assert WS.plan
    assert WS.verify_retries == 1


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
    ok = verdict("citations_exist", "25% needs the CFO (standard-terms §2).", policy)
    assert ok.ok
    bad = verdict("citations_exist", "Fine under standard-terms §9.", policy)
    assert not bad.ok
    assert "standard-terms §9" in bad.message
    assert verdict("citations_exist", "No citations here.").applies is False


def test_s11_ac8_right_approver() -> None:
    assert verdict("right_approver", GOOD).ok
    wrong = verdict("right_approver", "3.2 · 25% discount · Finance can approve it")
    assert not wrong.ok
    assert "CFO" in wrong.message
    assert "names Finance, who decides none" in wrong.message
    missing = verdict("right_approver", "4.1 · Net 60 · fine")
    assert not missing.ok
    assert "Finance" in missing.message
    never = verdict("right_approver", "6.1 · 99.99% uptime · Engineering approves")
    assert not never.ok
    assert "never allowed" in never.message
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
    assert "Citations Exist" in note  # §2 was cited but never read: also caught
    assert result.verified is True
    assert "CFO" in result.answer
    rounds = [e.data for e in events if e.type == "verify_finished"]
    assert [r["passed"] for r in rounds] == [False, True]


def test_s11_ac1_ac10_wiring_plan_tool_switches_and_pane() -> None:
    from agentic_harness.api import Off, describe_harness

    model = Scripted()
    h = create_harness(model, Limits(), WS, profile="sales", trace_dir=None, memory_dir=None)
    assert "update_plan" in h.tools
    assert next(c.name for c in h.checks) == "plan_complete"
    # Helpers never plan: the clause-reviewer's tools are its own list (AC1).
    child = h.tools["delegate_task"].function.make_child(WS.subagents[0], Limits())
    assert "update_plan" not in child.tools
    assert child.checks == ()
    # A check switched off doesn't run; the plan tool can be switched off too (AC10).
    off = Off(tools=("update_plan",), checks=("right_approver", "plan_complete"))
    h2 = create_harness(
        model, Limits(), WS, profile="sales", trace_dir=None, memory_dir=None, off=off
    )
    assert "update_plan" not in h2.tools
    assert [c.name for c in h2.checks] == [
        "every_change_covered",
        "citations_exist",
        "no_false_sent",
    ]
    pane = describe_harness(WS, "sales")["verify"]
    assert pane["plan_on"]
    assert pane["retries"] == 1
    assert [c["label"] for c in pane["checks"]][:2] == ["Plan Complete", "Every Change Covered"]
    assert pane["checks"][0]["source"] == "built-in"


def test_s11_ac10_the_pane_lists_the_harness_tools_and_each_can_be_switched_off() -> None:
    from agentic_harness.api import Off, describe_harness

    own = describe_harness(WS, "sales")["harness_tools"]
    assert [t["name"] for t in own] == ["load_skill", "save_note", "ask_human", "update_plan"]
    assert all(t["when_off"] for t in own)
    assert "3 or more" in own[-1]["description"]  # the same words the model reads
    off = Off(tools=("load_skill", "save_note", "ask_human", "update_plan"))
    h = create_harness(
        Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=tmp_dir(), off=off
    )
    assert not {"load_skill", "save_note", "ask_human", "update_plan"} & set(h.tools)
    assert "contract-review" not in h.system  # load_skill off: no skills listed either
    on = create_harness(
        Scripted(), Limits(), WS, profile="sales", trace_dir=None, memory_dir=tmp_dir()
    )
    assert {"load_skill", "save_note", "ask_human", "update_plan"} <= set(on.tools)
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
