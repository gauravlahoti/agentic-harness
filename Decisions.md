# Decisions

> Why we chose X over Y. One record per real choice. Rejected choices stay here too.

**Format:** Chose · Instead of · Because · Cost · Revisit if

---

### D-01 · Build a general harness, not one agent
✅ Accepted · all stages
- **Chose:** two layers: `src/agentic_harness/` (knows no domain) + workspaces (one per agent). CloudCo's Contract Assistant is the first workspace.
- **Instead of:** an agent with company logic mixed into the loop
- **Because:** every agent has a harness. Separating them proves you built the harness itself, the way Claude Code is a harness that coding work runs on.
- **Cost:** a config file and a loader; a little more structure
- **Revisit if:** never; this is the point of the project. Enforced by the generic-harness test (S02) and the swap test (S08).

### D-02 · From scratch, in the shape of a framework call
✅ Accepted · all stages
- **Chose:** our own `create_harness(...)` + `workspace.toml`, with every part written by us
- **Instead of:** Deep Agents (what the Northstar video used) · Google ADK
- **Because:** a framework hides exactly what we're teaching. Copying its clean shape keeps ours easy to use.
- **Cost:** more code to write and maintain
- **Revisit if:** the ADK bonus episode shows a part is better taken off the shelf

### D-03 · Gemini through `google-genai` and the Interactions API
✅ Accepted · S01
- **Chose:** `client.interactions.create` with the official SDK
- **Instead of:** `generateContent` (now "legacy") · raw HTTP · LiteLLM
- **Because:** Google recommends it (GA June 2026); its typed steps map 1:1 onto our events and cards
- **Cost:** a young API, with automatic caching only → the S01 test script checks real shapes first
- **Revisit if:** we need guaranteed cache discounts

### D-04 · We keep the history, not Google (`store=False`)
✅ Accepted · S01, S07
- **Chose:** send the full step list on every call
- **Instead of:** server-side history via `previous_interaction_id`
- **Because:** memory and trimming are core lessons. If the server holds the history, we can't trim it. Also, nothing is stored at Google.
- **Cost:** bigger requests; maybe fewer cache hits → we measure cached tokens
- **Revisit if:** we want a "stateless vs stateful" cost post

### D-05 · Model steps are kept exactly as received
✅ Accepted · S01, S07
- **Chose:** never edit, merge or split a model step; only our own tool results can be trimmed
- **Instead of:** converting everything into our own format
- **Because:** model steps carry thought signatures; changing them can break the next call
- **Cost:** trimming has fewer options
- **Revisit if:** the S01 test script shows otherwise

### D-06 · Only our own tools; no Gemini server-side tools
✅ Accepted · S03
- **Chose:** tools that run in our process, through our gate
- **Instead of:** Gemini's built-in search, code execution, managed agents
- **Because:** rule 1: the model asks, the harness decides. Server-side tools would skip our gate and traces.
- **Cost:** no free web search
- **Revisit if:** a workspace needs search; we'd add it as our own gated tool

### D-07 · Models: 3.8 Flash by default, Argon by config, Flash-Lite for sub-agents
✅ Accepted · S01, S04
- **Chose:** `gemini-3.8-flash` · `gemini-4-argon` for demo takes · `gemini-3.5-flash-lite` for the Clause Reviewer
- **Instead of:** one model for everything
- **Because:** many small calls → cheap and fast; reading for a sub-agent is easy work
- **Cost:** model choice becomes a setting to explain
- **Revisit if:** the eval pass rate is below target

### D-08 · AI Studio key by default; Agent Platform optional
✅ Accepted · S00, S01
- **Chose:** support both through config; start with an AI Studio API key (`GEMINI_API_KEY`). Confirmed 2026-11-10
- **Instead of:** only one of them
- **Because:** a key is the simplest local setup; Agent Platform suits billing and control in a GCP project
- **Cost:** two login paths; the live check proves only the one you use
- **Revisit if:** you pick one

### D-09 · The first workspace is a company assistant, not a coding agent
✅ Accepted · S02 → S07
- **Chose:** a Contract Assistant for CloudCo's Sales, Engineering and Finance teams
- **Instead of:** a coding agent (shell + file edits) · single-domain demos (refunds, claims, cloud cost)
- **Because:** no shell means simple, complete guardrails; contracts touch money, risk and approvals; every company has them
- **Cost:** no "agent fixes a bug" scene → the swap test's code-review workspace covers code
- **Revisit if:** the series needs a coding season

### D-10 · Simple names and one story across every episode
✅ Accepted · all stages
- **Chose:** CloudCo · ShopCo · Contract Assistant · one contract (CT-2207), two rounds
- **Instead of:** invented brand names · a separate task per team
- **Because:** names that need no explaining; one story makes the series easy to follow
- **Cost:** less memorable branding
- **Revisit if:** never needed

### D-11 · The harness decides risk, in a fixed order
📝 Proposed · S05, S06
- **Chose:** profile tools → data + files → "never" rules → approval rules → run
- **Instead of:** letting the model judge what's risky
- **Because:** rules in code can't be talked around; the order makes every decision explainable
- **Cost:** every rule must be written down
- **Revisit if:** a workspace needs rules that depend on context we can't express in the config

### D-12 · Configuration and rules files are out of the agent's reach
📝 Proposed · S02, S05
- **Chose:** `workspace.toml` is never shown to the model; memory files, skills and policies are read-only for everyone
- **Instead of:** letting the agent read or update its own setup
- **Because:** an agent that can rewrite its own rules has no rules
- **Cost:** rule changes need a human
- **Revisit if:** we add a reviewed "suggest a rule change" flow

### D-13 · Failure-first episodes, from real recordings
✅ Accepted · S01 → S07
- **Chose:** each part can be switched off (demo mode only, red banner); each episode shows ❌ then ✅
- **Instead of:** describing failures, or staging them
- **Because:** seeing the same model fail, then succeed with one part added, is the clearest lesson
- **Cost:** the ❌ clip shows whatever really happens, which may be less dramatic than predicted
- **Revisit if:** never; honesty is the point

### D-14 · Public version = replay page on gauravlahoti.dev
📝 Proposed · S08
- **Chose:** a static page that replays saved runs
- **Instead of:** a public live agent
- **Because:** no backend, no key, no cost per visitor, nothing to abuse; it fits the AI Lab page
- **Cost:** visitors can't ask their own questions
- **Revisit if:** we add auth, rate limits and an isolated runtime

### D-15 · Spec first, with a tracker; only you mark "verified"
✅ Accepted · all stages
- **Chose:** numbered checks per stage, a tracker, and a stage gate
- **Instead of:** building straight through
- **Because:** you can see what's done, pending and waiting on you, and every line traces back to a reason
- **Cost:** tracker upkeep at each step
- **Revisit if:** the overhead outweighs the clarity

### D-16 · Production-grade baseline from day one
✅ Accepted · S00
- **Chose:** `src/` layout, uv + lockfile, ruff, mypy strict, pytest + coverage ≥ 85%, pre-commit with gitleaks, CI running `make check`, Dependabot
- **Instead of:** a quick prototype hardened later
- **Because:** built as if for an enterprise client; quality gates and secret handling are cheapest before the first feature
- **Cost:** more files and stricter checks from the first commit
- **Revisit if:** a gate slows work without catching real problems

### D-17 · Naming: `agentic-harness`, Title-case docs, no ALL-CAPS
✅ Accepted · all stages
- **Chose:** project and command `agentic-harness`, package `agentic_harness`; root docs in Title case (`Decisions.md`); everything else lowercase; exceptions only where a tool requires an exact name (`CLAUDE.md`, `AGENTS.md`, `SKILL.md`)
- **Instead of:** ALL-CAPS docs (`DECISIONS.md`) · the generic name `harness`
- **Because:** your convention; a distinctive project name; a test enforces it so it never drifts
- **Cost:** three listed exceptions to remember
- **Revisit if:** another tool needs an exact upper-case name (add it to the test's exception list with its reason)

### D-18 · One rules file for every coding agent
✅ Accepted · all stages
- **Chose:** the rules stay in `CLAUDE.md`; a short root `AGENTS.md` points to it and repeats the top rules
- **Instead of:** two full copies (they drift) · a symlink (breaks on Windows and some tools)
- **Because:** Claude Code reads `CLAUDE.md`; Codex and Antigravity read `AGENTS.md`. One source of truth, every agent finds it
- **Cost:** a second file to keep in step when the top rules change
- **Revisit if:** the tools converge on one file name

### D-19 · Settings: a frozen dataclass; the key wrapped in `Secret`
✅ Accepted · S00
- **Chose:** a frozen dataclass + `python-dotenv`; the key wrapped in a `Secret` class that prints `***`; `.env` read with `dotenv_values` (it never enters `os.environ`)
- **Instead of:** pydantic-settings · `load_dotenv` into the environment
- **Because:** no new package; and a key that never enters the environment can't leak into child processes such as the test run
- **Cost:** a ~10-line wrapper class
- **Revisit if:** we need validated nested settings

### D-20 · The server address is fixed to `127.0.0.1`
✅ Accepted · S00
- **Chose:** host fixed in code; only the port can change; requests must name `127.0.0.1` or `localhost` as host, and page actions send a custom header
- **Instead of:** host from config
- **Because:** no setting can expose the harness to the network by mistake; the host check and header stop other websites and DNS tricks from driving it
- **Cost:** can't open it from a phone
- **Revisit if:** never (the public version is a static replay page, D-14)

### D-21 · Checks panel: a small pytest plugin streams one JSON line per test
✅ Accepted · S00
- **Chose:** a ~30-line plugin module, loaded only by the panel's fixed command (`-p`); the server streams its lines to the page as NDJSON
- **Instead of:** parsing pytest's text output · a reporting package
- **Because:** a stable format, no new package, testable on its own
- **Cost:** the module imports pytest, a dev-only tool; the panel needs the dev install
- **Revisit if:** pytest gains a built-in JSON stream

### D-22 · History is kept as plain dicts, exactly as received
✅ Accepted · S01
- **Chose:** store each step as the dict Gemini returned; send it back unchanged
- **Instead of:** the SDK's Python objects
- **Because:** one format for the API, the trace file and the page; no conversion code
- **Cost:** depends on S01-AC1 proving a saved-and-reloaded step still works
- **Revisit if:** S01-AC1 shows signatures break after a round trip

### D-23 · FakeModel replays recorded Gemini replies
⛔ Superseded by D-32 (2026-11-10) · S01
- **Chose:** replies recorded from live calls (S01-AC1), saved as fixtures with the key removed
- **Instead of:** hand-written replies
- **Because:** free tests that match real behaviour
- **Cost:** re-record when the API changes
- **Revisit if:** fixtures drift from live behaviour

### D-24 · Events: a subscriber list
✅ Accepted · S01
- **Chose:** the loop emits typed events; trace writer, page and tests subscribe
- **Instead of:** prints · an async queue
- **Because:** the simplest form of "the loop doesn't know who's watching"
- **Cost:** a small events module
- **Revisit if:** subscribers need back-pressure

### D-25 · Prices live in `pricing.toml`
✅ Accepted · S01
- **Chose:** a data file; an unknown model stops the run at startup
- **Instead of:** prices in Python
- **Because:** model names stay out of code; the cost limit can't silently count $0
- **Cost:** prices updated by hand
- **Revisit if:** Google publishes prices in the API

### D-26 · The toy workspace `hello` loads only `tools.py` in S01
✅ Accepted · S01
- **Chose:** `workspaces/hello/tools.py` with `get_time`; context files arrive in S02, the registry in S03
- **Instead of:** a tool hard-coded in the harness
- **Because:** the harness stays domain-free from the first tool
- **Cost:** the loader grows in later stages
- **Revisit if:** —

### D-27 · Default limits: 25 steps · $1.00 · 120 s
✅ Accepted · S01
- **Chose:** defaults in config, overridable per run
- **Instead of:** no limits until later
- **Because:** a loop without brakes is a bug
- **Cost:** a long task may stop early, with a named reason
- **Revisit if:** eval tasks hit the limits

### D-28 · Theme: follow the system, with a two-state toggle
✅ Accepted · S00 (page) · at your request
- **Chose:** every color is a `light-dark()` pair driven by one `color-scheme` value; a sidebar toggle pins the opposite of the system theme (choosing the system's own theme un-pins it); the new theme spreads in a circle from the toggle (View Transitions), instant with reduced motion; a tiny blocking script applies a saved theme before first paint
- **Instead of:** a three-state Light / Dark / System picker · a `.dark` class set by JavaScript · cross-fading every color
- **Because:** one switch flips all colors at once, so nothing flickers; the page still follows the system if JS fails; no flash on reload; strict security headers stay intact (no inline script)
- **Cost:** `light-dark()` and View Transitions need a 2024+ browser; older ones switch without the animation
- **Revisit if:** we add a settings panel (then offer all three states there)

### D-29 · No hidden SDK calls: continuation off, retries bounded
✅ Accepted · S01 · found while recording real replies
- **Chose:** `automatic_continuation=False` on every call; SDK retries limited, and each call bounded by the run's time left; a cut-off reply ends the run with a named reason
- **Instead of:** the SDK defaults (extra billed calls on its own; silent retries for minutes on a 503)
- **Because:** rule 1 (the harness decides) and honest cost and time limits; we saw a 503 "high demand" retried silently for about 5 minutes
- **Cost:** a busy model fails faster; the run reports `model_error` instead of waiting
- **Revisit if:** we add our own visible retry step to the loop
- **Changed 2026-11-10:** retries are now off entirely (D-42)

### D-30 · The base prompt tells the model to answer directly
✅ Accepted · S01 · after your report ("who is the prime minister" called `get_time`)
- **Chose:** "Answer directly when you already know the answer. Call a tool only when the task needs something that tool provides…"
- **Instead of:** "Use the tools you are given when they help"
- **Because:** measured live on 3.5 Flash-Lite, 5 runs each: needless tool calls 5/5 → 1/5; the time question still used the tool 5/5
- **Cost:** a model may skip a tool it should have used; the time question shows it doesn't
- **Revisit if:** S02's workspace instructions change the balance (they sit on top of this prompt)

### D-31 · Pick the model in the input box (Live only)
✅ Accepted · S01 · at your request
- **Chose:** a menu in the input box listing only models with a price in `pricing.toml`; the server refuses any other name; the last pick is remembered in this browser; the default stays `HARNESS_MODEL`
- **Instead of:** a model setting at the top of the page · free-text model names
- **Because:** on the free tier a busy model (503) can be swapped in one click; a priced list keeps the cost limit honest (D-25)
- **Cost:** a new model needs a price line in `pricing.toml` before it can be picked
- **Revisit if:** we add another provider

### D-32 · Only Gemini answers: no fake model anywhere
✅ Accepted · S01 · at your request
- **Chose:** remove Fake mode from the page and CLI, the recorded `fake_replies.json`, the `FakeModel` class, and the tests that replayed recordings through it; every answer comes from a real Gemini model; the server takes a `model_factory` (Gemini) so the client is chosen in one visible place
- **Instead of:** a free Fake mode for demos · replay-based loop tests (D-23)
- **Because:** the product should show real model behaviour only; the agent's quality will be judged by dedicated evals (S08) against real Gemini
- **Cost:** no free demo mode; the loop has no offline tests until the evals (see D-33); the 9 recorded replies stay only as evidence for `docs/gemini-api-notes.md`
- **Revisit if:** CI needs to prove loop behaviour before the evals exist

### D-33 · Coverage gate 75% until the evals land
✅ Accepted · S00-AC3 · at your request
- **Chose:** `fail_under = 75` (was 85) after D-32 removed the loop's offline tests (coverage 97% → 76%)
- **Instead of:** keeping 85% with CI red · live loop tests in `make live` · excluding the loop from coverage
- **Because:** keeps CI green and free; the loop's behaviour will be checked by the S08 evals
- **Cost:** `loop.py` is about 31% covered offline; a loop bug can pass `make check` until the evals exist
- **Revisit if:** the evals land (then back to 85%)

### D-34 · The agent's instruction file stays `AGENTS.md`
✅ Accepted · S02
- **Chose:** keep `workspaces/<name>/AGENTS.md`; the root `AGENTS.md` tells coding agents that files under `workspaces/` are product data, not their instructions
- **Instead of:** rename to `instructions.md`
- **Because:** keeps the clear parallel with `CLAUDE.md`; one line fixes the coding-agent collision
- **Cost:** relies on coding agents reading the root note
- **Revisit if:** a coding agent still picks them up

### D-35 · A tiny strict reader for `SKILL.md` frontmatter
✅ Accepted · S02
- **Chose:** read only `name` and `description` (one line each); check the Agent Skills rules (lowercase-hyphen name matching its folder, length limits); anything else is a clear error
- **Instead of:** the PyYAML package
- **Because:** runtime packages are capped at four (S00-AC9)
- **Cost:** fancier frontmatter is rejected
- **Revisit if:** skills need more fields

### D-36 · Skills load on demand, per profile
✅ Accepted · S02
- **Chose:** only name + description go in the prompt; the built-in `load_skill(name)` returns the full text, only for skills the current profile can see; shown as a CONTEXT line
- **Instead of:** putting whole skills in the prompt
- **Because:** the prompt stays small and identical on every call
- **Cost:** one extra tool call when a skill is needed
- **Revisit if:** skills are tiny

### D-37 · Fixed system prompt order, built once per run
✅ Accepted · S02
- **Chose:** base → memory files → skill list; built before the first call and never changed during the run; each call carries a short prompt ID so the trace proves it
- **Instead of:** rebuilding per call
- **Because:** Gemini caches a prompt that starts the same way (S02-AC8)
- **Cost:** none
- **Revisit if:** —

### D-38 · Size budget for memory files
✅ Accepted · S02
- **Chose:** estimate tokens as characters ÷ 4; warn above the workspace's `memory_budget_tokens` (default 2,000) on the CONTEXT line and in the CLI
- **Instead of:** a real tokenizer
- **Because:** memory files are paid for on every call; a rough number is enough to act on
- **Cost:** the estimate is rough
- **Revisit if:** warnings prove misleading

### D-39 · Profiles come from `workspace.toml`
✅ Accepted · S02
- **Chose:** the page sends the chosen profile and the CLI takes `--profile`; switching profile starts a fresh thread; rights per profile arrive in S05
- **Instead of:** profiles in harness code
- **Because:** each profile gets its own files and skills, with no harness change
- **Cost:** none
- **Revisit if:** —

### D-40 · Each workspace declares its own domain words
✅ Accepted · S02
- **Chose:** `domain_words` in `workspace.toml`; the domain-free test checks every text file in `src/agentic_harness/` against every workspace's list (S02-AC9)
- **Instead of:** one hard-coded list in the test
- **Because:** the guard grows with each agent and covers the page's JS/HTML too
- **Cost:** none
- **Revisit if:** —

### D-41 · `workspace.toml` is optional
✅ Accepted · S02
- **Chose:** a folder with only `tools.py` still loads, with sensible defaults
- **Instead of:** requiring it
- **Because:** shows how little a workspace needs
- **Cost:** two code paths
- **Revisit if:** —

### D-42 · No SDK retries at all; show Gemini's own error sentence
✅ Accepted · S02 · after your report (runs on 3.6 and 3.8 Flash "Thinking" for 2 minutes)
- **Chose:** `attempts=1`, so the SDK sends each request once; a failure reaches the loop at once as `model_error: Gemini 429: <Gemini's message>`
- **Instead of:** `attempts=2` (D-29), one "harmless" retry
- **Because:** measured: on a 429 the SDK sleeps for the server's `Retry-After` as-is, uncapped. 3.6 Flash's free tier (20 requests a day) said "retry in 41m43s", so every run sat silent until our 120 s limit and ended "hit the time limit", hiding the real reason
- **Cost:** a one-second blip now fails the run too; you resend or pick another model
- **Revisit if:** we add our own visible retry step to the loop

### D-43 · `@tool` builds the declaration from the function
✅ Accepted · S03 · brief choice 1
- **Chose:** a decorator reads type hints (`str`, `int`, `float`, `bool`, `Literal[...]` → enum, `list[...]`), `Annotated[T, "…"]` for parameter descriptions, and the docstring for the tool description
- **Instead of:** hand-written JSON schemas · Pydantic models
- **Because:** one source of truth; the schema can't drift from the code
- **Cost:** only simple types; anything else is a clear error when the workspace loads
- **Revisit if:** a tool truly needs nested objects

### D-44 · Every tool declares its risk
✅ Accepted · S03 · brief choice 2
- **Chose:** `risk` is required: `read`, `write` or `action`
- **Instead of:** optional with a default of `read`
- **Because:** guardrails (S05, S06) gate on it without knowing any tool; forgetting it must not mean "safe"
- **Cost:** one word per tool
- **Revisit if:** —

### D-45 · Built-in tools are opt-in per workspace
✅ Accepted · S03 · brief choice 3
- **Chose:** `builtins = ["read_file", "write_file"]` in `workspace.toml`; `load_skill` stays automatic when there are skills
- **Instead of:** every built-in for every workspace
- **Because:** every extra tool tempts the model (D-30); `hello` needs no files
- **Cost:** one config line
- **Revisit if:** —

### D-46 · `read_file` reaches only folders the workspace lists
✅ Accepted · S03 · brief choice 4
- **Chose:** `readable = [...]` in `workspace.toml`; paths resolved, escapes refused; `.env` and `workspace.toml` never readable
- **Instead of:** the whole workspace folder
- **Because:** `workspace.toml` stays hidden from the model; an allow-list is easy to reason about
- **Cost:** folders listed by hand
- **Revisit if:** —

### D-47 · Writes go to `tasks/<run-id>/`; actions to `outbox/`
✅ Accepted · S03 · brief choice 5
- **Chose:** a folder per run for drafts, one `outbox/` for actions; both git-ignored
- **Instead of:** one shared folder
- **Because:** a run's drafts stay together; nothing leaks into the repo; never real email
- **Cost:** drafts aren't shared across runs until S07
- **Revisit if:** S07 (memory)

### D-48 · The harness hands tools a `ctx`; all writes go through it
✅ Accepted · S03 · brief choice 6
- **Chose:** a function that declares a `ctx` parameter gets a `ToolContext` (run id, folders, `save_task_file`, `save_outbox_file`); `ctx` never appears in the schema
- **Instead of:** globals
- **Because:** tools stay plain, testable functions; the model can't see or set `ctx`; one place writes files, so S05/S06 can gate it and the page can show it (D-53)
- **Cost:** one bit of "magic", explained in the docstring
- **Revisit if:** —

### D-49 · Arguments are checked before a tool runs
✅ Accepted · S03 · brief choice 7
- **Chose:** our own check of required fields, types and enums; problems go back to the model as an error result
- **Instead of:** letting Python raise · the `jsonschema` library
- **Because:** the model reads "timezone is required" and fixes itself; no new dependency
- **Cost:** covers only the types `@tool` generates (D-43)
- **Revisit if:** D-43 grows nested types

### D-50 · Tool output is capped at 20,000 characters
✅ Accepted · S03 · brief choice 8
- **Chose:** a cut with a visible note: "[cut: N more characters; ask for a smaller part]"; tools are designed to return parts (a contract section, not the whole contract)
- **Instead of:** no limit
- **Because:** protects context and cost; the cut is named, never silent
- **Cost:** the model may need a second call
- **Revisit if:** S07 adds context trimming

### D-51 · Differences are found in code; the model judges them
✅ Accepted · S03 · brief choice 9
- **Chose:** `compare_to_standard` diffs two contract versions clause by clause (word level) and returns every edit with its clause ID
- **Instead of:** the model reading both contracts
- **Because:** deterministic, cheap, and every edit is citable; judgement stays with the model and the skill
- **Cost:** contracts must be split into numbered clauses
- **Revisit if:** —

### D-52 · CloudCo's data comes from a committed generator
✅ Accepted · S03 · brief choice 10
- **Chose:** `workspaces/cloudco/make_data.py` writes the JSON records and both contract versions deterministically; its output is committed
- **Instead of:** hand-writing ~60 edits across a long contract
- **Because:** consistent and reviewable; the script is the recipe
- **Cost:** one script to maintain
- **Revisit if:** —

### D-53 · File cards come from a `file_saved` event
✅ Accepted · S03 · brief choice 11
- **Chose:** `ctx.save_*` writes the file and emits `file_saved` (path, text); the page shows a card that opens to the text; tool results carry only the path
- **Instead of:** a new endpoint that serves files · the text inside the tool result
- **Because:** no new server surface; the trace holds it; the model doesn't pay tokens for its own draft twice
- **Cost:** a file changed outside the run won't refresh (not needed in S03)
- **Revisit if:** files become editable on the page
- **Changed 2026-11-10:** CloudCo no longer uses `write_file` (D-73); cards now come from outbox actions

### D-54 · The server tells the browser to re-check page files
✅ Accepted · S03 · found while checking the page
- **Chose:** `Cache-Control: no-cache` on every response: the browser asks each time, and gets a cheap 304 when nothing changed
- **Instead of:** no header (the browser guesses a freshness time) · version numbers in file names (a build step)
- **Because:** seen: after an update Chrome kept running the old `app.js`, so risk tags and file cards were missing
- **Cost:** one tiny request per file per load, on localhost
- **Revisit if:** the page is ever served from somewhere other than this local server

### D-55 · Sub-agents are declared in `workspace.toml`
✅ Accepted · S04 · brief choice 1
- **Chose:** `[subagents.<name>]` with description, instructions file, tools, model, word limit
- **Instead of:** Python in `tools.py`
- **Because:** configuration, not code; the harness has none built in
- **Cost:** one config section
- **Revisit if:** —

### D-56 · One `delegate_task(agent, brief)` tool
✅ Accepted · S04 · brief choice 2
- **Chose:** one built-in tool; the agent names are an enum, each described in the tool description
- **Instead of:** one tool per sub-agent
- **Because:** one generic built-in; adding a helper adds no tool
- **Cost:** a longer tool description
- **Revisit if:** —

### D-57 · The child sees only its own instructions and the brief
✅ Accepted · S04 · brief choice 3
- **Chose:** a short harness base prompt + the sub-agent's instructions file; the brief is its only message
- **Instead of:** inheriting the parent's memory files and skills
- **Because:** a clean context is the point
- **Cost:** rules the child needs are written into its own file
- **Revisit if:** —

### D-58 · Child tools are declared and read-only; no delegation
✅ Accepted · S04 · brief choice 4
- **Chose:** only the declared tools, each with risk `read`, checked at startup; never `delegate_task`
- **Instead of:** any declared tool
- **Because:** delegation can never get around the gates; depth stays 1
- **Cost:** actions stay with the main agent
- **Revisit if:** —

### D-59 · `delegate_only` tools leave the parent while delegation is on
✅ Accepted · S04 · brief choice 5
- **Chose:** tools listed in `delegate_only` go to the helper only; with delegation off they return to the parent
- **Instead of:** asking the parent to delegate while it keeps every tool
- **Because:** otherwise a small model may read the diff itself, and the on/off comparison means nothing
- **Cost:** one config line
- **Revisit if:** —

### D-60 · The child gets a slice of the parent's budget
✅ Accepted · S04 · brief choice 6
- **Chose:** 25% of the parent's remaining $ and seconds, at most 15 steps; the child's cost is charged to the parent; out of budget → partial text plus the reason, as a normal result
- **Instead of:** the parent's full limits
- **Because:** no runaway helper; the run's total cost stays honest
- **Cost:** about 30 s in a 120 s run: fine for Flash-Lite, tight for slower models
- **Revisit if:** helpers run out of time in practice
- **Changed 2026-11-10 (your choice):** half the remaining *time*, still a quarter of the *money*. Seen live: a busy Flash-Lite took 11 s for one call, and the helper stopped at ~30 s with no answer; it had spent $0.002 of its $0.25

### D-61 · The result's shape is written down; its length is enforced
✅ Accepted · S04 · brief choice 7
- **Chose:** the instructions describe the shape; the harness cuts the result at `max_words` with a visible note; only the final text enters the parent's history
- **Instead of:** Gemini structured output
- **Because:** no new model parameter; schema types stay simple (D-43)
- **Cost:** the shape is followed, not enforced
- **Revisit if:** results drift from the shape

### D-62 · Each sub-agent may name its own model
✅ Accepted · S04 · brief choice 8
- **Chose:** `model` per sub-agent (CloudCo: Flash-Lite); default is the parent's; price checked at startup
- **Instead of:** always the parent's model
- **Because:** reading is easy work; Flash-Lite has the most free quota
- **Cost:** `create_harness` gains a model factory
- **Revisit if:** —

### D-63 · Child events flow through the parent's events and trace
✅ Accepted · S04 · brief choice 9
- **Chose:** tagged with `agent_id`, `parent_id` and `agent`
- **Instead of:** a separate trace file per child
- **Because:** one trace tells the whole story; the page can nest them
- **Cost:** listeners must expect tagged events
- **Revisit if:** —

### D-64 · Delegation can be switched off
✅ Accepted · S04 · brief choice 10
- **Chose:** `delegation=` on `create_harness`, `--no-delegation` on the CLI
- **Instead of:** no switch
- **Because:** proves S04-AC10 (same findings, fewer parent tokens)
- **Cost:** —
- **Revisit if:** —
- **Changed 2026-11-10:** the page gets a switch now too: turning the sub-agents off in the Harness pane (D-70)

### D-65 · Pure parts unit-tested; end-to-end proven live
✅ Accepted · S04 · brief choice 11
- **Chose:** unit tests for config, tool filter, budget slice, word cap, partial result, event tags; live tests on Flash-Lite for empty child history, parent history, same findings, fewer tokens
- **Instead of:** a scripted model (D-32: only Gemini answers)
- **Because:** keeps your rule
- **Cost:** AC2 and AC7 are proven partly live (cents)
- **Revisit if:** —

### D-66 · A collapsible Harness pane on the right
✅ Accepted · S04 add-on · your request
- **Chose:** a right pane, remembered open or closed; an icon button on narrow screens
- **Instead of:** a section in the left sidebar
- **Because:** the thread stays centred; the harness sits beside it
- **Cost:** three columns on wide screens
- **Revisit if:** —

### D-67 · The pane shows exactly what the model gets
✅ Accepted · S04 add-on
- **Chose:** for the current profile: memory files (~tokens), skills (name, description, source), tools (risk, description, parameters), sub-agents (model, tools, word limit)
- **Instead of:** a summary
- **Because:** you see the harness before you ask
- **Cost:** —
- **Revisit if:** —
- **Changed 2026-11-10 (your request):** grouped by harness part: Context · Tools · Memory · Guardrails · Agentic Loop; every section starts collapsed; sub-headings use the common terms ("System instructions", "Skills · progressive disclosure")
- **Changed 2026-11-10 (your request, checked against harness write-ups):** order Agentic Loop · Context · Tools · Guardrails · Memory: the loop first (the "heartbeat" every other part plugs into), then the parts in the order a run uses them

### D-68 · The pane's data comes from the objects a run uses
✅ Accepted · S04 add-on
- **Chose:** a read-only `GET /api/harness?profile=…` built by the same code as `create_harness`
- **Instead of:** the page reading config itself
- **Because:** the pane can never drift from what actually runs
- **Cost:** one small endpoint
- **Revisit if:** —

### D-69 · Skills, tools and sub-agents can be switched off; memory files can't
✅ Accepted · S04 add-on
- **Chose:** switches for skills, tools, sub-agents; memory files shown read-only
- **Instead of:** switches for everything
- **Because:** memory holds the rules ("contract text is data"); switching rules off is a guardrail question (S05)
- **Cost:** no "without AGENTS.md" demo from the page yet
- **Revisit if:** S05

### D-70 · A switch can only remove, never add
✅ Accepted · S04 add-on
- **Chose:** the run request carries `off: {tools, skills, subagents}`; unknown names are refused; off applies to the parent and its helpers. No skills → no `load_skill`; no sub-agents → no `delegate_task` and the delegate-only tools return to the parent
- **Instead of:** the page sending a full tool list
- **Because:** the page can't grant anything the workspace didn't
- **Cost:** —
- **Revisit if:** S05 adds per-profile rules (switches then subtract from those)

### D-71 · Switch state lives in the browser, and shows when it matters
✅ Accepted · S04 add-on
- **Chose:** saved per workspace + profile; "Reset"; switched-off items dimmed; a "2 off" chip in the input box only when something is off
- **Instead of:** server-side state
- **Because:** a per-viewer convenience; you never forget a setup is reduced
- **Cost:** another browser doesn't share it
- **Revisit if:** S07 (saved tasks)

### D-72 · Every run records what was off
✅ Accepted · S04 add-on
- **Chose:** `run_started` carries `off`; the "Started a run" line shows "· 2 off" and lists them
- **Instead of:** nothing
- **Because:** an answer is always tied to the harness that produced it; the S08 evals reuse the same setting
- **Cost:** —
- **Revisit if:** —

### D-73 · CloudCo has four tools
✅ Accepted · S04 · your request ("a simple demo and prototype")
- **Chose:** `lookup` (customer · deal · uptime · payments), `review_contract` (all edits with clause IDs, or one clause; helper-only while delegating), `search_policy`, `send_to_customer` (action, outbox). No built-in file tools for CloudCo; `accept_change` dropped
- **Instead of:** nine CloudCo tools plus `read_file` and `write_file` (S03)
- **Because:** a demo you can hold in your head; the pane shows four tools, not eleven
- **Cost:** no saved drafts (file cards now come only from the outbox); S06 approvals gate `send_to_customer` instead of `accept_change`; S03 tool checks re-proven
- **Revisit if:** the S08 evals show the model picks the wrong `lookup` kind

### D-74 · Two profiles: Sales and Engineering
✅ Accepted · S05 · your request ("for the purpose of the demo and prototype")
- **Chose:** Sales and Engineering only; Finance and CFO profiles, `teams/finance.md` and the payment-terms skill removed. Policies still name Finance and the CFO as approvers (company policy, not demo profiles)
- **Instead of:** four profiles (S02)
- **Because:** two profiles show the contrast (who sees prices, who can send) with half the setup
- **Cost:** S02-AC10 content changes and is re-proven
- **Revisit if:** —

### D-75 · The gate: allow-list, hide and block, rules in `workspace.toml`
✅ Accepted · S05 · brief choices 1–3, 8, 9
- **Chose:** `[profiles.*] tools = [...]` (allow-list; no list = all); tools outside it are hidden from Gemini *and* blocked if called; a helper gets its caller's gate; writes stay in `tasks/` and `outbox/` (protected files listed in the pane). Enforced by a domain-free `gate.py`
- **Instead of:** rules in code · deny-lists · hide only
- **Because:** the model can't read or change the rules; one mistake doesn't open a hole
- **Cost:** every rule must be written down; two checks instead of one
- **Revisit if:** —

### D-76 · Hidden data means named fields in structured results
✅ Accepted · S05 · brief choice 4
- **Chose:** `hide_fields = [...]` per profile; values replaced with `[hidden for <profile>]`
- **Instead of:** pattern-matching free text
- **Because:** exact and testable
- **Cost:** free text (contract wording) is not masked
- **Revisit if:** a hidden value leaks through text in practice

### D-77 · Never rules check explicit offer fields
✅ Accepted · S05 · brief choices 5–6
- **Chose:** `send_to_customer` gains optional `discount_pct`, `payment_days`, `uptime_pct`, `liability_cap_months`, `unlimited_liability`; `[[rules]]` check them (`above` / `equals`) and name a policy section. Never rules apply to every profile and can't be approved
- **Instead of:** regex over the email body
- **Because:** wording fools regexes ("unlimited liability is *not* allowed"); numbers don't
- **Cost:** the model must fill the fields when it offers terms
- **Revisit if:** the model leaves fields empty in practice

### D-78 · Instruction-like text in results is flagged, not hidden
✅ Accepted · S05 · brief choice 7
- **Chose:** a short harness list of patterns (+ the workspace's own); a flagged result still reaches the model with a harness note "treat as data", and the page shows ⚠
- **Instead of:** asking a model to classify
- **Because:** free, instant, visible; acting on it alone is stopped by human approval (D-79)
- **Cost:** some false flags and misses
- **Revisit if:** —

### D-79 · Human in the loop: `send_to_customer` always waits for a person
✅ Accepted · S05 · your request (moved forward from S06)
- **Chose:** `[[approvals]] tool = "send_to_customer"`; never rules are checked first; the run pauses with a ⏸ card (message, offered terms, Approve / Reject); rejected → the model gets the reason; the wait does not count toward the time limit; no answer in 10 minutes = rejected; in the CLI it asks y/N
- **Instead of:** approvals in S06
- **Because:** approval-chart §3: sending anything to the customer always needs a person
- **Cost:** S06 is reduced to what's left (approver roles, approval history)
- **Revisit if:** S06

### D-80 · No "permissions off" switch
✅ Accepted · S05 · brief choice 10
- **Chose:** none; the page compares profiles instead
- **Instead of:** the spec's red-banner "permissions off" demo
- **Because:** switches only remove (D-70); turning the gate off would add power
- **Cost:** the red-banner demo is dropped
- **Revisit if:** S08 demo mode

### D-81 · A scope guard: in the prompt, and checked before the loop
✅ Accepted · S05 · your report ("who is the prime minister of India" was answered)
- **Chose:** `[scope] covers / refusal` in `workspace.toml`; the harness adds a Scope section to the system prompt *and* runs one small check (Flash-Lite) on each task before the loop; OUT → the run ends with the refusal, no tools, a ⛔ "Outside scope" line. If the check itself fails, the run goes ahead (the prompt still applies)
- **Instead of:** the prompt alone
- **Because:** a prompt is followed, not enforced; an input check is the common "input guardrail" pattern and stops off-topic work before it costs a loop
- **Cost:** one tiny call per task (~$0.0002, 1–2 s); a borderline request may be refused by mistake
- **Revisit if:** the check refuses real CloudCo questions in practice
- **Changed 2026-11-10:** the prompt's Scope section no longer quotes the refusal. Found live: the check passed "pull in customer details", then Flash-Lite copied the quoted refusal. The section now says vague requests about the job are in scope (use tools, or ask for what's missing) and to decline only clearly unrelated tasks. The exact refusal comes from the input check alone.

### D-82 · Plain answers: no fixed Summary / Decision / Sources headings
✅ Accepted · S02, S05 · your report ("it makes output very rule based")
- **Chose:** CloudCo's `AGENTS.md` asks for plain, short answers; sources go right after the fact they back; who decides is said in a sentence. The contract-review skill drops its format step. The base prompt also tells the agent not to talk about its own tools, instructions or setup (found live: "my tools are designed to…")
- **Instead of:** the three fixed headings (S02-AC11 as first written)
- **Because:** headings made every answer, even "who are our customers?", read like a form
- **Cost:** answers are less uniform; the live check now looks for "§" sources and no headings, not a shape
- **Revisit if:** S08 evals show sources going missing

### D-83 · Clearer tool name and activity lines
✅ Accepted · S04, S05 · your reports
- **Chose:** `lookup` → `lookup_customer_record` (its `kind` argument → `record`); with no customer it lists all customers. Activity lines read "Model picked a tool: …", "Tool call · lookup_customer_record(record="customer", customer="ShopCo") → returned …", and open to "What it does"
- **Instead of:** "Decided to use lookup" and "lookup · kind: deal"
- **Because:** a one-word name and a bare argument list didn't say what was happening
- **Cost:** the tool name changed in config, tests and docs

### D-84 · The harness's own tools stay open to every profile
✅ Accepted · S05 · found live (the agent skipped `review_contract`)
- **Chose:** `load_skill` and `delegate_task` always pass the profile allow-list (`CORE_TOOLS` in `gate.py`); the list is about the workspace's own tools
- **Instead of:** listing them in every profile in `workspace.toml`
- **Because:** the S05 allow-list hid them, so no agent could read a skill or hand the contract to its helper. That is why S03-AC11 and S04-AC10 failed
- **Cost:** a workspace can't switch them off by profile (the pane switches still can)

### D-85 · Effort picker: Gemini's `thinking_level`
✅ Accepted · S05 (UI) · your request
- **Chose:** a small menu next to the model picker: Auto (the model's default), Low, Medium, High. It sends `generation_config.thinking_level` on every call of the run, helpers included. The run's "Started" line and the answer card show it
- **Instead of:** `thinking_budget` (a token count; not recommended on Gemini 3.x, an error on Gemini 4), or also offering `minimal`
- **Because:** `thinking_level` is the documented control; `minimal` is missing on some models, so a 4th choice could fail with a 400
- **Cost:** higher effort costs more thinking tokens (billed as output); small models may call more tools at high effort

### D-86 · Company logo and an agent menu at the top; the harness mark moves
✅ Accepted · UI · your request
- **Chose:** `logo = "logo.svg"` in `workspace.toml` (a small .svg or .png inside the workspace, served read-only at `/api/workspace/logo`); the sidebar shows logo + company name, then a menu of the company's agents (one entry today: the page builds it from `agents` in `/api/health`). The loop mark moved to the Harness pane's title; "agentic-harness" is now a plain "powered by" line in the sidebar footer
- **Instead of:** the harness name and mark at the top, with the agent as plain text
- **Because:** the top of the page should say whose agents these are; the mark belongs where the harness is shown
- **Cost:** the menu cannot switch yet: the server runs one workspace, so a second agent needs the server to host several (a later change)
- **Revisit if:** a second agent is added to CloudCo

### D-87 · The approver is a named role, answered by role-play
✅ Accepted · S06 · your pick ("A looks good")
- **Chose:** every approval names an approver role (Sales, CFO, Finance, Engineering). The card says "Approve as CFO"; the person at the page clicks as that role; the outbox records the role and the time. The page labels it a demo
- **Instead of:** switching profile to approve (the thread resets), or real logins
- **Because:** this project has no accounts and runs on one machine; the mechanism (who must decide, who did) is what's being taught
- **Cost:** not security: anyone at the keyboard can click as any role
- **Revisit if:** the harness is ever hosted for several people

### D-88 · Several approvals per tool, each with a condition
✅ Accepted · S06
- **Chose:** `[[approvals]]` may repeat for one tool. Each has `approver`, `because`, an optional `label`, and an optional condition on one argument (`arg` with `above` or `equals`, the same words as the never rules). All that match are asked in order; a rejection stops the rest
- **Instead of:** one approval per tool
- **Because:** the approval chart says different people decide different amounts
- **Cost:** CloudCo's `workspace.toml` grows by four rules

### D-89 · `ask_human`: the model chooses to pause
✅ Accepted · S06
- **Chose:** a built-in tool, on when `workspace.toml` says `ask_human = true`. The loop sends the question down the approval channel; the page shows a card with a text box; the answer returns to the model as the tool result. No answer in 10 minutes counts as "no answer"
- **Instead of:** a second pause mechanism
- **Because:** one channel, one timeout, one place for tests
- **Cost:** a small model may ask too often; the tool description says to ask only when something needed is missing

### D-90 · A conversation is one append-only file of exact steps
✅ Accepted · S07 · your approval
- **Chose:** `.agentic-harness/sessions/<workspace>/<profile>/<id>.jsonl`: a header line, then each user input, model step and tool result as it happens, then a line per finished turn (task, answer, cost). A follow-up resends the steps (`store=false`). On resume, a tool call with no result gets a "cancelled" result and is never re-run
- **Instead of:** rebuilding from trace files (events, not model steps)
- **Because:** a crash loses at most one line; thought signatures stay exact; you can read it with `cat`
- **Cost:** a second record next to the trace

### D-91 · Conversations are listed by topic
✅ Accepted · S07 · your request
- **Chose:** the left pane's "Your work" lists the profile's conversations, newest first. The title comes from one small Flash-Lite call on the first task (3–6 words), run alongside the first turn; if it fails or times out (3 s), the title is the task's first words
- **Instead of:** always the raw first question
- **Because:** a topic is what you look for when you come back
- **Cost:** about $0.00005 per conversation

### D-92 · Notes enter the prompt once per task
✅ Accepted · S07
- **Chose:** `save_note` (on with `notes = true` in `workspace.toml`) appends to `.agentic-harness/notes/<workspace>/<profile>.md`. Notes are added at the end of the system prompt when a task starts, newest kept, capped at about 2,000 tokens
- **Instead of:** refreshing the prompt on every call
- **Because:** the prompt must be identical on every call (S02-AC8), and an unchanged start keeps Gemini's caching
- **Cost:** a note is not visible in the task that saved it

### D-93 · Forgetting, cheapest first, measured not guessed
✅ Accepted · S07
- **Chose:** (1) a tool result over 10,000 characters is cut to its start and end plus a marker; (2) past 50% of the working window, old tool results become one-line stubs, in batches; (3) still past 70% after that: one Flash-Lite call summarizes the oldest turns. The fill is the last reply's real input-token count; after pruning, an estimate (characters ÷ 4)
- **Instead of:** a tokenizer, or always summarizing
- **Because:** the model reports exact usage; pruning is free and invents nothing
- **Cost:** the 50% / 70% lines are my choice (set under `[trimming]` in `workspace.toml`)

### D-94 · The working window is small on purpose
✅ Accepted · S07
- **Chose:** `[trimming] window_tokens = 20000` for CloudCo, far below Gemini's 1M
- **Instead of:** the model's real limit
- **Because:** cost and quality fall long before 1M, and a small window lets the demo show trimming
- **Cost:** trims earlier than strictly needed

### D-95 · Trimming never touches the model's own steps
✅ Accepted · S07
- **Chose:** only tool results are shortened, and only whole old turns are replaced by a summary. A call's result is never removed while its call is kept. The saved file keeps everything; trimming changes only what is sent
- **Instead of:** editing steps in place
- **Because:** Gemini needs model steps and their thought signatures exactly as received
- **Cost:** a trimmed run is not byte-identical to the saved file

### D-96 · A line under the agent's name
✅ Accepted · UI · your request
- **Chose:** `description` in `workspace.toml` (one short line), shown under the agent menu
- **Instead of:** nothing, or putting it in the menu itself
- **Because:** a name alone doesn't say what the agent is for
- **Cost:** none

### D-97 · Fall back to another model on 429 / 503, for the rest of the run
✅ Accepted · S09 · your gap review
- **Chose:** `[models] fallback = [...]` in `workspace.toml`. A 429 or 503 moves the run to the next model at once and it stays there; a `model_fell_back` event names both models and the error. Each call is priced by the model that answered
- **Instead of:** SDK retries (they slept for the server's Retry-After: D-42), or retrying the same model
- **Because:** on the free tier one busy model ended run after run; Flash-Lite drops (does not reject) Flash's thought signatures, so switching mid-run is safe
- **Cost:** the rest of the run uses the smaller model; other errors still end the run
- **Revisit if:** a paid tier makes 429s rare

### D-98 · A checkpoint per step, and Resume
✅ Accepted · S09 · your gap review
- **Chose:** each step also appends `{"kind": "checkpoint", "run_id", "steps", "usd", "seconds"}` to the conversation file. A turn with no finish line can be resumed: the loop carries on from the saved steps, with no new message, and the budget starts from the checkpoint. A tool call that never got its result stays "cancelled"
- **Instead of:** asking the person to type the question again (step count and cost restart, and the half-done work is easy to lose)
- **Because:** a crash at step 15 of 25 should cost one step, not the run
- **Cost:** one line per step; the model may repeat a lookup that was cancelled

### D-99 · The Harness pane in seven sections
✅ Accepted · S09 · your pick
- **Chose:** Agentic Loop (+ output contract) · Models (new) · Context · Tools (+ hand-off to helpers) · Environment (new) · Guardrails · State & Memory (renamed). Where something is not enforced, the pane says "by convention" or "not restricted"
- **Instead of:** keeping five longer sections, or nine (one per question group)
- **Because:** every question a reviewer asks has one home, without a section per question
- **Cost:** a longer pane; every section starts collapsed

### D-100 · Declared, not built: sandbox, per-role effort, output schema
✅ Accepted · S09 · your pick
- **Chose:** the pane shows the truth: workspace tools run in the server's own process, file limits beyond `read_file` and the harness's writes are convention, network is not restricted; effort is per run only; answers have no schema
- **Instead of:** a static scan of workspace tools, `thinking` per role, a JSON schema for answers
- **Because:** real enforcement needs a container this local project doesn't have; a schema conflicts with plain answers (D-82)
- **Cost:** a workspace's Python could reach the network or the disk; downstream systems can't rely on a shape
- **Revisit if:** the harness is hosted for others, or a system consumes its answers

### D-101 · Short-term vs long-term memory, and a Memory page to see and forget facts
✅ Accepted · S07 · your request ("this section is very unclear")
- **Chose:** the Harness pane's Memory has two parts: **Short-term** (this conversation, resent each task) and **Long-term** (facts kept across conversations). Pruning and summarizing moved to **Context → Context management**: they keep one call small, they are not memory. A **Memory** page in the left lane lists every profile's facts side by side, newest first, each with **Forget** (two clicks)
- **Instead of:** notes, conversations and the working window mixed in one pane section
- **Because:** people need to see what the agent keeps about their work, per profile, and be able to remove it
- **Cost:** forgetting rewrites the facts file (the one memory file that is not append-only); the agent sees the change from its next task

### D-102 · Claude as a second provider, through the same model boundary
✅ Accepted · S09 · your request
- **Chose:** an `AnthropicModel` next to `GeminiModel`, behind the same `create(system, steps, tools)`. It translates the loop's steps to Claude's messages (`tool_use` / `tool_result`) and back, keeps Claude's `thinking` blocks exactly as received, and maps effort to `output_config.effort`. Models: `claude-haiku-5-5`, `claude-sonnet-5-5`, priced in `pricing.toml`. SDK retries off, like D-42
- **Instead of:** a neutral step format for both (a rewrite of every stored conversation), or Gemini only
- **Because:** one loop, one gate, one approval channel for both; the translation lives in one file
- **Cost:** thinking doesn't cross providers: on a switch mid-conversation the other provider's thinking steps are left out
- **Changes:** the "Gemini only" rule in `CLAUDE.md` becomes "Gemini by default; Claude as a paid option the person picks"

### D-103 · On a Claude run, small calls use Claude Haiku 5.5
✅ Accepted · S09 · your pick
- **Chose:** when the run's model is Claude, the helper, the off-topic check, titles and summaries use `claude-haiku-5-5` instead of their Gemini Flash-Lite setting
- **Instead of:** keeping them on Gemini (free, but out of quota some days)
- **Because:** a Claude run should not fail because Gemini's free quota ran out
- **Cost:** a little more per run (Haiku: $0.10 / $0.50 per 1M tokens)

### D-104 · The person pays for Claude, so nothing automatic calls it
✅ Accepted · S09 · your instruction ("don't use it for local testing at all")
- **Chose:** `ANTHROPIC_API_KEY` in `.env`, loaded by `config.py` only and redacted like the Gemini key. Offline tests use a recorded stand-in for the SDK; `make live` and every live test stay on Gemini; Claude runs only when the person picks it in the model menu (or names it in the CLI)
- **Instead of:** live Claude tests
- **Because:** every Claude call costs the person money
- **Cost:** Claude is checked live only by the person's own runs

### D-105 · A profile is told what it can't do, and the one sentence to say
✅ Accepted · S05 · your report ("engineering should be denied with a different message")
- **Chose:** the harness adds a "Not available to <profile>" section to the prompt, built from the gate and the workspace's profiles: each blocked tool's first description line, and the reply to give ("Engineering can't do that here. Sales can."), with no details, drafts or workarounds. The tool stays hidden and blocked as before (D-75)
- **Instead of:** leaving the model to improvise around a tool it can't see
- **Because:** found live: asked to send, Engineering explained approvals and repeated contract terms
- **Cost:** a prompt rule, so a model can still word it differently; the block itself is in code

### D-106 · Tools know the asking profile, so they can leave things out in code
✅ Accepted · S05 · your pick ("filter in the tool")
- **Chose:** `ToolContext.profile` is set by the loop for the main agent and every helper (a helper gets its caller's profile). CloudCo's `review_contract` leaves out §3 (fees and discounts) and §4 (invoicing and payment) for Engineering, says how many edits it left out and why, and returns no text for a single hidden clause
- **Instead of:** a firmer prompt rule (Haiku already ignored the softer one), or leaving contract text visible
- **Because:** found live: the reviewer returned ShopCo's payment terms to Engineering as plain text; field masking (D-76) only covers structured fields
- **Cost:** each workspace tool must filter its own free text; a new tool that returns text needs the same care

### D-107 · Engineering sees only technical clauses, and has its own review skill
✅ Accepted · S05 · your picks ("technical only", "own technical skill")
- **Chose:** an allow-list instead of D-106's deny-list. In a contract, Engineering sees sections 5 The services, 6 Service levels, 7 Support, 8 Data protection, and appendices A and B; everything else is left out with one neutral note ("Only technical clauses are shown to Engineering; Sales handles the rest": no count, no topics). In policy, it reads standard-terms §4 and the uptime line of approval-chart §1. Engineering gets a `technical-review` skill; the full `contract-review` moves to Sales
- **Instead of:** hiding fees and payment only (term, price locks, liability and payment rules from the policy still reached Engineering, found live)
- **Because:** spec/01-company.md: Engineering answers technical questions and approves uptime up to our record; prices, payment and the commercial review are Sales'
- **Cost:** a new contract section must be added to the allow-list to reach Engineering

### D-108 · Evals are their own stage, built next
✅ Accepted · S10 · your pick ("own stage, next")
- **Chose:** a new stage S10 · Evals, built right after S07, which takes over S08's eval part (AC7, AC8). S08 keeps the swap test, replay, export and demo mode
- **Instead of:** growing S08, which would hold swap test, replay, demo, DeepEval and a new page
- **Because:** one clear goal per stage
- **Cost:** stage numbers no longer follow the build order (the Tracker says so)

### D-109 · Code checks exact rules; a judge model checks judgment
✅ Accepted · S10
- **Chose:** three metrics in code (tool and argument correctness, guardrails held, guardrails across turns) and nine judged by a model (plan adherence, argument correctness, task completion, step efficiency, knowledge retention, conversation completeness, role adherence, topic adherence, turn faithfulness)
- **Instead of:** judging everything with a model, or only code checks
- **Because:** safety rules must be exact, free and never flaky; completeness and faithfulness can't be read by code
- **Cost:** two kinds of metric to explain

### D-110 · DeepEval scores a replay of our saved trace
✅ Accepted · S10 · proven in a spike (no model calls)
- **Chose:** `evals/replay.py` re-emits a saved run as DeepEval spans (`@observe` agent → llm / tool, a helper as a nested agent) inside `evals_iterator`, so the trajectory metrics get a real trace
- **Instead of:** `@observe` inside the harness core, or plain test cases (TaskCompletion, StepEfficiency and PlanAdherence "MUST be used in the `evals_iterator` or `observe` decorator")
- **Because:** the harness core stays free of DeepEval, and a saved run can be re-scored for judge cost only
- **Cost:** a replay layer to explain
- **Changed 2026-11-11:** each metric is called directly (`a_measure`) on a test case carrying the trace dict built from our events, instead of `@observe` spans inside `evals_iterator`; same trace shape, no DeepEval global state or files, and each score names its own judge

### D-111 · The judge goes through our own model clients: Gemini Flash-Lite, then Claude Haiku
✅ Accepted · S10 · your pick ("Gemini with fallback as Claude Haiku")
- **Chose:** a small `DeepEvalBaseLLM` wrapper over `make_model`. The judge is Gemini 3.5 Flash-Lite; a 429 or 503 switches the rest of the eval to Claude Haiku 5.5, only if `ANTHROPIC_API_KEY` is set. Every score records its judge; costs come from `pricing.toml`
- **Instead of:** DeepEval's own `GeminiModel` (its own key handling and retry policy), or Claude only
- **Because:** one key path (`config.py`), no hidden retries (D-42), real costs, and the eval still finishes when Gemini's free quota runs out
- **Cost:** Haiku costs a few cents per eval; two judges can score differently
- **Changed 2026-11-12** (your request): the Run dialog picks the judge as well as the agent, in the same animated menu. Gemini 3.5 Flash-Lite stays the default (`EVAL_JUDGE_MODEL` in `config.py`); a Claude judge is paid from the first call and has no fallback

### D-112 · A case passes only if all 3 runs pass
✅ Accepted · S10
- **Chose:** 3 runs per case (1 while building), pass^3
- **Instead of:** one run, or an average
- **Because:** one lucky run doesn't count; an agent that fails one run in three isn't reliable
- **Cost:** 3× the quota

### D-113 · An Evals page with a Run button behind a dialog and a budget cap
✅ Accepted · S10 · your pick ("show + run button")
- **Chose:** a sidebar page with DeepEval's two category tables, a cases × metrics grid, reasons and history; a Run button opens an in-page dialog (cases, runs, model, judge, estimated calls, cap) and starts one fixed command; one eval at a time, with Stop
- **Instead of:** results only, run from the terminal
- **Because:** see, learn and start evals in one place
- **Cost:** one click spends quota; guarded by the dialog, the cap and one-at-a-time

### D-114 · 12 metrics, not all of DeepEval's
✅ Accepted · S10 · your review of DeepEval's categories
- **Chose:** the 12 metrics in `spec/stages/S10-evals.md`; skipped: PlanQuality, TurnRelevancy, GoalAccuracy, ToolUse, the turn contextual relevancy / precision / recall metrics, and a separate Custom block
- **Instead of:** every metric in the two tables
- **Because:** each skipped one overlaps another or grades something this agent doesn't have (a ranked retriever); the page still shows them, greyed, with the reason
- **Cost:** about 10 judge calls per run

### D-115 · Everything for evals lives in a dedicated `evals/` folder
✅ Accepted · S10 · your request ("all of this should be in a dedicated evals folder")
- **Chose:** `evals/` at the top level (runner, replay, checks, judge, report, cases), `tests/evals/` for its tests, results in `.agentic-harness/evals/`. The server reads result files and starts `python -m evals.run` as a fixed command
- **Instead of:** `src/agentic_harness/evals/`
- **Because:** the harness never imports DeepEval; a workspace's cases sit next to the code that runs them
- **Cost:** one more top-level folder to lint, type-check and cover

### D-116 · When Gemini runs out mid-eval, the agent moves to Claude Haiku
✅ Accepted · S10 · your request ("if Gemini is out of free tier, fall back to Claude Haiku; evals should not break")
- **Chose:** on a 429 or 503 the eval's agent switches to Claude Haiku 5.5 for the rest of the eval, and the run that hit it starts again (a half-run never counts). Only with `ANTHROPIC_API_KEY`; a Claude agent has no fallback. The result names both models; the Run dialog says what happens if Gemini runs out. Same rule as the judge (D-111)
- **Instead of:** stopping the eval (before), or retrying Gemini later
- **Because:** a 16 × 3 eval needs more calls than one day of free quota; the person started the eval, so the paid fallback is theirs (D-104)
- **Cost:** Haiku agent runs cost cents each; the eval's $0.50 cap still stops it with a named reason. Runs before and after the switch used different models

### D-117 · A Next Run cost panel: what each role costs, and what you pay
✅ Accepted · S10 · your request ("cost projected beside the models, for the agent and for judging")
- **Chose:** three cards on the Evals card (Agent, Judge, You Pay). Each role card shows Free Tier or Paid, one big number, the work it does and Google's free daily limit where known (`free_per_day` in `pricing.toml`: Flash-Lite 500, 3.6 Flash 20); You Pay shows the total, the range if Claude Haiku takes over, and how agent and judge split it. Token counts are the averages of your last 5 evals (agent tokens and replies per turn, judge tokens per call, now saved in each result); cautious numbers before any
- **Instead of:** one line of text in the Run dialog
- **Because:** picking a model is a cost decision; seeing it beside the picker, per role, makes the choice clear to anyone
- **Cost:** results files gain a token block (older ones are skipped); 3.8 Flash shows "Free limit unknown" until we know its limit

### D-118 · After the first full eval: judge errors aren't failures, a clean trace for the judge, Turn Faithfulness dropped, the scope check reads the last exchange
✅ Accepted · S10 · your review of the 2026-11-12 eval (9 core tests, Haiku as agent and judge, 2 of 9 passed)
- **Chose:**
  - a metric whose judge fails is **Not Scored**, and one with nothing to grade is **Not Applicable**: both are shown with the reason and never fail a case; the judge tries once more on a reply in the wrong shape;
  - Turn Faithfulness is dropped (it crashed on every case, and it grades retrieval we don't have): 11 metrics;
  - the judge's copy of the trace leaves out `load_skill` (the skill text becomes "the plan") and nests each helper inside its `delegate_task` call;
  - the scope check also reads the last question and answer, so follow-ups pass;
  - the reply skill always tries to send when asked (the approval step asks the CFO);
  - on the page: an activity panel, time estimates, a progress ring while running and a labelled pass-rate ring after, This Run cost, Reset, delete a past eval, case groups folded.
- **Instead of:** counting judge errors as failures; keeping the raw trace; leaving the scope bug deferred
- **Because:** 5 of the 7 failures came from our scoring or our hand-off, not the agent; an eval has to blame the right thing
- **Cost:** Not Scored metrics can hide a judge that keeps failing (the reason is shown, and the count is visible per case); the scope check reads a little more text per task
