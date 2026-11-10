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
    async def says_out(task: str) -> Verdict:
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
    async def breaks(task: str) -> Verdict:
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
