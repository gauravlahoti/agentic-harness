"""Plan and Verify in the loop (S11-AC1 to AC7; D-121 to D-127).

A scripted model stands in for Gemini: each test lists the replies it gives, in order,
and checks what the harness did with them. No model is called.
"""

import json
from pathlib import Path
from typing import Any

from agentic_harness.events import Event
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness, last_exchange
from agentic_harness.model import ModelReply, Step
from agentic_harness.planning import PLAN_TOOL, Item, latest_plan, plan_tool
from agentic_harness.pricing import load_prices
from agentic_harness.tools.registry import tool
from agentic_harness.trimming import prune
from agentic_harness.verify import (
    NOTE_PREFIX,
    PLAN_CHECK,
    Call,
    Record,
    Verdict,
    check,
    failed,
    passed,
)


class Scripted:
    """Replies in order. A reply is a list of steps; text only means "the answer"."""

    name = "gemini-3.5-flash-lite"

    def __init__(self, *replies: list[Step]) -> None:
        self.replies = list(replies)
        self.sent: list[list[Step]] = []

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        self.sent.append(list(steps))
        return ModelReply(self.replies.pop(0), "completed", {}, self.name)


def say(text: str) -> list[Step]:
    return [{"type": "model_output", "content": [{"type": "text", "text": text}]}]


def call(name: str, args: dict[str, Any], id_: str = "c1") -> list[Step]:
    return [{"type": "function_call", "id": id_, "name": name, "arguments": args}]


def plan(*items: tuple[str, str] | tuple[str, str, str], id_: str = "p1") -> list[Step]:
    rows = [{"text": i[0], "status": i[1], **({"note": i[2]} if len(i) > 2 else {})} for i in items]
    return call(PLAN_TOOL, {"items": rows}, id_)


@tool(risk="read")
def find(q: str = "") -> str:
    """Find a thing."""
    return f"found {q}: owner is Ada"


@check("Names the Owner", "The answer names the owner the tool returned")
def names_owner(answer: str, record: Record) -> Verdict | None:
    owners = [o for o in record.outputs("find") if "Ada" in o]
    if not owners:
        return None  # nothing to check: find never ran
    return passed("Names Ada.") if "Ada" in answer else failed("The tool said the owner is Ada.")


def harness(
    model: Scripted, *, checks: Any = (), with_plan: bool = True
) -> tuple[Harness, list[Event]]:
    tools = [find, *([plan_tool()] if with_plan else [])]
    h = Harness(
        model,
        Limits(),
        tools,
        prices=load_prices(),
        checks=[*([PLAN_CHECK] if with_plan else []), *checks],
        retries=1,
        root=Path(__file__).parent,
    )
    events: list[Event] = []
    h.subscribe(events.append)
    return h, events


def of(events: list[Event], kind: str) -> list[dict[str, Any]]:
    return [e.data for e in events if e.type == kind]


# ── AC1 · the plan lives in run state ────────────────────────────────────────────────────


async def test_s11_ac1_write_plan_stores_the_list_and_says_so() -> None:
    model = Scripted(
        plan(("Look up the owner", "doing"), ("Answer", "open")),
        plan(("Look up the owner", "done"), ("Answer", "done"), id_="p2"),
        say("The owner is Ada."),
    )
    h, events = harness(model)
    result = await h.run("Who owns it?")
    updates = of(events, "plan_updated")
    assert [len(u["items"]) for u in updates] == [2, 2]
    assert updates[-1]["items"][0] == {"text": "Look up the owner", "status": "done", "note": ""}
    assert updates[-1]["done"] == 2
    assert updates[-1]["total"] == 2
    # The model gets the whole list back, so the newest copy is always in its history.
    output = [d for d in of(events, "tool_finished") if d["name"] == PLAN_TOOL][-1]["output"]
    assert "[x] Look up the owner" in output
    assert "2 of 2 done" in output
    assert result.outcome == "completed"
    finished = of(events, "run_finished")[0]
    assert finished["plan"][1]["status"] == "done"


def test_s11_ac1_the_tool_is_a_harness_tool_with_a_schema_gemini_accepts() -> None:
    t = plan_tool()
    items = t.parameters["properties"]["items"]
    assert items["type"] == "array"
    assert items["items"]["type"] == "object"
    assert items["items"]["properties"]["status"]["enum"] == ["open", "doing", "done", "skipped"]
    # Not supported in Gemini declarations (docs/gemini-api-notes.md): no bounds, no defaults.
    assert "minItems" not in json.dumps(t.declaration())
    assert "default" not in json.dumps(t.declaration())
    assert "3 or more" in t.description  # the model decides when to plan (D-121)


# ── AC2 · saved as steps, rebuilt from them ──────────────────────────────────────────────


async def test_s11_ac2_the_plan_is_saved_as_steps_and_rebuilt_from_them() -> None:
    model = Scripted(
        plan(("Look up", "done"), ("Answer", "doing")),
        plan(("Look up", "done"), ("Answer", "done"), id_="p2"),
        say("Done."),
    )
    h, _ = harness(model)
    saved: list[Step] = []
    await h.run("Do it", record=saved.extend)
    rebuilt = latest_plan(saved)
    assert rebuilt == [Item("Look up", "done"), Item("Answer", "done")]
    assert latest_plan([]) is None


def test_s11_ac2_a_rejected_update_is_not_the_plan() -> None:
    steps: list[Step] = [
        *plan(("A", "done")),
        {"type": "function_result", "name": PLAN_TOOL, "call_id": "p1", "result": []},
        *plan(("A", "skipped"), id_="p2"),
        {
            "type": "function_result",
            "name": PLAN_TOOL,
            "call_id": "p2",
            "result": [],
            "is_error": True,
        },
    ]
    assert latest_plan(steps) == [Item("A", "done")]


# ── AC3 · trimming keeps the newest plan whole ───────────────────────────────────────────


def test_s11_ac3_trimming_never_stubs_the_newest_plan() -> None:
    def result(name: str, id_: str, text: str) -> Step:
        return {
            "type": "function_result",
            "name": name,
            "call_id": id_,
            "result": [{"type": "text", "text": text}],
        }

    steps: list[Step] = [
        *plan(("A", "open")),
        result(PLAN_TOOL, "p1", "old plan " * 50),
        *plan(("A", "doing"), id_="p2"),
        result(PLAN_TOOL, "p2", "new plan " * 50),
        *call("find", {}, "f1"),
        result("find", "f1", "x" * 500),
        *call("find", {}, "f2"),
        result("find", "f2", "y" * 500),
    ]
    out, cleared = prune(steps, keep_recent=1)
    texts = {
        s["call_id"]: s["result"][0]["text"] for s in out if s.get("type") == "function_result"
    }
    assert texts["p2"].startswith("new plan")  # pinned
    assert texts["p1"].startswith("[")  # an older plan may shrink
    assert texts["f1"].startswith("[")
    assert texts["f2"].startswith("y")
    assert cleared == 2


# ── AC4 · open items: one reminder, then finish ──────────────────────────────────────────


async def test_s11_ac4_open_items_get_one_reminder_then_the_run_finishes() -> None:
    model = Scripted(
        plan(("Look up", "done"), ("Send", "open")),
        say("Looked it up."),
        say("Looked it up, still."),
    )
    h, events = harness(model)
    result = await h.run("Look up and send")
    reminder = model.sent[2][-1]
    assert reminder["type"] == "user_input"
    text = reminder["content"][0]["text"]
    assert text.startswith(NOTE_PREFIX)
    assert "Send" in text
    assert "skipped" in text
    assert len(model.sent) == 3  # one reminder, no loop
    assert result.outcome == "completed"
    assert result.answer == "Looked it up, still."
    rounds = of(events, "verify_finished")
    assert [r["passed"] for r in rounds] == [False, False]
    assert rounds[0]["retrying"] is True
    assert rounds[1]["retrying"] is False
    finished = of(events, "run_finished")[0]
    assert finished["checks"]["passed"] is False
    assert finished["plan"][1]["status"] == "open"  # shown incomplete
    assert result.verified is False


async def test_s11_ac4_a_light_question_makes_no_plan_and_skips_the_plan_check() -> None:
    model = Scripted(say("Yes, Net 45 is standard."))
    h, events = harness(model)
    result = await h.run("Is Net 45 OK?")
    assert of(events, "plan_updated") == []
    assert len(model.sent) == 1
    assert result.verified is None  # nothing applied: neither verified nor not
    (round_,) = of(events, "verify_finished")  # every switched-on check is accounted for
    assert round_["passed"] is None
    assert [r["status"] for r in round_["results"]] == ["skipped"]
    assert "No plan was made" in round_["results"][0]["message"]


# ── AC5 · a skip needs a reason ──────────────────────────────────────────────────────────


async def test_s11_ac5_skipped_needs_a_note() -> None:
    model = Scripted(
        plan(("Send", "skipped")),
        plan(("Send", "skipped", "the person asked only for a review"), id_="p2"),
        say("Reviewed; not sent, as asked."),
    )
    h, events = harness(model)
    result = await h.run("Review only")
    first, second = [d for d in of(events, "tool_finished") if d["name"] == PLAN_TOOL]
    assert first["is_error"]
    assert "note" in first["output"]
    assert not second["is_error"]
    assert result.verified is True  # a skipped item with a reason counts as finished


async def test_s11_ac5_bad_items_are_explained_to_the_model() -> None:
    model = Scripted(call(PLAN_TOOL, {"items": [{"text": "", "status": "later"}]}), say("ok"))
    h, events = harness(model)
    await h.run("x")
    out = of(events, "tool_finished")[0]
    assert out["is_error"]
    assert "status" in out["output"]
    assert "text" in out["output"]
    assert of(events, "plan_updated") == []


# ── AC6 · VERIFY runs after the draft, before run_finished ───────────────────────────────


async def test_s11_ac6_checks_run_after_the_draft_and_before_the_finish() -> None:
    model = Scripted(call("find", {"q": "acme"}), say("The owner is Ada."))
    h, events = harness(model, checks=[names_owner])
    result = await h.run("Who owns acme?")
    kinds = [e.type for e in events]
    assert (
        kinds.index("verify_started") < kinds.index("verify_finished") < kinds.index("run_finished")
    )
    started = of(events, "verify_started")[0]
    assert started["round"] == 1
    assert [c["label"] for c in started["checks"]] == ["Plan Complete", "Names the Owner"]
    verdict = of(events, "verify_finished")[0]
    assert verdict["passed"] is True
    assert verdict["round"] == 1
    assert [(r["name"], r["status"]) for r in verdict["results"]] == [
        ("plan_complete", "skipped"),  # no plan: shown as skipped, with why
        ("names_owner", "passed"),
    ]
    assert verdict["results"][1] == {
        "name": "names_owner",
        "label": "Names the Owner",
        "status": "passed",
        "message": "Names Ada.",
    }
    assert result.verified is True


async def test_s11_ac6_the_record_holds_every_call_including_a_helpers() -> None:
    h, _ = harness(Scripted(), checks=[])
    from agentic_harness.loop import _Run

    run = _Run(h._bus)
    run.emit("tool_started", call_id="a", name="find", arguments={"q": "1"})
    run.emit(
        "tool_started",
        call_id="a",
        name="find",
        arguments={"q": "2"},
        agent_id="h1",
        agent="helper",
    )
    run.emit(
        "tool_finished",
        call_id="a",
        name="find",
        output="two",
        is_error=False,
        agent_id="h1",
        agent="helper",
    )
    run.emit("tool_finished", call_id="a", name="find", output="one", is_error=False)
    record = run.record(profile="sales")
    assert record.calls == (
        Call("find", {"q": "2"}, "two", False, "helper"),
        Call("find", {"q": "1"}, "one", False, ""),
    )
    assert record.outputs("find") == ["two", "one"]
    assert record.profile == "sales"


async def test_s11_ac6_a_broken_check_is_shown_and_never_sent_back() -> None:
    @check("Broken", "Always raises")
    def broken(answer: str, record: Record) -> Verdict | None:
        raise ValueError("bug in the check")

    model = Scripted(say("Hi."))
    h, events = harness(model, checks=[broken])
    result = await h.run("Hi")
    verdict = of(events, "verify_finished")[0]
    assert verdict["results"][1]["status"] == "error"  # [0] is the skipped plan check
    assert "bug in the check" in verdict["results"][1]["message"]
    assert verdict["passed"] is None  # only a broken check and a skipped one: nothing verified
    assert len(model.sent) == 1
    assert result.verified is None


# ── AC7 · one retry, then "Not verified" ─────────────────────────────────────────────────


async def test_s11_ac7_a_failed_check_is_sent_back_once_and_the_retry_can_pass() -> None:
    model = Scripted(
        call("find", {"q": "acme"}), say("The owner is Bob."), say("The owner is Ada.")
    )
    h, events = harness(model, checks=[names_owner])
    result = await h.run("Who owns acme?")
    note = model.sent[2][-1]["content"][0]["text"]
    assert note.startswith(NOTE_PREFIX)
    assert "Names the Owner" in note
    assert "Ada" in note
    rounds = of(events, "verify_finished")
    assert [r["passed"] for r in rounds] == [False, True]
    assert rounds[0]["draft"] == "The owner is Bob."  # the page folds the first draft
    assert rounds[0]["note"].startswith(NOTE_PREFIX)  # the page shows what the agent was told
    assert rounds[1]["note"] == ""
    assert result.answer == "The owner is Ada."
    assert result.verified is True


async def test_s11_ac7_a_second_failure_goes_out_marked_not_verified() -> None:
    model = Scripted(call("find", {"q": "acme"}), say("Bob."), say("Still Bob."))
    h, events = harness(model, checks=[names_owner])
    result = await h.run("Who owns acme?")
    assert len(model.sent) == 3  # one retry only
    assert result.outcome == "completed"
    assert result.answer == "Still Bob."
    assert result.verified is False
    checks = of(events, "run_finished")[0]["checks"]
    assert checks == {
        "passed": False,
        "rounds": 2,
        "results": [
            {
                "name": "plan_complete",
                "label": "Plan Complete",
                "status": "skipped",
                "message": "No plan was made: the agent treated the task as simple.",
            },
            {
                "name": "names_owner",
                "label": "Names the Owner",
                "status": "failed",
                "message": "The tool said the owner is Ada.",
            },
        ],
    }


async def test_s11_ac7_the_harness_note_is_not_read_as_the_persons_question() -> None:
    note: Step = {
        "type": "user_input",
        "content": [{"type": "text", "text": f"{NOTE_PREFIX} fix it"}],
    }
    history: list[Step] = [
        {"type": "user_input", "content": [{"type": "text", "text": "Who owns acme?"}]},
        note,
        {"type": "model_output", "content": [{"type": "text", "text": "Ada."}]},
    ]
    assert "Person: Who owns acme?" in last_exchange(history)


def test_s11_ac11_a_saved_turn_keeps_its_plan_and_checks(tmp_path: Path) -> None:
    from agentic_harness.memory import SessionStore, Turn

    store = SessionStore(tmp_path, "ws")
    session = store.create("sales")
    checks = {"passed": True, "rounds": 2, "results": []}
    plan_rows = [{"text": "Look up", "status": "done", "note": ""}]
    store.finish_turn(
        session.id,
        "sales",
        Turn("t", "a", "completed", 0.0, 1.0, "r", plan=plan_rows, checks=checks),
    )
    store.finish_turn(session.id, "sales", Turn("light", "b", "completed", 0.0, 1.0, "r2"))
    first, second = store.load(session.id, "sales").turns
    assert first.plan == plan_rows
    assert first.checks == checks
    assert second.plan is None
    assert second.checks is None


def test_s11_trimming_keeps_a_skills_text_whole() -> None:
    """Found live: stubbed mid-run, the reply skill's instructions vanished (D-123 extended)."""
    from agentic_harness.skills import SKILL_TOOL

    steps: list[Step] = [
        *call(SKILL_TOOL, {"name": "reply"}, "s1"),
        {
            "type": "function_result",
            "name": SKILL_TOOL,
            "call_id": "s1",
            "result": [{"type": "text", "text": "Step 1 " * 80}],
        },
        *call("find", {}, "f1"),
        {
            "type": "function_result",
            "name": "find",
            "call_id": "f1",
            "result": [{"type": "text", "text": "x" * 500}],
        },
        *call("find", {}, "f2"),
        {
            "type": "function_result",
            "name": "find",
            "call_id": "f2",
            "result": [{"type": "text", "text": "y" * 500}],
        },
    ]
    out, cleared = prune(steps, keep_recent=1)
    texts = {
        s["call_id"]: s["result"][0]["text"] for s in out if s.get("type") == "function_result"
    }
    assert texts["s1"].startswith("Step 1")
    assert texts["f1"].startswith("[")
    assert cleared == 1
