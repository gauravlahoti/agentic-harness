# S00 · Scaffold and setup

> **Goal:** a production-grade, empty-but-safe project. One command each to install, check, and open the page.
> **Why it matters:** everything builds on this. Quality gates and secret handling are far cheaper on day one than retrofitted.

**Part A: Scaffold** (production baseline, recorded in [`Scaffold.md`](../../Scaffold.md))
**Part B: Setup** (secrets loader, local server, page shell, Checks panel)
**Not yet:** Gemini calls, the loop, workspaces

## Done when

| ID | Check | How |
|---|---|---|
| S00-AC1 | A fresh copy: `make setup` installs exactly what `uv.lock` says; `make check` passes offline | 🧪 |
| S00-AC2 | `src/` layout, typed package `agentic_harness`; `agentic-harness --version` works | 🧪 |
| S00-AC3 | Quality gates: ruff lint + format, mypy strict, pytest with coverage ≥ 85% | 🧪 |
| S00-AC4 | Naming: no ALL-CAPS file names (except `CLAUDE.md`, `AGENTS.md`, `SKILL.md`); folders and Python files lowercase | 🧪 |
| S00-AC5 | Domain-free harness: no workspace words in `src/agentic_harness/` | 🧪 |
| S00-AC6 | CI runs `make check` + a full-history secret scan, with a read-only token | 📄 |
| S00-AC7 | Pre-commit runs file hygiene, gitleaks, ruff and mypy at the locked versions | 📄 |
| S00-AC8 | Repo documents: Readme, Scaffold, Decisions, Tracker, Security, Contributing, Changelog | 📄 |
| S00-AC9 | Runtime packages are only `google-genai`, `fastapi`, `uvicorn`, `python-dotenv` | 📄 |
| S00-AC10 | `.env` is ignored by git; `.env.example` has the names, no values | 🧪 📄 |
| S00-AC11 | Only `config.py` loads the key; printing it shows `***` | 🧪 |
| S00-AC12 | No key? Everything offline still works | 🧪 |
| S00-AC13 | `agentic-harness serve` listens on `127.0.0.1:8000` only and serves the page shell | 🧪 👀 |
| S00-AC14 | Checks panel runs one fixed test command, one row per test, live | 🧪 👀 |
| S00-AC15 | Smoke row: server up ✓ · key present ✓ or skipped (never ✗) | 👀 |
| S00-AC16 | First commit, tag `stage-0`, walkthrough in `docs/stage-0.md` | 📄 |

## Key choices

All scaffold choices, with trade-offs, are in [`Scaffold.md`](../../Scaffold.md#choices). The setup choices:

- **Secrets load in one file only** → one place to audit. *Cost:* a tiny wrapper class.
- **The browser can't pass arguments to the test run** → the page can never become a remote shell. *Cost:* no custom test flags.
- **The harness is a command** (`agentic-harness serve`, later `agentic-harness run`) → a runtime you point at a workspace, the way you run Claude Code. *Cost:* a small CLI file.

## Try it

`make check` → green. Then `uv run agentic-harness serve` → open `127.0.0.1:8000` → **Run checks** → rows turn green.

## Explain it back

1. Why does CI run `make check` instead of its own list of commands?
2. Why load the key in exactly one place, and why bind to `127.0.0.1`?
3. What would the domain-free test catch, and why does it matter for "harness vs agent"?

## Changes

- 2026-11-10 · Created (v3).
- 2026-11-10 · Part A (production scaffold) added at your request; project renamed `agentic-harness`; checks renumbered (now 16).
