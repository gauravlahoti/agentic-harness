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
- The loop (S01): `ModelClient` with `GeminiModel` (stateless, no hidden SDK calls); stop rules for steps, cost and time; cost counts thought tokens (`pricing.toml`); events and JSONL traces with the key scrubbed; `create_harness(...)`; `agentic-harness run`; the `hello` workspace with a `get_time` tool.
- Agent view on the page: a calm chat (task bubble, Activity lines that open to the harness's facts and raw events, prose answer, "✓ Run complete"), live counters, and an animated model menu in the input box (priced models only, D-31).
- `scripts/record_gemini_shapes.py` and 9 recorded Gemini replies as test fixtures; `docs/gemini-api-notes.md`.
- Theme toggle: follows the system by default; a sun/moon switch overrides it with a circular reveal; no flash on reload (D-28).
- Server hardening: host-name check, a page-only action header, strict browser security headers (D-20).
- Context (S02): `workspace.toml` (memory files, skill folders, profiles, memory budget, domain words, examples); system prompt built once in a fixed order (base → memory → skill list) with a prompt ID on every call; skills in the open `SKILL.md` format, loaded on demand by the built-in `load_skill`; a size warning for memory files.
- CloudCo Contract Assistant workspace (all made up): `AGENTS.md` with the answer format, 3 team files, 4 skills, 2 policies, 4 profiles.
- Page: profile picker in the sidebar; CONTEXT lines for the loaded context and for each skill read; example tasks come from the workspace.
- Tools (S03): `@tool` builds Gemini's declaration from type hints and the docstring, with a required risk (read · write · action); arguments checked before a tool runs; errors go back to the model; output capped at 20,000 characters with a visible note; tools get a `ctx` and write files only through it (`tasks/<run-id>/`, `outbox/`).
- Built-in tools a workspace can opt into: `read_file` (listed folders only; never `.env` or `workspace.toml`) and `write_file` (this run's folder).
- CloudCo tools: `get_customer`, `get_deal`, `get_contract`, `compare_to_standard` (61 edits, each with its clause ID), `search_policy`, `get_uptime`, `get_payment_history`; actions `accept_change` and `send_to_customer` write only to the local outbox. Made-up data from a committed generator (`make_data.py`).
- Page: a risk tag on every tool line; a file card for every saved draft or outbox message.
- Sub-agents (S04): declared in `workspace.toml`; one built-in `delegate_task`; the child gets a clean context, read-only tools, ½ the time and ¼ the money left; only its short result returns; its events are tagged and nested on the page in their own lane.
- Harness pane: Agentic Loop · Context · Tools · Guardrails · Memory, in plain words; switches remove skills, tools or sub-agents for the next run (`GET /api/harness`, `off` in the run request).

### Changed
- CloudCo has four tools: `lookup`, `review_contract`, `search_policy`, `send_to_customer` (D-73).
- The server sends `Cache-Control: no-cache`, so the browser never runs an old page script after an update (D-54).
- `hello`'s `get_time` uses `@tool`.
- SDK retries are off; a failed model call ends the run at once with Gemini's own message ("Gemini 429: … retry in 41m") instead of waiting silently until the time limit (D-42).
- The domain-free test also checks each workspace's own words from its `workspace.toml` (D-40).
- Only Gemini answers: Fake mode, `FakeModel` and replay-based loop tests removed (D-32). Coverage gate 75% until the evals (D-33).
- Base system prompt: answer directly; call a tool only when the task needs it (D-30).
- Project named `agentic-harness` (package `agentic_harness`).
- Root documents renamed to Title case (`Decisions.md`, `Tracker.md`); `spec/README.md` → `spec/how-we-build.md`.
- `Readme.md` rewritten as a short project-level overview: what it is, start steps, what the harness does (with status), building an agent, scope.
