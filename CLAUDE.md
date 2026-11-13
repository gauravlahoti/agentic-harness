# Agent harness: rules for the AI

A learning project: a **general agent harness** built from scratch in plain Python on Gemini. The first agent on it is CloudCo's **Contract Agent** (`workspaces/cloudco/`). **The user must understand every line.** Teaching matters as much as working code.

## Source of truth
`Scaffold.md` (baseline) → `spec/00-product.md` → `spec/01-company.md` → `spec/02-ui.md` → `spec/stages/SNN-*.md` → `Tracker.md` → `Decisions.md`.

## The one architecture rule
`src/agentic_harness/` knows **no domain**. Nothing about CloudCo, contracts, discounts or profiles by name goes in `src/agentic_harness/`; it all lives in the workspace (`workspace.toml`, `tools.py`, `AGENTS.md`, skills). A test enforces this. If you're tempted to special-case a workspace inside `src/agentic_harness/`, stop and add a config option instead.

## Workflow (details in `spec/how-we-build.md`)
- Work only on the current stage. Next stage only after the user verifies, or explicitly waives, the current one.
- **Stage brief first (the user's primary condition):** before any code, present the goal, what we'll have at the end, and every design choice as options → chosen → why → cost. Wait for approval → 🟦.
- Tests come first, written from the checks. Put the check ID (`S05-AC4`) in each test's name or docstring.
- Tests pass → mark 🟨 with the test name as evidence. Always show the real output, failures included.
- **Never mark ✅ yourself.** Only after the user says it's verified.
- Never change an approved plan silently: add a dated line under **Changes**, a decision record if a choice changed, and reset affected checks to 📝.
- Add a dated line to the tracker log on every status change.

## Explain as you go (the user asked for this)
- **Before a file:** what it's for, which checks it serves, its main choice.
- **After a file:** walk through the key lines in simple words.
- **Every real choice:** options → choice → why → cost. Then add it to `Decisions.md`.
- **In code:** a module docstring (purpose · which harness part · what it does *not* do). Comments say *why*, not *what*.
- **End of stage:** walkthrough in `docs/stage-N.md`.
- Simple, short words. If code is hard to explain, simplify the code.

## Gemini rules
- `google-genai` only. Never `google-generativeai`.
- Interactions API with `store=False`. Never `previous_interaction_id`.
- We run the tools ourselves: no automatic function calling, no server-side tools, no managed agents.
- Keep model steps exactly as received (thought signatures).
- Check current docs (`gcp-developer-knowledge` MCP, or the `gemini-api-dev` skill) before writing Gemini code, not memory. Record verified shapes in `docs/gemini-api-notes.md`.
- Model names live in config only.

## Claude rules (from S09, D-102–D-104)
- Claude Haiku 5.5 / Sonnet 5.5 are a **paid, person-chosen** option. Never call Anthropic from tests, `make live`, or any check: use a recorded stand-in. Only runs the person starts use the key.
- `anthropic` SDK only; retries off; keep `thinking` blocks exactly as received; check the `claude-api` skill before writing Claude code.

## Secrets and safety
- Never read or print `.env`. The user fills it in. Only `src/agentic_harness/config.py` loads it.
- The key never reaches logs, traces, exports, the page or tool results.
- The server binds to `127.0.0.1` only. Actions write to a local outbox, never real email.
- The one exception is public tour mode (`HARNESS_PUBLIC=1`, D-189): the hosted tour listens on every address but answers only GET/HEAD and holds no key. Keep it that way: never add a write route that works in public mode, and never deploy with `agents-cli deploy` (it uploads `.env`). The only exception is the owner unlock (D-190): with the owner passphrase, `/api/run` and `/api/approval` open, on Claude only. Never widen `OWNER_ROUTES`.
- All CloudCo data is made up; label it so.

## Commands
`make setup` · `make check` (everything CI runs) · `make live` (🔑, costs cents) · `make help` · `uv run agentic-harness serve --workspace workspaces/cloudco` → http://127.0.0.1:8000 · `uv run agentic-harness run --workspace … --profile … "task"`

## Naming and quality
- **UI text casing.** Names, headings, buttons, menu items, column headers and short labels use **Title Case**: "Plan Adherence", "Tool Correctness", "Run Evals", "New Conversation". Small words (a, an, and, as, at, by, for, in, of, on, or, per, the, to, via, with) stay lowercase unless first; hyphenated parts are both capitalised ("Multi-Turn"). Sentences, descriptions, answers and questions use **sentence case**: "Gaurav Lahoti is very good." A test enforces it for metric and case-group names.
- No ALL-CAPS file names. Root docs in Title case (`Decisions.md`); everything else lowercase. Exceptions only: `CLAUDE.md`, `AGENTS.md`, `SKILL.md`. A test enforces it.
- Package `agentic_harness` (`src/` layout); command `agentic-harness`.
- `make check` must pass before anything is marked 🟨: ruff, mypy strict, pytest + coverage ≥ 75% (D-33; back to 85% with the S08 evals).

## Git
Commit at meaningful points. Tag `stage-N` after the user verifies. Push only when asked.
