# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · versions follow [SemVer](https://semver.org).

## [Unreleased]

### Added
- Production scaffold: `src/` layout, uv + lockfile, ruff, mypy strict, pytest + coverage, Makefile, pre-commit (gitleaks), GitHub Actions CI, Dependabot ([Scaffold.md](Scaffold.md)).
- `agentic-harness` command with `--version`.
- Architecture tests: naming convention, domain-free harness.
- Root `AGENTS.md` pointing coding agents (Codex, Antigravity) to the rules in `CLAUDE.md` (D-18).
- Spec v3: general harness + CloudCo Contract Assistant workspace, 9 stages.
- `config.py`: settings and the API key in one place; the key prints as `***` and never enters the environment.
- `agentic-harness serve`: a local page on `127.0.0.1` with a live Checks panel (one fixed test command, one row per test) and a smoke row (server up · key present or skipped).
- The loop (S01): `ModelClient` with `GeminiModel` (stateless, no hidden SDK calls) and `FakeModel` (replays recorded replies); stop rules for steps, cost and time; cost counts thought tokens (`pricing.toml`); events and JSONL traces with the key scrubbed; `create_harness(...)`; `agentic-harness run`; the `hello` workspace with a `get_time` tool.
- Agent view on the page: input box, live activity timeline, status line, Fake/Live switch.
- `scripts/record_gemini_shapes.py` and 9 recorded Gemini replies as test fixtures; `docs/gemini-api-notes.md`.
- Theme toggle: follows the system by default; a sun/moon switch overrides it with a circular reveal; no flash on reload (D-28).
- Server hardening: host-name check, a page-only action header, strict browser security headers (D-20).

### Changed
- Project named `agentic-harness` (package `agentic_harness`).
- Root documents renamed to Title case (`Decisions.md`, `Tracker.md`); `spec/README.md` → `spec/how-we-build.md`.
- `Readme.md` rewritten as a short project-level overview: what it is, start steps, what the harness does (with status), building an agent, scope.
