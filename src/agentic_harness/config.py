"""Settings and secrets: the only module that reads ``.env``.

Harness part: setup. Every other module gets a ``Settings`` object and never
looks at files or environment variables for the key itself. One place to audit.

Does not: put the key into ``os.environ`` (child processes would inherit it),
call Gemini, or fail when the key is missing. Offline work never needs it.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast, get_args

from dotenv import dotenv_values

Backend = Literal["gemini_api", "agent_platform"]

# The key's variable names. Other modules import this list (e.g. to strip the key from a
# child process) instead of spelling the names themselves.
SECRET_ENV_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")

MISSING_KEY_MESSAGE = "No Gemini key. Copy .env.example to .env and set GEMINI_API_KEY."

DEFAULT_MODEL = "gemini-3.8-flash"  # D-07; model names live in config only
# Claude (D-102 to D-104): a paid option the person picks. Its key has its own name.
ANTHROPIC_KEY_NAME = "ANTHROPIC_API_KEY"
CLAUDE_PREFIX = "claude-"
CLAUDE_SMALL_MODEL = "claude-haiku-5-5"  # a Claude run's helper, checks and titles (D-103)
EVAL_JUDGE_MODEL = "gemini-3.5-flash-lite"  # the evals' default judge: most free quota (D-111)
MISSING_ANTHROPIC_KEY = "No Claude key. Add ANTHROPIC_API_KEY to .env, then restart."
DEFAULT_ENV_FILE = Path(".env")


class MissingKeyError(RuntimeError):
    """A live Gemini call was asked for, but no key is set."""


class Secret:
    """A value that prints as ``***`` everywhere: str, repr, f-strings, logs."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        """Return the real value. Call this only where the value is sent to Google."""
        return self._value

    def __repr__(self) -> str:
        return "***"

    __str__ = __repr__


@dataclass(frozen=True, slots=True)
class Settings:
    """Everything the harness can be configured with. Frozen: nothing changes it mid-run."""

    api_key: Secret | None = None
    backend: Backend = "gemini_api"
    model: str = DEFAULT_MODEL
    project: str | None = None
    location: str = "global"
    # How hard the model thinks: Gemini's ``thinking_level``. None: the model's own default.
    thinking: str | None = None
    anthropic_key: Secret | None = None  # Claude's key, if the person added one (D-104)

    @property
    def has_key(self) -> bool:
        return self.api_key is not None

    @property
    def has_anthropic_key(self) -> bool:
        return self.anthropic_key is not None

    def require_anthropic_key(self) -> str:
        """Return Claude's key for a call the person chose, or explain how to add one."""
        if self.anthropic_key is None:
            raise MissingKeyError(MISSING_ANTHROPIC_KEY)
        return self.anthropic_key.reveal()

    def require_key(self) -> str:
        """Return the key for a live call, or explain how to add one."""
        if self.api_key is None:
            raise MissingKeyError(MISSING_KEY_MESSAGE)
        return self.api_key.reveal()


def load_settings(
    env_file: Path = DEFAULT_ENV_FILE, environ: Mapping[str, str] | None = None
) -> Settings:
    """Read ``.env`` (if present) and the real environment. The real environment wins."""
    file_values = {k: v for k, v in dotenv_values(env_file).items() if v is not None}
    values = {**file_values, **(os.environ if environ is None else environ)}

    def get(name: str) -> str | None:
        value = values.get(name, "").strip()
        return value or None  # an empty line in .env means "not set"

    backend = get("HARNESS_BACKEND") or "gemini_api"
    if backend not in get_args(Backend):
        raise ValueError(f"HARNESS_BACKEND must be one of {get_args(Backend)}, not {backend!r}")

    key = next((v for name in SECRET_ENV_NAMES if (v := get(name))), None)
    return Settings(
        api_key=Secret(key) if key else None,
        backend=cast(Backend, backend),  # checked against Backend just above
        model=get("HARNESS_MODEL") or DEFAULT_MODEL,
        project=get("GOOGLE_CLOUD_PROJECT"),
        location=get("GOOGLE_CLOUD_LOCATION") or "global",
        anthropic_key=Secret(claude) if (claude := get(ANTHROPIC_KEY_NAME)) else None,
    )
