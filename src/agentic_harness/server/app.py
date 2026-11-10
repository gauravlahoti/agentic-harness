"""The FastAPI app behind the page (S00-AC13 to AC15, S01-AC13).

Harness part: the page. Serves the static page, a smoke status, the Checks
panel's test run, and the agent's run as a live event stream.

Security (D-20): answers only to the names 127.0.0.1 and localhost (blocks
DNS rebinding); actions need a custom header that other websites can't send
without our permission (blocks cross-site requests); strict browser headers.

Does not: bind the network address (the CLI does, always 127.0.0.1), or read secrets.
"""

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
from agentic_harness.config import MISSING_KEY_MESSAGE, Settings
from agentic_harness.limits import Limits
from agentic_harness.model import GeminiModel, ModelClient
from agentic_harness.pricing import PriceNotFoundError, load_prices
from agentic_harness.server.approvals import Approvals
from agentic_harness.server.checks import run_checks
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


class ApprovalAnswer(BaseModel):
    """A person's click on a ⏸ card: approve or reject one waiting tool call (D-79)."""

    call_id: str = Field(min_length=1, max_length=200)
    approved: bool
    note: str = Field(default="", max_length=500)


class RunRequest(BaseModel):
    """What the page may send: a task, and optionally a model, profile and switches."""

    task: str = Field(min_length=1, max_length=4000)
    model: str | None = Field(default=None, max_length=100)  # must have a price (D-31)
    profile: str | None = Field(default=None, max_length=50)  # must be one of the workspace's
    effort: Literal["low", "medium", "high"] | None = None  # Gemini's thinking_level; None: default
    off: OffRequest = Field(default_factory=OffRequest)


def create_app(
    settings: Settings,
    *,
    project_root: Path = PROJECT_ROOT,
    workspace: Workspace | None = None,
    trace_dir: Path = DEFAULT_TRACE_DIR,
    model_factory: Callable[[Settings], ModelClient] = GeminiModel,
) -> FastAPI:
    """Build the app. ``project_root`` is where the Checks panel runs the tests.

    ``model_factory`` builds the model for each run (Gemini). It is a parameter so the
    choice of client is visible in one place, not buried inside the route.
    """
    app = FastAPI(title="agentic-harness", version=__version__, docs_url=None, redoc_url=None)
    app.state.checks_running = False
    app.state.run_active = False
    approvals = Approvals()  # tool calls waiting for the person on the page
    priced_models = load_prices().models()
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
            "key": "present" if settings.has_key else "missing",
            "version": __version__,
            "model": settings.model,
            "models": priced_models,
            "efforts": ["low", "medium", "high"],
            "workspace": None
            if workspace is None
            else {
                "name": workspace.name,
                "title": workspace.title,
                "owner": workspace.owner,
                "logo": bool(workspace.logo),
                # One agent per workspace folder for now; the page lists them as a menu so a
                # company with several is one more entry, not a redesign.
                "agents": [{"id": workspace.name, "name": workspace.title}],
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
            return describe_harness(workspace, profile, Limits())  # the limits a run gets
        except WorkspaceError as error:
            raise HTTPException(400, str(error)) from None

    @app.post("/api/approval")
    async def approval(request: Request, body: ApprovalAnswer) -> dict[str, bool]:
        if request.headers.get("x-harness-page") != "1":
            raise HTTPException(403, "Page actions must come from the harness page.")
        if not approvals.answer(body.call_id, body.approved, body.note):
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
        if not settings.has_key and settings.backend == "gemini_api":
            raise HTTPException(400, MISSING_KEY_MESSAGE + " Then restart.")
        name = body.model or settings.model
        if name not in priced_models:
            raise HTTPException(400, f"Model {name!r} has no price in pricing.toml.")
        model = model_factory(replace(settings, model=name, thinking=body.effort))
        secrets = [settings.api_key.reveal()] if settings.api_key else []
        off = Off(tuple(body.off.tools), tuple(body.off.skills), tuple(body.off.subagents))
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
            )
        except (WorkspaceError, PriceNotFoundError) as error:
            raise HTTPException(400, str(error)) from None
        app.state.run_active = True

        async def lines() -> AsyncIterator[str]:
            try:
                async for line in stream_run(harness, body.task):
                    yield line
            finally:
                app.state.run_active = False

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    return app
