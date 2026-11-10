"""The smallest possible workspace: one real tool, so the loop has something to call (D-26).

Not part of the harness: the harness loads this file by path and knows nothing about it.
``@tool`` builds the declaration Gemini sees from the function itself (D-43).
"""

from datetime import datetime
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agentic_harness.tools.registry import tool


@tool(risk="read")
def get_time(timezone: Annotated[str, "IANA name, e.g. 'UTC' or 'Asia/Tokyo'"]) -> str:
    """Returns the current time in a time zone, as ISO 8601."""
    try:
        zone = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError(f"Unknown time zone: {timezone}") from None
    return datetime.now(zone).isoformat(timespec="seconds")


TOOLS = [get_time]
