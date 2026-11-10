"""Entry points (S01-AC12): ``create_harness`` checks, the ``run`` command, workspace tools."""

from pathlib import Path

import pytest

from agentic_harness.api import create_harness
from agentic_harness.cli import main
from agentic_harness.config import Settings
from agentic_harness.limits import Limits
from agentic_harness.model import GeminiModel
from agentic_harness.pricing import PriceNotFoundError
from agentic_harness.workspace import Workspace, WorkspaceError

ROOT = Path(__file__).resolve().parents[2]
HELLO = ROOT / "workspaces" / "hello"


def test_s01_ac12_hello_workspace_loads_its_tools() -> None:
    workspace = Workspace.load(HELLO)
    assert workspace.name == "hello"
    assert [t.name for t in workspace.tools] == ["get_time"]


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


def test_s01_ac12_unknown_model_price_fails_at_startup(tmp_path: Path) -> None:
    model = GeminiModel(Settings(model="no-such-model"), client=object())
    with pytest.raises(PriceNotFoundError):
        create_harness(model, Limits(), Workspace.load(tmp_path), trace_dir=None)


def test_s01_ac12_cli_run_live_without_key_explains(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("agentic_harness.config.load_settings", Settings)  # no key, no .env
    code = main(["run", "--workspace", str(HELLO), "Hi"])
    assert code == 2
    assert ".env.example" in capsys.readouterr().err


CLOUDCO = ROOT / "workspaces" / "cloudco"


def test_s02_ac2_create_harness_builds_the_context(tmp_path: Path) -> None:
    model = GeminiModel(Settings(model="gemini-3.6-flash"), client=object())
    agent = create_harness(
        model, Limits(), Workspace.load(CLOUDCO), profile="engineering", trace_dir=None
    )
    assert "**Engineering**" in agent.system
    assert "load_skill" in agent.tools  # built in, because this profile has skills
    assert agent.tools["load_skill"].part == "context"
    assert agent.context["profile"] == "engineering"
    assert agent.context["prompt_id"] == agent.prompt_id


def test_s02_ac2_no_skills_means_no_load_skill(tmp_path: Path) -> None:
    model = GeminiModel(Settings(model="gemini-3.6-flash"), client=object())
    agent = create_harness(model, Limits(), Workspace.load(HELLO), trace_dir=None)
    assert "load_skill" not in agent.tools


def test_s02_ac3_cli_refuses_an_unknown_profile(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from agentic_harness.config import Secret

    key = Secret("test-value-not-a-real-key")
    monkeypatch.setattr("agentic_harness.config.load_settings", lambda: Settings(api_key=key))
    code = main(["run", "--workspace", str(CLOUDCO), "--profile", "pirates", "Hi"])
    assert code == 2
    assert "pirates" in capsys.readouterr().err


def test_s03_ac2_create_harness_adds_only_the_builtins_asked_for(tmp_path: Path) -> None:
    model = GeminiModel(Settings(model="gemini-3.5-flash-lite"), client=object())
    plain = create_harness(model, Limits(), Workspace.load(tmp_path), trace_dir=None)
    assert list(plain.tools) == []
    (tmp_path / "workspace.toml").write_text('builtins = ["write_file"]\n')
    harness = create_harness(model, Limits(), Workspace.load(tmp_path), trace_dir=None)
    assert list(harness.tools) == ["write_file"]


def test_s03_ac3_a_workspace_tool_may_not_shadow_a_builtin(tmp_path: Path) -> None:
    (tmp_path / "workspace.toml").write_text('builtins = ["read_file"]\n')
    (tmp_path / "tools.py").write_text(
        "from agentic_harness.tools.registry import tool\n\n"
        '@tool(risk="read")\ndef read_file(path: str) -> str:\n    """Mine."""\n    return path\n\n'
        "TOOLS = [read_file]\n"
    )
    model = GeminiModel(Settings(model="gemini-3.5-flash-lite"), client=object())
    with pytest.raises(WorkspaceError, match="read_file"):
        create_harness(model, Limits(), Workspace.load(tmp_path), trace_dir=None)
