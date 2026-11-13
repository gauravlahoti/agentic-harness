"""The page's Evals view: read saved results, and start or stop one eval (S10-AC9, AC10).

Harness part: the page. The evals live outside the harness (``evals/``, D-115): this file
never imports them. It does two things only:

- **reads** the result files the evals write (``<memory>/evals/<id>.json``) and the
  metric catalog (``evals/catalog.json``);
- **starts one fixed command**, ``python -m evals.run --json …``, the same way the Checks
  panel starts pytest. The page can pick cases (IDs only), runs (1 or 3), and a priced model
  for the agent and for the judge, each checked here; it can never add a flag or a path.
  Its lines stream back as NDJSON.

An eval costs quota or money, so only one runs at a time, and Stop sends it SIGTERM: the
eval finishes the run it is on, saves what it has, and says "Stopped by you".

Does not: score anything, or know any workspace's cases.
"""

import asyncio
import contextlib
import json
import re
import shutil
import sys
from collections.abc import AsyncIterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from agentic_harness.config import EVAL_JUDGE_MODEL

EVAL_JUDGE = EVAL_JUDGE_MODEL  # the judge when the page picks none (D-111)

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


def delete_result(folder: Path, eval_id: str) -> bool:
    """Remove one saved eval: its result file and its working folder. False if none."""
    if not RESULT_ID.match(eval_id):  # an ID, never a path: nothing outside the folder
        raise EvalError("Not an eval ID.")
    path, work = folder / f"{eval_id}.json", folder / eval_id
    if not path.is_file():
        return False
    path.unlink()
    if work.is_dir():
        shutil.rmtree(work)  # that eval's copy of the workspace and its traces
    return True


def command(
    suite: Path,
    out: Path,
    *,
    cases: Sequence[str],
    runs: int,
    model: str,
    judge: str,
    models: Sequence[str],
    plan: bool = False,
) -> list[str]:
    """The one command the page may start, with every input checked."""
    if runs not in RUNS:
        raise EvalError("Runs must be 1 or 3.")
    for picked in (model, judge):
        if picked not in models:
            raise EvalError(f"No price for {picked!r}; pick a model from the menu.")
    if bad := [c for c in cases if not CASE_ID.match(c)]:
        raise EvalError(f"Not a case ID: {bad[0]!r}.")
    args = [sys.executable, "-m", "evals.run", "--json", "--suite", str(suite), "--out", str(out)]
    args += ["--runs", str(runs), "--model", model, "--judge", judge]
    if cases:
        args += ["--cases", ",".join(cases)]
    if plan:
        args.append("--plan")
    return args


# An owner's eval on a hosted copy runs with the Claude key (D-213). The eval is its own
# process: with HARNESS_PUBLIC it would count no key at all. The passphrase stays behind.
HOSTED_ONLY = ("HARNESS_PUBLIC", "HARNESS_OWNER_KEY")


def eval_env(environ: Mapping[str, str], *, owner: bool) -> dict[str, str] | None:
    """The eval process's environment: the owner's without the hosted switches, else None
    (inherit the server's, unchanged)."""
    if not owner:
        return None
    return {k: v for k, v in environ.items() if k not in HOSTED_ONLY}


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
    """At most one eval at a time, read by the server itself; pages follow it (D-119).

    The eval used to be read only while the page that started it kept listening. A reload
    left it unwatched (no Stop, no progress), and Stop only asked it politely. Now:

    - ``start`` launches the eval and a reader that keeps every event, watched or not;
    - ``follow`` replays the events so far and then the new ones, so any page (a reloaded
      one too) shows the whole run;
    - ``stop`` asks the eval to stop (SIGTERM: it saves what finished) and, if it hasn't
      ended within ``stop_grace_seconds``, ends it.
    """

    def __init__(
        self,
        limit_seconds: float = LIMIT_SECONDS,
        stop_grace_seconds: float = STOP_GRACE_SECONDS,
    ) -> None:
        self._process: asyncio.subprocess.Process | None = None
        self._events: list[dict[str, Any]] = []
        self._changed = asyncio.Event()
        self._done = True
        self._limit = limit_seconds
        self._grace = stop_grace_seconds
        self._reader: asyncio.Task[None] | None = None

    @property
    def running(self) -> bool:
        return not self._done

    async def start(
        self, project_root: Path, args: list[str], env: dict[str, str] | None = None
    ) -> None:
        if self.running:
            raise EvalError("An eval is already running.")
        process = await asyncio.create_subprocess_exec(
            *args,
            cwd=project_root,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        self._process, self._events, self._done = process, [], False
        self._reader = asyncio.create_task(self._read(process))

    def _add(self, event: dict[str, Any]) -> None:
        self._events.append(event)
        self._changed.set()  # wake every follower
        self._changed = asyncio.Event()

    async def _read(self, process: asyncio.subprocess.Process) -> None:
        """Keep every JSON line the eval prints, until it ends (or runs over its limit)."""
        if process.stdout is None:  # can't happen with stdout=PIPE; says so to the type checker
            raise RuntimeError("eval started without an output pipe")
        try:
            async with asyncio.timeout(self._limit):
                async for raw in process.stdout:
                    text = raw.decode(errors="replace").strip()
                    if text.startswith("{"):
                        with contextlib.suppress(json.JSONDecodeError):
                            self._add(json.loads(text))
                code = await process.wait()
        except TimeoutError:
            self._add(
                {"type": "error", "message": f"Stopped: the eval ran over {self._limit:g} s."}
            )
            await self._end(process)
            code = process.returncode if process.returncode is not None else -9
        self._done = True
        self._add({"type": "exit", "code": code})

    async def _end(self, process: asyncio.subprocess.Process) -> None:
        """SIGTERM; if it's still there after the grace period, kill it."""
        if process.returncode is not None:
            return
        process.terminate()
        try:
            await asyncio.wait_for(process.wait(), self._grace)
        except TimeoutError:
            process.kill()
            await process.wait()

    def stop(self) -> bool:
        if not self.running or self._process is None:
            return False
        asyncio.get_running_loop().create_task(self._end(self._process))
        return True

    async def follow(self) -> AsyncIterator[dict[str, Any]]:
        """Every event of the current (or last) eval from the start, then new ones, to ``exit``."""
        seen = 0
        while True:
            changed = self._changed
            while seen < len(self._events):
                event = self._events[seen]
                seen += 1
                yield event
                if event.get("type") == "exit":
                    return
            if self._done and seen >= len(self._events):
                return
            await changed.wait()

    async def stream(
        self, project_root: Path, args: list[str], env: dict[str, str] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Start the eval and follow it (what the Run button does)."""
        await self.start(project_root, args, env)
        async for event in self.follow():
            yield event
