"""Entry points (S01-AC12): create_harness(...), ``agentic-harness run``, workspace tools."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from agentic_harness.api import create_harness
from agentic_harness.cli import main
from agentic_harness.config import Settings
from agentic_harness.limits import Limits
from agentic_harness.model import FakeModel
from agentic_harness.pricing import PriceNotFoundError
from agentic_harness.workspace import Workspace, WorkspaceError

ROOT = Path(__file__).resolve().parents[2]
HELLO = ROOT / "workspaces" / "hello"
Recorded = Callable[[str], dict[str, Any]]


def test_s01_ac12_hello_workspace_loads_its_tools() -> None:
    workspace = Workspace.load(HELLO)
    assert workspace.name == "hello"
    assert [t.name for t in workspace.tools] == ["get_time"]
    assert workspace.fake_replies  # a recorded run for Fake mode


def test_s01_ac12_hello_get_time_really_works() -> None:
    get_time = Workspace.load(HELLO).tools[0].function
    assert get_time(timezone="UTC").endswith("+00:00")
    with pytest.raises(ValueError, match="Unknown time zone"):
        get_time(timezone="Mars/Olympus")


def test_s01_ac12_workspace_errors_are_clear(tmp_path: Path) -> None:
    with pytest.raises(WorkspaceError, match="not a folder"):
        Workspace.load(tmp_path / "missing")
    (tmp_path / "tools.py").write_text("TOOLS = 'not a list'\n")
    with pytest.raises(WorkspaceError, match="TOOLS"):
        Workspace.load(tmp_path)


def test_s01_ac12_workspace_without_tools_is_fine(tmp_path: Path) -> None:
    workspace = Workspace.load(tmp_path)
    assert workspace.tools == ()
    assert workspace.fake_replies == ()


async def test_s01_ac12_create_harness_runs_a_task(tmp_path: Path, recorded: Recorded) -> None:
    model = FakeModel([recorded("02_tool_call"), recorded("03_tool_round_trip")])
    agent = create_harness(model, Limits(), Workspace.load(HELLO), trace_dir=tmp_path)
    result = await agent.run("What time is it in UTC?")
    assert result.outcome == "completed"
    assert result.model_calls == 2
    trace = (tmp_path / f"{result.run_id}.jsonl").read_text().splitlines()
    assert json.loads(trace[-1])["type"] == "run_finished"


def test_s01_ac12_unknown_model_price_fails_at_startup(tmp_path: Path, recorded: Recorded) -> None:
    model = FakeModel([recorded("01_text")], name="no-such-model")
    with pytest.raises(PriceNotFoundError):
        create_harness(model, Limits(), Workspace.load(tmp_path), trace_dir=None)


def test_s01_ac12_cli_run_fake(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code = main(
        [
            "run",
            "--workspace",
            str(HELLO),
            "--fake",
            "--trace-dir",
            str(tmp_path),
            "What time is it?",
        ]
    )
    out = capsys.readouterr().out
    assert code == 0
    assert "get_time" in out
    assert "completed in 2 calls" in out
    assert list(tmp_path.glob("*.jsonl"))


def test_s01_ac12_cli_run_live_without_key_explains(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agentic_harness.config.load_settings", Settings)  # no key, no .env
    code = main(["run", "--workspace", str(HELLO), "Hi"])
    assert code == 2
    assert ".env.example" in capsys.readouterr().err


def test_s01_ac12_cli_fake_needs_a_recording(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    code = main(["run", "--workspace", str(tmp_path), "--fake", "Hi"])
    assert code == 2
    assert "fake_replies.json" in capsys.readouterr().err
