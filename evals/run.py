"""``python -m evals.run``: run an eval from the terminal, ``make eval``, or the page (S10).

Part of the evals. Costs quota or money, so nothing runs it automatically: a person starts
it (D-104). The page starts this same command with fixed flags and reads ``--json`` lines.

    python -m evals.run                         every case, once, on the default model
    python -m evals.run --cases off-topic,find-changes --runs 3
    python -m evals.run --plan --json           what it would run and cost; calls nothing

Exit code: 0 finished, 1 stopped early (cap, quota, Stop), 2 setup error (no key, bad case).

Does not: decide what passes (``evals/scoring.py``) or choose the judge's models (``plan``).
"""

import argparse
import asyncio
import json
import signal
import sys
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from agentic_harness import config
from agentic_harness.model import ModelClient, make_model
from agentic_harness.pricing import PriceNotFoundError, load_prices
from evals.cases import CaseError, load_suite
from evals.plan import DEFAULT_CAP_USD, FALLBACK_AGENT, FALLBACK_JUDGE, JUDGE_MODEL, RUNS, estimate

DEFAULT_SUITE = Path("evals") / "cases" / "cloudco.toml"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m evals.run", description=__doc__.split("\n")[0])
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--cases", default="", help="comma-separated case IDs (default: all)")
    parser.add_argument("--runs", type=int, choices=RUNS, default=1)
    parser.add_argument("--model", default="", help="the agent's model (default: HARNESS_MODEL)")
    parser.add_argument("--cap", type=float, default=DEFAULT_CAP_USD, help="USD for the eval")
    parser.add_argument("--json", action="store_true", help="one JSON event per line")
    parser.add_argument("--plan", action="store_true", help="say what would run; run nothing")
    parser.add_argument("--out", type=Path, default=None, help="results folder")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def emit(event: dict[str, Any]) -> None:
        if args.json:
            print(json.dumps(event, ensure_ascii=False), flush=True)
        else:
            from evals.report import line

            print(line(event), flush=True)

    try:
        suite = load_suite(args.suite)
        cases = suite.pick([c for c in args.cases.split(",") if c] or None)
    except CaseError as error:
        emit({"type": "error", "message": str(error)})
        return 2
    settings = config.load_settings()
    model = args.model or settings.model
    fallback = FALLBACK_JUDGE if settings.has_anthropic_key else None
    # A Claude agent has no fallback: it is already the paid choice (D-116).
    claude_agent = model.startswith(config.CLAUDE_PREFIX)
    agent_fallback = FALLBACK_AGENT if fallback and not claude_agent else None
    if args.plan:
        emit(
            {
                "type": "plan",
                "cases": [
                    {"id": c.id, "group": c.group, "profile": c.profile, "turns": list(c.turns)}
                    for c in cases
                ],
                "runs": args.runs,
                "model": model,
                "judge": JUDGE_MODEL,
                "fallback_judge": fallback,
                "fallback_agent": agent_fallback,
                "cap_usd": args.cap,
                "estimate": estimate(cases, args.runs),
            }
        )
        return 0
    return asyncio.run(_run(args, suite, model, fallback, agent_fallback, settings, emit))


async def _run(
    args: argparse.Namespace,
    suite: Any,
    model: str,
    fallback: str | None,
    agent_fallback: str | None,
    settings: config.Settings,
    emit: Any,
) -> int:
    from evals.judge import Judge
    from evals.report import DEFAULT_FOLDER, save
    from evals.runner import Options, run_eval

    prices = load_prices()

    def factory(name: str) -> ModelClient:
        return make_model(replace(settings, model=name))

    try:
        prices.for_model(model)
        factory(model)  # no key for this model → say so now, not after the first case
        judge = Judge(
            factory(JUDGE_MODEL),
            prices,
            fallback=(lambda: factory(fallback)) if fallback else None,
        )
    except (config.MissingKeyError, PriceNotFoundError) as error:
        emit({"type": "error", "message": str(error)})
        return 2
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):  # Stop on the page sends SIGTERM
        loop.add_signal_handler(sig, stop.set)
    secrets = [k.reveal() for k in (settings.api_key, settings.anthropic_key) if k]
    folder = args.out or DEFAULT_FOLDER
    result = await run_eval(
        suite,
        Options(
            model=model,
            cases=[c for c in args.cases.split(",") if c] or None,
            runs=args.runs,
            max_usd=args.cap,
            fallback=agent_fallback,
        ),
        factory=factory,
        judge=judge,
        folder=folder,
        emit=emit,
        stop=stop,
        secrets=secrets,
    )
    emit({"type": "saved", "id": result["id"], "path": str(save(result, folder, secrets))})
    return 0 if result["status"] == "finished" else 1


if __name__ == "__main__":
    sys.exit(main())
