"""The smallest possible workspace: one real tool, so the loop has something to call (D-26).

Not part of the harness: the harness loads this file by path and knows nothing
about it. S03 replaces the hand-written schema with a ``@tool`` decorator.
"""

from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agentic_harness.tools import Tool


def get_time(timezone: str) -> str:
    """The current time in an IANA time zone, as ISO 8601."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown time zone: {timezone}") from None
    return datetime.now(zone).isoformat(timespec="seconds")


TOOLS = [
    Tool(
        name="get_time",
        description="Returns the current time in a time zone, as ISO 8601.",
        parameters={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "IANA name, e.g. 'UTC' or 'Asia/Tokyo'",
                }
            },
            "required": ["timezone"],
        },
        function=get_time,
    )
]
