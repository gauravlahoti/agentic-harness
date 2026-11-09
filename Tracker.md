# Tracker

> **Now:** S00 Part A (scaffold) built → waiting for your verification · then S00 Part B + S01
> **Updated:** 2026-11-10 · **Checks:** 10 built · 0 verified · 107 total

Icons: 🧪 test · 👀 you watch it · 📄 file · 🔑 needs key · Status: 📝 drafted · 🟦 approved · 🟨 built · ✅ verified · ⛔ blocked

## Waiting on you

| | What | Unblocks |
|---|---|---|
| 1 | Verify the scaffold: follow "Verify it yourself" in `Scaffold.md` | S00 Part A → ✅ |
| 2 | Approve the S00 Part B + S01 brief (or change a choice) | Building the loop |
| 3 | Create `.env` from `.env.example` and paste your key (the AI never reads it) | Every 🔑 check |
| 4 | Confirm access type: AI Studio key (default) or Agent Platform (D-08) | Every 🔑 check |
| 5 | Second workspace for the swap test: code reviewer (default) or other | S08-AC1 |
| 6 | Public or private GitHub repo | First push, CI's first run, license |

## Stages

| Stage | Name | Plan | Built | Verified | 🔑 checks |
|---|---|---|---|---|---|
| [S00](spec/stages/S00-setup.md) | Scaffold and setup | 🟨 Part A | 10/16 | 0/16 | – |
| [S01](spec/stages/S01-loop.md) | The loop | 📝 | 0/14 | 0/14 | 2 |
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
| AC1 | A fresh copy: `make setup` installs exactly what `uv.lock` says; `make check` passes offline | 🧪 | 🟨 | `make check` green in working copy · fresh-clone run after first commit |
| AC2 | `src/` layout, typed package `agentic_harness`; `agentic-harness --version` works | 🧪 | 🟨 | `test_cli.py` (3 tests) · `agentic-harness --version` → 0.1.0 |
| AC3 | Quality gates: ruff lint + format, mypy strict, pytest with coverage ≥ 85% | 🧪 | 🟨 | `make check`: ruff ✓ · mypy strict ✓ · 7 tests ✓ · coverage 100% |
| AC4 | Naming: no ALL-CAPS file names (except `CLAUDE.md`, `AGENTS.md`, `SKILL.md`); folders and Python files lowercase | 🧪 | 🟨 | `test_naming.py` · proven: a `NOTES.md` file made it fail |
| AC5 | Domain-free harness: no workspace words in `src/agentic_harness/` | 🧪 | 🟨 | `test_generic_harness.py` · proven: the word 'contract' in cli.py made it fail |
| AC6 | CI runs `make check` + a full-history secret scan, with a read-only token | 📄 | 🟨 | `.github/workflows/ci.yml` written · first run once the repo is on GitHub |
| AC7 | Pre-commit runs file hygiene, gitleaks, ruff and mypy at the locked versions | 📄 | 🟨 | `.pre-commit-config.yaml` validated · run `make hooks` to install |
| AC8 | Repo documents: Readme, Scaffold, Decisions, Tracker, Security, Contributing, Changelog | 📄 | 🟨 | All 7 documents present |
| AC9 | Runtime packages are only `google-genai`, `fastapi`, `uvicorn`, `python-dotenv` | 📄 | 🟨 | `pyproject.toml` dependencies |
| AC10 | `.env` is ignored by git; `.env.example` has the names, no values | 🧪 📄 | 🟨 | `git check-ignore .env` ✓ · automated test arrives with `config.py` |
| AC11 | Only `config.py` loads the key; printing it shows `***` | 🧪 | 📝 |  |
| AC12 | No key? Everything offline still works | 🧪 | 📝 |  |
| AC13 | `agentic-harness serve` listens on `127.0.0.1:8000` only and serves the page shell | 🧪 👀 | 📝 |  |
| AC14 | Checks panel runs one fixed test command, one row per test, live | 🧪 👀 | 📝 |  |
| AC15 | Smoke row: server up ✓ · key present ✓ or skipped (never ✗) | 👀 | 📝 |  |
| AC16 | First commit, tag `stage-0`, walkthrough in `docs/stage-0.md` | 📄 | 📝 |  |

### S01 · The loop

| ID | Check | How | Status | Evidence |
|---|---|---|---|---|
| AC1 | A test script records Gemini's real reply shapes in `docs/gemini-api-notes.md` (text, tool call, result, statuses, usage, max-tokens, safety block) | 🔑 📄 | 📝 |  |
| AC2 | `ModelClient` has one method: `create(system, steps, tools)` | 🧪 | 📝 |  |
| AC3 | `GeminiModel` sends the full history with `store=False`, never `previous_interaction_id` | 🧪 | 📝 |  |
| AC4 | `FakeModel` replays scripted replies shaped like the real ones | 🧪 | 📝 |  |
| AC5 | Plain answer → 1 call, ends `completed` | 🧪 | 📝 |  |
| AC6 | Tool round trip → 2 calls; the result carries the matching `call_id` | 🧪 | 📝 |  |
| AC7 | Two calls in one reply → both run in order, results sent together | 🧪 | 📝 |  |
| AC8 | Model steps are kept exactly as received | 🧪 | 📝 |  |
| AC9 | Stop rules (steps, cost, time) end the run with a named reason; cost counts thought tokens | 🧪 | 📝 |  |
| AC10 | An unexpected status ends the run with a named error, never a silent loop | 🧪 | 📝 |  |
| AC11 | Every step emits an event and is saved to a trace file; the key never appears in it | 🧪 | 📝 |  |
| AC12 | `create_harness(model, limits, workspace)` and `agentic-harness run "…"` both work | 🧪 | 📝 |  |
| AC13 | Page: input box, activity timeline, status line, Fake/Live switch | 👀 | 📝 |  |
| AC14 | A real tool round trip works on Gemini (thought signatures survive) | 🔑 🧪 | 📝 |  |

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
| P-SC4 | All offline tests < 10 s | 🟨 0.16 s today |
| P-SC5 | ≥ 5 of 6 eval tasks pass | ⬜ |
| P-SC6 | Every episode has a real without/with clip pair | ⬜ |
| P-SC7 | 75 s demo from replay, zero API calls | ⬜ |
| P-SC8 | You can explain any file | ⬜ |

## Log

| Date | What changed |
|---|---|
| 2026-11-10 | Spec v3 written: general harness + CloudCo Contract Assistant workspace, 9 stages. Old spec deleted. |
| 2026-11-10 | Production scaffold built (S00 Part A, 10 checks 🟨). Renamed `agentic-harness`; docs to Title case. |
