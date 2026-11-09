"""The Checks panel's test run (S00-AC14).

One fixed command, one event per test, streamed as the tests finish.
The runner is tested against a tiny throwaway suite, never our own (that would recurse).
"""

import json
import textwrap
from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from agentic_harness.server import checks, pytest_stream


class FakeReporter:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def write_line(self, line: str) -> None:
        self.lines.append(line)


def fake_config(reporter: FakeReporter | None) -> Any:
    return SimpleNamespace(pluginmanager=SimpleNamespace(getplugin=lambda _name: reporter))


def events_from(reporter: FakeReporter) -> list[dict[str, Any]]:
    prefix = pytest_stream.PREFIX
    return [json.loads(line.removeprefix(prefix)) for line in reporter.lines]


def report(nodeid: str, when: str, outcome: str, duration: float = 0.01) -> Any:
    return SimpleNamespace(nodeid=nodeid, when=when, outcome=outcome, duration=duration)


# ── The plugin, in-process ───────────────────────────────────────────────────


def test_s00_ac14_plugin_announces_every_collected_test() -> None:
    reporter = FakeReporter()
    stream = pytest_stream.Stream(fake_config(reporter))
    stream.pytest_collection_finish(SimpleNamespace(items=[SimpleNamespace(nodeid="t.py::a")]))
    assert events_from(reporter) == [{"type": "collected", "tests": ["t.py::a"]}]


def test_s00_ac14_plugin_emits_one_result_per_test() -> None:
    reporter = FakeReporter()
    stream = pytest_stream.Stream(fake_config(reporter))
    stream.pytest_runtest_logreport(report("t.py::a", "setup", "passed"))  # not a result yet
    stream.pytest_runtest_logreport(report("t.py::a", "call", "passed", 0.1234))
    stream.pytest_runtest_logreport(report("t.py::a", "teardown", "passed"))  # nothing new
    stream.pytest_runtest_logreport(report("t.py::b", "setup", "skipped"))  # skipped before call
    stream.pytest_runtest_logreport(report("t.py::c", "teardown", "failed"))  # broke after call
    stream.pytest_sessionfinish(SimpleNamespace(), 1)
    assert events_from(reporter) == [
        {"type": "result", "test": "t.py::a", "outcome": "passed", "seconds": 0.123},
        {"type": "result", "test": "t.py::b", "outcome": "skipped", "seconds": 0.01},
        {"type": "result", "test": "t.py::c", "outcome": "failed", "seconds": 0.01},
        {"type": "finished", "exit_code": 1},
    ]


def test_s00_ac14_plugin_is_silent_without_a_terminal() -> None:
    stream = pytest_stream.Stream(fake_config(None))
    stream.pytest_sessionfinish(SimpleNamespace(), 0)  # must not crash


def test_s00_ac14_plugin_registers_itself() -> None:
    registered: list[object] = []
    config = SimpleNamespace(
        pluginmanager=SimpleNamespace(register=lambda plugin, _name: registered.append(plugin))
    )
    pytest_stream.pytest_configure(config)  # type: ignore[arg-type]
    assert isinstance(registered[0], pytest_stream.Stream)


# ── The runner, as a real subprocess ─────────────────────────────────────────


def make_suite(tmp_path: Path, body: str) -> Path:
    (tmp_path / "test_tiny.py").write_text(textwrap.dedent(body))
    return tmp_path


async def collect(events: AsyncIterator[dict[str, Any]]) -> list[dict[str, Any]]:
    return [event async for event in events]


def test_s00_ac14_command_is_fixed() -> None:
    """The browser can't add arguments: the command is a constant, not built from input."""
    assert isinstance(checks.CHECKS_COMMAND, tuple)
    assert "agentic_harness.server.pytest_stream" in checks.CHECKS_COMMAND


async def test_s00_ac14_streams_one_row_per_test(tmp_path: Path) -> None:
    suite = make_suite(
        tmp_path,
        """
        def test_ok():
            assert True

        def test_broken():
            assert False
        """,
    )
    events = await collect(checks.run_checks(suite))
    kinds = [event["type"] for event in events]
    assert kinds == ["collected", "result", "result", "finished", "exit"]
    outcomes = {event["test"]: event["outcome"] for event in events if event["type"] == "result"}
    assert outcomes == {"test_tiny.py::test_ok": "passed", "test_tiny.py::test_broken": "failed"}
    assert events[-1] == {"type": "exit", "code": 1}


async def test_s00_ac14_child_run_never_sees_the_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "should-not-leak")
    suite = make_suite(
        tmp_path,
        """
        import os

        def test_no_key_in_child():
            assert "GEMINI_API_KEY" not in os.environ
        """,
    )
    events = await collect(checks.run_checks(suite))
    assert {"type": "exit", "code": 0} in events


async def test_s00_ac14_a_stuck_run_is_stopped(tmp_path: Path) -> None:
    suite = make_suite(
        tmp_path,
        """
        import time

        def test_slow():
            time.sleep(30)
        """,
    )
    events = await collect(checks.run_checks(suite, limit_seconds=3))
    assert events[-1]["type"] == "error"
    assert "3 s" in events[-1]["message"]
