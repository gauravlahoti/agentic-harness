"""Command-line entry point: the ``agentic-harness`` command.

Harness part: packaging. It makes the harness a runtime you point at a
workspace, the way you run Claude Code, rather than a one-off script.
Later stages add ``serve`` (S00) and ``run`` (S01).

Does not: hold any agent logic. It only reads arguments and hands off.
"""

import argparse
from collections.abc import Sequence

from agentic_harness import __version__


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line. One place, so help text and tests agree."""
    parser = argparse.ArgumentParser(
        prog="agentic-harness",
        description="Run agents on the harness. An agent is a workspace folder.",
    )
    parser.add_argument("--version", action="version", version=f"agentic-harness {__version__}")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return an exit code (0 = success)."""
    parser = build_parser()
    parser.parse_args(argv)
    # No sub-commands yet: show help instead of doing nothing silently.
    parser.print_help()
    return 0
