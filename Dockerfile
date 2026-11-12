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
RUN uv sync --frozen --no-default-groups \
    && useradd --system --uid 10001 harness \
    && mkdir .agentic-harness && chown harness .agentic-harness

USER harness
# Public mode is baked in: this image can't start as a local, key-holding harness.
ENV PATH="/app/.venv/bin:$PATH" HARNESS_PUBLIC=1
CMD ["agentic-harness", "serve", "--workspace", "workspaces/cloudco"]
