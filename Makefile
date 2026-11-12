# One entry point for every routine task. CI runs `make check`, so local and CI never differ.
.DEFAULT_GOAL := help
.PHONY: help setup hooks format lint type test check live eval clean deploy-tour

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

deploy-tour: ## Host the read-only tour on Cloud Run (no key): make deploy-tour PROJECT=… HOSTS=…
	@test -n "$(PROJECT)" || { echo "Set PROJECT=<your Google Cloud project>"; exit 2; }
	@test -n "$(HOSTS)" || { echo "Set HOSTS=<names it answers to, comma-separated>"; exit 2; }
	gcloud run deploy $(SERVICE) --project $(PROJECT) --region $(REGION) --source . \
		--allow-unauthenticated --min-instances 0 --max-instances 1 \
		--memory 512Mi --cpu 1 --concurrency 20 --cpu-throttling --cpu-boost \
		--execution-environment gen2 \
		--set-env-vars '^;^HARNESS_PUBLIC=1;HARNESS_ALLOWED_HOSTS=$(HOSTS)'
