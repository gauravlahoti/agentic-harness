"""Re-grade a finished eval's saved runs, for chosen metrics only (eval debugging, D-154).

Part of the evals. A full eval re-runs the agent, so a grading fix and the agent's own
variance get mixed up, and it costs the whole eval again. This keeps the agent's answers
fixed (the traces saved under ``.agentic-harness/evals/<id>/traces``) and asks the judge
again for only the metrics named, so one change is measured on its own, for cents.

    uv run python -m evals.rescore 20261112-161801-55a809 --metrics plan_adherence
    uv run python -m evals.rescore <id> --metrics online --online-judge claude-haiku-5-5

``online`` re-scores the six Answer Quality metrics with the harness's online evals, from
each turn's tool calls as the trace recorded them.

Does not: run the agent, change the saved eval, or spend past ``--cap``.
"""

import argparse
import asyncio
import json
import sys
import time
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

from agentic_harness import config
from agentic_harness.model import make_model
from agentic_harness.online_evals import DEFAULT_IDS, OnlineEvals
from agentic_harness.pricing import load_prices
from agentic_harness.verify import Call, Record
from agentic_harness.workspace import Workspace
from evals.cases import load_suite
from evals.checks import Score
from evals.judge import Judge
from evals.runner import role_of, topics_of
from evals.scoring import ANSWER_QUALITY, one_metric, quality_scores
from evals.traces import RunView, read_run

FOLDER = Path(".agentic-harness/evals")
SUITE = Path("evals/cases/cloudco.toml")


def views_of(eval_dir: Path, run: dict[str, Any]) -> list[RunView]:
    return [read_run(eval_dir / "traces" / f"{t['run_id']}.jsonl") for t in run["turns"]]


async def online_again(views: Sequence[RunView], evals: OnlineEvals) -> tuple[list[RunView], float]:
    """Each turn's six Answer Quality metrics again, with the harness's current code."""
    out: list[RunView] = []
    usd, before = 0.0, ""
    earlier: tuple[str, ...] = ()
    for view in views:
        calls = tuple(Call(t.name, t.arguments, t.output, t.is_error, t.agent) for t in view.tools)
        if view.outcome == "completed" and view.answer:
            scored = await evals.score(
                view.task, view.answer, Record(calls, earlier=earlier), before
            )
            usd += scored.usd
            view = replace(
                view,
                online=tuple(r.to_dict() for r in scored.results),
                online_usd=scored.usd,
                online_judge=scored.judge,
            )
        out.append(view)
        earlier = (*earlier, *(c.output for c in calls if not c.is_error))
        before = f"Person: {view.task}\nAgent: {view.answer}"
    return out, usd


async def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("eval_id")
    parser.add_argument("--metrics", required=True, help="comma list, or 'online'")
    parser.add_argument("--judge", default="claude-sonnet-5-5")
    parser.add_argument("--online-judge", default="claude-haiku-5-5")
    parser.add_argument("--cap", type=float, default=0.5, help="stop past this many dollars")
    parser.add_argument("--label", default="", help="what changed, for the saved file")
    parser.add_argument("--cases", default="", help="comma list of case IDs; default every case")
    args = parser.parse_args(argv)

    eval_dir = FOLDER / args.eval_id
    saved = json.loads((FOLDER / f"{args.eval_id}.json").read_text())
    suite = load_suite(SUITE)
    cases = {c.id: c for c in suite.cases}
    workspace = Workspace.load(eval_dir / "workspace")
    role = {p.id: role_of(workspace, p.id) for p in workspace.profiles}
    topics = topics_of(workspace)
    settings = config.load_settings()
    prices = load_prices()
    judge = Judge(make_model(replace(settings, model=args.judge)), prices)
    online = args.metrics == "online"
    metrics = list(ANSWER_QUALITY) if online else args.metrics.split(",")
    evals = None
    if online and workspace.online:
        evals = OnlineEvals(
            make_model(replace(settings, model=args.online_judge)),
            prices,
            ids=workspace.online.ids or DEFAULT_IDS,
            style=workspace.online.style,
            workspace_metrics=workspace.metrics,
        )

    spent = 0.0
    rows: list[dict[str, Any]] = []
    wanted = [c for c in args.cases.split(",") if c]
    over = False
    for case_row in saved["cases"]:
        if over:
            break
        if wanted and case_row["id"] not in wanted:
            continue
        case = cases[case_row["id"]]
        for run in case_row["runs"]:
            if spent + judge.usd >= args.cap:
                print(f"Stopped: ${spent + judge.usd:.3f} of the ${args.cap:.2f} cap.")
                over = True
                break
            views = views_of(eval_dir, run)
            new: dict[str, Score] = {}
            if online and evals:
                views, usd = await online_again(views, evals)
                spent += usd
                new = {s.metric: s for s in quality_scores(views)}
            else:
                ran = [(n, v) for n, v in enumerate(views, 1) if v.loop_ran]
                for metric in metrics:
                    if metric not in run["metrics"]:
                        continue  # this metric didn't apply to this case
                    new[metric] = await one_metric(
                        metric,
                        case,
                        views,
                        ran,
                        len(views) > 1,
                        judge,
                        role.get(case.profile, ""),
                        topics,
                    )
            old = run["metrics"]
            merged = {k: dict(v) for k, v in old.items()}
            for k, s in new.items():
                merged[k] = s.to_dict()
            passed = all(
                v["passed"] for v in merged.values() if v.get("status", "scored") == "scored"
            )
            rows.append(
                {
                    "case": case.id,
                    "before": {k: old[k] for k in new if k in old},
                    "after": {k: s.to_dict() for k, s in new.items()},
                    "passed_before": run["passed"],
                    "passed_after": passed,
                }
            )

    def cell(m: dict[str, Any] | None) -> str:
        if not m:
            return "  —  "
        if m.get("status", "scored") != "scored":
            return " n/a "
        mark = "✓" if m["passed"] else "✗"
        return f"{mark}{m['score']:.2f}" if m.get("score") is not None else f"{mark}  —"

    print(f"\nRe-graded {args.eval_id} · {', '.join(metrics)} · {args.label}")
    for r in rows:
        changes = "  ".join(
            f"{k}: {cell(r['before'].get(k))} → {cell(r['after'].get(k))}" for k in r["after"]
        )
        word = {True: "pass", False: "fail"}
        verdict = f"{word[r['passed_before']]} → {word[r['passed_after']]}"
        print(f"  {r['case']:<20} {verdict:<12} {changes}")
    before = sum(r["passed_before"] for r in rows)
    after = sum(r["passed_after"] for r in rows)
    total = spent + judge.usd
    print(f"Cases passed: {before} → {after} of {len(rows)} · cost ${total:.3f}")
    out = FOLDER / "rescores" / f"{args.eval_id}-{time.strftime('%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "eval": args.eval_id,
                "metrics": metrics,
                "label": args.label,
                "usd": total,
                "rows": rows,
            },
            indent=1,
        )
    )
    print(f"Saved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
