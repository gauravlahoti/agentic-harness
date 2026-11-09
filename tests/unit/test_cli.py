"""The ``agentic-harness`` command starts, reports its version, and exits cleanly (S00-AC2)."""

import runpy
import sys

import pytest

from agentic_harness import __version__
from agentic_harness.cli import main


def test_s00_ac2_version_flag_prints_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert capsys.readouterr().out.strip() == f"agentic-harness {__version__}"


def test_s00_ac2_no_arguments_shows_help(capsys: pytest.CaptureFixture[str]) -> None:
    assert main([]) == 0
    assert "usage: agentic-harness" in capsys.readouterr().out


def test_s00_ac2_python_dash_m_runs_the_same_command(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["agentic-harness"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("agentic_harness", run_name="__main__")
    assert exit_info.value.code == 0
    assert "usage: agentic-harness" in capsys.readouterr().out
