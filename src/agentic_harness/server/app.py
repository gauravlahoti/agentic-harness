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

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

import agentic_harness
from agentic_harness import __version__
from agentic_harness.api import DEFAULT_TRACE_DIR, create_harness
from agentic_harness.config import MISSING_KEY_MESSAGE, Settings
from agentic_harness.limits import Limits
from agentic_harness.model import GeminiModel, ModelClient
from agentic_harness.pricing import load_prices
from agentic_harness.server.checks import run_checks
from agentic_harness.server.runs import stream_run
from agentic_harness.workspace import Workspace

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


class RunRequest(BaseModel):
    """What the page may send: a task and, optionally, a model. Nothing else."""

    task: str = Field(min_length=1, max_length=4000)
    model: str | None = Field(default=None, max_length=100)  # must have a price (D-31)


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
    priced_models = load_prices().models()
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])

    @app.middleware("http")
    async def add_security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers.update(SECURITY_HEADERS)
        return response

    app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def page() -> FileResponse:
        return FileResponse(WEB_DIR / "index.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> FileResponse:
        # Browsers ask for this path on their own; answer instead of logging a 404.
        return FileResponse(WEB_DIR / "favicon.svg", media_type="image/svg+xml")

    @app.get("/api/health")
    async def health() -> dict[str, object]:
        # "missing" is not an error: offline work never needs the key (S00-AC12, AC15).
        return {
            "server": "up",
            "key": "present" if settings.has_key else "missing",
            "version": __version__,
            "model": settings.model,
            "models": priced_models,
            "workspace": None
            if workspace is None
            else {
                "name": workspace.name,
                "tools": [tool.name for tool in workspace.tools],
            },
        }

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
        if not settings.has_key and settings.backend == "gemini_api":
            raise HTTPException(400, MISSING_KEY_MESSAGE + " Then restart.")
        name = body.model or settings.model
        if name not in priced_models:
            raise HTTPException(400, f"Model {name!r} has no price in pricing.toml.")
        model = model_factory(replace(settings, model=name))
        secrets = [settings.api_key.reveal()] if settings.api_key else []
        harness = create_harness(model, Limits(), workspace, trace_dir=trace_dir, secrets=secrets)
        app.state.run_active = True

        async def lines() -> AsyncIterator[str]:
            try:
                async for line in stream_run(harness, body.task):
                    yield line
            finally:
                app.state.run_active = False

        return StreamingResponse(lines(), media_type="application/x-ndjson")

    return app
