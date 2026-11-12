"""Run an eval: every case, N times, through the real harness; then score it (S10-AC2, AC6).

Part of the evals. For each run of each case:

1. **Run the agent** with ``create_harness``, exactly as the page does, with four
   differences:
   - a scripted approver answers each ⏸ from the case;
   - each run gets its own memory folder, so notes from one run never leak into another;
   - the runs aren't saved as conversations, so they never show in Your work;
   - the agent works in a copy of the workspace, so a draft or an approved "send" lands in
     the eval's folder, never in the real ``outbox/``.

   A conversation resends its history each turn, like the page.
2. **Read** each turn's saved trace (``evals/traces.py``).
3. **Score:** the code metrics, then the judged ones (``evals/scoring.py``).

A run passes when every metric that applies passes; a case passes only if all its runs pass
(pass^N, D-112).

**When Gemini runs out** (a 429 or 503), the agent moves to Claude Haiku for the rest of
the eval and the run that hit it starts again, if a Claude key is set (D-116). The judge does
the same on its own (D-111).

**The eval stops, with a named reason, when:**
- its own cap is spent;
- the agent's model is out of quota and nothing can take over;
- no judge can answer;
- the person presses Stop.

Whatever finished is kept.

``emit`` gets one small dict per step (eval started, run finished, …): the CLI prints them,
and the page streams them to fill its grid live.

Does not: write files (``evals/report.py`` does) or choose models (the caller does).
"""

import asyncio
import contextlib
import re
import secrets as random
import shutil
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

from agentic_harness.api import create_harness
from agentic_harness.config import CLAUDE_PREFIX, CLAUDE_SMALL_MODEL
from agentic_harness.gate import ApprovalRequest
from agentic_harness.limits import Limits
from agentic_harness.loop import Approver
from agentic_harness.model import ModelClient
from agentic_harness.workspace import Workspace
from evals.cases import Case, Suite
from evals.checks import Score
from evals.judge import BUSY, Judge, JudgeUnavailableError
from evals.plan import DEFAULT_CAP_USD, estimate
from evals.scoring import code_scores, decides, judged_scores
from evals.traces import RunView, read_run

ModelFactory = Callable[[str], ModelClient]
Emit = Callable[[dict[str, Any]], None]


@dataclass(frozen=True, slots=True)
class Options:
    model: str  # the agent's model
    cases: list[str] | None = None  # None: every case
    runs: int = 1
    max_usd: float = DEFAULT_CAP_USD
    fallback: str | None = None  # the agent's model when the first runs out (D-116)


@dataclass(slots=True)
class Tally:
    agent: str  # the agent's model now
    agent_usd: float = 0.0
    paid_usd: float = 0.0  # the agent's Claude runs: what the person pays for (D-104)
    switched: str = ""  # why the agent moved to the fallback, if it did
    stop: str = ""  # why the eval stopped early; "" while it runs
    started: float = field(default_factory=time.time)


RETRY = re.compile(r"retry in (\d[\dhms.]*)", re.IGNORECASE)


def out_of_quota(model: str, reason: str, fallback: str | None) -> str:
    """A stop reason in plain words; the raw error stays in the run's trace."""
    what = "busy" if "503" in reason else "out of quota"
    if model == fallback:
        return f"{model} is {what} too."
    when = f" (it resets in {m.group(1)})" if (m := RETRY.search(reason)) else ""
    return f"{model} is {what}{when}, and there's no Claude key to take over."


class StoppedError(Exception):
    """Stop was pressed while a test was in progress."""


async def unless_stopped[T](work: Awaitable[T], stop: asyncio.Event | None) -> T:
    """Wait for ``work``, unless Stop comes first: then cancel it (D-119).

    Stop used to be checked only between tests, so a hung judge call meant Stop did nothing.
    """
    task = asyncio.ensure_future(work)
    if stop is None:
        return await task
    stopped = asyncio.ensure_future(stop.wait())
    done, _ = await asyncio.wait({task, stopped}, return_when=asyncio.FIRST_COMPLETED)
    if task in done:
        stopped.cancel()
        return task.result()
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await task
    raise StoppedError


def metric_events(emit: Emit, case_id: str) -> Callable[[str, str, int, int], None]:
    """Tell the page as each judged metric starts and finishes (D-118)."""

    def tell(what: str, metric: str, index: int, of: int) -> None:
        emit(
            {"type": f"metric_{what}", "case": case_id, "metric": metric, "index": index, "of": of}
        )

    return tell


def scripted_approver(case: Case) -> Approver:
    """Answers every ⏸ from the case: its role's scripted decision, else reject."""

    async def approve(request: ApprovalRequest) -> tuple[bool, str]:
        if request.kind == "question":
            return False, "No one answers questions during an eval."
        if case.approvals.get(request.approver) == "approve":
            return True, ""
        return False, f"{request.approver or 'The approver'} rejected this (eval script)."

    return approve


def role_of(workspace: Workspace, profile: str) -> str:
    """Who the agent is for this profile: RoleAdherence checks it stays in this role."""
    label = next((p.label for p in workspace.profiles if p.id == profile), profile)
    name = workspace.title or workspace.name
    owner = f"{workspace.owner}'s " if workspace.owner else ""
    return f"{owner}{name}, working for the {label} team. {workspace.description}".strip()


def topics_of(workspace: Workspace) -> list[str]:
    """What the agent may talk about: TopicAdherence uses the workspace's own scope."""
    if workspace.scope:
        return [workspace.scope.covers]
    return [workspace.description or workspace.name]


async def run_case(
    case: Case,
    number: int,
    *,
    workspace: Workspace,
    model: str,
    factory: ModelFactory,
    folder: Path,
    secrets: Sequence[str] = (),
) -> list[RunView]:
    """One run of one case, every turn, through the same harness as the page (S10-AC2)."""
    claude = model.startswith(CLAUDE_PREFIX)
    history: list[Any] = []
    views: list[RunView] = []
    for task in case.turns:
        harness = create_harness(
            factory(model),
            Limits(),
            workspace,
            profile=case.profile,
            trace_dir=folder / "traces",
            secrets=secrets,
            model_factory=factory,
            small_model=CLAUDE_SMALL_MODEL if claude else None,  # D-103
            approver=scripted_approver(case),
            memory_dir=folder / "memory" / f"{case.id}-{number}",  # notes stay in this run
        )
        result = await harness.run(task, history=history)
        history = list(result.steps)  # the next turn resends the conversation
        views.append(read_run(folder / "traces" / f"{result.run_id}.jsonl"))
    return views


def turn_record(view: RunView) -> dict[str, Any]:
    return {
        "task": view.task,
        "answer": view.answer,
        "outcome": view.outcome,
        "reason": view.reason,
        "run_id": view.run_id,
        "model_calls": view.model_calls,
        "usd": round(view.usd, 6),
        "seconds": view.seconds,
        "tokens_in": view.tokens_in,
        "tokens_out": view.tokens_out,
        "replies": view.replies,
        "scope": None if view.scope_in is None else ("in" if view.scope_in else "out"),
        "tools": [
            {
                "name": t.name,
                "arguments": t.arguments,
                "agent": t.agent,
                "ok": t.completed,
                "blocked": t.blocked,
                "approvals": list(t.approvals),
                "flagged": t.flagged,
            }
            for t in view.tools
        ],
    }


RUN_OUTPUT = ("outbox", "tasks", "__pycache__", ".*")  # what a run writes; not copied


def copy_workspace(source: Path, folder: Path) -> Path:
    """The workspace's files (config, tools, data, skills) without anything runs wrote."""
    target = folder / "workspace"
    shutil.copytree(source, target, ignore=shutil.ignore_patterns(*RUN_OUTPUT), dirs_exist_ok=True)
    return target


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + random.token_hex(3)


async def run_eval(
    suite: Suite,
    options: Options,
    *,
    factory: ModelFactory,
    judge: Judge,
    folder: Path,
    emit: Emit = lambda event: None,
    stop: asyncio.Event | None = None,
    secrets: Sequence[str] = (),
    eval_id: str | None = None,
) -> dict[str, Any]:
    """Run and score every picked case ``options.runs`` times; return the result (a dict)."""
    cases = suite.pick(options.cases)
    eval_id = eval_id or new_id()
    workspace = Workspace.load(copy_workspace(suite.workspace, folder / eval_id))
    tally = Tally(agent=options.model)
    role = {p.id: role_of(workspace, p.id) for p in workspace.profiles}
    topics = topics_of(workspace)
    emit(
        {
            "type": "eval_started",
            "id": eval_id,
            "cases": [
                {
                    "id": c.id,
                    "group": c.group,
                    "profile": c.profile,
                    "turns": len(c.turns),
                    "ask": c.turns[0],  # the page shows the question, not just the ID
                }
                for c in cases
            ],
            "runs": options.runs,
            "model": options.model,
            "judge": judge.current,
            "cap_usd": options.max_usd,
            "estimate": estimate(cases, options.runs),
        }
    )
    results: dict[str, list[dict[str, Any]]] = {c.id: [] for c in cases}

    def spent() -> float:
        return tally.agent_usd + judge.usd

    for case in cases:
        number = 1
        while number <= options.runs:
            if stop is not None and stop.is_set():
                tally.stop = "Stopped by you."
            elif spent() >= options.max_usd:
                tally.stop = f"Budget: ${spent():.2f} of the ${options.max_usd:.2f} cap spent."
            if tally.stop:
                break
            emit({"type": "run_started", "case": case.id, "run": number})
            began = time.time()
            try:
                views = await unless_stopped(
                    run_case(
                        case,
                        number,
                        workspace=workspace,
                        model=tally.agent,
                        factory=factory,
                        folder=folder / eval_id,
                        secrets=secrets,
                    ),
                    stop,
                )
            except StoppedError:
                tally.stop = "Stopped by you."
                break
            emit(
                {
                    "type": "agent_finished",
                    "case": case.id,
                    "run": number,
                    "seconds": round(time.time() - began, 1),
                    "tools": [t.name for v in views for t in v.tools],
                    "usd": round(sum(v.usd for v in views), 6),
                }
            )
            tally.agent_usd += sum(v.usd for v in views)
            if tally.agent.startswith(CLAUDE_PREFIX):
                tally.paid_usd += sum(v.usd for v in views)
            scores: list[Score] = code_scores(case, views)
            failed = next((v for v in views if v.outcome == "failed"), None)
            if failed and BUSY.search(failed.reason):
                if options.fallback and tally.agent != options.fallback:
                    # Same run again on the fallback; the half-run never counts (D-116).
                    what = "busy" if "503" in failed.reason else "out of quota"
                    tally.switched = f"{tally.agent} → {options.fallback}: {tally.agent} was {what}"
                    emit({"type": "agent_switched", "from": tally.agent, "to": options.fallback})
                    tally.agent = options.fallback
                    continue
                tally.stop = out_of_quota(tally.agent, failed.reason, options.fallback)
            else:
                try:
                    scores += await unless_stopped(
                        judged_scores(
                            case,
                            views,
                            judge,
                            role=role.get(case.profile, ""),
                            topics=topics,
                            progress=metric_events(emit, case.id),
                        ),
                        stop,
                    )
                except JudgeUnavailableError as error:
                    tally.stop = str(error)
                except StoppedError:
                    tally.stop = "Stopped by you."
            record: dict[str, Any] = {
                "run": number,
                "model": tally.agent,
                # Not Scored / Not Applicable never fail a run (D-118)
                # Reported-only metrics show their score but never fail a run (D-158).
                "passed": not tally.stop
                and all(s.passed for s in scores if s.counted and decides(s.metric)),
                "complete": not tally.stop,
                "turns": [turn_record(v) for v in views],
                "metrics": {s.metric: s.to_dict() for s in scores},
                "usd": round(sum(v.usd for v in views) + sum(s.usd for s in scores), 6),
                "seconds": round(time.time() - began, 1),  # agent + judging (D-118)
            }
            results[case.id].append(record)
            emit(
                {
                    "type": "run_finished",
                    "case": case.id,
                    "run": number,
                    "passed": record["passed"],
                    "metrics": {
                        k: {"score": v["score"], "passed": v["passed"], "status": v["status"]}
                        for k, v in record["metrics"].items()
                    },
                    "seconds": record["seconds"],
                    "usd": record["usd"],
                    "spent_usd": round(spent(), 6),
                    "paid_usd": round(paid(tally, judge), 6),
                    "judge": judge.current,  # the page shows when the judge moves to Claude
                }
            )
            if tally.stop:
                break
            number += 1
        if tally.stop:
            break

    result = build_result(eval_id, suite, workspace, cases, results, options, judge, tally)
    emit(
        {
            "type": "eval_finished",
            "id": eval_id,
            "status": result["status"],
            "stop_reason": result["stop_reason"],
            "summary": result["summary"],
            "usd": result["usd"],
        }
    )
    return result


def build_result(
    eval_id: str,
    suite: Suite,
    workspace: Workspace,
    cases: Sequence[Case],
    results: dict[str, list[dict[str, Any]]],
    options: Options,
    judge: Judge,
    tally: Tally,
) -> dict[str, Any]:
    case_rows = []
    for case in cases:
        runs = results[case.id]
        complete = [r for r in runs if r["complete"]]
        if len(complete) < options.runs:
            status = "failed" if any(not r["passed"] for r in complete) else "incomplete"
        else:
            status = "passed" if all(r["passed"] for r in complete) else "failed"
        case_rows.append(
            {
                "id": case.id,
                "group": case.group,
                "profile": case.profile,
                "turns": list(case.turns),
                "expected_outcome": case.expected_outcome,
                "multi_turn": case.multi_turn,
                "status": status,
                "runs": runs,
                "metrics": metric_means(runs),
            }
        )
    every = [r for runs in results.values() for r in runs]
    judge_usd = judge.usd
    return {
        "id": eval_id,
        "suite": suite.path.name,
        "workspace": workspace.title or workspace.name,
        "started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(tally.started)),
        "seconds": round(time.time() - tally.started, 1),
        "status": "stopped" if tally.stop else "finished",
        "stop_reason": tally.stop,
        "model": options.model,
        "agent": {"first": options.model, "now": tally.agent, "switched": tally.switched},
        "runs": options.runs,
        "cap_usd": options.max_usd,
        "judge": {
            "first": judge.first,
            "now": judge.current,
            "switched": judge.switched,
            "calls": judge.calls,
            "tokens_in": judge.tokens_in,
            "tokens_out": judge.tokens_out,
        },
        "usd": {
            "agent": round(tally.agent_usd, 6),
            "judge": round(judge_usd, 6),
            "total": round(tally.agent_usd + judge_usd, 6),
            "paid": round(paid(tally, judge), 6),  # Claude's part; Gemini's free tier bills $0
        },
        "summary": {
            "cases": len(cases),
            "passed": sum(r["status"] == "passed" for r in case_rows),
            "failed": sum(r["status"] == "failed" for r in case_rows),
            "incomplete": sum(r["status"] == "incomplete" for r in case_rows),
        },
        "metrics": metric_means(every),
        "cases": case_rows,
    }


def paid(tally: Tally, judge: Judge) -> float:
    """What Claude cost (agent and judge); the rest ran on Gemini."""
    judged = sum(usd for name, usd in judge.by_model.items() if name.startswith(CLAUDE_PREFIX))
    return tally.paid_usd + judged


def metric_means(runs: Sequence[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per metric: the mean score and how many of its runs passed."""
    table: dict[str, list[dict[str, Any]]] = {}
    for run in runs:
        for metric, score in run["metrics"].items():
            if score.get("status", "scored") == "scored":  # only real scores count (D-118)
                table.setdefault(metric, []).append(score)
    return {
        metric: {
            "score": round(mean(numbers), 3)
            if (numbers := [s["score"] for s in scores if s["score"] is not None])
            else None,
            "passed": sum(bool(s["passed"]) for s in scores),
            "runs": len(scores),
        }
        for metric, scores in table.items()
    }
