"""Run the project's offline tests and stream one event per test (S00-AC14).

Harness part: the page's Checks panel. The command is fixed: the browser can
start a run but can't add a single argument, so the page can never become a
remote shell (S00 key choice).

Does not: run live (paid) tests, or let the test run see the API key.
"""

import asyncio
import json
import os
import sys
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from agentic_harness.config import SECRET_ENV_NAMES
from agentic_harness.server.pytest_stream import PREFIX

CHECKS_COMMAND = (
    sys.executable,
    "-m",
    "pytest",
    "-p",
    "agentic_harness.server.pytest_stream",
    "-p",
    "no:cacheprovider",  # a test run from the page leaves no files behind
    "-m",
    "not live",  # never spend money from a button
    "-q",
)

DEFAULT_LIMIT_SECONDS = 120.0  # a stuck test must not hold the panel forever


def _child_env() -> dict[str, str]:
    """The current environment minus the key: offline tests never need it."""
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV_NAMES}


async def run_checks(
    project_root: Path, limit_seconds: float = DEFAULT_LIMIT_SECONDS
) -> AsyncIterator[dict[str, Any]]:
    """Yield the plugin's events as tests finish, then ``exit`` (or ``error`` on timeout)."""
    process = await asyncio.create_subprocess_exec(
        *CHECKS_COMMAND,
        cwd=project_root,
        env=_child_env(),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    if process.stdout is None:  # can't happen with stdout=PIPE; says so to the type checker
        raise RuntimeError("test run started without an output pipe")
    try:
        async with asyncio.timeout(limit_seconds):
            async for raw in process.stdout:
                # pytest may print a progress mark (".", "F") on the same line first,
                # so look for our prefix anywhere; the JSON after it is always one line.
                _, found, event = raw.decode(errors="replace").rstrip().partition(PREFIX)
                if found:
                    yield json.loads(event)
            code = await process.wait()
    except TimeoutError:
        message = f"Stopped: the tests took longer than {limit_seconds:g} s."
        yield {"type": "error", "message": message}
        return
    finally:
        if process.returncode is None:  # timed out, or the page went away mid-run
            process.kill()
            await process.wait()
    yield {"type": "exit", "code": code}
