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
from agentic_harness.gate import ApprovalRequest

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
    run.add_argument("--profile", help="whose view to use (default: the first profile listed)")
    run.add_argument("--trace-dir", type=Path, help="where to save the trace")
    run.add_argument("--max-steps", type=int, help="stop after this many model calls")
    run.add_argument("--max-usd", type=float, help="stop after spending this much")
    run.add_argument("--max-seconds", type=float, help="stop after this long")
    run.add_argument(
        "--no-delegation", action="store_true", help="no helper agents: do everything itself"
    )
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
    from dataclasses import replace

    from agentic_harness import config
    from agentic_harness.api import DEFAULT_TRACE_DIR, create_harness
    from agentic_harness.limits import Limits
    from agentic_harness.model import GeminiModel, ModelClient
    from agentic_harness.workspace import Workspace, WorkspaceError

    workspace = Workspace.load(args.workspace)
    settings = config.load_settings()
    try:
        model: ModelClient = GeminiModel(settings)
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
    try:
        harness = create_harness(
            model,
            limits,
            workspace,
            profile=args.profile,
            trace_dir=trace_dir,
            secrets=secrets,
            # A helper may name its own model (D-62).
            model_factory=lambda name: GeminiModel(replace(settings, model=name)),
            delegation=not args.no_delegation,
            approver=ask_in_terminal,  # a person answers y/N here (D-79)
        )
    except WorkspaceError as error:
        print(error, file=sys.stderr)
        return 2
    harness.subscribe(print_event)
    result = asyncio.run(harness.run(args.task))
    print(f"trace: {trace_dir / (result.run_id + '.jsonl')}")
    return 0 if result.outcome == "completed" else 1


async def ask_in_terminal(request: ApprovalRequest) -> tuple[bool, str]:
    """Human in the loop, in the terminal: show what would happen, wait for y/N."""
    print(f"  ⏸ {request.tool} needs your approval · {request.because}")
    for key, value in request.arguments.items():
        print(f"      {key}: {value}")
    try:
        answer = await asyncio.to_thread(input, "    Approve? [y/N] ")
    except EOFError:  # no terminal to ask: the answer is no
        return False, "no one at the terminal"
    approved = answer.strip().lower() in ("y", "yes")
    return approved, "" if approved else "rejected in the terminal"


def print_event(event: Event) -> None:
    """One short line per step, for people. A helper's steps are indented under it."""
    d = event.data
    if d.get("agent_id"):
        _print_helper_event(event)
    elif event.type == "run_started":
        print(f"▶ {d['task']}  [{d['model']}]")
        context = d.get("context") or {}
        if context.get("files") or context.get("skills"):
            files = ", ".join(f"{f['path']} (~{f['tokens']})" for f in context["files"])
            skills = ", ".join(s["name"] for s in context["skills"]) or "none"
            who = f"{context['profile']} · " if context.get("profile") else ""
            print(
                f"  context: {who}{files} · skills: {skills} · ~{context['prompt_tokens']} tokens"
            )
        for warning in context.get("warnings", []):
            print(f"  ⚠ {warning}")
    elif event.type == "scope_checked":
        if not d["in_scope"]:
            print(f"  ⛔ outside scope: {d['reason']}")
        elif d.get("error"):
            print("  · scope check skipped (busy); the prompt still keeps it on topic")
        else:
            print("  ✓ in scope")
    elif event.type == "model_called":
        print(f"  → asking the model (call {d['step']})")
    elif event.type == "model_replied":
        wants = f" · wants {', '.join(d['tool_calls'])}" if d["tool_calls"] else ""
        print(f"  ← {d['status']}{wants} · ${d['usd']:.5f}")
    elif event.type == "tool_started":
        args = ", ".join(f"{k}={v!r}" for k, v in d["arguments"].items())
        mark = "📖" if d.get("part") == "context" else "⚙"
        print(f"  {mark} {d['name']}({args})")
    elif event.type == "tool_finished":
        if blocked := d.get("blocked"):
            print(f"    ⛔ blocked: {blocked['label']} ({blocked['because']})")
            return
        mark = "✗" if d["is_error"] else "✓"
        print(f"    {mark} {d['output'][:200]}")
        if d.get("hidden"):
            print(f"    🔒 hidden: {', '.join(d['hidden'])}")
        if d.get("flags"):
            print(f"    ⚠ flagged: {d['flags'][0]!r}")
    elif event.type == "approval_decided":
        verdict = "✓ approved" if d["approved"] else "✗ rejected"
        print(f"    {verdict}{': ' + d['note'] if d['note'] else ''}")
    elif event.type == "run_finished":
        if d["answer"]:
            print(f"\n{d['answer']}\n")
        calls = d["model_calls"]
        print(
            f"■ {d['outcome']} in {calls} call{'s' if calls != 1 else ''} · "
            f"{d['reason']} · ${d['usd']:.5f} · {d['seconds']:.1f} s"
        )


def _print_helper_event(event: Event) -> None:
    d, bar = event.data, f"    ┆ {event.data['agent']}"
    if event.type == "run_started":
        print(f"{bar} ▶ started · {d['model']} · tools: {', '.join(d['tools']) or 'none'}")
    elif event.type == "model_replied":
        wants = f" · wants {', '.join(d['tool_calls'])}" if d["tool_calls"] else ""
        print(f"{bar} ← {d['status']}{wants} · ${d['usd']:.5f}")
    elif event.type == "tool_started":
        print(f"{bar} ⚙ {d['name']}")
    elif event.type == "run_finished":
        calls, usd, secs = d["model_calls"], d["usd"], d["seconds"]
        print(f"{bar} ■ {d['outcome']} · {calls} calls · ${usd:.5f} · {secs:.1f} s")


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
