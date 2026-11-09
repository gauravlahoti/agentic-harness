"""Shared test helpers: real Gemini replies recorded by scripts/record_gemini_shapes.py."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

FIXTURES = Path(__file__).parent / "fixtures" / "gemini"


def load_reply(name: str) -> dict[str, Any]:
    """The reply part of a recorded case, e.g. ``load_reply("02_tool_call")``."""
    reply: dict[str, Any] = json.loads((FIXTURES / f"{name}.json").read_text())["reply"]
    return reply


@pytest.fixture
def recorded() -> Callable[[str], dict[str, Any]]:
    return load_reply
