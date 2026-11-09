"""Command-line entry point: the ``agentic-harness`` command.

Harness part: packaging. It makes the harness a runtime you point at a
workspace, the way you run Claude Code, rather than a one-off script.
``serve`` opens the local page (S00); ``run`` arrives with the loop (S01).

Does not: hold any agent logic. It only reads arguments and hands off.
"""

import argparse
from collections.abc import Sequence

from agentic_harness import __version__

# Fixed, not an option: nothing on your network can reach the harness (D-20).
HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def build_parser() -> argparse.ArgumentParser:
    """Describe the command line. One place, so help text and tests agree."""
    parser = argparse.ArgumentParser(
        prog="agentic-harness",
        description="Run agents on the harness. An agent is a workspace folder.",
    )
    parser.add_argument("--version", action="version", version=f"agentic-harness {__version__}")
    commands = parser.add_subparsers(dest="command")
    serve = commands.add_parser("serve", help=f"open the local page on http://{HOST}:PORT")
    serve.add_argument("--port", type=int, default=DEFAULT_PORT, help="default: %(default)s")
    return parser


def serve(port: int) -> int:
    """Start the local server. Imports stay inside so ``--version`` stays instant."""
    import uvicorn

    from agentic_harness.config import load_settings
    from agentic_harness.server.app import create_app

    print(f"agentic-harness → http://{HOST}:{port}  (Ctrl+C to stop)")
    uvicorn.run(create_app(load_settings()), host=HOST, port=port, log_level="info")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return an exit code (0 = success)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        return serve(args.port)
    # No command: show help instead of doing nothing silently.
    parser.print_help()
    return 0
