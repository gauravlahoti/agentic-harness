"""Checks on an action, before anyone is asked (S12-AC1, AC3; D-134, D-135).

Found in the S11 run: the email went out before anything checked it, because the checks read
only the final answer. Here a tiny tool, gate and check stand in for a workspace; no model.
"""

from pathlib import Path
from typing import Any

from agentic_harness.config import Settings
from agentic_harness.events import Event
from agentic_harness.gate import Approval, ApprovalRequest, Gate, Rule
from agentic_harness.limits import Budget, Limits
from agentic_harness.loop import Harness, _Run
from agentic_harness.model import GeminiModel
from agentic_harness.pricing import load_prices
from agentic_harness.tools.registry import tool
from agentic_harness.verify import Record, Verdict, action_check, failed, passed

sent: list[str] = []


@tool(risk="action")
def send(body: str, price: int | None = None) -> str:
    """Send a message."""
    sent.append(body)
    return "sent"


@action_check("send", "Body Says the Price", "The body states the price the call offers")
def body_says_price(arguments: dict[str, Any], record: Record) -> Verdict | None:
    if arguments.get("price") is None:
        return None
    price = str(arguments["price"])
    if price in arguments.get("body", ""):
        return passed(f"The body says {price}.")
    return failed(f"The price is {price}, but the body doesn't say it.")


GATE = Gate(
    "Alpha",
    ("send",),
    (),
    (Rule("price-never", "Price above 50", "send", "price", above=50, because="terms §2"),),
    (Approval("send", approver="Boss", because="chart §1"),),
)


def harness() -> tuple[Harness, list[Event], list[str]]:
    asked: list[str] = []

    async def approve(request: ApprovalRequest) -> tuple[bool, str]:
        asked.append(request.approver)
        return True, ""

    model = GeminiModel(Settings(model="gemini-3.5-flash-lite"), client=object())  # never called
    h = Harness(
        model,
        Limits(),
        [send],
        prices=load_prices(),
        gate=GATE,
        approver=approve,
        action_checks=[body_says_price],
        root=Path(__file__).parent,
    )
    events: list[Event] = []
    h.subscribe(events.append)
    return h, events, asked


async def step(h: Harness, args: dict[str, Any]) -> dict[str, Any]:
    call = {"type": "function_call", "id": "c1", "name": "send", "arguments": args}
    return await h._run_tool(call, _Run(h._bus), Budget(Limits()))


def kinds(events: list[Event]) -> list[str]:
    return [e.type for e in events]


async def test_s12_ac1_a_failed_action_check_stops_the_call_before_anyone_is_asked() -> None:
    h, events, asked = harness()
    sent.clear()
    result = await step(h, {"body": "Our offer is attached.", "price": 20})
    assert result.get("is_error") is True
    text = result["result"][0]["text"]
    assert text.startswith("Not done: the harness checked this call before anyone was asked.")
    assert "Body Says the Price: The price is 20" in text
    assert asked == []  # no one saw it
    assert sent == []  # it never ran
    assert kinds(events) == ["tool_started", "limits_checked", "action_checked", "tool_finished"]
    checked = next(e.data for e in events if e.type == "action_checked")
    assert checked["passed"] is False
    assert checked["results"][0]["status"] == "failed"


async def test_s12_ac1_a_passing_action_check_is_shown_then_people_are_asked() -> None:
    h, events, asked = harness()
    sent.clear()
    result = await step(h, {"body": "Our price is 20.", "price": 20})
    assert not result.get("is_error")
    assert asked == ["Boss"]
    assert sent == ["Our price is 20."]
    order = kinds(events)
    # limits → the check → the person → the run
    assert (
        order.index("limits_checked")
        < order.index("action_checked")
        < order.index("approval_requested")
    )


async def test_s12_ac1_a_blocked_call_never_reaches_the_check() -> None:
    h, events, asked = harness()
    sent.clear()
    result = await step(h, {"body": "Our price is 90.", "price": 90})
    assert "Blocked by the harness: Price above 50" in result["result"][0]["text"]
    assert "action_checked" not in kinds(events)
    (limit,) = next(e.data for e in events if e.type == "limits_checked")["limits"]
    assert limit["held"] is False  # the step shows which line it crossed (AC3)
    assert asked == []
