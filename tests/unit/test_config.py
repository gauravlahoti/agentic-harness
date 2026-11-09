"""Settings and secrets (S00-AC10, S00-AC11, S00-AC12).

The key is loaded in one place, never shows when printed, and is optional:
everything offline works without it.
"""

import os
import subprocess
from pathlib import Path

import pytest

from agentic_harness.config import MissingKeyError, Secret, Settings, load_settings

ROOT = Path(__file__).resolve().parents[2]
FAKE_KEY = "AIza-fake-key-for-tests-0123456789"


def write_env(tmp_path: Path, text: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(text)
    return env_file


def test_s00_ac11_secret_never_shows_when_printed() -> None:
    secret = Secret(FAKE_KEY)
    for shown in (str(secret), repr(secret), f"{secret}", f"{secret!r}"):
        assert shown == "***"
    assert secret.reveal() == FAKE_KEY


def test_s00_ac11_settings_repr_hides_the_key(tmp_path: Path) -> None:
    settings = load_settings(write_env(tmp_path, f"GEMINI_API_KEY={FAKE_KEY}\n"), environ={})
    assert FAKE_KEY not in repr(settings)
    assert FAKE_KEY not in str(settings)
    assert settings.require_key() == FAKE_KEY


def test_s00_ac11_loading_does_not_put_the_key_in_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A key in os.environ would reach every child process (e.g. the Checks panel's test run).
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    load_settings(write_env(tmp_path, f"GEMINI_API_KEY={FAKE_KEY}\n"))
    assert "GEMINI_API_KEY" not in os.environ


def test_s00_ac11_real_environment_overrides_the_file(tmp_path: Path) -> None:
    env_file = write_env(tmp_path, "HARNESS_MODEL=from-file\n")
    settings = load_settings(env_file, environ={"HARNESS_MODEL": "from-env"})
    assert settings.model == "from-env"


def test_s00_ac11_only_config_reads_the_env_file() -> None:
    """No module but config.py may touch dotenv or the key's variable name."""
    src = ROOT / "src" / "agentic_harness"
    offenders = [
        str(path.relative_to(src))
        for path in src.rglob("*.py")
        if path.name != "config.py"
        and any(word in path.read_text() for word in ("dotenv", "GEMINI_API_KEY"))
    ]
    assert offenders == []


def test_s00_ac12_no_key_still_loads(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.env", environ={})
    assert settings.api_key is None
    assert settings.has_key is False
    assert settings.backend == "gemini_api"
    assert settings.model  # a default model name exists


def test_s00_ac12_empty_key_counts_as_no_key(tmp_path: Path) -> None:
    settings = load_settings(write_env(tmp_path, "GEMINI_API_KEY=\n"), environ={})
    assert settings.has_key is False


def test_s00_ac12_asking_for_a_missing_key_explains_what_to_do() -> None:
    settings = Settings()
    with pytest.raises(MissingKeyError, match=r"\.env\.example"):
        settings.require_key()


def test_s00_ac12_unknown_backend_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="HARNESS_BACKEND"):
        load_settings(write_env(tmp_path, "HARNESS_BACKEND=other\n"), environ={})


def test_s00_ac10_env_file_is_git_ignored() -> None:
    result = subprocess.run(["git", "check-ignore", "--quiet", ".env"], cwd=ROOT, check=False)
    assert result.returncode == 0, ".env must be ignored by git"


def test_s00_ac10_env_example_has_names_but_no_values() -> None:
    lines = (ROOT / ".env.example").read_text().splitlines()
    settings = [line for line in lines if line and not line.lstrip().startswith("#")]
    assert settings, ".env.example lists at least one setting"
    for line in settings:
        name, _, value = line.partition("=")
        assert value.strip() == "", f"{name} must have no value in .env.example"
