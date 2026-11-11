"""Save an eval's result as one JSON file the page can read (S10-AC7).

Part of the evals. Results live in ``.agentic-harness/evals/<id>.json`` (git-ignored); the
page lists that folder. The catalog (the 11 metrics and the skipped ones) is copied in, so
an old result still explains itself after the catalog changes.

Before writing, every key the run could touch is replaced by ``***``. The traces are already
redacted by the harness; this is the same promise for the result file.

Does not: run or score anything.
"""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from evals.scoring import catalog


def save(result: dict[str, Any], folder: Path, secrets: Sequence[str] = ()) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    text = json.dumps({**result, "catalog": catalog()}, ensure_ascii=False, indent=1)
    for secret in secrets:
        if secret:
            text = text.replace(secret, "***")
    path = folder / f"{result['id']}.json"
    path.write_text(text)
    return path


def line(event: dict[str, Any]) -> str:
    """One event as a line for a person reading the terminal."""
    kind = event.get("type")
    if kind == "eval_started":
        cost = event["estimate"]
        return (
            f"Eval {event['id']} · {len(event['cases'])} cases x {event['runs']} runs · "
            f"agent {event['model']} · judge {event['judge']} · "
            f"≈ {cost['agent_runs']} agent runs, {cost['judge_calls']} judge calls · "
            f"cap ${event['cap_usd']:.2f}"
        )
    if kind == "run_started":
        return f"  … {event['case']} run {event['run']}"
    if kind == "run_finished":
        failed = [m for m, s in event["metrics"].items() if not s["passed"]]
        mark = "✓" if event["passed"] else "✗"
        why = f" · failed: {', '.join(failed)}" if failed else ""
        return f"  {mark} {event['case']} run {event['run']} · ${event['usd']:.4f}{why}"
    if kind == "eval_finished":
        s = event["summary"]
        stop = f" · {event['stop_reason']}" if event["stop_reason"] else ""
        return (
            f"{s['passed']}/{s['cases']} cases passed · {s['failed']} failed · "
            f"{s['incomplete']} incomplete · ${event['usd']['total']:.4f}{stop}"
        )
    if kind == "saved":
        return f"Result: {event['path']}"
    if kind == "error":
        return f"✗ {event['message']}"
    return json.dumps(event)
