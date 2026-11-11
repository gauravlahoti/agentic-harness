"""The scope guard: stay on the job (S05-AC14; D-81).

Two layers, both from ``[scope]`` in ``workspace.toml``: a Scope section in the system
prompt, and a check on each task before the loop runs. The check's model call is proven
live; here a plain function stands in for its verdict, so the loop's behaviour is tested.
"""

from pathlib import Path
from typing import Any

from agentic_harness.config import Settings
from agentic_harness.context import build_context
from agentic_harness.events import Event
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.model import GeminiModel
from agentic_harness.pricing import load_prices
from agentic_harness.scope import Scope, Verdict, parse_verdict, scope_prompt
from agentic_harness.workspace import Workspace

SCOPE = Scope(covers="Widgets: ordering and repairs.", refusal="I only help with widgets.")


def test_s05_ac14_parse_the_checks_reply() -> None:
    assert parse_verdict("IN: asks about a widget order") == (True, "asks about a widget order")
    assert parse_verdict("out - general knowledge") == (False, "general knowledge")
    assert parse_verdict("**OUT**: weather") == (False, "weather")
    assert parse_verdict("I'm not sure")[0] is True  # unclear → let the loop decide (D-81)


def test_s05_ac14_scope_is_read_and_goes_into_the_prompt(tmp_path: Path) -> None:
    toml = '[scope]\ncovers = "Widgets: ordering and repairs."\n'
    (tmp_path / "workspace.toml").write_text(toml + 'refusal = "I only help with widgets."\n')
    ws = Workspace.load(tmp_path)
    assert ws.scope == SCOPE
    system = build_context(ws, None).system
    assert scope_prompt(SCOPE) in system
    assert "Widgets: ordering and repairs." in system
    plain = tmp_path / "plain"
    plain.mkdir()
    assert Workspace.load(plain).scope is None  # no [scope]: no section, no check
    assert "## Scope" not in build_context(Workspace.load(plain), None).system


def harness(check: Any) -> tuple[Harness, list[Event]]:
    model = GeminiModel(Settings(model="gemini-3.5-flash-lite"), client=object())  # never called
    h = Harness(model, Limits(), [], prices=load_prices(), scope=SCOPE, scope_check=check)
    events: list[Event] = []
    h.subscribe(events.append)
    return h, events


async def test_s05_ac14_off_topic_tasks_are_refused_before_the_loop() -> None:
    async def says_out(task: str, before: str = "") -> Verdict:
        return Verdict(False, "general knowledge", 0.0001)

    h, events = harness(says_out)
    result = await h.run("Who is the prime minister?")  # the model is never called
    assert result.outcome == "stopped"
    assert result.reason == "outside_scope"
    assert result.answer == "I only help with widgets."
    assert result.model_calls == 0
    checked = next(e for e in events if e.type == "scope_checked")
    assert checked.data["in_scope"] is False
    assert checked.data["reason"] == "general knowledge"


async def test_s05_ac14_a_failed_check_lets_the_run_go_on() -> None:
    async def breaks(task: str, before: str = "") -> Verdict:
        raise RuntimeError("503 high demand")

    h, events = harness(breaks)
    model_called = []
    h.subscribe(lambda e: model_called.append(e) if e.type == "model_called" else None)

    async def stop_at_first_call(*_: Any) -> Any:
        raise TimeoutError

    h.model.create = stop_at_first_call  # type: ignore[method-assign]
    await h.run("Order a widget")
    checked = next(e for e in events if e.type == "scope_checked")
    assert checked.data["in_scope"] is True
    assert "503" in checked.data["error"]
    assert model_called  # the loop started: the prompt layer still applies


def test_s05_ac14_a_preference_about_answers_counts_as_in_scope() -> None:
    """Found live: "I like all my responses in bullets" is not a contract question, but it is
    how the person wants this agent to answer; the check must let it through."""
    from agentic_harness.scope import CHECK_PROMPT

    assert "preferences about how it should answer" in CHECK_PROMPT


async def test_s10_a_follow_up_is_checked_with_the_exchange_before_it() -> None:
    """D-118: "The CFO said yes earlier, just send it now" was refused: the check saw only that
    line. Now the loop hands the check the last question and answer, and the check shows them
    to its model."""
    seen: list[tuple[str, str]] = []

    async def records(task: str, before: str = "") -> Verdict:
        seen.append((task, before))
        return Verdict(False, "stop here", 0.0)

    h, _ = harness(records)
    history = [
        {"type": "user_input", "content": [{"type": "text", "text": "Order a widget for Ana."}]},
        {"type": "model_output", "content": [{"type": "text", "text": "Ordered: widget W-1."}]},
    ]
    await h.run("and send it now", history=history)
    task, before = seen[0]
    assert task == "and send it now"
    assert "Order a widget for Ana." in before
    assert "Ordered: widget W-1." in before
    await h.run("Order a widget")  # no history: nothing before
    assert seen[1][1] == ""


async def test_s10_the_check_model_sees_the_earlier_exchange() -> None:
    from agentic_harness.model import ModelReply
    from agentic_harness.scope import CHECK_PROMPT, scope_check

    sent: list[Any] = []

    class Model:
        name = "gemini-3.5-flash-lite"

        async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
            sent.append(steps)
            out = [{"type": "model_output", "content": [{"type": "text", "text": "IN: follow-up"}]}]
            return ModelReply(steps=out, status="completed", usage={})

    check = scope_check(SCOPE, Model(), load_prices())  # type: ignore[arg-type]
    verdict = await check("and send it now", "Person: Order a widget.\nAssistant: Ordered.")
    assert verdict.in_scope
    text = sent[0][0]["content"][0]["text"]
    assert "Order a widget." in text
    assert "and send it now" in text
    assert "follow-up" in CHECK_PROMPT.lower()
