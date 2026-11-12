"""The FastAPI app behind the page (S00-AC13 to AC15, S01-AC13).

Harness part: the page. Serves the static page, a smoke status, the Checks
panel's test run, and the agent's run as a live event stream.

Security (D-20): answers only to the names 127.0.0.1 and localhost (blocks
DNS rebinding); actions need a custom header that other websites can't send
without our permission (blocks cross-site requests); strict browser headers.

Does not: bind the network address (the CLI does, always 127.0.0.1), or read secrets.
"""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

import agentic_harness
from agentic_harness import __version__
from agentic_harness.api import DEFAULT_TRACE_DIR, Off, create_harness, describe_harness
from agentic_harness.config import (
    CLAUDE_PREFIX,
    CLAUDE_SMALL_MODEL,
    MISSING_ANTHROPIC_KEY,
    MISSING_KEY_MESSAGE,
    Settings,
)
from agentic_harness.events import Event
from agentic_harness.limits import Limits
from agentic_harness.memory import (
    SessionStore,
    Turn,
    fallback_title,
    forget_note,
    list_notes,
    make_title,
    note_path,
)
from agentic_harness.model import ModelClient, make_model
from agentic_harness.pricing import PriceNotFoundError, load_prices
from agentic_harness.server.approvals import Approvals, WrongRoleError
from agentic_harness.server.checks import run_checks
from agentic_harness.server.evals import (
    EVAL_JUDGE,
    EvalError,
    EvalProcess,
    catalog,
    command,
    delete_result,
    list_results,
    plan,
    read_result,
    suite_path,
)
from agentic_harness.server.runs import stream_run
from agentic_harness.workspace import LOGO_TYPES, Workspace, WorkspaceError

WEB_DIR = Path(agentic_harness.__file__).parent / "web"
PROJECT_ROOT = Path(agentic_harness.__file__).resolve().parents[2]  # src/ layout → repo root

# Page actions send this header. A plain cross-site form or fetch can't add it without
# a CORS preflight, and this server allows no cross-origin requests.
PAGE_HEADER = {"X-Harness-Page": "1"}

SECURITY_HEADERS = {
    "Content-Security-Policy": (
        "default-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
    ),
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


Name = Annotated[str, Field(max_length=100)]  # one tool, skill or helper name


class OffRequest(BaseModel):
    """Names switched off in the Harness pane. Each must exist; nothing can be added (D-70)."""

    tools: list[Name] = Field(default_factory=list, max_length=100)
    skills: list[Name] = Field(default_factory=list, max_length=100)
    subagents: list[Name] = Field(default_factory=list, max_length=100)
    checks: list[Name] = Field(default_factory=list, max_length=100)


ONLINE_ROWS = 100  # the Online Evals page lists this many answers, newest first (D-148)
TITLE_WAIT_SECONDS = 3.0  # how long the end of a first turn waits for its topic title (D-91)


class ForgetFact(BaseModel):
    """The person removes one saved fact from the agent's long-term memory (D-101)."""

    profile: str | None = Field(default=None, max_length=50)
    line: str = Field(min_length=1, max_length=700)


class ApprovalAnswer(BaseModel):
    """A person's click on a ⏸ card: approve or reject one waiting tool call (D-79)."""

    call_id: str = Field(min_length=1, max_length=200)
    approved: bool
    note: str = Field(default="", max_length=500)
    person: str | None = Field(default=None, max_length=50)  # who is answering (D-137)


class EvalRequest(BaseModel):
    """The Run dialog's choices: case IDs, 1 or 3 runs, priced agent and judge models."""

    cases: list[Annotated[str, Field(max_length=60)]] = Field(default_factory=list, max_length=100)
    runs: Literal[1, 3] = 1
    model: str | None = Field(default=None, max_length=100)
    judge: str | None = Field(default=None, max_length=100)


class RunRequest(BaseModel):
    """What the page may send: a task, and optionally a model, profile and switches."""

    task: str = Field(min_length=1, max_length=4000)
    model: str | None = Field(default=None, max_length=100)  # must have a price (D-31)
    profile: str | None = Field(default=None, max_length=50)  # must be one of the workspace's
    effort: Literal["low", "medium", "high"] | None = None  # Gemini's thinking_level; None: default
    session: str | None = Field(default=None, max_length=60)  # continue this conversation
    person: str | None = Field(default=None, max_length=50)  # who picked "You Are" (D-166)
    off: OffRequest = Field(default_factory=OffRequest)


def create_app(
    settings: Settings,
    *,
    project_root: Path = PROJECT_ROOT,
    workspace: Workspace | None = None,
    trace_dir: Path = DEFAULT_TRACE_DIR,
    memory_dir: Path | None = None,
    model_factory: Callable[[Settings], ModelClient] = make_model,
) -> FastAPI:
    """Build the app. ``project_root`` is where the Checks panel runs the tests.

    ``model_factory`` builds the model for each run (Gemini). It is a parameter so the
    choice of client is visible in one place, not buried inside the route.
    """
    app = FastAPI(title="agentic-harness", version=__version__, docs_url=None, redoc_url=None)
    app.state.checks_running = False
    app.state.run_active = False
    approvals = Approvals()  # tool calls waiting for the person on the page
    app.state.approvals = approvals  # tests and tools may reach it
    # Claude shows only when its key is in .env: the person pays for it (D-104).
    priced_models = [
        m
        for m in load_prices().models()
        if not m.startswith(CLAUDE_PREFIX) or settings.has_anthropic_key
    ]
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        # Re-check page files on every load (a cheap 304 when unchanged); without it the
        # browser guesses a freshness time and runs an old app.js after an update.
        response.headers["Cache-Control"] = "no-cache"
        return response

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def page() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> FileResponse:
        # Browsers ask for this path on their own; answer instead of logging a 404.
        return FileResponse(WEB_DIR / "favicon.svg", media_type="image/svg+xml")

    memory_root = memory_dir or project_root / ".agentic-harness"
    sessions = SessionStore(memory_root, workspace.name if workspace else "_")

    def need_workspace() -> Workspace:
        if workspace is None:
            raise HTTPException(409, "No workspace loaded. Start with: serve --workspace PATH")
        return workspace

    def profile_of(value: str | None) -> str | None:
        try:
            return need_workspace().check_profile(value)
        except WorkspaceError as error:
            raise HTTPException(400, str(error)) from None

    @app.get("/api/sessions")
    async def list_sessions(profile: str | None = None) -> dict[str, object]:
        """The profile's conversations, newest first: the left pane's "Your work" (D-91)."""
        found = sessions.list(profile_of(profile))
        return {
            "sessions": [
                {"id": s.id, "title": s.title, "turns": s.turns, "updated": s.updated}
                for s in found
            ]
        }

    @app.get("/api/sessions/{session_id}")
    async def open_session(session_id: str, profile: str | None = None) -> dict[str, object]:
        try:
            session = sessions.load(session_id, profile_of(profile))
        except KeyError:
            raise HTTPException(404, "No such conversation.") from None
        return {
            "id": session.id,
            "title": session.title or "New Conversation",
            "turns": [
                {
                    "task": t.task,
                    "answer": t.answer,
                    "outcome": t.outcome,
                    "usd": t.usd,
                    "seconds": t.seconds,
                    "plan": t.plan,
                    "checks": t.checks,
                    "online": t.online,
                }
                for t in session.turns
            ],
        }

    @app.get("/api/online-evals")
    async def online_evals(profile: str | None = None) -> dict[str, object]:
        """Every scored answer of the profile's conversations, newest first (D-148): the
        Online Evals page. Read from the saved conversations, so it needs no other store."""
        rows = []
        for info in sessions.list(profile_of(profile)):
            session = sessions.load(info.id, profile_of(profile))
            for t in session.turns:
                if t.online:
                    rows.append(
                        {
                            "session": session.id,
                            "title": session.title or "New Conversation",
                            "task": t.task,
                            "at": t.at,
                            "run_id": t.run_id,
                            **t.online,
                        }
                    )
        rows.sort(key=lambda r: float(str(r["at"])), reverse=True)
        return {"answers": rows[:ONLINE_ROWS]}

    @app.delete("/api/sessions/{session_id}")
    async def delete_session(
        request: Request, session_id: str, profile: str | None = None
    ) -> dict[str, bool]:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        try:
            sessions.delete(session_id, profile_of(profile))
        except KeyError:
            raise HTTPException(404, "No such conversation.") from None
        return {"ok": True}

    @app.get("/api/facts")
    async def facts() -> dict[str, object]:
        """Long-term memory: the facts the agent saved, for every profile (S07, D-101)."""
        ws = need_workspace()
        profiles: list[tuple[str | None, str]] = [(p.id, p.label) for p in ws.profiles]
        profiles = profiles or [(None, "Everyone")]
        return {
            "on": ws.notes,
            "profiles": [
                {
                    "id": pid,
                    "label": label,
                    "facts": list_notes(note_path(memory_root, ws.name, pid)) if ws.notes else [],
                }
                for pid, label in profiles
            ],
        }

    @app.post("/api/facts/forget")
    async def forget(request: Request, body: ForgetFact) -> dict[str, bool]:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        ws = need_workspace()
        if not forget_note(note_path(memory_root, ws.name, profile_of(body.profile)), body.line):
            raise HTTPException(404, "That fact isn't saved.")
        return {"ok": True}

    @app.get("/api/workspace/logo")
    async def workspace_logo() -> FileResponse:
        """The workspace's logo, if it declares one. Read-only, and only that one file."""
        if workspace is None or not workspace.logo:
            raise HTTPException(404, "No logo.")
        file = workspace.path / workspace.logo
        return FileResponse(file, media_type=LOGO_TYPES[file.suffix.lower()])

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        # "missing" is not an error: offline work never needs the key (S00-AC12, AC15).
        return {
            "server": "up",
            "key": "present" if settings.has_key or settings.has_anthropic_key else "missing",
            "version": __version__,
            "model": settings.model,
            "models": priced_models,
            "efforts": ["low", "medium", "high"],
            # What a Claude run's helper, checks and titles use (D-103), for the Harness pane.
            "claude_small_model": CLAUDE_SMALL_MODEL if settings.has_anthropic_key else None,
            "workspace": None
            if workspace is None
            else {
                "name": workspace.name,
                "title": workspace.title,
                "owner": workspace.owner,
                "logo": bool(workspace.logo),
                "synthetic_data": workspace.synthetic_data,
                # Made-up people who can answer approvals, by role (D-137).
                "people": [{"id": p.id, "name": p.name, "role": p.role} for p in workspace.people],
                # One agent per workspace folder for now; the page lists them as a menu so a
                # company with several is one more entry, not a redesign.
                "agents": [
                    {
                        "id": workspace.name,
                        "name": workspace.title,
                        "description": workspace.description,
                    }
                ],
                "tools": [tool.name for tool in workspace.tools],
                "profiles": [{"id": p.id, "label": p.label} for p in workspace.profiles],
                "examples": list(workspace.examples),
            },
        }

    @app.get("/api/harness")
    async def harness_info(profile: str | None = None) -> dict[str, object]:
        """What a run for this profile gets: the page's Harness pane (D-67, D-68)."""
        if workspace is None:
            raise HTTPException(409, "No workspace loaded. Start with: serve --workspace PATH")
        try:
            # The limits a run gets, and what it remembers (S07).
            return describe_harness(workspace, profile, Limits(), memory_root)
        except WorkspaceError as error:
            raise HTTPException(400, str(error)) from None

    @app.post("/api/approval")
    async def approval(request: Request, body: ApprovalAnswer) -> dict[str, bool]:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        who, role = "", None
        if workspace is not None and workspace.people:
            # With people declared, an answer names one, and only that person's role counts.
            person = next((p for p in workspace.people if p.id == body.person), None)
            if person is None:
                raise HTTPException(400, "Say who you are before answering an approval.")
            who, role = f"{person.name} ({person.role})", person.role
        try:
            answered = approvals.answer(
                body.call_id, body.approved, body.note, person=who, role=role
            )
        except WrongRoleError as wrong:
            raise HTTPException(
                403, f"This one needs the {wrong}; you are {who}. Switch to the right person."
            ) from None
        if not answered:
            raise HTTPException(404, "Nothing is waiting for that approval.")
        return {"ok": True}

    @app.post("/api/checks")
    async def checks(request: Request) -> StreamingResponse:
        # No parameters and no body: the page can start the fixed command, nothing more.
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        if app.state.checks_running:
            raise HTTPException(409, "Checks are already running.")
        app.state.checks_running = True

        async def lines() -> AsyncIterator[str]:
            try:
                async for event in run_checks(project_root):
                    yield json.dumps(event) + "\n"  # NDJSON: one event per line
            finally:
                app.state.checks_running = False

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    # ── Evals (S10): read results; start or stop the one fixed eval command ──────────
    evals_folder = memory_root / "evals"
    evals = EvalProcess()

    def eval_suite() -> Path:
        if workspace is None:
            raise HTTPException(409, "No workspace loaded. Start with: serve --workspace PATH")
        suite = suite_path(project_root, workspace.name)
        if not suite.is_file():
            raise HTTPException(404, f"No eval cases for this agent ({suite.name}).")
        return suite

    @app.get("/api/evals")
    async def evals_index() -> dict[str, object]:
        has_cases = workspace is not None and suite_path(project_root, workspace.name).is_file()
        return {
            "results": list_results(evals_folder),
            "catalog": catalog(project_root),
            "running": evals.running,
            "has_cases": has_cases,
        }

    @app.get("/api/evals/plan")
    async def evals_plan(
        cases: str = "", runs: int = 1, model: str | None = None, judge: str | None = None
    ) -> dict[str, object]:
        try:
            args = command(
                eval_suite(),
                evals_folder,
                cases=[c for c in cases.split(",") if c][:100],
                runs=runs,
                model=model or settings.model,
                judge=judge or EVAL_JUDGE,
                models=priced_models,
                plan=True,
            )
        except EvalError as error:
            raise HTTPException(400, str(error)) from None
        return await plan(project_root, args)

    @app.get("/api/evals/follow")
    async def evals_follow() -> StreamingResponse:
        """A page that came back (a reload) follows the running eval from its start (D-119)."""
        if not evals.running:
            raise HTTPException(409, "No eval is running.")

        async def lines() -> AsyncIterator[str]:
            async for event in evals.follow():
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @app.get("/api/evals/{eval_id}")
    async def evals_result(eval_id: str) -> dict[str, object]:
        try:
            result = read_result(evals_folder, eval_id)
        except EvalError as error:
            raise HTTPException(400, str(error)) from None
        if result is None:
            raise HTTPException(404, "No such eval.")
        return result

    @app.post("/api/evals/run")
    async def evals_run(request: Request, body: EvalRequest) -> StreamingResponse:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        if evals.running:
            raise HTTPException(409, "An eval is already running.")
        try:
            args = command(
                eval_suite(),
                evals_folder,
                cases=body.cases,
                runs=body.runs,
                model=body.model or settings.model,
                judge=body.judge or EVAL_JUDGE,
                models=priced_models,
            )
        except EvalError as error:
            raise HTTPException(400, str(error)) from None

        async def lines() -> AsyncIterator[str]:
            async for event in evals.stream(project_root, args):
                yield json.dumps(event, ensure_ascii=False) + "\n"

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    @app.delete("/api/evals/{eval_id}")
    async def evals_delete(request: Request, eval_id: str) -> dict[str, bool]:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        try:
            gone = delete_result(evals_folder, eval_id)
        except EvalError as error:
            raise HTTPException(400, str(error)) from None
        if not gone:
            raise HTTPException(404, "No such eval.")
        return {"deleted": True}

    @app.post("/api/evals/stop")
    async def evals_stop(request: Request) -> dict[str, bool]:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        return {"stopping": evals.stop()}

    @app.post("/api/run")
    async def run(request: Request, body: RunRequest) -> StreamingResponse:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        if workspace is None:
            raise HTTPException(409, "No workspace loaded. Start with: serve --workspace PATH")
        if app.state.run_active:
            raise HTTPException(409, "A run is already going.")
        try:
            profile = workspace.check_profile(body.profile)
        except WorkspaceError as error:
            raise HTTPException(400, str(error)) from None
        person = next((p for p in workspace.people if p.id == body.person), None)
        if body.person and person is None:
            raise HTTPException(400, f"No person {body.person!r} in workspace.toml [[people]].")
        name = body.model or settings.model
        claude = name.startswith(CLAUDE_PREFIX)
        if claude and not settings.has_anthropic_key:
            raise HTTPException(400, MISSING_ANTHROPIC_KEY)
        if not claude and not settings.has_key and settings.backend == "gemini_api":
            raise HTTPException(400, MISSING_KEY_MESSAGE + " Then restart.")
        if name not in priced_models:
            raise HTTPException(400, f"Model {name!r} has no price in pricing.toml.")
        model = model_factory(replace(settings, model=name, thinking=body.effort))
        # Every key the run could touch is scrubbed from its trace.
        secrets = [k.reveal() for k in (settings.api_key, settings.anthropic_key) if k]
        small = CLAUDE_SMALL_MODEL if claude else None  # a Claude run's small calls (D-103)
        off = Off(
            tuple(body.off.tools),
            tuple(body.off.skills),
            tuple(body.off.subagents),
            tuple(body.off.checks),
        )
        try:
            harness = create_harness(
                model,
                Limits(),
                workspace,
                profile=profile,
                trace_dir=trace_dir,
                secrets=secrets,
                # A helper may name its own model (D-62); same settings, other name.
                model_factory=lambda helper: model_factory(
                    replace(settings, model=helper, thinking=body.effort)
                ),
                off=off,
                approver=approvals.ask,  # the page's ⏸ card answers (D-79)
                memory_dir=memory_root,
                small_model=small,
                person=person,  # the model knows who it's talking to (D-166)
            )
        except (WorkspaceError, PriceNotFoundError) as error:
            raise HTTPException(400, str(error)) from None
        # The conversation: continue the one asked for, or start a new one (S07, D-90).
        try:
            session = sessions.load(body.session, profile) if body.session else None
        except KeyError:
            raise HTTPException(404, "No such conversation.") from None
        fresh = session is None
        if session is None:
            session = sessions.create(profile)
            sessions.set_title(session.id, profile, fallback_title(body.task))
            session.title = fallback_title(body.task)
        elif session.repaired:
            sessions.append_steps(session.id, profile, session.repaired)  # settle it on disk
        history = list(session.steps)
        session_id = session.id

        def finished(event: Event) -> None:
            data = event.data
            if event.type == "online_evals_finished" and not data.get("agent_id"):
                sessions.save_scores(session_id, profile, event.run_id, dict(data))
            if event.type == "run_finished" and not data.get("agent_id"):
                sessions.finish_turn(
                    session_id,
                    profile,
                    Turn(
                        body.task,
                        str(data.get("answer", "")),
                        str(data.get("outcome", "")),
                        float(data.get("usd", 0.0)),
                        float(data.get("seconds", 0.0)),
                        event.run_id,
                        plan=data.get("plan"),
                        checks=data.get("checks"),
                    ),
                )

        harness.subscribe(finished)
        title_model = model_factory(
            replace(
                settings,
                model=small
                or workspace.title_model
                or (workspace.scope.model if workspace.scope and workspace.scope.model else name),
            )
        )
        mine = object()  # this run's hold on the page; released when its answer is in
        app.state.run_active = mine

        def release() -> None:
            if app.state.run_active is mine:  # a later run may already hold it
                app.state.run_active = False

        def note(type_: str, **data: object) -> str:
            event = Event(type_, run_id="", seq=0, time=0.0, data=data)
            return json.dumps(event.to_dict(), ensure_ascii=False) + "\n"

        async def lines() -> AsyncIterator[str]:
            titling = asyncio.create_task(make_title(title_model, body.task)) if fresh else None
            try:
                yield note("session_started", session_id=session_id, title=session.title, new=fresh)
                async for line in stream_run(
                    harness,
                    body.task,
                    history=history,
                    record=lambda steps: sessions.append_steps(session_id, profile, steps),
                ):
                    yield line
                    if '"run_finished"' in line and not json.loads(line)["data"].get("agent_id"):
                        release()  # the answer is in: online evals may still be scoring (D-148)
                if titling is not None:
                    try:
                        title = await asyncio.wait_for(titling, TITLE_WAIT_SECONDS)
                    except TimeoutError:
                        title = session.title  # the first words stay
                    if title and title != session.title:
                        sessions.set_title(session_id, profile, title)
                    yield note(
                        "session_titled", session_id=session_id, title=title or session.title
                    )
            finally:
                if titling is not None and not titling.done():
                    titling.cancel()
                release()

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    return app
