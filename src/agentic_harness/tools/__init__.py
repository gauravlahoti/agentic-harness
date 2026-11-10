"""Tools: a name, a description, a JSON schema, and the Python function behind it.

Harness part: actions. The model only ever sees the declaration (name,
description, parameters); it never gets the function itself. S03 adds the
``@tool`` decorator, risk levels and built-in tools on top of this record.

Does not: run tools (the loop does) or know any workspace's tools by name.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any] = field(default_factory=lambda: {"type": "object"})
    function: Callable[..., Any] = field(default=lambda: None, repr=False)
    # Which harness part acts when this tool runs: "tool" for actions, "context" for
    # built-ins that only read context (load_skill). The page colours lines by it.
    part: str = "tool"

    def declaration(self) -> dict[str, Any]:
        """What Gemini is shown: its function-tool format."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
