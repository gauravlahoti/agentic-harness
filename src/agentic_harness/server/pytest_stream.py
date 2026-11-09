"""Pytest plugin: one JSON line per test, so the Checks panel can fill in live.

Harness part: the page's Checks panel (S00-AC14, D-21). Loaded only by the
panel's fixed command (``-p agentic_harness.server.pytest_stream``).

Does not: change how tests run, or run during ``make check``. pytest is a
dev tool, so this module works only in a dev install, like the panel itself.
"""

import json
from typing import Any

import pytest

# Lines starting with this are ours; everything else pytest prints is ignored.
PREFIX = "HARNESS-CHECK "


class Stream:
    """Writes events through pytest's own terminal, so test output capture can't swallow them."""

    def __init__(self, config: pytest.Config) -> None:
        self._config = config

    def _emit(self, event: dict[str, Any]) -> None:
        terminal = self._config.pluginmanager.getplugin("terminalreporter")
        if terminal is not None:
            terminal.write_line(PREFIX + json.dumps(event))

    def pytest_collection_finish(self, session: pytest.Session) -> None:
        # Announce every test first, so the page can draw all rows as "waiting".
        self._emit({"type": "collected", "tests": [item.nodeid for item in session.items]})

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        # pytest reports three phases per test. One row = the call, or the phase that
        # decided the outcome without a call (a skip in setup, a crash in teardown).
        decided = (
            report.when == "call"
            or (report.when == "setup" and report.outcome != "passed")
            or (report.when == "teardown" and report.outcome == "failed")
        )
        if decided:
            self._emit(
                {
                    "type": "result",
                    "test": report.nodeid,
                    "outcome": report.outcome,
                    "seconds": round(report.duration, 3),
                }
            )

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        self._emit({"type": "finished", "exit_code": int(exitstatus)})


def pytest_configure(config: pytest.Config) -> None:
    config.pluginmanager.register(Stream(config), "harness-check-stream")
