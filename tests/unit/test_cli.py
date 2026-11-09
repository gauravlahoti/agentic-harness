"""The ``agentic-harness`` command starts, reports its version, and exits cleanly (S00-AC2)."""

import runpy
import sys

import pytest

from agentic_harness import __version__
from agentic_harness.cli import main
from agentic_harness.config import Settings


def test_s00_ac2_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"agentic-harness {__version__}"


def test_s00_ac2_no_arguments_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: agentic-harness" in capsys.readouterr().out


def test_s00_ac13_serve_binds_to_localhost_only(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("uvicorn.run", lambda _app, **kwargs: calls.append(kwargs))
    monkeypatch.setattr("agentic_harness.config.load_settings", Settings)  # never read a real .env
    assert main(["serve", "--port", "8123"]) == 0
    assert calls == [{"host": "127.0.0.1", "port": 8123, "log_level": "info"}]


def test_s00_ac13_serve_has_no_host_option() -> None:
    with pytest.raises(SystemExit):
        main(["serve", "--host", "0.0.0.0"])  # noqa: S104 (proving it's refused)


def test_s00_ac2_python_dash_m_runs_the_same_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agentic-harness"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("agentic_harness", run_name="__main__")
    assert exit_info.value.code == 0
    assert "usage: agentic-harness" in capsys.readouterr().out
