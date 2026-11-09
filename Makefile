# One entry point for every routine task. CI runs `make check`, so local and CI never differ.
.DEFAULT_GOAL := help
.PHONY: help setup hooks format lint type test check live clean

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
