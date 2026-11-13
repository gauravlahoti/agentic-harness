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
# The evals package: the Golden Dataset page asks it for the plan (stdlib only, no DeepEval).
COPY evals/ evals/
# .agentic-harness/ is where a bucket is mounted when hosted (D-198): facts, chats, the judge
# switch and eval summaries live there and survive scale-to-zero. Seed it with `make seed-memory`.
RUN uv sync --frozen --no-default-groups \
    && useradd --system --uid 10001 harness \
    && mkdir -p .agentic-harness workspaces/cloudco/tasks workspaces/cloudco/outbox \
    && chown -R harness .agentic-harness workspaces/cloudco/tasks workspaces/cloudco/outbox

USER harness
# Public mode is baked in: this image can't start as a local, key-holding harness. Only an
# owner passphrase (HARNESS_OWNER_KEY) opens live Claude runs, and only for its holder (D-190).
# The run's own folders are the only places the app may write.
ENV PATH="/app/.venv/bin:$PATH" HARNESS_PUBLIC=1
CMD ["agentic-harness", "serve", "--workspace", "workspaces/cloudco"]
