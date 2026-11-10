# Tracker

> **Now:** S04 verified except AC10 (clause IDs) · next: S05 (permissions) brief · S02 verified · S00 and S01 built, verification waived for now
> **Updated:** 2026-11-10 · **Checks:** 56 built · 30 verified · 110 total

Icons: 🧪 test · 👀 you watch it · 📄 file · 🔑 needs key · Status: 📝 drafted · 🟦 approved · 🟨 built · ✅ verified · ⛔ blocked

## Waiting on you

| | What | Unblocks |
|---|---|---|
| 0 | Yes/no: add "name every change with its clause ID" to the contract-review skill | S04-AC10, S03-AC11 |
| 0b | Approve the S05 (Permissions) brief | S05 → 🟦 |
| 1 | Verify S01 when convenient: "Verify it yourself" in `docs/stage-1.md` (waived to start S02) | S01 → ✅ |
| 1b | Verify S00 when convenient: "Verify it yourself" in `docs/stage-0.md` (waived to start S01) | S00 → ✅ |
| 2 | Remove the old `GEMINI_API_KEY` export from your shell profile (e.g. `~/.zshrc`); it overrides `.env` | Live runs from your terminal |
| 3 | Second workspace for the swap test: code reviewer (default) or other | S08-AC1 |
| 4 | Repo is **private** (github.com/gauravlahoti/agentic-harness); make it public when ready for LinkedIn | License, public demo |

## Stages

| Stage | Name | Plan | Built | Verified | 🔑 checks |
|---|---|---|---|---|---|
| [S00](spec/stages/S00-setup.md) | Scaffold and setup | 🟨 Part A + B | 15/16 | 0/16 | – |
| [S01](spec/stages/S01-loop.md) | The loop | 🟦 | 7/13 | 0/13 | 2 |
| [S02](spec/stages/S02-context.md) | Context | ✅ | 12/12 | 12/12 | 1 |
| [S03](spec/stages/S03-tools.md) | Tools | 🟨 | 10/11 | 6/11 | 1 |
| [S04](spec/stages/S04-subagent.md) | Sub-agent | 🟨 | 12/13 | 12/13 | 1 |
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
| AC3 | Quality gates: ruff lint + format, mypy strict, pytest with coverage ≥ 75% (D-33) | 🧪 | 🟨 | `make check`: ruff ✓ · mypy strict ✓ · 7 tests ✓ · coverage 100% |
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
| AC4 | ~~`FakeModel` replays scripted replies~~ Removed (D-32) | 🧪 | – | Removed at your request: only Gemini answers |
| AC5 | Plain answer → 1 call, ends `completed` | 🧪 | 📝 | Offline tests removed (D-32); seen working live on Gemini; the S08 evals will re-prove it |
| AC6 | Tool round trip → 2 calls; the result carries the matching `call_id` | 🧪 | 📝 | Offline tests removed (D-32); seen working live on Gemini; the S08 evals will re-prove it |
| AC7 | Two calls in one reply → both run in order, results sent together | 🧪 | 📝 | Offline tests removed (D-32); seen working live on Gemini; the S08 evals will re-prove it |
| AC8 | Model steps are kept exactly as received | 🧪 | 📝 | Offline tests removed (D-32); seen working live on Gemini; the S08 evals will re-prove it |
| AC9 | Stop rules (steps, cost, time) end the run with a named reason; cost counts thought tokens | 🧪 | 📝 | Offline tests removed (D-32); seen working live on Gemini; the S08 evals will re-prove it |
| AC10 | An unexpected status ends the run with a named error, never a silent loop | 🧪 | 📝 | Offline tests removed (D-32); seen working live on Gemini; the S08 evals will re-prove it |
| AC11 | Every step emits an event and is saved to a trace file; the key never appears in it | 🧪 | 🟨 | `test_loop.py::test_s01_ac11_*` + `test_trace.py` (4): 8 events for a round trip; JSONL trace; key scrubbed · live trace: key found 0 times |
| AC12 | `create_harness(model, limits, workspace)` and `agentic-harness run "…"` both work | 🧪 | 🟨 | `test_api.py`: price check, workspace loading, `run` without a key · live: `agentic-harness run` 2 parallel tool calls on Gemini |
| AC13 | Page: input box, activity timeline, status line, model menu | 👀 | 🟨 | `test_server_run.py` + `test_page_baseline.py` · Chrome: live runs on 3.5 Flash-Lite, 3.6 Flash; model menu opens, picks and closes with a real click |
| AC14 | A real tool round trip works on Gemini (thought signatures survive) | 🔑 🧪 | 🟨 | `tests/live/test_live_loop.py` passed (`make live`, gemini-3.5-flash-lite) · CLI live: 2 parallel calls, signatures kept in both replies |

### S02 · Context

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | The harness reads `workspace.toml`: memory files, skill folders, tools file | 🧪 | ✅ | `test_workspace.py::test_s02_ac1_*` (4): reads every field; file optional (D-41); wrong types and broken TOML are clear errors |
| AC2 | System prompt is built in a fixed order: base → memory files → skill list | 🧪 | ✅ | `test_context.py::test_s02_ac2_*` + `test_api.py` (4): base → memory → skills, in that order; no skills → no section and no `load_skill` |
| AC3 | `{profile}` in a path picks the active profile's file | 🧪 | ✅ | `test_workspace.py` + `test_api.py::test_s02_ac3_*` (5): `{profile}` picks the file; missing profile file skipped, missing fixed file an error; unknown profile refused (CLI exit 2) |
| AC4 | Only skill names + descriptions go in the prompt; `load_skill` returns the full text | 🧪 | ✅ | `test_skills.py` + `test_context.py::test_s02_ac4_*` (3): only `name: description` in the prompt; `load_skill` returns body + source; only visible names offered · live: "Read skill contract-review" |
| AC5 | Skills use the open `SKILL.md` format (name, description) and are checked on load | 🧪 | ✅ | `test_skills.py::test_s02_ac5_*` (12): name + description only, name matches folder, ≤ 1024 chars, same name twice refused |
| AC6 | Each profile sees only its own skill folders | 🧪 | ✅ | `test_workspace.py::test_s02_ac6_*` (2): alpha sees shared + alpha only · Chrome: Engineering gets uptime-check, CFO gets 1 skill |
| AC7 | A memory file over its size budget gives a warning | 🧪 | ✅ | `test_context.py::test_s02_ac7_*` (2): a file over budget gives a named warning; estimate = chars ÷ 4 |
| AC8 | The prompt is identical on every call in a session | 🧪 | ✅ | `test_context.py::test_s02_ac8_*` · live: `test_s02_ac11_*` checks one `prompt_id` across all calls (`77e41f5c0001` for Sales) |
| AC9 | The domain-free test (from S00) also checks each workspace's own words, declared in its `workspace.toml` | 🧪 | ✅ | `test_generic_harness.py::test_s02_ac9_*`: every workspace declares `domain_words`; all `src/` text files scanned (caught hello's examples in `app.js` → moved to `workspace.toml`) |
| AC10 | CloudCo files written: `AGENTS.md`, 3 team files, 4 skills, 2 policies | 📄 | ✅ | `test_cloudco.py::test_s02_ac10_*` (7): AGENTS.md, 3 team files, 4 skills, 2 policies; each marked fictional; every profile within budget |
| AC11 | Answers follow: Summary → Needs a human decision → Sources | 🔑 👀 | ✅ | `test_cloudco.py::test_s02_ac11_*` · `make live` passed on 3.5 Flash-Lite: `test_s02_ac11_answer_follows_cloudco_format` (Summary → Needs a human decision → Sources; CFO named) |
| AC12 | Page: profile switcher, Context tags, the skill listed in Sources | 👀 | ✅ | `test_server_run.py` + `test_context.py::test_s02_ac12_*` (3) · Chrome, Sales, 3.5 Flash-Lite: profile switcher, 2 CONTEXT lines, `skills/company/contract-review/SKILL.md` in Sources, console clean |

### S03 · Tools

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | `@tool` records name, description, schema and risk, and outputs Gemini's tool format | 🧪 | ✅ | `test_tool_registry.py::test_s03_ac1_*` (6): name, docstring, risk; schema from hints (str/int/float/bool/Literal/list, `Annotated` descriptions, defaults); `ctx` hidden; Gemini function format; risk required; bad types fail at load |
| AC2 | Built-in tools work for any workspace | 🧪 | ✅ | `test_builtin_tools.py::test_s03_ac2_*` (12) + `test_api.py`: `read_file` only inside `readable` (refuses `..`, links out, `.env`, `workspace.toml`, absolute paths); folders list; `write_file` only to `tasks/<run-id>/`; only opted-in built-ins added |
| AC3 | Workspace tools load from `tools.py`; the harness knows none of them by name | 🧪 | ✅ | `test_workspace.py` + `test_api.py` + `test_generic_harness.py::test_s03_ac3_*` (5): `@tool` tools load from `tools.py`; unknown built-in and name clash are errors; no workspace tool name appears in `src/` |
| AC4 | CloudCo lookups return records with IDs | 🧪 | 🟨 | `test_cloudco_tools.py::test_s03_ac4_*` (4): `lookup` returns records with IDs; unknown records list what exists; one clause in both versions |
| AC5 | `review_contract` returns every edit (~60) with clause IDs | 🧪 | 🟨 | `test_s03_ac5_*`: `review_contract` returns 61 edits with clause IDs, under the 20k cap |
| AC6 | `search_policy` returns the rule and its section number | 🧪 | ✅ | `test_cloudco_tools.py::test_s03_ac6_*`: "discount approval CFO" → `standard-terms §2` with its text; no match → empty list |
| AC7 | Actions write only to the local outbox, never to real email | 🧪 | 🟨 | `test_s03_ac7_*` (3): `send_to_customer` writes only under `outbox/`; no network imports |
| AC8 | Tool errors go back to the model; the loop never crashes | 🧪 | ✅ | `test_tool_registry.py::test_s03_ac8_*` (7): bad arguments, exceptions and a missing workspace all come back as error results; async tools; output cut with a visible note; `file_saved` announced |
| AC9 | CloudCo data is made up and labelled fictional | 📄 | ✅ | `test_cloudco_tools.py::test_s03_ac9_*` (3): data matches `make_data.py` exactly; every data file says fictional; one hidden line in a ~19,000-word redline |
| AC10 | Page: tool steps, record IDs in Sources, file cards | 👀 | 🟨 | Chrome: risk tags, short labels, outbox file card (synthetic event); drafts no longer saved (D-73) |
| AC11 | Live: finds all 5 changes that matter, with IDs | 🔑 👀 | 📝 | Live run failed: changes found, clause IDs missing (same cause as S04-AC10) |

### S04 · Sub-agent

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Sub-agents come from `workspace.toml`; the harness has none built in | 🧪 | ✅ | `test_subagents.py::test_s04_ac1_*` (8): `[subagents.*]` read from `workspace.toml`; bad declarations are clear errors; no helper without config |
| AC2 | `delegate_task` starts the child with an empty history | 🧪 | ✅ | Live (Chrome + `test_live_subagent.py`): the helper's first call sends 1 step (the brief) · `child_system` = base + its own file |
| AC3 | The child has only its declared tools, and none are actions | 🧪 | ✅ | `test_s04_ac3_*` (2): helpers may only read; the child gets exactly its declared tools |
| AC4 | The child can't delegate (depth 1) | 🧪 | ✅ | `test_s04_ac4_*` + `test_s04_ac3_ac4_*`: no `delegate_task` in a child; declaring it is refused |
| AC5 | Budget slice enforced (50% of the time left, 25% of the money, ≤ 15 steps); out of budget → partial answer + reason | 🧪 | ✅ | `test_s04_ac5_*` (3): 50% time / 25% money / ≤ 15 steps; delegate-only tools leave the parent; partial answer + reason on stop |
| AC6 | The child returns the declared short shape | 🧪 | ✅ | `test_s04_ac6_*`: result cut at `max_words` with a note · live result under 200 words |
| AC7 | The parent's history holds only the result, not the 40 pages | 🧪 | ✅ | Live trace: the parent's history holds `delegate_task`'s result, never `review_contract`'s |
| AC8 | Child events are tagged `agent_id` + `parent_id` | 🧪 | ✅ | `test_s04_ac8_*` (2): child events tagged `agent_id`/`parent_id`/`agent`; a helper's finish no longer ends the page stream (bug found live, fixed) |
| AC9 | Page: nested sub-agent lane with its own mini counters | 👀 | ✅ | Chrome: `clause-reviewer` lane under "Handed the job to…", own counters (3 calls · 6.7k tokens · $0.003 · 19 s) |
| AC10 | Live: same 5 findings with delegation on and off; the parent uses fewer tokens with it on | 🔑 👀 | 🟦 | Live run failed: both answers find the changes and flag B.7, but omit clause IDs (skill asks for policy sections only). Fix proposed: one line in the contract-review skill, awaiting your yes |
| AC11 | Page: a collapsible Harness pane shows the profile's memory files, skills, tools (risk, description) and sub-agents | 🧪 👀 | ✅ | `test_s04_ac11_*` + `/api/harness` test · Chrome: Agentic Loop · Context · Tools · Guardrails · Memory, collapsed, plain words |
| AC12 | Switching a skill, tool or sub-agent off removes it for the next run only; unknown names are refused; nothing is switched on beyond the workspace | 🧪 | ✅ | `test_s04_ac12_*` (3): switches remove tools/skills/helpers, unknown names refused · Chrome: real click → "1 off" chip |
| AC13 | Each run records what was off (event, trace, "Started a run" line) | 🧪 👀 | ✅ | `run_started.off` recorded; "Started a run · 1 off" line · live test checks the event |

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
| 2026-11-10 | At your request: only Gemini answers. Fake mode, `FakeModel`, `fake_replies.json` and the replay-based loop tests removed (D-32). S01-AC4 dropped; AC5–AC10 → 📝 until the evals. Coverage gate 75% (D-33). Model menu restyled (animated customizable select); helper phrases removed. UI baseline written in `spec/02-ui.md` and guarded by `test_page_baseline.py`. |
| 2026-11-10 | You waived S01 verification and approved the S02 brief ("proceed with stage 2"); choice 8 (Fake recordings) dropped per D-32. S02-AC1–AC12 → 🟦. Choices recorded as D-34–D-41. |
| 2026-11-10 | Your report: runs on 3.6/3.8 Flash stuck at "Thinking" until the time limit. Cause: the SDK silently slept on a 429 "retry in 41m" (3.6 Flash free tier: 20 requests/day used up) and a 503 on 3.8 Flash. Fix (D-42): SDK retries off; the run now fails at once with Gemini's own sentence. |
| 2026-11-10 | S02-AC1–AC12 → 🟨: 123 offline tests pass; `make live` 2/2 on 3.5 Flash-Lite; page checked in Chrome. Walkthrough in `docs/stage-2.md`. Waiting for your verification. |
| 2026-11-10 | You verified S02 ("looks good"): S02-AC1–AC12 → ✅. Tagged `stage-2`. |
| 2026-11-10 | You approved the S03 brief ("go ahead"): S03-AC1–AC11 → 🟦. Choices recorded as D-43–D-53. |
| 2026-11-10 | S03-AC1–AC11 → 🟨: 168 offline tests pass; `make live` 3/3 on 3.5 Flash-Lite; page checked in Chrome. Found and fixed: stale `app.js` in the browser (D-54). Walkthrough in `docs/stage-3.md`. Waiting for your verification. |
| 2026-11-10 | You verified S03 ("looks good to me"): S03-AC1–AC11 → ✅. Tagged `stage-3`. |
| 2026-11-10 | You approved the S04 brief ("go ahead"): S04-AC1–AC10 → 🟦. Choices recorded as D-55–D-65. You also asked for a Harness pane with on/off switches; its brief is pending. |
| 2026-11-10 | You approved the Harness pane add-on ("sound fair, go ahead"): S04-AC11–AC13 added → 🟦 (D-66–D-72); D-64 changed. |
| 2026-11-10 | S04-AC5 changed at your choice (D-60): helpers get 50% of the time left, 25% of the money. Seen live: a 30 s slice ran out under load. |
| 2026-11-10 | At your request: CloudCo consolidated to four tools (D-73). S03 reopened: AC4, AC5, AC7, AC10, AC11 → 📝 until re-proven. Harness pane grouped by part and collapsed by default. Found and fixed: a helper's finish ended the page stream and cancelled the main run. |
| 2026-11-10 | You verified S04 ("s4 looks ok"): 12 of 13 checks ✅. S04-AC10 open: live answers omit clause IDs. S03 re-proven with four tools: AC4, AC5, AC7, AC10 → 🟨; AC11 → 📝 (same cause). |
