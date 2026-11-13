# One entry point for every routine task. CI runs `make check`, so local and CI never differ.
.DEFAULT_GOAL := help
.PHONY: help setup hooks format lint type test check live eval clean deploy-tour seed-memory

help: ## Show the commands
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "} {printf "  make %-7s %s\n", $$1, $$2}'

setup: ## Install everything, exactly as locked in uv.lock
	uv sync --locked

hooks: ## Install the git pre-commit hooks (run once)
	uv run pre-commit install

format: ## Auto-fix formatting and simple lint issues
	uv run ruff format .
	uv run ruff check --fix .

lint: ## Lint and check formatting (no changes)
	uv run ruff check .
	uv run ruff format --check .

type: ## Strict type check
	uv run mypy

test: ## Offline tests + coverage (free, no API key)
	uv run pytest --cov --cov-report=term-missing

check: lint type test ## Everything CI runs

live: ## Tests against real Gemini (needs a key in .env, costs cents)
	uv run pytest -m live

clean: ## Remove caches and coverage files
	rm -rf .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov

eval: ## Run the evals (🔑 spends quota or money): make eval CASES=off-topic RUNS=1
	uv run python -m evals.run $(if $(CASES),--cases $(CASES),) --runs $(or $(RUNS),1)

# The hosted guided tour (S14, D-189). Your own project and names, given on the command line.
PROJECT ?=
REGION ?= us-central1
SERVICE ?= agentic-harness
HOSTS ?=
# Owner unlock (D-190), optional: Secret Manager names for Claude's key and the passphrase.
CLAUDE_SECRET ?=
OWNER_SECRET ?=
# Persistent memory (D-198), optional: a bucket mounted at .agentic-harness/ (facts, chats, judge).
MEMORY_BUCKET ?=
# The service runs as its own account: the two secrets and the memory bucket only (D-199).
RUN_SA ?=
RUN_SA_FLAGS = $(if $(RUN_SA),--service-account $(RUN_SA))
MEMORY_FLAGS = $(if $(MEMORY_BUCKET),--add-volume 'name=memory$(,)type=cloud-storage$(,)bucket=$(MEMORY_BUCKET)$(,)mount-options=uid=10001;gid=10001' --add-volume-mount 'volume=memory$(,)mount-path=/app/.agentic-harness')
OWNER_FLAGS = $(if $(and $(CLAUDE_SECRET),$(OWNER_SECRET)),--update-secrets ANTHROPIC_API_KEY=$(CLAUDE_SECRET):latest$(,)HARNESS_OWNER_KEY=$(OWNER_SECRET):latest)
, := ,

deploy-tour: ## Host the tour on Cloud Run: make deploy-tour PROJECT=… HOSTS=… [CLAUDE_SECRET=… OWNER_SECRET=… MEMORY_BUCKET=… RUN_SA=…]
	@test -n "$(PROJECT)" || { echo "Set PROJECT=<your Google Cloud project>"; exit 2; }
	@test -n "$(HOSTS)" || { echo "Set HOSTS=<names it answers to, comma-separated>"; exit 2; }
	gcloud run deploy $(SERVICE) --project $(PROJECT) --region $(REGION) --source . \
		--allow-unauthenticated --min-instances 0 --max-instances 1 \
		--memory 512Mi --cpu 1 --concurrency 20 --cpu-throttling --cpu-boost \
		--execution-environment gen2 --timeout 3600 \
		--set-env-vars '^;^HARNESS_PUBLIC=1;HARNESS_ALLOWED_HOSTS=$(HOSTS)' $(OWNER_FLAGS) $(MEMORY_FLAGS) $(RUN_SA_FLAGS)

seed-memory: ## Seed the memory bucket once (made-up facts, eval summaries): make seed-memory MEMORY_BUCKET=…
	@test -n "$(MEMORY_BUCKET)" || { echo "Set MEMORY_BUCKET=<bucket>"; exit 2; }
	for p in sales engineering; do gcloud storage cp --no-clobber workspaces/cloudco/demo-memory/$$p.txt gs://$(MEMORY_BUCKET)/notes/cloudco/$$p.md; done
	gcloud storage cp --no-clobber '.agentic-harness/evals/*.json' gs://$(MEMORY_BUCKET)/evals/
