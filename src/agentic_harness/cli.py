"""Command-line entry point: the ``agentic-harness`` command.

Harness part: packaging. It makes the harness a runtime you point at a
workspace, the way you run Claude Code, rather than a one-off script.
``serve`` opens the local page (S00); ``run`` runs one task in the terminal (S01).

Does not: hold any agent logic. It reads arguments, builds a harness with
``create_harness`` and prints the events it emits.
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from agentic_harness import __version__
from agentic_harness.events import Event

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
    serve.add_argument("--workspace", type=Path, help="the agent to run from the page")

    run = commands.add_parser("run", help="run one task in the terminal")
    run.add_argument("task", help="what you want the agent to do")
    run.add_argument("--workspace", type=Path, required=True, help="the agent's folder")
    run.add_argument("--fake", action="store_true", help="replay the workspace's recorded run")
    run.add_argument("--trace-dir", type=Path, help="where to save the trace")
    run.add_argument("--max-steps", type=int, help="stop after this many model calls")
    run.add_argument("--max-usd", type=float, help="stop after spending this much")
    run.add_argument("--max-seconds", type=float, help="stop after this long")
    return parser


def serve(port: int, workspace: Path | None) -> int:
    """Start the local server. Imports stay inside so ``--version`` stays instant."""
    import uvicorn

    from agentic_harness import config
    from agentic_harness.server.app import create_app
    from agentic_harness.workspace import Workspace

    app = create_app(
        config.load_settings(), workspace=Workspace.load(workspace) if workspace else None
    )
    print(f"agentic-harness → http://{HOST}:{port}  (Ctrl+C to stop)")
    uvicorn.run(app, host=HOST, port=port, log_level="info")
    return 0


def run(args: argparse.Namespace) -> int:
    """Run one task and print each step. Exit code: 0 completed, 1 stopped/failed, 2 setup."""
    from agentic_harness import config
    from agentic_harness.api import DEFAULT_TRACE_DIR, create_harness
    from agentic_harness.limits import Limits
    from agentic_harness.model import FakeModel, GeminiModel, ModelClient
    from agentic_harness.workspace import Workspace

    workspace = Workspace.load(args.workspace)
    model: ModelClient
    secrets: list[str] = []
    if args.fake:  # no key needed, so settings (and .env) are not even read
        if not workspace.fake_replies:
            print(f"{workspace.name} has no fake_replies.json to replay.", file=sys.stderr)
            return 2
        model = FakeModel(workspace.fake_replies)
    else:
        settings = config.load_settings()
        try:
            model = GeminiModel(settings)
        except config.MissingKeyError as error:
            print(error, file=sys.stderr)
            return 2
        secrets = [settings.api_key.reveal()] if settings.api_key else []  # kept out of traces

    defaults = Limits()
    limits = Limits(
        max_steps=args.max_steps or defaults.max_steps,
        max_usd=args.max_usd or defaults.max_usd,
        max_seconds=args.max_seconds or defaults.max_seconds,
    )
    trace_dir = args.trace_dir or DEFAULT_TRACE_DIR
    harness = create_harness(model, limits, workspace, trace_dir=trace_dir, secrets=secrets)
    harness.subscribe(print_event)
    result = asyncio.run(harness.run(args.task))
    print(f"trace: {trace_dir / (result.run_id + '.jsonl')}")
    return 0 if result.outcome == "completed" else 1


def print_event(event: Event) -> None:
    """One short line per step, for people."""
    d = event.data
    if event.type == "run_started":
        print(f"▶ {d['task']}  [{d['model']}]")
    elif event.type == "model_called":
        print(f"  → asking the model (call {d['step']})")
    elif event.type == "model_replied":
        wants = f" · wants {', '.join(d['tool_calls'])}" if d["tool_calls"] else ""
        print(f"  ← {d['status']}{wants} · ${d['usd']:.5f}")
    elif event.type == "tool_started":
        args = ", ".join(f"{k}={v!r}" for k, v in d["arguments"].items())
        print(f"  ⚙ {d['name']}({args})")
    elif event.type == "tool_finished":
        mark = "✗" if d["is_error"] else "✓"
        print(f"    {mark} {d['output'][:200]}")
    elif event.type == "run_finished":
        if d["answer"]:
            print(f"\n{d['answer']}\n")
        calls = d["model_calls"]
        print(
            f"■ {d['outcome']} in {calls} call{'s' if calls != 1 else ''} · "
            f"{d['reason']} · ${d['usd']:.5f} · {d['seconds']:.1f} s"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command and return an exit code (0 = success)."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "serve":
        return serve(args.port, args.workspace)
    if args.command == "run":
        return run(args)
    # No command: show help instead of doing nothing silently.
    parser.print_help()
    return 0
