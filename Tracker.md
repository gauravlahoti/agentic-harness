# Tracker

> **Now:** S12 · Guarded actions and identity: Part A building · S11 · Plan and Verify built (14/15 🟨), waiting for your check; AC12 is live · S10 verified (AC11 live 16 × 3 still open) · S07 built, waiting for your check (AC10 live waits for quota) · S06 verified except AC12 (live: waits for Gemini quota) · S04-AC10 and S03-AC11 live re-check waits for quota too · next: S07 brief
> **Updated:** 2026-11-10 · **Checks:** 70 built · 43 verified · 113 total

Icons: 🧪 test · 👀 you watch it · 📄 file · 🔑 needs key · Status: 📝 drafted · 🟦 approved · 🟨 built · ✅ verified · ⛔ blocked

## Waiting on you

| | What | Unblocks |
|---|---|---|
| 0 | Yes/no: add "name every change with its clause ID" to the contract-review skill | S04-AC10, S03-AC11 |
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
| [S05](spec/stages/S05-permissions.md) | Permissions | ✅ | 14/14 | 14/14 | 1 |
| [S06](spec/stages/S06-approvals.md) | Approvals | 🟨 | 11/12 | 11/12 | 1 |
| [S07](spec/stages/S07-memory.md) | Memory | 🟨 | 10/11 | 0/11 | 2 |
| [S08](spec/stages/S08-demo.md) | Proof and demo | 📝 | 0/11 | 0/11 | 3 |
| [S09](spec/stages/S09-production.md) | Production readiness | 🟨 | 5/14 | 0/14 | 1 |
| [S10](spec/stages/S10-evals.md) | Evals | 🟨 | 10/11 | 10/11 | 1 |
| [S11](spec/stages/S11-plan-verify.md) | Plan and Verify | 🟨 | 14/15 | 0/15 | 1 |
| [S12](spec/stages/S12-guarded-actions.md) | Guarded actions and identity | 🟨 | 13/14 | 0/14 | 1 |
| [S13](spec/stages/S13-guided-tour.md) | Guided Tour | 🟦 | 6/9 | 0/9 | 1 |
| [S14](spec/stages/S14-public-tour.md) | Public Tour Mode | 🟦 | 9/10 | 0/10 | 1 |

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
| AC1 | Profiles come from `workspace.toml`; the model can't read or change them | 🧪 | ✅ | `test_workspace.py::test_s05_ac1_*` (2): profiles (tools, hidden fields), `[[rules]]`, `[[approvals]]` read from `workspace.toml`; bad rules are clear errors |
| AC2 | Tools outside the profile are hidden from Gemini and blocked by the gate if called | 🧪 | ✅ | `test_gate.py` + `test_gate_loop.py::test_s05_ac2_*`: tools outside the profile hidden from Gemini and blocked if called · live: Engineering never offered `send_to_customer` |
| AC3 | Fields in structured results are masked per profile (Engineering never sees prices or payments) | 🧪 | ✅ | `test_s05_ac3_*` (3): named fields replaced with `[hidden for <profile>]` · live CLI: Engineering's deal + payments came back hidden, IDs kept |
| AC4 | Memory files, skills and policies are read-only for everyone, the agent included | 🧪 | ✅ | `test_cloudco_tools.py::test_s05_ac4_ac5_*`: `AGENTS.md`, policies, skills can't be written (writes only via `ctx`, by plain name) |
| AC5 | Writes only inside the current task folder | 🧪 | ✅ | Same test + S03 `ctx` tests: writes only in `tasks/<run-id>/` and `outbox/` |
| AC6 | "Never" rules always block and can't be approved | 🧪 | ✅ | `test_s05_ac6_*` (6): CloudCo's 4 never rules block; a never rule is checked before approval, so it can't be approved |
| AC7 | Instruction-like text in tool results is flagged ⚠ | 🧪 | ✅ | `test_s05_ac7_*` + `test_gate_loop.py`: instruction-like text flagged; the model gets a "treat as data" note; ⚠ line on the page |
| AC8 | A sub-agent's rights are always within its caller's | 🧪 | ✅ | `test_s05_ac8_*`: a helper's tools are its declared ∩ its caller's; same gate |
| AC9 | Every block names the rule that blocked it | 🧪 | ✅ | `test_s05_ac2_ac9_*`, `test_s05_ac6_ac9_*`: every block names its rule and policy section |
| AC10 | Page: ⛔ and ⚠ cards, "This profile can…" panel | 👀 | ✅ | `test_page_baseline.py::test_s05_*` · Chrome: ⏸ card, Approve/Reject, ✓ Approved line, outbox card; Guardrails cards in both themes |
| AC11 | Live: the same question as Sales and as Engineering gives 2 different, correct answers | 🔑 👀 | ✅ | `make live`: `test_s05_ac11_two_profiles_two_answers` passed (Sales sees $480,000; Engineering is told it's hidden) |
| AC12 | `send_to_customer` waits for a person: approve runs it, reject sends the reason back; the wait doesn't count toward the time limit | 🧪 👀 | ✅ | `test_gate_loop.py::test_s05_ac12_*` (5): approve runs, reject returns the reason, no approver = no, the wait doesn't use the time limit · Chrome: real Approve click → outbox file, run completed in 6.1 s |
| AC13 | Harness pane: Guardrails shows Permissions, Never allowed, Human in the loop for the current profile | 👀 | ✅ | Chrome: Guardrails = green Allowed · red Not allowed (tools, hidden data, locked files, hard limits with § badges) · amber Human in the loop |
| AC14 | Questions outside the workspace's scope are refused before the loop runs (and the scope is in the prompt) | 🧪 🔑 | ✅ | `test_scope.py::test_s05_ac14_*` (4) + CloudCo/page tests · `make live` 3/3: "prime minister" and "a poem" refused (0 loop calls, ~$0.00005, ~2 s); an uptime question still answered · Chrome: ⛔ Outside scope line + polite reply |

### S06 · Approvals

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Approval rules come from `workspace.toml`: several per tool, each with an approver role and an optional condition; CloudCo's match the approval chart (§1, §3) | 🧪 | ✅ | `test_gate.py::test_s06_ac1_*` + `test_workspace.py::test_s06_ac1_*` (2) + `test_cloudco_tools.py::test_s06_ac1_cloudco_approvals_match_the_chart`: roles, conditions, order; CloudCo's five rules match chart §1 and §3 |
| AC2 | A matching action pauses the loop until a person decides, once for each approval it needs | 🧪 | ✅ | `test_gate_loop.py::test_s06_ac2_ac7_ac10_*`: the boss, then Sales, each asked in turn; the run waits |
| AC3 | The card shows the action's values, the reason, the rule and the approver role, and counts down to the timeout | 🧪 👀 | ✅ | `test_gate_loop.py::test_s06_ac3_*` (the request carries `timeout_s`, role, step) · Chrome: card shows role, "1 of 2", rule, values, countdown, reason box |
| AC4 | Approve → it runs; the result goes back to the model | 🧪 | ✅ | `test_gate_loop.py::test_s05_ac12_approved_actions_run` and the two-approval test: both approved → the tool runs |
| AC5 | Reject → the reason goes back to the model, it adapts, and approvals still to come are not asked | 🧪 | ✅ | `test_gate_loop.py::test_s06_ac5_*`: the boss rejects, Sales is never asked, the model reads who and why |
| AC6 | No answer in time → treated as Reject | 🧪 | ✅ | `test_gate_loop.py::test_s06_ac6_*`: a time-out (patched to 0.05 s) is a no |
| AC7 | Each card names who must decide ("Approve as CFO") and the answer is recorded with that role. A demo of the mechanism, not a login (D-87) | 🧪 👀 | ✅ | `test_gate_loop.py::test_s06_ac2_ac7_ac10_*` (request names the role; decision records it) · Chrome: "Approve as CFO", "Demo: you are acting as CFO" |
| AC8 | Sending anything to a customer always needs the Sales approval, on top of any other | 🧪 | ✅ | `test_cloudco_tools.py::test_s06_ac1_*`: every send ends with Sales, up to and including a 20% discount + Net 60 |
| AC9 | `ask_human` lets the model pause to ask a question; the answer goes back to it | 🧪 👀 | ✅ | `test_gate_loop.py::test_s06_ac9_*` (2): the answer returns to the model; no answer is not a crash · Chrome: question card · live test written (`test_live_approvals.py`), not run: quota |
| AC10 | The outbox file records who approved (role), when, and which rule asked | 🧪 | ✅ | `test_cloudco_tools.py::test_s06_ac10_*` + loop test: the outbox file lists role, time and rule |
| AC11 | Page: "Waiting for CFO", the card after the answer, and "Nothing ran" after a rejection | 👀 | ✅ | Chrome (synthetic events): "Waiting for CFO · 1 of 2", "✓ Approved as …", "✗ Rejected as CFO" + "Nothing ran. The agent has been told why." |
| AC12 | Live: 25% discount → CFO rejects ("max 20%") → the agent proposes 20% → CFO approves → Sales approves the send | 🔑 👀 | 🟦 |  |

### S07 · Memory

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Each task is saved as an append-only file; model steps are saved exactly | 🧪 | 🟨 | `test_memory.py::test_s07_ac1_*` (3) + `test_server_sessions.py`: exact steps incl. signatures, a crash loses one line, a follow-up resends the history |
| AC2 | The sidebar lists the profile's conversations, newest first, each titled by its topic: open, continue, delete | 🧪 👀 | 🟨 | `test_memory.py::test_s07_ac2_*` (2) + `test_server_sessions.py::test_s07_ac2_*` (2) · Chrome: Your work lists conversations by topic, open restores the thread, two-click delete removes the file |
| AC3 | After a server restart the task resumes; an unfinished tool call is marked cancelled, not re-run | 🧪 | 🟨 | `test_memory.py::test_s07_ac3_*`: an unfinished call gets a "cancelled" result; `test_server_sessions.py::test_s07_ac3_*`: a second server over the same folder resumes |
| AC4 | `save_note` keeps notes per profile; they enter the prompt next time (capped at ~2,000 tokens) | 🧪 | 🟨 | `test_notes.py` (9): dated lines per profile, newest kept under the cap, notes last in the prompt, read once per task, `save_note` open to every profile |
| AC5 | Big tool output → start + end + marker | 🧪 | 🟨 | `test_trimming.py::test_s07_ac5_*` (2): start + end + marker, cut before it reaches the model |
| AC6 | Old tool results → one-line stubs, in batches past 50% | 🧪 | 🟨 | `test_trimming.py::test_s07_ac6_*` (3): old results become stubs in a batch, newest stay, idempotent; the loop sends the pruned history and emits `context_trimmed` |
| AC7 | Summarize only if still past 70% after pruning | 🧪 | 🟨 | `test_trimming.py::test_s07_ac7_*` (2): pruned and under 70% → no summary; still over → one summary call |
| AC8 | Model steps are never edited; a call never loses its result | 🧪 | 🟨 | `test_trimming.py::test_s07_ac8_*` (2): model steps identical (signatures too), no step removed, the current turn untouched |
| AC9 | Page: context fill bar, trimming card, cached tokens shown | 👀 | 🟨 | Chrome (synthetic run): "Trimmed context" line, Context 8,200 / 20,000 (41%) bar, Cached tokens, Memory pane shows the window |
| AC10 | Live: in round 2 the agent recalls round 1's decisions | 🔑 👀 | 🟦 |  |
| AC11 | A conversation gets a short topic title from a small model call; if that fails, the first words of the task | 🧪 🔑 | 🟨 | `test_memory.py::test_s07_ac11_*` (3) + `test_server_sessions.py`: model title, first-words fallback · live test written, not run: quota |

### S08 · Proof and demo

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Swap test: the second workspace runs; `git diff src/agentic_harness/` is empty | 🧪 🔑 | 📝 |  |
| AC2 | Replay plays a saved task on the page with zero model calls | 🧪 | 📝 |  |
| AC3 | X-ray shows, per step: what Gemini saw, tool input/output, the gate's decision, cost | 👀 | 📝 |  |
| AC4 | Mini loop ring lights the part acting right now | 👀 | 📝 |  |
| AC5 | Run summary card: steps, tools, approvals, blocks, tokens, cost, time | 👀 | 📝 |  |
| AC6 | Each harness part can be switched off for recording, only in demo mode, with a red banner | 🧪 👀 | 📝 |  |
| AC7 | Eval set: 6 tasks with check scripts, 3 runs each, own budget cap | 🧪 🔑 | ➡️ | Moved to S10 (D-108) |
| AC8 | Eval pass rate ≥ 5 of 6 | 🔑 | ➡️ | Moved to S10 (D-108) |
| AC9 | Export a saved run as a static page: no backend, no key, no API calls | 🧪 📄 | 📝 |  |
| AC10 | Demo mode: big type, slower cards, short output | 👀 | 📝 |  |
| AC11 | A clean 1080p recording in 16:9, 1:1 and 4:5 | 👀 | 📝 |  |

### S09 · Production readiness

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | A 429/503 on the main model moves the run to the next fallback model at once; the event names both models and the error | 🧪 | 📝 |  |
| AC2 | Each call is priced by the model that answered; other errors still fail the run | 🧪 | 📝 |  |
| AC3 | Every step writes a checkpoint (steps, cost, time) to the conversation file | 🧪 | 📝 |  |
| AC4 | A conversation whose last turn never finished can be resumed; the step count and cost carry on from the checkpoint | 🧪 👀 | 📝 |  |
| AC5 | Resume never re-runs a tool call that had no result (it stays "cancelled") | 🧪 | 📝 |  |
| AC6 | Harness pane has 7 sections; Models shows every role's model, effort and the fallback chain | 🧪 👀 | 📝 |  |
| AC7 | Environment shows where tools run, read/write paths, network, what persists, and says "by convention" / "not restricted" where true | 👀 | 📝 |  |
| AC8 | State & Memory separates run state from long-term memory; Tools shows what a helper gets and doesn't | 👀 | 📝 |  |
| AC9 | Live: with the main model out of quota, a run finishes on the fallback | 🔑 👀 | 📝 |  |
| AC10 | Claude Haiku 5.5 and Sonnet 5.5 are in the model menu when `ANTHROPIC_API_KEY` is set; a run on either works through the same loop, tools, gate and approvals | 🧪 👀 | 🟨 | `test_anthropic_model.py` (a run on Claude goes through the same loop; the menu offers Claude only with its key; a Claude name gets the Claude client) · Chrome: Claude Haiku 5.5 / Sonnet 5.5 in the menu, no run made |
| AC11 | The loop's steps translate to Claude's messages and back; Claude's thinking blocks are kept exactly as received; switching provider mid-conversation drops only the other provider's thinking | 🧪 | 🟨 | `test_anthropic_model.py::test_s09_ac11_*` (4): steps ↔ messages, thinking passed back unchanged, each provider's thinking left out for the other |
| AC12 | The effort menu maps to Claude's `output_config.effort` (Auto sends nothing); each Claude call is priced from `pricing.toml` | 🧪 | 🟨 | `test_anthropic_model.py::test_s09_ac12_*` (2): effort → `output_config.effort`, Auto sends nothing; cache reads and 1.25× writes priced |
| AC13 | On a Claude run, the helper, off-topic check, titles and summaries use Claude Haiku 5.5 | 🧪 | 🟨 | `test_anthropic_model.py::test_s09_ac13_*`: on a Claude run, helper, check, summary and title models are all `claude-haiku-5-5` |
| AC14 | No test and no `make live` run calls Anthropic: the key is used only for runs the person starts on the page or with the CLI | 🧪 | 🟨 | `test_anthropic_model.py::test_s09_ac14_*` (2): key read from its own name and shown as `***`; no live test names a Claude model |

### S10 · Evals

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | 16 golden cases load and validate; a bad case names its field | 🧪 | ✅ | `tests/evals/test_cases.py::test_s10_ac1_*` (13): 16 cases, 5 conversations; a bad field is named |
| AC2 | Each case runs through `create_harness` with a scripted approver, its own memory folder and trace folder; multi-turn cases resend the history | 🧪 | ✅ | `tests/evals/test_runner.py::test_s10_ac2_*` (4): real `create_harness`, scripted CFO reject, history resent, off-topic refused; sends land in the eval's workspace copy, never the real outbox |
| AC3 | Replay: a saved trace (with a sub-agent) becomes DeepEval spans and test cases with zero model calls | 🧪 | ✅ | `test_replay_and_checks.py::test_s10_ac3_*` (4): a saved Claude Haiku run with the clause-reviewer becomes a nested trace + test cases; zero model calls (spikes 1 and 2 also checked with the network blocked) |
| AC4 | The 3 code metrics score pass and fail cases correctly on recorded traces | 🧪 | ✅ | `test_replay_and_checks.py::test_s10_ac4_*` (5): tool correctness, guardrails (blocked, rejected, flagged, scope, across turns) and required words, pass and fail |
| AC5 | The 9 judged metrics run through DeepEval with our judge; Gemini 429/503 → Claude Haiku, named per score; no usable judge → a clear stop | 🧪 | ✅ | `test_judge_and_scoring.py::test_s10_ac5_*` (6): 9 DeepEval metrics run with the judge; Gemini 429 → Claude Haiku for the rest, named per score; no key or a 400 → the eval stops |
| AC6 | 3 runs per case, pass only if all 3 pass; the eval's own budget cap stops it with a named reason; Gemini out of quota → the agent moves to Claude Haiku (D-116) | 🧪 | ✅ | `test_runner.py::test_s10_ac6_*` (8): pass^3; the cap, Stop and judge failures stop it with a named reason; a Gemini 429 hands the agent to Haiku and reruns that run; Haiku out too → plain stop reason; the plan names the fallback only with a Claude key and a Gemini agent |
| AC7 | Result JSON saved; telemetry off; DeepEval reads no `.env`; no key in any result or trace | 🧪 | ✅ | `test_runner.py::test_s10_ac7_*` (4): result JSON with the catalog, key replaced by `***`; a subprocess shows telemetry off and `.env` not read; CLI plan and bad cases |
| AC8 | No test calls Gemini or Anthropic; `make check` passes with coverage back to 85% | 🧪 | ✅ | `make check`: 354 tests, coverage 91.2% (gate 85%); stand-in agent and judge only, no Gemini or Anthropic call |
| AC9 | Evals page: summary, metrics table (Metric · What it checks · Score), case rows that open to runs and reasons, past evals; baseline test passes | 🧪 👀 | ✅ | `test_server_evals.py::test_s10_ac9_*` (2) + `test_page_baseline.py::test_s10_ac9_ac10_*` · Chrome on :8000 with the 2026-11-11 live result: summary card, 12-row metrics table, opened case with tool calls and per-metric reasons, past evals |
| AC10 | Run button: dialog with estimate and what happens if Gemini runs out, live progress, Stop, one eval at a time; only the fixed command | 🧪 👀 | ✅ | `test_server_evals.py::test_s10_ac10_*` (5): only `python -m evals.run` with checked cases, runs, priced model; Stop; one at a time · Chrome 2026-11-11: a live 2-case run filled rows and stopped on the 429 with a named reason |
| AC11 | Live: a full eval (16 × 3) finishes; ≥ 14 of 16 cases pass | 🔑 👀 | 🟦 |  |

### S11 · Plan and Verify

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | `write_plan` stores the list in run state and emits `plan_updated`; helpers don't get it | 🧪 | 🟨 | `test_plan_verify.py::test_s11_ac1_*` (2): list kept, `plan_updated`, whole list sent back; schema without bounds/defaults · `test_cloudco_checks.py::test_s11_ac1_ac10_*`: helpers don't get it |
| AC2 | The plan is saved as steps; Resume and replay rebuild it | 🧪 | 🟨 | `test_s11_ac2_*` (2): rebuilt from saved steps; a rejected update is not the plan. (Resume itself is S09-AC4, not built: it will use `latest_plan`.) |
| AC3 | Trimming never stubs the newest plan result | 🧪 | 🟨 | `test_s11_ac3_trimming_never_stubs_the_newest_plan` |
| AC4 | An answer with open items gets one reminder; the second time it finishes, the plan shown incomplete | 🧪 | 🟨 | `test_s11_ac4_*` (2): one reminder then finish, plan shown open; a light question makes no plan and runs no check |
| AC5 | Skipped needs a note, or the tool returns an error | 🧪 | 🟨 | `test_s11_ac5_*` (2): a skip without a note is refused; bad items are named |
| AC6 | VERIFY runs the workspace's checks after the draft, before `run_finished` | 🧪 | 🟨 | `test_s11_ac6_*` (3): checks after the draft, before `run_finished`; the record holds a helper's calls; a broken check is shown, never sent back |
| AC7 | A failed check sends the failures back once; a second failure → the answer plus "Not verified" | 🧪 | 🟨 | `test_s11_ac7_*` (3) + `test_cloudco_checks.py::test_s11_ac7_wrong_approver_is_caught_and_corrected` (the demo: Finance → CFO) |
| AC8 | CloudCo's gates (Every Change Covered, Right Approver, No False Sent), each with a pass and a fail case; Citations is now an online metric (D-150) | 🧪 | 📝 | reset 2026-11-12 (D-150): `test_cloudco_checks.py::test_s11_ac8_*` pass again on the 3 gates; waits for your check |
| AC9 | `src/agentic_harness/` stays domain-free (existing test) | 🧪 | 🟨 | `tests/architecture/test_generic_harness.py` passes: no domain word in `planning.py` / `verify.py` |
| AC10 | Pane: Plan & Verify section with check switches; a switched-off check doesn't run | 🧪 👀 | 🟨 | `test_s11_ac1_ac10_wiring_*`: a switched-off check doesn't run; pane data lists 5 checks · Chrome 2026-11-12: Plans row, Harness Tools (4, each switchable), Verification section with switches · `test_s11_ac10_the_pane_lists_the_harness_tools_and_each_can_be_switched_off` |
| AC11 | Chat: live To-Do card and Checks card; old conversations show both | 👀 | 🟨 | `test_s11_ac11_a_saved_turn_keeps_its_plan_and_checks` · Chrome 2026-11-12 with sample events (no model): To-Do card, "2 Failed → Retried → Passed" with draft folded, red Not Verified |
| AC13 | Answer style always in the prompt; AGENTS.md has no own "How to answer" | 🧪 | 🟨 | `test_cloudco_checks.py::test_s11_ac13_the_answer_style_is_always_in_the_prompt` (both profiles; AGENTS.md has none of its own) · `test_s02_ac11_*`, `test_s04_ac11_*` updated |
| AC14 | ~~Answer Format check~~ → the online metric Style & Format, LLM as Judge against `answer-style.md` (D-150) | 🧪 | 📝 | reset 2026-11-12: the code check is removed; `test_online_evals.py::test_d149_*` cover the judged metric |
| AC15 | Page renders headings, nested lists and source badges; no HTML injection | 🧪 👀 | 🟨 | `test_page_baseline.py::test_s11_ac15_*` + `test_s01_ac13_text_is_never_inserted_as_html` · Chrome 2026-11-12: a sample answer with 7 badges, 2 nested lists, brackets dropped |
| AC12 | Live: "Is Net 60 OK?" makes no plan; "review ShopCo's contract and send it" plans and finishes every item | 🔑 👀 | 🟦 |  |

### S12 · Guarded actions and identity

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | An action check runs after the hard limits and before anyone is asked; a failure returns "Not sent: …" and no one is asked | 🧪 | 🟨 | `test_action_checks.py::test_s12_ac1_*` (3): a failed check stops the call before anyone is asked; a pass is shown, then people; a blocked call never reaches it |
| AC2 | Body Matches Terms passes the real outbox emails and fails a body saying 20% when the argument says 15%; a refusal in the body isn't an offer | 🧪 | 🟨 | `test_body_matches_terms.py::test_s12_ac2_*` (8): six real outbox emails labelled by hand (one real catch: a 24-month cap the CFO never saw), a 20%/15% mismatch, a refusal isn't an offer |
| AC3 | A hard-limits step shows each rule with its value and line, before the approval card | 🧪 👀 | 🟨 | `test_gate_loop.py::test_s05_ac12_approved_actions_run` (limits_checked before the approval, each rule's value and line) · `test_action_checks.py::test_s12_ac1_a_blocked_call_*` · page: `test_s12_ac3_ac4_ac5_*` |
| AC4 | The email card appears under its send step, in run order | 👀 | 🟨 | Chrome 2026-11-12 with replayed events: memory read → send → hard limits held → checked before sending → the email inside the run's steps |
| AC5 | The injection step names the response; the memory step lists the facts read | 🧪 👀 | 🟨 | `test_cloudco_checks.py::test_s12_ac5_the_context_says_which_facts_it_read` · page: `test_s12_ac3_ac4_ac5_*` (injection wording, memory step) |
| AC6 | Personas from `workspace.toml`; the server refuses an approval from the wrong role | 🧪 | 🟨 | `test_identity.py::test_s12_ac6_*` (5): people from `workspace.toml`, a role nobody has is refused at load, the server refuses a wrong role and accepts the right one, the page gets the people |
| AC7 | The card offers "Switch to <persona>"; the run keeps waiting; the thread stays | 👀 | 🟨 | Chrome 2026-11-12: Priya on the CFO card sees "This one needs the CFO" and **Switch to Dana Whitfield (CFO)**; switching flips the card to "Approve as Dana Whitfield" and the picker follows (replayed events; the run keeps waiting by design) |
| AC8 | The sender can give the "any message" sign-off; the CFO card needs the CFO | 🧪 | 🟨 | `test_identity.py::test_s12_ac8_ac9_*`: Priya signs off the send, Elena and Dana answer their own cards · the role rule itself: `test_s12_ac6_the_approvals_object_refuses_a_wrong_role` |
| AC9 | The outbox and trace record the person and the role | 🧪 | 🟨 | `test_identity.py::test_s12_ac8_ac9_*`: the outbox and the send tool's result name each person; `approval_decided` carries `person` |
| AC10 | Live: a 25% discount send waits for Dana (CFO); Priya can't approve it | 🔑 👀 | 🟦 |  |
| AC11 | `draft_reply` saves a mail-shaped file to the run's task folder, addressed to the customer's contact; never the outbox | 🧪 | 🟨 | `test_drafts_and_person.py::test_s12_ac11_*` (3): a task file "To: Maya Chen, ShopCo", no outbox; every customer has a contact; Sales may draft, Engineering may not |
| AC12 | The picked person reaches the run: the context says who the agent helps; an unknown person is refused | 🧪 | 🟨 | `test_drafts_and_person.py::test_s12_ac12_*` (4): context line, harness wiring, server 400 on an unknown person, the page sends the person |
| AC13 | A task file with mail headers shows as a **Draft** email card under the answer; `>` lines show as a quote | 🧪 👀 | 🟨 | `test_drafts_and_person.py::test_s12_ac13_*` (2) · 👀 waits for your run |
| AC14 | Sales prompts: concerns vs policy first, then a question; a draft only after agreement, then "send it to <contact>?" | 🧪 🔑 👀 | 🟨 | `test_drafts_and_person.py::test_s12_ac14_*` (2): prompts and golden cases · 🔑 live behaviour waits for your run |

### S13 · Guided Tour

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | `tour.toml` loads; every step has an id, a caption and a valid "play until" event; every run and clip it names exists | 🧪 | 🟨 | `test_tour.py::test_s13_ac1_*` (9): the tour loads; caption, `until`, order, missing run, no tour, helper events, skipped kinds, the server route |
| AC2 | The export is one folder: relative asset paths, no `/api/` call in tour mode, nothing key-shaped in any file | 🧪 | 🟦 |  |
| AC3 | `tour.js`, `export.py` and the player know no domain | 🧪 | 🟨 | `test_generic_harness.py` covers `tour.py` and `tour.js` (no domain words) |
| AC4 | The replay draws the same cards as the live run | 👀 | 🟨 | 👀 Chrome: the replay draws the live cards (context, memory, scope, tools, helper lane, flagged line, checks failed → fixed, hard limits, body check, 4 approvals, sent email, run summary); waits for your look |
| AC5 | Voice leads; Pause, Back, Next and Mute work; the caption is always shown | 👀 | 🟦 | reset: the guide redesign (D-178) |
| AC6 | Each step opens and highlights its Harness pane section | 👀 | 🟨 | 👀 Chrome: each step opens and lights its part; step 2 and 10 light all six |
| AC7 | It plays from a subfolder with zero model or API calls | 👀 | 🟦 |  |
| AC8 | Audio total ≤ 15 MB; a step without a clip advances on reading time | 🧪 | 🟨 | `test_tour.py::test_s13_ac8_*` (4): reading time without a clip, a new take replaces the old, clip checks, 15 MB in all |
| AC9 | It works at phone width | 👀 | 🟨 | 👀 Chrome at 390 px: no sideways scroll, the pane stays closed, the tour bar fits |

### S14 · Public Tour Mode

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | Public mode refuses every change (POST, PUT, PATCH, DELETE → 403), even with the page header; a refused clip leaves the voice alone | 🧪 | 🟨 | `test_public_mode.py::test_s14_ac1_*` (12) |
| AC2 | The page, tour and clips are served under an allowed name; other names get 400; extra names don't count in local mode; clips are cached by version | 🧪 | 🟨 | `test_public_mode.py::test_s14_ac2_*` (5) |
| AC3 | Public mode holds no key, whatever the environment says; the switch and `PORT` must be clear | 🧪 | 🟨 | `test_public_mode.py::test_s14_ac3_*` (8) |
| AC4 | Public mode listens on every address; local mode stays on 127.0.0.1 even with `$PORT`; `--port` wins | 🧪 | 🟨 | `test_public_mode.py::test_s14_ac4_*` (3) |
| AC5 | Health reports the mode; the page opens on the tour with the read-only note and hides what it can't do | 🧪 👀 | 🟨 | `test_public_mode.py::test_s14_ac5_*` (3) · 👀 Chrome: opens on Start Tour, note + View the Code, no Exit, voice plays, no console errors |
| AC6 | Local mode is unchanged | 🧪 | 🟨 | all 596 offline tests pass (`make check`, 89% coverage) |
| AC7 | Hosted on Cloud Run: the same checks pass against the live URL; min 0, max 1; only the owner secrets mounted | 👀 | 🟨 | 👀 run.app URL: reads 200, writes 403, key missing, 10 clips; min 0, max 1, no secrets (before D-190) |
| AC8 | The owner passphrase keeps Claude's key (never Gemini's) in public mode; it must be 20+ characters; it means nothing locally | 🧪 | 🟨 | `test_public_mode.py::test_s14_ac8_*` (3) |
| AC9 | Visitors still can't run; the owner runs on Claude only and reaches nothing but run and approval; health opens Claude for the owner only | 🧪 👀 | 🟨 | `test_public_mode.py::test_s14_ac9_*` (4) · 👀 Chrome, local: ?owner box, wrong passphrase refused and not kept, right one opens Claude models + composer, Lock forgets it |
| AC10 | Ten wrong passphrases lock the unlock; no Claude key means no owner mode | 🧪 🔑 | 🟨 | `test_public_mode.py::test_s14_ac10_*` (2) · 🔑 your first live owner run on the hosted copy |

## Product goals

| ID | Goal | Status |
|---|---|---|
| P-SC1 | Each harness part is its own module | ⬜ |
| P-SC2 | `src/agentic_harness/` contains zero domain words | 🟨 guarded by a test from day one |
| P-SC3 | A second workspace runs with zero harness changes | ⬜ |
| P-SC4 | All offline tests < 10 s | 🟨 6.3 s today (96 tests) |
| P-SC5 | ≥ 14 of 16 eval cases pass, all 3 runs (S10) | ⬜ |
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
| 2026-11-10 | You approved S05 ("go ahead with the build") with changes: two profiles (D-74), human approval for `send_to_customer` now (D-79), Guardrails pane in three parts. S05-AC1–AC13 → 🟦. Choices D-75–D-80. |
| 2026-11-10 | S05-AC1–AC13 → 🟨: 220 offline tests; live AC11 passed; Approve tested with a real click. Found and fixed: the input box covered the Approve button. Guardrails pane redesigned as three colour-coded cards at your request. |
| 2026-11-10 | You verified S05 ("s5 looks good to me"): S05-AC1–AC13 → ✅. Tagged `stage-5`. Your report: an off-topic question ("who is the prime minister of India") was answered; a scope guardrail is needed. |
| 2026-11-10 | You chose "prompt + input check" for the scope guard (D-81). S05-AC14 added → 🟦. |
| 2026-11-10 | S05-AC14 → 🟨: off-topic tasks refused before the loop (prompt + Flash-Lite check, D-81); 227 offline tests, 3 live tests passed. |
| 2026-11-10 | At your request: "Contract Assistant" renamed "Contract Agent"; Guardrails cards condensed (one line per rule, shorter rule labels, details on hover). No status change. |
| 2026-11-10 | Your report: "pull in customer details" was refused although the check said IN. Cause: the prompt's quoted refusal, copied by Flash-Lite. Fixed (D-81 change); new live test `test_s05_ac14_vague_requests_on_the_job_are_not_refused`; live scope tests 4/4 passed three times. S05-AC14 stays 🟨. |
| 2026-11-10 | At your request: plain answers instead of Summary/Decision/Sources (D-82); `lookup` → `lookup_customer_record`, clearer Activity lines (D-83). S02-AC11 evidence now means plain answers with sources; S05-AC14 stays 🟨. Open since before today: S03-AC11 and S04-AC10 live (the agent skips `review_contract`; fails on the committed code too). |
| 2026-11-10 | You verified the scope guard, plain answers and the new Activity lines: S05-AC14 → ✅, S05 14/14 verified. |
| 2026-11-10 | Found the cause of the `review_contract` failures: the S05 allow-list hid `load_skill` and `delegate_task` (D-84). Fixed; the agent now reads the contract (answers list five changes) but live answers still left out clause IDs, so the skill now asks for them. Live re-check blocked: Flash-Lite free tier hit 500 requests/day. S03-AC11, S04-AC10 stay 🟨. Also: no "Run complete" line; metrics under the answer; animated profile cards. |
| 2026-11-10 | At your request: effort picker (Thinking: Auto / Low / Medium / High = Gemini `thinking_level`, D-85) next to the model menu; the final answer now ends in a run-summary card (count-up numbers, token split bar) instead of chips. Offline tests 230; checked in Chrome with a synthetic run (live quota spent). |
| 2026-11-10 | At your request: CloudCo logo (made up) and an agent menu at the top of the sidebar, loop mark moved to the Harness pane, "agentic-harness" now a footer line (D-86); run summary is a visible pill again. 232 offline tests; checked in Chrome. |
| 2026-11-10 | S06 re-briefed; you approved option A (role-play approver, D-87). S06-AC1–AC12 → 🟦. Choices D-87–D-89. |
| 2026-11-10 | S06-AC1–AC11 → 🟨: 243 offline tests; approval cards, the question card and the rejection path checked in Chrome with synthetic events. AC12 (and the live half of AC9) stays 🟦: the Gemini free-tier quota is spent (retry in ~15 h); `tests/live/test_live_approvals.py` is written. Walkthrough in `docs/stage-6.md`. |
| 2026-11-10 | You verified S06 ("looks good"): S06-AC1–AC11 → ✅. AC12 stays open until the live run (quota). Moving to S07. |
| 2026-11-10 | You approved the S07 brief ("go ahead and build") and asked that conversations appear in the left pane, titled by topic. S07-AC1–AC11 → 🟦 (AC11 new). Choices D-90–D-95. |
| 2026-11-10 | S07-AC1–AC9, AC11 → 🟨: 284 offline tests; Your work, trimming card, Context bar and Memory pane checked in Chrome (synthetic events). AC10 (round 2 recalls round 1) stays 🟦: live, waits for Gemini quota; `tests/live/test_live_memory.py` written. Also at your request: a one-line description under the agent's name. Walkthrough in `docs/stage-7.md`. |
| 2026-11-10 | Gap review (your 15 questions): answered from the code; S09 · Production readiness added after S08 (model fallback, checkpoint + Resume, 7-section pane). You chose fallback + Resume, not the environment scan or per-role effort. S09-AC1–AC9 → 📝. Choices D-97–D-100. |
| 2026-11-10 | At your request (D-101): Memory pane split into Short-term and Long-term; pruning/summarizing moved to Context → Context management; new left-lane **Memory** page lists facts per profile with Forget. 288 offline tests; checked in Chrome (sample facts seeded, then forgotten through the page). |
| 2026-11-10 | Claude Haiku 5.5 and Sonnet 5.5 added to S09 at your request (D-102–D-104): background calls on a Claude run use Haiku (your pick); never in tests or `make live`. You put `ANTHROPIC_API_KEY` in `.env` (git-ignored; added at your request). S09-AC10–AC14 → 📝. |
| 2026-11-10 | Claude built early at your request ("implement it asap"): S09-AC10–AC14 → 🟨. 304 offline tests, none calls Anthropic; the menu checked in Chrome without a run. Not done: the server-side refusal fallback for Sonnet 5.5 (needs a beta; untestable without spending your key). The rest of S09 stays after S08. |
| 2026-11-10 | Debugged two Claude Haiku runs ("review the ShopCo contract and send it"): the harness worked; CloudCo's text misled the agent. (1) The customer record had no contract ID, (2) the skill and the reviewer's description read as "you must paste the markup", (3) the reply skill said "never send". Fixed in the workspace only: the customer record lists contract IDs; the reviewer takes just an ID; sending is allowed when asked (approval still applies). 304 offline tests. Not re-run live (your key). |
| 2026-11-11 | Debugged a Claude run that ended in "Cannot read properties of undefined (reading 'input')": the helper ran on Claude Haiku as designed and the run finished on the server; the page crashed on the helper's first reply (its lane lacked the token-split counters added with the run summary), so the answer never showed. Fixed; the pane now shows helpers' real model on a Claude run; the hand-off line reads "Handed the job to the clause-reviewer sub-agent" with a SUB-AGENT tag. Checked by replaying the failed run's trace into the page (no model calls). |
| 2026-11-11 | Your report: Engineering, asked to send, gave a long answer with contract terms. Debugged: send_to_customer was hidden (correct) but the agent wasn't told what to say; the terms came from an earlier turn where the reviewer returned payment clauses as free text (field masking only covers structured fields). Fixed: each profile is told what it can't do and the one sentence to say (D-105); the run's tool list now shows only what the profile was offered. The free-text leak is open: your choice next. |
| 2026-11-11 | Your pick: filter in the tool (D-106). Tools now get the asking profile (helpers get their caller's); CloudCo's contract tool leaves out fee, discount and payment clauses for Engineering. 306 offline tests. |
| 2026-11-11 | Your report: Engineering's contract review still showed a price lock, Net 60 and liability. Debugged: the contract filter hid only §3/§4, `search_policy` didn't filter at all, the note named the hidden topics, and Engineering ran Sales' review skill. Fixed (D-107, your picks): technical sections only (allow-list), technical policy only, a neutral note, and Engineering's own `technical-review` skill. 307 offline tests; the leaked run's tool calls replayed offline with no leaked words. |
| 2026-11-11 | You approved S10 · Evals (DeepEval, 12 metrics in its categories, Gemini judge with Claude Haiku fallback, a Run button, a dedicated `evals/` folder) and asked to build it now, before the S07 check. S10-AC1–AC11 → 🟦; S08-AC7/AC8 moved to S10. The replay spike passed (AC3 evidence). Your report of a refused follow-up ("who is the point of contact": the scope check reads only the newest message) became eval case `follow-up-in-scope`, not fixed yet at your request. D-108–D-115. |
| 2026-11-11 | S10-AC1–AC10 → 🟨: eval engine (`evals/`), server endpoints and the Evals page; 354 offline tests, coverage 91% (gate back to 85%, D-33). Found while building: approved sends in eval runs wrote to the real outbox (now a workspace copy per eval; 4 stand-in files removed); DeepEval's pytest plugin auto-loaded before our privacy switches (now off). At your request: the sidebar's page links restyled (gliding highlight, colour dot per page). AC11 (live 16 × 3) waits for your run. |
| 2026-11-12 | Your feedback on the Evals page. (1) When Gemini runs out, the eval's agent moves to Claude Haiku and the run starts again (D-116); stop reasons are plain words. (2) The page is simpler: one Metrics table (Metric · What it checks · Score), only the 12 metrics we score; a summary card; case rows that show the question and open to the runs and each metric's reason; Past evals. The cases × metrics grid, chips and greyed rows are gone. S10-AC6/AC9/AC10 → 📝 → 🟨 (tests below). One server on :8000 again (the old one predated S10). |
| 2026-11-12 | Your questions: why 2 cases, what it costs. The page lists all 16 cases (11 single, 5 multi), run or not; the Run dialog ticks a core set (6 + 3, scores all 12 metrics); the dialog shows cost to you ($0 on Gemini's free tier, ≈ $0.10 at most for the core set if Haiku does it all); the summary shows what Claude cost. Dialog's agent defaults to Gemini. S10-AC1/AC6/AC10 stay 🟨 (tests below). |
| 2026-11-12 | Your feedback on the Evals page for leaders. The summary is a hero: pass-rate ring, one sentence, tiles (tests completed, safety rules held, cost to you with who pays, time), agent and judge as actually used. The raw stop banner is gone. Sidebar: Your work and the page links fold, remembered per browser; the page links got a heading (name is yours to pick). |
| 2026-11-12 | Your requests: pick the judge model in the Run dialog (animated menu, like the chat's); sidebar headings Profiles, Chats ("New conversation") and Workspace, all foldable; hero footer: Agent and Judge only. 363 offline tests. |
| 2026-11-12 | Your rule: UI names in Title Case, sentences in sentence case (added to `CLAUDE.md`, test on metric and case-group names; page labels renamed). Evals card opens ready (no stale verdict) with the Agent and Judge menus on it; a past eval opens dated. |
| 2026-11-12 | Golden Dataset page (your request): the 16 golden cases as cards with their right answers and rules, filterable; no scores. |
| 2026-11-12 | D-117: Next Run cost panel (Agent, Judge, You Pay cards; free-limit meters; learns from your last 5 evals). "Synthetic Data" tag from a workspace setting. 368 offline tests, coverage 91%. |
| 2026-11-12 | First full eval reviewed (2 of 9; 5 of 7 failures were ours). D-118: Not Scored / Not Applicable, Turn Faithfulness dropped, clean judge trace, scope check reads the last exchange, reply skill always tries to send; page: activity panel, times, clear rings, Reset, delete, folded groups. 377 offline tests, coverage 92%. |
| 2026-11-12 | The eval with a Claude Sonnet judge stopped at the $0.50 cap after 7 of 9 tests ($0.57). Your call: the cap is now $3 (D-113 changed). |
| 2026-11-12 | A Sonnet-judged eval froze 20+ min (no time limit on judge calls; Stop only between tests; a reload lost the run). D-119: time limits, a Stop that always works, pages follow a running eval, stall warning. You ended the stuck process. 383 offline tests, coverage 91%. |
| 2026-11-12 | Your chat report: approvals asked CFO first and Sales last, and after all approved the agent said it still needed approval. D-120: Sales → Engineering → Finance → CFO; the send tool says "sent" and who approved. 384 offline tests. |
| 2026-11-12 | Your report: Fable says task decomposition and self-verification are missing. You approved the S11 · Plan and Verify brief (model decides when to plan; pane + chat; code checks only). S11-AC1–AC12 → 🟦. Choices D-121–D-128. Build waits on S10: verify or waive it. |
| 2026-11-12 | You verified S10 ("S10 is good, build S11"): S10-AC1–AC10 → ✅; AC11 (live 16 × 3) stays 🟦. S11 build started. |
| 2026-11-12 | S11 harness core built (tests first): `planning.py` (update_plan), `verify.py` (checks, Plan Complete, one retry), loop VERIFY step, trimming pins the newest plan, gate opens update_plan. `tests/unit/test_plan_verify.py` 15/15; 399 offline tests pass. Not yet: wiring in `create_harness`/workspace, CloudCo `checks.py`, pane and chat cards, eval cases. S11 checks stay 🟦 until the rest is in. |
| 2026-11-12 | S11-AC1–AC11 → 🟨: `make check` 407 tests, coverage 91.2%; pane and cards checked in Chrome with sample events. Golden set 16 → 18 (`light-question-no-plan`, `review-and-send-plans`). Changed while building (spec Changes): Plan Complete is a check (one mechanism), the note is a `[Harness check]` text, No False "Sent" checks both ways. AC12 (live) stays 🟦. Walkthrough in `docs/stage-11.md`. |
| 2026-11-12 | Your review of the pane: Plan and Verify split by when they happen (D-128 changed): Plans row in Agentic Loop, `update_plan` + the harness's other own tools under Tools → Harness Tools, Verification after Guardrails. Your request: the run summary is one horizontal band. Checked in Chrome; S11-AC10 stays 🟨. |
| 2026-11-12 | Your question: why no switch on the harness tools. No good reason: every harness tool now switches off (load_skill off also drops the skill list from the prompt). Checked in Chrome; S11-AC10 stays 🟨. |
| 2026-11-12 | Your report: "Thinks with" read as a fixed model. It did follow the menu, but now says so: **Model** (picked in the chat box, with Thinking level, per run) and **Small Jobs** (Haiku on a Claude run, else Flash-Lite). Checked in Chrome with all 5 models. |
| 2026-11-12 | Your live Sonnet run reviewed: Every Change Covered had silently skipped (gate warning before the JSON), Right Approver's message was cut, repeated and partly wrong ("24-month cap"). Fixed both; every check now shows (skipped ones say why); a card per round in run order (draft → sent back → rewrote → passed); the plan tool says a skill's steps are the recipe, the list the progress. 411 offline tests; replayed in Chrome. |
| 2026-11-12 | You approved the answer-format add-on ("go ahead"): rules always in the prompt, a check, styling on the page. S11-AC13–AC15 → 🟦. D-129–D-131. |
| 2026-11-12 | S11-AC13–AC15 → 🟨: `answer-style.md` always in the prompt, Answer Format check, headings / nested lists / source badges on the page. 414 offline tests; checked in Chrome. AC12 (live) stays 🟦. |
| 2026-11-12 | Your question: why no "create plan". One tool writes the whole list each time (D-122); the name misled, so `update_plan` → `write_plan` everywhere (code, tests, eval case, docs). No status change. |
| 2026-11-12 | Your Haiku run: no plan again (a loaded skill now asks for one, D-121 changed); the reviewer ran twice (the retry note invited it; now it says fix with what you have); the final "Not verified" was our false failure (Right Approver read a whole paragraph; now sentences); Answer Format let paragraphs through (now fails 3+ clauses without a list). Check rounds are compact activity lines (D-128 changed); the summary says "Model Calls". 417 offline tests; replayed in Chrome. |
| 2026-11-12 | Your report: Right Approver failed a correct Haiku answer twice (a list item cut into sentences). Fixed: claims, not lines or sentences; Answer Format asks a source only of decisions; `tests/unit/test_real_answers.py` checks six real answers labelled by hand. Your request: the check round is live (circle, ticking chips, answer after the ticks). 424 offline tests; checked in Chrome. |
| 2026-11-12 | Your request: the check round is a card like the To-Do card (title, count, one row per check ticking ○ → ✓/✗, reasons under failures). Checked in Chrome. |
| 2026-11-12 | Your report: no approvals, and every first draft sent back. Cause 1: the agent never called the send tool (Sales file: "approve first, then send"); fixed in CloudCo's words (D-133), and trimming no longer clears a skill's text. Cause 2: most failures were the checks' (follow-ups, emails, "Nothing has been sent", "wrong person named"); fixed and tested on 14 real answers (D-130). The prompt names the checks (D-132). 439 offline tests. |
| 2026-11-12 | Your request: the sent email shows as an email (headers, body, terms and approvers as chips), not a .md file; "Outbox · not sent" label removed. Your run confirmed the send now happens (Sales approved). 440 offline tests; checked in Chrome with the run's real email. |
| 2026-11-12 | External feedback reviewed against the code (4 of 5 points true, self-approval partly by design) plus your note that the email appears before verification. You approved S12 · Guarded actions and identity (personas on the page; two parts). S12-AC1–AC10 → 🟦. D-134–D-139. Part A building. |
| 2026-11-12 | S12 Part A built: action checks run after the hard limits and before anyone is asked (CloudCo's Body Matches Terms, tested on six real emails), hard limits shown when they hold, the email under its send step, injection response and memory read stated. AC1, AC2, AC3, AC5 → 🟨 (454 offline tests); AC4 waits for the Chrome check. |
| 2026-11-12 | Your request: Claude Opus 5.5 selectable for the agent and in Evals (agent and judge), priced from the claude-api reference ($4 / $20). D-140. Committed and pushed S12 Part A first, as you asked. |
| 2026-11-12 | S12-AC4 → 🟨 (checked in Chrome). Part A (AC1–AC5) built and waiting for your check; Part B (identity) starts after. |
| 2026-11-12 | Your report: card 1 of 4 (Sales) listed the 25% discount, so it read as if Sales approved it. Now one card per person (the CFO once for both rules: 3 steps), each saying what that person approves, with the chain as a stepper. Checked in Chrome. 455 offline tests. |
| 2026-11-12 | Your request: the approval card shows the message and its terms open (no fold, no "See what will be sent"): an email preview and a Term · Offered · Decided by table with your own rows marked. Checked in Chrome. |
| 2026-11-12 | Your request (D-141): the approval card shows where each term started (contract today, customer asked, our offer with ↑/↓, the clause), from a generic workspace hook; CloudCo reads it from the contract files. 457 offline tests; checked in Chrome. |
| 2026-11-12 | Your last run reviewed: execution good (email passed its check, three approvals). Fixed (D-142): after a send, the answer reports the send, not the review (two checks skip it, the style says so, the retry note says write for the person); the sent email shows open under the answer. 460 offline tests. |
| 2026-11-12 | S12 Part B built: personas in `workspace.toml`, a "You Are" picker, the server accepts an approval only from the card's role, the outbox names who approved, a hand-off with a Switch button on cards you can't answer, 30-minute timeout, an Identity fact in the pane. AC6–AC9 → 🟨 (467 offline tests; AC7 checked in Chrome). AC10 (live: a 25% discount send waits for Dana) waits for your run. The planned per-rule "sender may" flag dropped: role match covers it (D-138). |
| 2026-11-12 | Your request: pull a contract without a review. Added `read_contract` (outline, then a section's text; Engineering sees technical sections only) and wording so only a request to review runs a review. D-143. 4 new offline tests (471 pass). Live check ("Show me CT-2207" gives an outline, no review) waits for your run. |
| 2026-11-12 | Your request: demo memory. 4 Sales and 3 Engineering facts seeded (D-144), replacing the old "no bullet points" fact; 2 offline tests. Live demo (Read 4 facts step, Forget one, answers change) waits for your run. |
| 2026-11-12 | Found live: the scope check refused "what is Shopco ?". Fixed (D-145): the check leans to IN and a workspace `knows` list names our customers, contract IDs and people. 4 offline tests (477 pass); live Gemini: weather and poem still refused, 4 record questions pass. Your Chrome check waits. |
| 2026-11-12 | Found live on a pull ("is ShopCo a customer? pull the contract"): no plan, no checks applied, section names only. Fixed (D-146): plan on two-part asks, outline key terms, Records Match and Sections Are Real (0 false failures on the 14 real answers). 486 offline tests. Your re-run waits. |
| 2026-11-12 | Your notes on the pull re-run: Right Approver skips a pull, check names appear only with results, and a "No To-Do plan · the model chose to work directly" line (planning stays the model's choice). D-147. 488 offline tests; checked in Chrome on your run's trace. |
| 2026-11-12 | Your review: more checks is not the answer. Three layers (D-148): Verification keeps only the harm gates (Plan Complete, Every Change Covered, Right Approver, No False Sent, Body Matches Terms); **Online Evals** score every answer after you see it (Groundedness, Hallucination, Context Relevancy, Answer Relevancy, Citations, Style & Format: 2 Code, 4 LLM as Judge in one call, D-149); "Evals" is now **Offline Evals** with a Graded By column and an Answer Quality group (D-151). Records Match and Sections Are Real deleted; Citations and Answer Format became metrics (D-150). S11-AC8, AC14 → 📝. 499 offline tests; live Flash-Lite judge scored all 6 ($0.0010); checked in Chrome on a real pull. Your check waits. |
| 2026-11-12 | Your requests (D-152): Threshold column on both metrics tables; the pane is now **Agent** = Model box (synced model menu) + Harness box holding every part; Online Evals and Offline Evals (with Golden Dataset) under a folded **Observability** sidebar group; Checks link removed. Fixed: sidebar groups after Acting As never folded. 501 offline tests; checked in Chrome. |
| 2026-11-12 | Your request: debug the failing evals, one change at a time, $3 cap. Rounds 0–5 (D-154–D-157, `docs/eval-debug.md`): online judge sees failed calls, Plan Adherence grades the written plan, bookkeeping hidden from the judge, a concrete length rule. 1 → 2 of 7 passed. Paused at $1.43: one run per case is too noisy to measure single changes. |
| 2026-11-12 | Your report on a live run: no email card for the draft, a vague reply with placeholders, no talking through the concerns. You approved the fix plan: S12-AC11–AC14 → 🟦 (D-164–D-166). |
| 2026-11-12 | S12-AC11–AC14 built → 🟨 (529 offline tests, coverage 89%): `draft_reply` writes a Draft email card addressed to the contact, the picked person reaches the prompt, concerns before any draft, golden cases updated (`review-then-confirm`) and added (`agree-then-draft`). Five older tests now check D-165 instead of D-163. Live run and page look wait for you. |
| 2026-11-12 | Your request: the Online Evals card is folded by default; its header ("3 of 6 passed") stays visible and opens it. `test_online_evals_card_is_folded_by_default`; 530 offline tests. |
| 2026-11-12 | Your notes on the approval card: Sales' rule renamed "Sign-Off to Send" (was "Any message to a customer"); the message header shows To, Customer and Contract from the workspace (`{fact, value}` context rows, D-141 extended); every offered term sits in the table ("Within limits" when no one else decides); header values line up; a sign-off on its own lines; after an approval the next card scrolls to its buttons. 531 offline tests. |
| 2026-11-12 | Your point on cost: the online judge has an On/Off switch on the Online Evals page, Off by default and kept on the server; code metrics still run free (D-167; the sampling plan dropped at your choice). `test_online_judge_switch.py` (5); 536 offline tests. |
| 2026-11-12 | Your request: every sidebar group starts folded except Chats (Profiles joins Workspace and Observability); remembered folds reset once under a new key (D-153 changed). `test_sidebar_groups_start_folded_except_chats`; 537 offline tests; checked in Chrome. |
| 2026-11-12 | S13 · Guided Tour drafted at your request: a voice-led replay of a recorded run, exported as static files for gauravlahoti.dev; no Cloud Run, no key (D-168–D-174 proposed). Takes S08-AC2 and AC9. Brief waits for your approval. |
| 2026-11-12 | S13 brief approved → 🟦 (your go-ahead: "implement the guided tour on the local version first, with my voice"). S12 stays 🟨, waiting for your check. D-168–D-177. Recorded the tour's run live on Flash-Lite (2 turns, 4 approvals). |
| 2026-11-12 | S13 built locally (7/9 🟨): `/?tour` replays the recorded run in 10 steps through the page's own `onEvent()`; `/?tour=record` records a clip per step. Export (AC2) and subfolder (AC7) wait for the hosting step. `test_tour.py` (16); 553 offline tests. Next: your voice via ElevenLabs ("Gaurav"), step 1 as a sample. |
| 2026-11-12 | S13: step 1's clip in your cloned ElevenLabs voice "Gaurav" (`workspaces/cloudco/tour/audio/01-jar.mp3`, 25 s, eleven_v4, 2 takes ~$0.15). Served at `/api/tour/audio/01-jar` (200, audio/mpeg). Tour tests 25 passed. D-181. Steps 2–10 next, once you like the sample. |
| 2026-11-12 | S13: steps 2–10 voiced in your cloned voice; all 10 clips in `workspaces/cloudco/tour/audio/` (4 min 43 s, 4.5 MB ≤ 15 MB, AC8). Each served at `/api/tour/audio/<step>` (200, audio/mpeg). ~9.5 of 30 ElevenLabs minutes used. Waiting for your listen-through (AC5). |
| 2026-11-12 | S13: end-to-end check in Chrome: Start → all 10 clips play in order (no autoplay block, no console errors), voice end moves to the next step, Next walks 1→10, only `/api/health`, `/api/harness`, `/api/tour` and the 10 clips are fetched. Fixed (your report): with the Harness pane hidden in the tour, its show button sat under the spotlight's dim (z-index 5 < 40); now 50, like the side panels. |
| 2026-11-12 | S13 (your review): no pause between steps; the next starts when the voice ends (D-182). `test_s13_ac5_the_tour_pauses_between_steps` updated (default 0). Chrome: step 9 → 10 gap 285 ms, no countdown. AC5 waits for your re-check. |
| 2026-11-12 | S13 (your review): step 1 opens with a welcome naming the four primary parts; step 10 lists what a production-grade harness still needs. Both re-voiced (37.6 s, 39.1 s); audio total 5.2 MB. D-183. AC5 waits for your re-check. |
| 2026-11-12 | S13 (your review): step 2's parts pop as the voice names them (Chrome: 25.1 / 25.8 / 26.9 / 27.6 s inside the 23.4–28.0 s sentence). Step 9 now frames the answer and the cost line (it stayed on the last check row: the answer is drawn after the check ticks). `test_s13_ac6_pop_marks_pop_each_part_as_the_voice_names_it`, `test_s13_ac6_a_pop_must_name_a_diagram_part`. D-184. AC5, AC6 wait for your re-check. |
| 2026-11-12 | S13 (your review): step 1 is the agenda + the brain in a jar (re-voiced, 34 s); step 2 starts bare and each part springs in as named (Chrome: 25.4 / 26.1 / 27.2 / 28.0 s), then the whole harness + equation (28.1 s). Jar's grey shine removed. `test_s13_ac6_the_harness_is_built_part_by_part_then_shown_whole`, `test_s13_ac6_a_scene_mark_must_name_a_scene`. D-185. AC5, AC6 wait for your re-check. |
| 2026-11-12 | S13 (your review): the Harness part being toured only opens, no tint or coloured edge. Hide Guide / Show Guide (Chrome: strip folds to the orb, page gains 86 px, voice and replay carry on; Show Guide restores it). `test_s13_ac5_the_guide_can_be_hidden_and_shown_again`. D-186. AC5 waits for your re-check. |
| 2026-11-12 | S13 (your review): the tour scrolls the spotlight to mid-screen (Chrome, step 8: centre 422 / middle 422, ~400 px below; tall approval card shows its end with ~160 px below). Step 9 ends at "About a cent, on a small model." (clip cut to 9.1 s). Tour now ~5 min 5 s. D-187. AC5 waits for your re-check. |
| 2026-11-13 | S13 (your review): every approval card fits on screen in the tour (email body, header lines and note field folded; subject and terms table kept). Chrome: Sales 704, Engineering 656, Finance 738, CFO 757 px, all inside 821 px. D-187. AC5 waits for your re-check. |
| 2026-11-13 | Security audit for a public repo: no key ever committed (gitleaks + key-format search over all commits). Voice clips removed from history, commits on the no-reply email, `main` and tags force-pushed. Secret scanning waits until the repo is public. D-188. |
| 2026-11-12 | Your review → D-178/D-179: the tour is presented by a voice orb (no name) with subtitles, chapter titles, a living diagram and a spotlight; 10-second pause between steps; dark + cyan theme for the whole page; Observability stays visible. AC5 waits for your look. |
| 2026-11-13 | S14 · Public Tour Mode, your request: host the tour on gauravlahoti.dev via Cloud Run (min 0), with no key because visitors won't type their own. Brief approved → 🟦 (plan approval). Built 6/7 🟨: GET/HEAD-only middleware, keyless config, public bind, page note, Dockerfile + allowlist `.gcloudignore` (upload preview: 10 clips, no `.env`). `test_public_mode.py` (29); 596 offline tests. D-189. AC7 waits for the deploy. |
| 2026-11-13 | S14 + D-190 (your request): owner unlock for live demos. `?owner` passphrase opens Claude runs on the hosted copy, Claude key from Secret Manager; visitors unchanged. Profile, person and chats greyed out for visitors; note says "model API key". 606 offline tests. Waits for the `harness-owner-key` secret and your first live owner run. |
| 2026-11-13 | Deployed the tour with owner mode (revision agentic-harness-00004-gb2): visitors read-only and keyless, run/evals refused without the passphrase (403). Then (your review): switches locked for visitors, quiet note with GitHub mark and View the Code. Local checks in Chrome: public copy locked, normal page unchanged. D-193. |
| 2026-11-13 | S14 (your review): the tour leaves out "No To-Do plan" (it came before the recorded run's plan). Chrome: full replay shows no such line, To-Do cards intact. `test_s14_the_tour_never_claims_no_plan_before_the_plan_arrives`. D-194. |
