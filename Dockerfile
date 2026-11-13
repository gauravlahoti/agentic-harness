# The hosted guided tour (S14, D-189): the harness in public tour mode. Read-only, no key.
# Built by `make deploy-tour`. Only what the tour needs goes in: no tests, evals or docs.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1

WORKDIR /app
# Dependencies first: they change less often than the code, so this layer stays cached.
COPY pyproject.toml uv.lock Readme.md ./
RUN uv sync --frozen --no-default-groups --no-install-project
COPY src/ src/
COPY workspaces/cloudco/ workspaces/cloudco/
# For the owner's Observability (D-196): the golden cases, their catalog and saved eval
# summaries (made-up CloudCo cases only; no traces, no chats).
COPY evals/catalog.json evals/catalog.json
COPY evals/cases/ evals/cases/
COPY .agentic-harness/evals/*.json .agentic-harness/evals/
# Also seeds the demo's long-term memory from the made-up facts (D-196), not anyone's notes.
RUN uv sync --frozen --no-default-groups \
    && useradd --system --uid 10001 harness \
    && mkdir -p .agentic-harness/notes/cloudco workspaces/cloudco/tasks workspaces/cloudco/outbox \
    && for p in sales engineering; do cp "workspaces/cloudco/demo-memory/$p.txt" ".agentic-harness/notes/cloudco/$p.md"; done \
    && chown -R harness .agentic-harness workspaces/cloudco/tasks workspaces/cloudco/outbox

USER harness
# Public mode is baked in: this image can't start as a local, key-holding harness. Only an
# owner passphrase (HARNESS_OWNER_KEY) opens live Claude runs, and only for its holder (D-190).
# The run's own folders are the only places the app may write.
ENV PATH="/app/.venv/bin:$PATH" HARNESS_PUBLIC=1
CMD ["agentic-harness", "serve", "--workspace", "workspaces/cloudco"]
