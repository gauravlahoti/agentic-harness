# Tracker

> **Now:** S01 built → waiting for your verification · S00 built (verification waived for now)
> **Updated:** 2026-11-10 · **Checks:** 29 built · 0 verified · 107 total

Icons: 🧪 test · 👀 you watch it · 📄 file · 🔑 needs key · Status: 📝 drafted · 🟦 approved · 🟨 built · ✅ verified · ⛔ blocked

## Waiting on you

| | What | Unblocks |
|---|---|---|
| 1 | Verify S01: "Verify it yourself" in `docs/stage-1.md` | S01 → ✅, then S02 |
| 1b | Verify S00 when convenient: "Verify it yourself" in `docs/stage-0.md` (waived to start S01) | S00 → ✅ |
| 2 | Remove the old `GEMINI_API_KEY` export from your shell profile (e.g. `~/.zshrc`); it overrides `.env` | Live runs from your terminal |
| 3 | Second workspace for the swap test: code reviewer (default) or other | S08-AC1 |
| 4 | Repo is **private** (github.com/gauravlahoti/agentic-harness); make it public when ready for LinkedIn | License, public demo |

## Stages

| Stage | Name | Plan | Built | Verified | 🔑 checks |
|---|---|---|---|---|---|
| [S00](spec/stages/S00-setup.md) | Scaffold and setup | 🟨 Part A + B | 15/16 | 0/16 | – |
| [S01](spec/stages/S01-loop.md) | The loop | 🟦 | 14/14 | 0/14 | 2 |
| [S02](spec/stages/S02-context.md) | Context | 📝 | 0/12 | 0/12 | 1 |
| [S03](spec/stages/S03-tools.md) | Tools | 📝 | 0/11 | 0/11 | 1 |
| [S04](spec/stages/S04-subagent.md) | Sub-agent | 📝 | 0/10 | 0/10 | 1 |
| [S05](spec/stages/S05-permissions.md) | Permissions | 📝 | 0/11 | 0/11 | 1 |
| [S06](spec/stages/S06-approvals.md) | Approvals | 📝 | 0/12 | 0/12 | 1 |
| [S07](spec/stages/S07-memory.md) | Memory | 📝 | 0/10 | 0/10 | 1 |
| [S08](spec/stages/S08-demo.md) | Proof and demo | 📝 | 0/11 | 0/11 | 3 |

## Checks

### S00 · Scaffold and setup

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | A fresh copy: `make setup` installs exactly what `uv.lock` says; `make check` passes offline | 🧪 | 🟨 | CI run 42684153010: fresh clone → `uv sync --locked` → `make check` ✓ |
| AC2 | `src/` layout, typed package `agentic_harness`; `agentic-harness --version` works | 🧪 | 🟨 | `test_cli.py` (3 tests) · `agentic-harness --version` → 0.1.0 |
| AC3 | Quality gates: ruff lint + format, mypy strict, pytest with coverage ≥ 85% | 🧪 | 🟨 | `make check`: ruff ✓ · mypy strict ✓ · 7 tests ✓ · coverage 100% |
| AC4 | Naming: no ALL-CAPS file names (except `CLAUDE.md`, `AGENTS.md`, `SKILL.md`); folders and Python files lowercase | 🧪 | 🟨 | `test_naming.py` · proven: a `NOTES.md` file made it fail |
| AC5 | Domain-free harness: no workspace words in `src/agentic_harness/` | 🧪 | 🟨 | `test_generic_harness.py` · proven: the word 'contract' in cli.py made it fail |
| AC6 | CI runs `make check` + a full-history secret scan, with a read-only token | 📄 | 🟨 | CI run 42684153010 green · actions pinned to commit SHAs · ⚠ the CI secret scan checks staged changes only, so nothing in CI (fix on hold; see `docs/stage-0.md` → Known gap) |
| AC7 | Pre-commit runs file hygiene, gitleaks, ruff and mypy at the locked versions | 📄 | 🟨 | `.pre-commit-config.yaml` validated · run `make hooks` to install |
| AC8 | Repo documents: Readme, Scaffold, Decisions, Tracker, Security, Contributing, Changelog | 📄 | 🟨 | All 7 documents present |
| AC9 | Runtime packages are only `google-genai`, `fastapi`, `uvicorn`, `python-dotenv` | 📄 | 🟨 | `pyproject.toml` dependencies |
| AC10 | `.env` is ignored by git; `.env.example` has the names, no values | 🧪 📄 | 🟨 | `git check-ignore .env` ✓ · `test_config.py::test_s00_ac10_*` (2 tests) |
| AC11 | Only `config.py` loads the key; printing it shows `***` | 🧪 | 🟨 | `test_config.py::test_s00_ac11_*` (5 tests): prints `***`, never enters `os.environ`, only `config.py` reads it |
| AC12 | No key? Everything offline still works | 🧪 | 🟨 | `test_config.py::test_s00_ac12_*` (4 tests) · Checks panel child run has no key (`test_checks.py`) |
| AC13 | `agentic-harness serve` listens on `127.0.0.1:8000` only and serves the page shell | 🧪 👀 | 🟨 | `test_server.py` + `test_cli.py` (`test_s00_ac13_*`, 6 tests) · live: `lsof` shows `127.0.0.1:8000` only; foreign Host → 400 |
| AC14 | Checks panel runs one fixed test command, one row per test, live | 🧪 👀 | 🟨 | `test_checks.py` + `test_server.py` (`test_s00_ac14_*`, 12 tests) · live in Chrome: 38 rows, "✓ 38 passed · 0 failed · 4.8 s" |
| AC15 | Smoke row: server up ✓ · key present ✓ or skipped (never ✗) | 👀 | 🟨 | `test_server.py::test_s00_ac15_smoke_status` (key present / missing) · live: "Server up ✓ · Key present ✓" |
| AC16 | First commit, tag `stage-0`, walkthrough in `docs/stage-0.md` | 📄 | 📝 | Commits `51e31c0` · `3fe0a62` · `d617ca8` pushed · tag + walkthrough after your verification |

### S01 · The loop

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | A test script records Gemini's real reply shapes in `docs/gemini-api-notes.md` (text, tool call, result, statuses, usage, max-tokens, safety block) | 🔑 📄 | 🟨 | `scripts/record_gemini_shapes.py` → 9 fixtures in `tests/fixtures/gemini/` · findings in `docs/gemini-api-notes.md` (tool calls end `requires_action`; D-22 round trip confirmed; safety block not captured) |
| AC2 | `ModelClient` has one method: `create(system, steps, tools)` | 🧪 | 🟨 | `test_model.py::test_s01_ac2_*` (2): one method `create(system, steps, tools)`; Gemini + Fake both fit |
| AC3 | `GeminiModel` sends the full history with `store=False`, never `previous_interaction_id` | 🧪 | 🟨 | `test_model.py::test_s01_ac3_*` (4): `store=False`, full history, no `previous_interaction_id`, `automatic_continuation=False`; SDK errors → `ModelError`, key removed |
| AC4 | `FakeModel` replays scripted replies shaped like the real ones | 🧪 | 🟨 | `test_model.py::test_s01_ac4_*` (4): replays the 9 recorded replies in `tests/fixtures/gemini/` |
| AC5 | Plain answer → 1 call, ends `completed` | 🧪 | 🟨 | `test_loop.py::test_s01_ac5_plain_answer_is_one_call` |
| AC6 | Tool round trip → 2 calls; the result carries the matching `call_id` | 🧪 | 🟨 | `test_loop.py::test_s01_ac6_tool_round_trip_is_two_calls`: result carries the call's `call_id` |
| AC7 | Two calls in one reply → both run in order, results sent together | 🧪 | 🟨 | `test_loop.py::test_s01_ac7_*`: UTC then Tokyo, both results sent together · live: 2 calls in one reply |
| AC8 | Model steps are kept exactly as received | 🧪 | 🟨 | `test_loop.py::test_s01_ac8_*`: second request holds the recorded steps byte-for-byte, signature included |
| AC9 | Stop rules (steps, cost, time) end the run with a named reason; cost counts thought tokens | 🧪 | 🟨 | `test_loop.py` + `test_limits_pricing.py` (`test_s01_ac9_*`, 14): steps, cost, time, output limit; thought tokens priced · live: 3.8 Flash overload → `time_limit` after 60 s |
| AC10 | An unexpected status ends the run with a named error, never a silent loop | 🧪 | 🟨 | `test_loop.py::test_s01_ac10_*` (9): unknown status, `requires_action` without calls, model error, tool error, unknown tool |
| AC11 | Every step emits an event and is saved to a trace file; the key never appears in it | 🧪 | 🟨 | `test_loop.py::test_s01_ac11_*` + `test_trace.py` (4): 8 events for a round trip; JSONL trace; key scrubbed · live trace: key found 0 times |
| AC12 | `create_harness(model, limits, workspace)` and `agentic-harness run "…"` both work | 🧪 | 🟨 | `test_api.py` (9): `create_harness`, `agentic-harness run --fake`, workspace loading, clear errors |
| AC13 | Page: input box, activity timeline, status line, Fake/Live switch | 👀 | 🟨 | `test_server_run.py` (7) · Chrome: live run "✓ Completed in 2 calls · $0.00034 · 2.3 s", Fake run in dark theme, console clean |
| AC14 | A real tool round trip works on Gemini (thought signatures survive) | 🔑 🧪 | 🟨 | `tests/live/test_live_loop.py` passed (`make live`, gemini-3.5-flash-lite) · CLI live: 2 parallel calls, signatures kept in both replies |

### S02 · Context

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | The harness reads `workspace.toml`: memory files, skill folders, tools file | 🧪 | 📝 |  |
| AC2 | System prompt is built in a fixed order: base → memory files → skill list | 🧪 | 📝 |  |
| AC3 | `{profile}` in a path picks the active profile's file | 🧪 | 📝 |  |
| AC4 | Only skill names + descriptions go in the prompt; `load_skill` returns the full text | 🧪 | 📝 |  |
| AC5 | Skills use the open `SKILL.md` format (name, description) and are checked on load | 🧪 | 📝 |  |
| AC6 | Each profile sees only its own skill folders | 🧪 | 📝 |  |
| AC7 | A memory file over its size budget gives a warning | 🧪 | 📝 |  |
| AC8 | The prompt is identical on every call in a session | 🧪 | 📝 |  |
| AC9 | The domain-free test (from S00) also checks each workspace's own words, declared in its `workspace.toml` | 🧪 | 📝 |  |
| AC10 | CloudCo files written: `AGENTS.md`, 3 team files, 4 skills, 2 policies | 📄 | 📝 |  |
| AC11 | Answers follow: Summary → Needs a human decision → Sources | 🔑 👀 | 📝 |  |
| AC12 | Page: profile switcher, Context tags, the skill listed in Sources | 👀 | 📝 |  |

### S03 · Tools

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | `@tool` records name, description, schema and risk, and outputs Gemini's tool format | 🧪 | 📝 |  |
| AC2 | Built-in tools work for any workspace | 🧪 | 📝 |  |
| AC3 | Workspace tools load from `tools.py`; the harness knows none of them by name | 🧪 | 📝 |  |
| AC4 | CloudCo lookups return records with IDs | 🧪 | 📝 |  |
| AC5 | `compare_to_standard` returns every edit (~60) with clause IDs | 🧪 | 📝 |  |
| AC6 | `search_policy` returns the rule and its section number | 🧪 | 📝 |  |
| AC7 | Actions write only to the local outbox, never to real email | 🧪 | 📝 |  |
| AC8 | Tool errors go back to the model; the loop never crashes | 🧪 | 📝 |  |
| AC9 | CloudCo data is made up and labelled fictional | 📄 | 📝 |  |
| AC10 | Page: tool steps, record IDs in Sources, file cards | 👀 | 📝 |  |
| AC11 | Live: finds all 5 changes that matter, with IDs | 🔑 👀 | 📝 |  |

### S04 · Sub-agent

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Sub-agents come from `workspace.toml`; the harness has none built in | 🧪 | 📝 |  |
| AC2 | `delegate_task` starts the child with an empty history | 🧪 | 📝 |  |
| AC3 | The child has only its declared tools, and none are actions | 🧪 | 📝 |  |
| AC4 | The child can't delegate (depth 1) | 🧪 | 📝 |  |
| AC5 | Budget slice enforced (25% of what's left, ≤ 15 steps); out of budget → partial answer + reason | 🧪 | 📝 |  |
| AC6 | The child returns the declared short shape | 🧪 | 📝 |  |
| AC7 | The parent's history holds only the result, not the 40 pages | 🧪 | 📝 |  |
| AC8 | Child events are tagged `agent_id` + `parent_id` | 🧪 | 📝 |  |
| AC9 | Page: nested sub-agent lane with its own mini counters | 👀 | 📝 |  |
| AC10 | Live: same 5 findings with delegation on and off; the parent uses fewer tokens with it on | 🔑 👀 | 📝 |  |

### S05 · Permissions

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Profiles come from `workspace.toml`; the model can't read or change them | 🧪 | 📝 |  |
| AC2 | Tools outside the profile are hidden from Gemini and blocked by the gate if called | 🧪 | 📝 |  |
| AC3 | Fields are masked per profile (Engineering never sees prices or payments) | 🧪 | 📝 |  |
| AC4 | Memory files, skills and policies are read-only for everyone, the agent included | 🧪 | 📝 |  |
| AC5 | Writes only inside the current task folder | 🧪 | 📝 |  |
| AC6 | "Never" rules always block and can't be approved | 🧪 | 📝 |  |
| AC7 | Instruction-like text in tool results is flagged ⚠ | 🧪 | 📝 |  |
| AC8 | A sub-agent's rights are always within its caller's | 🧪 | 📝 |  |
| AC9 | Every block names the rule that blocked it | 🧪 | 📝 |  |
| AC10 | Page: ⛔ and ⚠ cards, "This profile can…" panel | 👀 | 📝 |  |
| AC11 | Live: the same question under 3 profiles gives 3 different, correct answers | 🔑 👀 | 📝 |  |

### S06 · Approvals

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Approval rules come from `workspace.toml` and match CloudCo's approval chart | 🧪 | 📝 |  |
| AC2 | A matching action pauses the loop until a human decides | 🧪 | 📝 |  |
| AC3 | The card shows the action, values, reason, evidence IDs, rule and approver | 🧪 👀 | 📝 |  |
| AC4 | Approve → it runs; the result goes back to the model | 🧪 | 📝 |  |
| AC5 | Reject → the reason goes back to the model, and it adapts | 🧪 | 📝 |  |
| AC6 | No answer in time → treated as Reject | 🧪 | 📝 |  |
| AC7 | Only someone with the authority can approve (CFO items need the CFO profile) | 🧪 | 📝 |  |
| AC8 | Sending anything to a customer always needs approval | 🧪 | 📝 |  |
| AC9 | `ask_human` lets the model pause to ask a question | 🧪 | 📝 |  |
| AC10 | The outbox records who approved what, and when | 🧪 | 📝 |  |
| AC11 | Page: approval cards, "Waiting for CFO", "nothing was sent" | 👀 | 📝 |  |
| AC12 | Live: the CFO rejects 25% ("max 20%") → the agent proposes 20% → approved → the reply is sent after Sales approves | 🔑 👀 | 📝 |  |

### S07 · Memory

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Each task is saved as an append-only file; model steps are saved exactly | 🧪 | 📝 |  |
| AC2 | The sidebar lists the profile's tasks: open, continue, delete | 🧪 👀 | 📝 |  |
| AC3 | After a server restart the task resumes; an unfinished tool call is marked cancelled, not re-run | 🧪 | 📝 |  |
| AC4 | `save_note` keeps notes per profile; they enter the prompt next time (capped at ~2,000 tokens) | 🧪 | 📝 |  |
| AC5 | Big tool output → start + end + marker | 🧪 | 📝 |  |
| AC6 | Old tool results → one-line stubs, in batches past 50% | 🧪 | 📝 |  |
| AC7 | Summarize only if still past 70% after pruning | 🧪 | 📝 |  |
| AC8 | Model steps are never edited; a call never loses its result | 🧪 | 📝 |  |
| AC9 | Page: context fill bar, trimming card, cached tokens shown | 👀 | 📝 |  |
| AC10 | Live: in round 2 the agent recalls round 1's decisions | 🔑 👀 | 📝 |  |

### S08 · Proof and demo

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Swap test: the second workspace runs; `git diff src/agentic_harness/` is empty | 🧪 🔑 | 📝 |  |
| AC2 | Replay plays a saved task on the page with zero model calls | 🧪 | 📝 |  |
| AC3 | X-ray shows, per step: what Gemini saw, tool input/output, the gate's decision, cost | 👀 | 📝 |  |
| AC4 | Mini loop ring lights the part acting right now | 👀 | 📝 |  |
| AC5 | Run summary card: steps, tools, approvals, blocks, tokens, cost, time | 👀 | 📝 |  |
| AC6 | Each harness part can be switched off for recording, only in demo mode, with a red banner | 🧪 👀 | 📝 |  |
| AC7 | Eval set: 6 tasks with check scripts, 3 runs each, own budget cap | 🧪 🔑 | 📝 |  |
| AC8 | Eval pass rate ≥ 5 of 6 | 🔑 | 📝 |  |
| AC9 | Export a saved run as a static page: no backend, no key, no API calls | 🧪 📄 | 📝 |  |
| AC10 | Demo mode: big type, slower cards, short output | 👀 | 📝 |  |
| AC11 | A clean 1080p recording in 16:9, 1:1 and 4:5 | 👀 | 📝 |  |

## Product goals

| ID | Goal | Status |
|---|---|---|
| P-SC1 | Each harness part is its own module | ⬜ |
| P-SC2 | `src/agentic_harness/` contains zero domain words | 🟨 guarded by a test from day one |
| P-SC3 | A second workspace runs with zero harness changes | ⬜ |
| P-SC4 | All offline tests < 10 s | 🟨 6.3 s today (96 tests) |
| P-SC5 | ≥ 5 of 6 eval tasks pass | ⬜ |
| P-SC6 | Every episode has a real without/with clip pair | ⬜ |
| P-SC7 | 75 s demo from replay, zero API calls | ⬜ |
| P-SC8 | You can explain any file | ⬜ |

## Log

| Date | What changed |
|---|---|
| 2026-11-10 | Spec v3 written: general harness + CloudCo Contract Assistant workspace, 9 stages. Old spec deleted. |
| 2026-11-10 | Production scaffold built (S00 Part A, 10 checks 🟨). Renamed `agentic-harness`; docs to Title case. |
| 2026-11-10 | Repo created (private) and pushed. First CI run failed (`setup-uv@v10` tag doesn't exist); fixed by pinning actions to commit SHAs → CI green. |
| 2026-11-10 | S00 Part B + S01 brief approved → 🟦 (S00-AC11–15, S01-AC1–14). D-03–D-08 accepted (D-08: AI Studio key). Choices recorded as D-19–D-27. |
| 2026-11-10 | S00 Part B built: `config.py`, server (`app.py`, `checks.py`, `pytest_stream.py`), page shell + Checks panel. S00-AC10–15 → 🟨 (38 tests, coverage 99%). Walkthrough in `docs/stage-0.md`. |
| 2026-11-10 | Theme toggle added to the page (D-28). You waived S00 verification ("for stage 1, go ahead"); S00 stays 🟨 until you verify. S01 build started. |
| 2026-11-10 | S01-AC1 recording script written; first live call returned 402 (prepaid credits depleted). S01-AC1, AC14 → ⛔ until credits are added. |
| 2026-11-10 | New free-tier key. Old key still exported in the shell overrode `.env`. 3.8/3.7/3.6 Flash returned 503 "high demand"; recorded with 3.5 Flash-Lite. S01-AC1 → 🟨, AC14 → 🟦. D-29 added. |
| 2026-11-10 | S01 built: model, loop, limits, pricing, events, trace, tools, workspace, api, `run` command, `/api/run`, Agent view. S01-AC2–AC14 → 🟨 (96 offline tests + 1 live). Walkthrough in `docs/stage-1.md`. |
| 2026-11-10 | Agent view restyled to the calm-chat layout (task bubble, Activity lines that open to an X-ray, prose answer, run footer); sidebar pinned so the theme toggle stays visible. Approved by you. |
| 2026-11-10 | Your report: "who is the prime minister" called `get_time`. Cause: vague base prompt. Tightened (D-30): needless calls 5/5 → 1/5 on Flash-Lite. Model menu added to the input box (D-31): 3.8 Flash, 3.6 Flash, 3.5 Flash-Lite. |
