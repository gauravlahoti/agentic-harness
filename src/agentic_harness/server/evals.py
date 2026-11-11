"""The page's Evals view: read saved results, and start or stop one eval (S10-AC9, AC10).

Harness part: the page. The evals live outside the harness (``evals/``, D-115): this file
never imports them. It does two things only:

- **reads** the result files the evals write (``<memory>/evals/<id>.json``) and the
  metric catalog (``evals/catalog.json``);
- **starts one fixed command**, ``python -m evals.run --json …``, the same way the Checks
  panel starts pytest. The page can pick cases (IDs only), runs (1 or 3) and a priced model,
  each checked here; it can never add a flag or a path. Its lines stream back as NDJSON.

An eval costs quota or money, so only one runs at a time, and Stop sends it SIGTERM: the
eval finishes the run it is on, saves what it has, and says "Stopped by you".

Does not: score anything, or know any workspace's cases.
"""

import asyncio
import json
import re
import sys
from collections.abc import AsyncIterator, Sequence
from pathlib import Path
from typing import Any

CASE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,59}$")
RESULT_ID = re.compile(r"^\d{8}-\d{6}-[0-9a-f]{6}$")
RUNS = (1, 3)
PLAN_SECONDS = 30.0  # the plan reads a TOML file; it never calls a model
LIMIT_SECONDS = 60 * 60.0  # a stuck eval must not hold the page forever
STOP_GRACE_SECONDS = 20.0  # after Stop, time to finish the current run and save
SUMMARY_KEYS = (
    "id",
    "started",
    "seconds",
    "status",
    "stop_reason",
    "model",
    "runs",
    "judge",
    "usd",
    "summary",
    "workspace",
)


class EvalError(ValueError):
    """A request the page should not have sent (bad case ID, runs, model)."""


def suite_path(project_root: Path, workspace: str) -> Path:
    """A workspace's golden cases: ``evals/cases/<workspace>.toml``."""
    return project_root / "evals" / "cases" / f"{workspace}.toml"


def catalog(project_root: Path) -> dict[str, Any] | None:
    path = project_root / "evals" / "catalog.json"
    if not path.is_file():
        return None
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def list_results(folder: Path) -> list[dict[str, Any]]:
    """Every saved eval, newest first, as a short summary."""
    rows = []
    for path in sorted(folder.glob("*.json"), reverse=True):
        if not RESULT_ID.match(path.stem):
            continue
        try:
            data = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            continue  # a half-written file is skipped, not an error page
        rows.append({k: data.get(k) for k in SUMMARY_KEYS})
    return rows


def read_result(folder: Path, eval_id: str) -> dict[str, Any] | None:
    if not RESULT_ID.match(eval_id):
        raise EvalError("Not an eval ID.")
    path = folder / f"{eval_id}.json"
    if not path.is_file():
        return None
    data: dict[str, Any] = json.loads(path.read_text())
    return data


def command(
    suite: Path,
    out: Path,
    *,
    cases: Sequence[str],
    runs: int,
    model: str,
    models: Sequence[str],
    plan: bool = False,
) -> list[str]:
    """The one command the page may start, with every input checked."""
    if runs not in RUNS:
        raise EvalError("Runs must be 1 or 3.")
    if model not in models:
        raise EvalError(f"No price for {model!r}; pick a model from the menu.")
    if bad := [c for c in cases if not CASE_ID.match(c)]:
        raise EvalError(f"Not a case ID: {bad[0]!r}.")
    args = [sys.executable, "-m", "evals.run", "--json", "--suite", str(suite), "--out", str(out)]
    args += ["--runs", str(runs), "--model", model]
    if cases:
        args += ["--cases", ",".join(cases)]
    if plan:
        args.append("--plan")
    return args


async def plan(project_root: Path, args: list[str]) -> dict[str, Any]:
    """What the eval would run and cost (the Run dialog); calls no model."""
    process = await asyncio.create_subprocess_exec(
        *args,
        cwd=project_root,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        async with asyncio.timeout(PLAN_SECONDS):
            out, _ = await process.communicate()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
    for raw in out.decode(errors="replace").splitlines():
        if raw.startswith("{"):
            event: dict[str, Any] = json.loads(raw)
            return event
    return {"type": "error", "message": out.decode(errors="replace")[-300:] or "No plan."}


class EvalProcess:
    """At most one eval at a time; Stop asks it to finish politely, then insists."""

    def __init__(self) -> None:
        self._process: asyncio.subprocess.Process | None = None

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def stop(self) -> bool:
        if not self.running or self._process is None:
            return False
        self._process.terminate()  # SIGTERM: the eval saves what it has (evals/run.py)
        return True

    async def stream(
        self, project_root: Path, args: list[str], limit_seconds: float = LIMIT_SECONDS
    ) -> AsyncIterator[dict[str, Any]]:
        """Start the eval and yield its JSON events, then ``exit``."""
        if self.running:
            raise EvalError("An eval is already running.")
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=project_root,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._process = process
        if process.stdout is None:  # can't happen with stdout=PIPE; says so to the type checker
            raise RuntimeError("eval started without an output pipe")
        try:
            async with asyncio.timeout(limit_seconds):
                async for raw in process.stdout:
                    text = raw.decode(errors="replace").strip()
                    if text.startswith("{"):
                        yield json.loads(text)
                code = await process.wait()
        except TimeoutError:
            yield {"type": "error", "message": f"Stopped: the eval ran over {limit_seconds:g} s."}
            return
        finally:
            if process.returncode is None:  # timed out, or the page went away mid-eval
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), STOP_GRACE_SECONDS)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            self._process = None
        yield {"type": "exit", "code": code}
