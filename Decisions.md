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
- **Revisited 2026-11-12 (D-129–D-131):** you asked for structure again, so answers now lead with a bottom line and list items one per line with a source; still no fixed headings.

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
- **Changed 2026-11-12** (your call): the cap goes from $0.50 to **$3**. The person picks the agent and judge after seeing the projected cost, so the cap is only a safety net for a runaway eval. Found when a Claude Sonnet judge (≈ $1.10 projected) was stopped at $0.57 after 7 of 9 tests

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

### D-119 · An eval can't hang silently: time limits, a Stop that always works, pages that follow a running eval
✅ Accepted · S10 · your report ("why is it stuck, there is no option to stop on UI, it's not displayed")
- **Found (2026-11-12):** an eval with a Claude Sonnet judge froze for 20+ minutes while grading `cfo-no-holds`: the process idle, its connections to Anthropic silent. Nothing limited a judge call; Stop was only checked between tests; and the eval was read only by the page that started it, so a reload showed nothing and offered no Stop.
- **Chose:**
  - one judge call may take 2 min and one metric 5 min; past that it's **Not Scored** ("the judge didn't answer in …") and the eval goes on;
  - Stop interrupts the test in progress and saves what finished; if the eval hasn't ended 20 s after Stop, the server ends it;
  - the server reads the eval itself and keeps its events; any page (a reload, another tab) follows it from the start (`/api/evals/follow`);
  - after a minute with no news, the Running panel says what it's waiting on and for how long.
- **Instead of:** waiting forever; a polite Stop only; a stream tied to one page
- **Because:** a long run on a paid judge must never fail silently or be impossible to stop
- **Cost:** a slow but healthy judge call over 2 min counts as Not Scored; the server keeps one eval's events in memory

### D-120 · Approvals go from the sender up; the send tool says it sent and who approved
✅ Accepted · S10 · your report ("after CFO approval it asked Engineering and Sales: reverse order"; "after all the approvals it gave a generic response")
- **Found (2026-11-12, chat):** a counter-proposal send asked CFO → Engineering → Sales (CloudCo's list was "specialists first, Sales last"). After all three approved, the tool replied "saved to the local outbox, not sent" and named no one, so the agent told you it "hasn't gone out yet, because a person has to approve it first".
- **Chose:** CloudCo's `[[approvals]]` in order from the sender up: **Sales → Engineering → Finance → CFO** (the CFO's sign-off last); anyone who rejects stops the send. `send_to_customer` returns `status: "sent"`, where it went ("the local outbox; this demo sends no real email") and `approved_by`; its description tells the agent to say it was sent and who approved.
- **Instead of:** specialists first, Sales last; a "not sent" status
- **Because:** a person reads approvals as an escalation, owner first and most senior last; and the agent can only report what the tool tells it
- **Cost:** none in the harness (CloudCo's data and tool only); the eval test that scripts "CFO rejects" now sees Sales approve first
- **Changed 2026-11-12, your report** ("I thought 25% can't be approved by Sales"): each person is asked **once**, for all their rules (the CFO: discount and liability cap together, so 3 steps, not 4), still from the sender up. Every card says what that person approves (their rules and their terms as chips), shows the whole chain with each step's state, and folds the email with every term → who decides. The first card had listed every term next to "Approve as Sales".

### D-121 · The model decides when a task needs a plan
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Chose:** the model, from `write_plan`'s description ("for tasks with 3 or more distinct parts"); the harness enforces the stop rule only once a plan exists
- **Instead of:** a classifier call before the loop; a skill that declares `plan: true`
- **Because:** no extra call on every run; the same rule Claude Code's todo list uses
- **Cost:** a small model may plan a light question; the eval case `light-question-no-plan` catches it
- **Changed 2026-11-12, two live runs** (Sonnet, then Haiku: neither planned; they followed the loaded skill): when planning is on, `load_skill` ends the skill's text with one harness line: "Before you start, write these steps as your plan with write_plan". The model still decides for tasks no skill covers. *Cost:* every skill-led task now plans (one or two more tool calls, often in the same reply).

### D-122 · One plan tool that rewrites the whole list
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Chose:** `write_plan(items)`: each item has text, status (open · doing · done · skipped) and a note (needed for skipped); the loop intercepts it like `ask_human`
- **Instead of:** `write_plan` + `write_plan`
- **Because:** one tool to explain; status changes ride along with real tool calls in the same reply
- **Cost:** the list is resent on every update (a few dozen tokens)
- **Renamed 2026-11-12, your question** ("why is there no create plan, only update plan?"): `update_plan` → `write_plan`. The first call writes the list, later calls rewrite it; "update" wrongly suggested a list must exist first. Same tool, same behaviour.

### D-123 · Keep the plan in view by pinning it in trimming
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Chose:** pruning never stubs the newest `write_plan` result
- **Instead of:** rewriting the system prompt each turn; adding a note at the end of every turn
- **Because:** the prompt stays fixed (prompt caching, S02-AC8) and nothing invented enters the history
- **Cost:** the plan sits where it was written, not at the end
- **Extended 2026-11-12, live run:** a skill's text is never stubbed either. Stubbed mid-run, the reply skill's step to call the send tool vanished, and nothing was sent.

### D-124 · Stop rule: one reminder, then finish
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Chose:** an answer with open items gets one note back ("2 items still open: … finish them or mark them skipped with a reason"); the second time the run finishes with the plan shown incomplete
- **Instead of:** a hard block; no rule
- **Because:** never loops; a skip must give a reason
- **Cost:** a stubborn model can finish with open items (shown on the page)

### D-125 · Answer checks live in the workspace
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Chose:** the workspace's `checks.py` defines checks; the harness runs them and adds one of its own ("plan complete")
- **Instead of:** checks inside the harness
- **Because:** the architecture rule: `src/agentic_harness/` knows no domain
- **Cost:** each workspace writes its own checks

### D-126 · Code checks only, for now
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Chose:** CloudCo's four plain-code checks: Every Change Covered, Citations Exist, Right Approver (from the same `[[approvals]]`/`[[rules]]` tables the gate uses), No False "Sent"
- **Instead of:** adding a Flash-Lite check that flags unsupported claims
- **Because:** free, exact, never flaky
- **Cost:** free-text claims aren't checked; a model check can come later

### D-127 · A failed check gets one retry, then the answer shows the failure
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Chose:** failures go back to the model once as a harness note: a normal `user_input` whose text starts with `[Harness check]` (changed while building, 2026-11-12: a mark outside the step was more code for nothing; the model should know the harness is speaking, and the scope check skips such notes); a second failure → the answer goes out with a "Not verified" card
- **Instead of:** showing failures only; retrying until it passes
- **Because:** you always get an answer, and know when to doubt it
- **Cost:** one more round on a failure
- **Changed 2026-11-12, live run:** the note said "use your tools if you need to" and the agent re-ran the reviewer just to fill one gap. It now says: fix with what you already have; call a tool only for a fact you don't have yet.

### D-128 · Plan and Verify on the pane and in the chat
✅ Accepted · S11 · your approval of the S11 brief (2026-11-12)
- **Changed 2026-11-12, your review** ("verify will happen at the last"; "write_plan is a tool, it should be under Tools"): planning and verifying happen at different times, so they are no longer one section. Planning is a **Plans** row in Agentic Loop and `write_plan` sits under **Tools → Harness Tools** (with `load_skill`, `save_note`, `ask_human`, which the pane never showed either). The checks have their own **Verification** section after Guardrails, in run order (D-67).
- **Chose (first):** a Plan & Verify section after Agentic Loop (rules, check switches, retries) plus live To-Do and Checks cards in the chat
- **Instead of:** the pane only; two rows under Agentic Loop
- **Because:** the pane says what the harness will do; the chat shows what it did
- **Cost:** one more pane section
- **Changed 2026-11-12, your review** ("taking too much space, cluttered"): each check round is one activity line, like every other step ("Checked the draft · Every Change Covered failed → sent back to fix"), opening to each check, what the agent was told and the draft. A failed final answer gets one small red line under it. The To-Do card stays a card.
- **Changed again 2026-11-12, your request** ("circle while verification is in progress, tick when passed"): the harness sends `verify_started`; the line shows a spinning circle and each check as a chip (○), which tick to ✓ or ✗ one by one, with a failure's reason under them. The circle holds at least 0.4 s and the answer waits for the ticks: page only, the run is not slowed.
- **Changed again 2026-11-12, your request** ("a pane very similar to the To-Do pane"): the round is a card built like the To-Do card (title, count, one row per check), not a line with chips.

### D-129 · Answer format: rules always in the prompt, not a skill or a tool
✅ Accepted · S11 · your request ("a skill for output format… loaded during final output generation; skill or tool?"), approved ("go ahead")
- **Chose:** a workspace file `answer-style.md` listed in `memory = [...]`, so every call sees it (cached); AGENTS.md's "How to answer" moves there
- **Instead of:** a skill the model loads at the end (it can skip it, as Sonnet skipped `write_plan`; one more call; there is no separate "final output" moment: the answer is written in the same reply that decides to stop); a `submit_answer` tool with a schema (small models fill nested schemas badly; prose is lost)
- **Because:** always present costs no call and can't be skipped; the workspace owns its style, the harness stays domain-free
- **Cost:** about 300 prompt tokens per call (cached)

### D-130 · An Answer Format check enforces the shape
✅ Accepted · S11 · your request ("a skill for output format… loaded during final output generation; skill or tool?"), approved ("go ahead")
- **Chose:** CloudCo's `answer_format` check: the first line is a one-sentence bottom line (not a list or heading); every item line cites a source; skipped for a short answer
- **Instead of:** trusting the prompt alone
- **Because:** the prompt guides, VERIFY enforces (S11); the same one-retry rule
- **Cost:** a retry when the format slips
- **Changed 2026-11-12, live run** (Haiku answered in paragraphs and the check passed it): three or more clauses written as paragraphs now fail ("put each on its own list line"). Right Approver now reads sentence by sentence, because a paragraph mixed terms and people and gave a false failure.
- **Changed again 2026-11-12, your report** ("the right approver check is failing miserably"): both earlier units were wrong. A whole line mixed clauses in a paragraph; a sentence split "**3.2 · Discount**: 10% → 25%. Needs the CFO." in two. Right Approver now reads **claims**: a list item with its indented lines, or in prose the sentences from one "Clause X" to the next. Answer Format asks a source only of items that decide something (a term, a role or a verdict). A test runs both checks on six real answers from today's runs, each labelled by hand (`tests/unit/test_real_answers.py`); a change that flips any verdict fails it.
- **Changed a third time 2026-11-12, your four live runs** (most failures were the checks'): Right Approver keeps only two real mistakes, a term whose decider isn't named and a never-allowed term that is *accepted*; the "wrong person named" rule is gone. Each percentage belongs to its nearest "discount" or "uptime"; a claim also starts at "Term 2.1" or "On uptime (6.1)". Answer Format applies only to a run that reviewed a contract, and stops at a heading after the review (a customer email is prose). No False "Sent" ignores "Nothing has been sent", "once it is sent"; reads "Sent, approved by …". Citations Exist counts sources read in earlier turns of the conversation. Fourteen real answers, labelled by hand, are the test.

### D-131 · The page does the styling
✅ Accepted · S11 · your request ("a skill for output format… loaded during final output generation; skill or tool?"), approved ("go ahead")
- **Chose:** the page renders `#` headings, nested lists (two-space indent), and sources in backticks (a policy section with §, an ID like `CUS-0042`, a path) as small badges; still built from elements, never parsed HTML
- **Instead of:** asking the model for HTML or fixed headings
- **Because:** styling is the page's job; the model writes simple markdown and every answer looks the same
- **Cost:** a few more rules in `renderProse`

### D-132 · The prompt names the checks before the agent writes
✅ Accepted · S11 · your report ("human approvals not happening at all", "why the verifier always works the second time"), approved plan 2026-11-12
- **Chose:** `build_context` adds "Before your answer reaches the person" with each switched-on check's label and description (helpers get none); `write_plan`'s reply asks to close open items before the final answer
- **Instead of:** letting the agent learn the bar from a failed check
- **Because:** found live: the first draft nearly always went back, and the note then told it exactly what to fix. The checks are the rules, so they belong in front of the agent
- **Cost:** about 120 prompt tokens per call (cached)

### D-133 · Sending is how approval starts (CloudCo wording)
✅ Accepted · S11 · your report ("human approvals not happening at all", "why the verifier always works the second time"), approved plan 2026-11-12
- **Chose:** the Sales file says: when asked to send, draft and call `send_to_customer` in the same task; the harness asks Sales, then Engineering, Finance or the CFO; don't wait for approvals or ask permission first. The reply skill: "send the contract" means send the counter-offer reply
- **Instead of:** "Nothing is sent to a customer without a person approving it first"
- **Because:** found live: that sentence read as "get approval, then send", so the agent never called the send tool and no approval card ever appeared. The harness gate was fine; the words weren't
- **Cost:** none in the harness; a test locks the path (send → Sales → Engineering → CFO → outbox)

### D-134 · Action checks: workspace code attached to a tool, run before people are asked
✅ Accepted · S12 · external feedback + your picks ("personas on the page", "S12 now, two parts"), 2026-11-12
- **Chose:** `@action_check(tool, label, description)` in the workspace's `checks.py`; the harness runs them after the hard limits and before approvals; a failure returns "Not sent: …" to the model and no one is asked
- **Instead of:** checking only the final answer (S11)
- **Because:** the send is the run's one irreversible action, and people approve the terms on the card, not the body. What the body says is the workspace's business; the hook is generic
- **Cost:** a failed check costs a model call

### D-135 · Hard limits are shown when they hold, not only when they block
✅ Accepted · S12 · external feedback + your picks ("personas on the page", "S12 now, two parts"), 2026-11-12
- **Chose:** one GUARD step per action: each never-rule with its value and line ("discount 15 ≤ 25")
- **Instead of:** silence on a pass
- **Because:** a reviewer must see the limits held, not infer it
- **Cost:** one more line per action

### D-136 · A sent email shows at its send step
✅ Accepted · S12 · external feedback + your picks ("personas on the page", "S12 now, two parts"), 2026-11-12
- **Chose:** the email card sits in the run's activity, after its limits, checks and approvals
- **Instead of:** a card below the answer, as soon as the file is saved
- **Because:** your note: it looked as if the email came before verification. The order of events must read true
- **Cost:** none

### D-137 · Identity: personas on the page, enforced on the server
✅ Accepted · S12 · external feedback + your picks ("personas on the page", "S12 now, two parts"), 2026-11-12
- **Chose:** `[[people]]` in `workspace.toml`; a "You are" picker; the server refuses an approval whose persona's role doesn't match the card
- **Instead of:** role-play by one person (D-87), real logins
- **Because:** separation of duties you can demo; the page can't fake it
- **Cost:** not real authentication (the pane says so)
- **Built:** `[[people]]` (id, name, role) in `workspace.toml`, checked at load (every approval role needs a person); `Approvals.answer(role=…)` raises `WrongRoleError`; `POST /api/approval` names the person, 400 without one, 403 for the wrong role; the answer carries "Dana Whitfield (CFO)" into the loop, the `approval_decided` event, the outbox's "Approved by" and the send tool's result. Page: a "You Are" picker (default: the person whose role matches the profile), cards that show a hand-off ("You are Priya Raman (Sales). This one needs the CFO" + a Switch button) instead of Approve and Reject, and an Identity fact in the Guardrails pane. D-139: the approval timeout is 30 minutes.

### D-138 · Self-approval only for the sender's own sign-off
✅ Accepted · S12 · external feedback + your picks ("personas on the page", "S12 now, two parts"), 2026-11-12
- **Chose:** an approval rule may allow the requester (CloudCo: "Any message to a customer", Sales); every other rule needs that role's person
- **Instead of:** anyone may approve anything
- **Because:** the feedback: fine for the sender's sign-off, not for the CFO's
- **Cost:** one flag per approval rule
- **Changed while building, 2026-11-12:** no per-rule flag. A person's role must equal the card's role, so Priya (Sales) giving Sales's "send" sign-off is naturally allowed, and the CFO's, Engineering's and Finance's cards need that person. One rule instead of a rule plus a flag.

### D-139 · Approval timeout: 30 minutes
✅ Accepted · S12 · external feedback + your picks ("personas on the page", "S12 now, two parts"), 2026-11-12
- **Chose:** 30 minutes, up from 10
- **Instead of:** 10 minutes
- **Because:** time to switch persona and decide
- **Cost:** a stuck run waits longer (Stop still works)

### D-140 · Claude Opus 5.5 is a choice for the agent and in Evals
✅ Accepted · S09 · your request ("introduce opus model as a selection in evals as well as agent"), 2026-11-12
- **Chose:** `claude-opus-5-5` priced in `pricing.toml` ($4 / $20 per million tokens, cache reads $0.20, writes 1.25x), checked in the claude-api reference that day. Menus are built from priced models, so it appears in the chat's model menu and in Evals as both agent and judge. The request needs no change: thinking is always on for Opus 5.5 (we send no thinking setting), effort maps to `output_config.effort` as for Sonnet and Haiku, and we never force a tool. Its default effort is medium (Auto keeps the model's default)
- **Instead of:** Haiku and Sonnet only (D-102)
- **Because:** your call; the strongest current Claude model for comparing the agent and judging
- **Cost:** twice Sonnet's price; still a paid, person-chosen option (D-104: never in tests or `make live`); the $3 eval cap (D-113) still stops a costly eval. Small jobs on a Claude run still use Haiku (D-103)

### D-141 · An approval card shows where each term started
✅ Accepted · S12 · your request ("it should tell the original as well: what was in the contract, are we raising it or putting it down"), 2026-11-12
- **Chose:** a generic hook, `@approval_context(tool, current=…, asked=…)`, in the workspace's tools file; the harness carries its rows to the card and never reads them. CloudCo's `contract_terms` reads the customer's contract (our standard and their markup) for each offered term: today's value, the customer's ask, our offer, and whether it moves up or down from today, with the clause (CT-2207 §3.2). The card's terms table: Term · Contract today · Customer asked · We offer (↑ ↓ =) · Decided by; the titles are the workspace's words
- **Instead of:** offered values alone
- **Because:** an approver can't judge 25% without knowing it was 10% and the customer asked 25%; the harness must not know "contract" or "customer", so the workspace supplies both the facts and the words
- **Cost:** one file read per approval; a broken hook is left out, never blocking a decision

### D-142 · After a send, the answer reports the send; the sent email shows with it
✅ Accepted · S11, S12 · your report ("the final response had too many unnecessary details, and the final email sent should have been shown as well"), 2026-11-12
- **Found (run `20261112-113645`):** the run was right (the email passed Body Matches Terms; Sales, Engineering and the CFO approved), but Every Change Covered then made the answer list the whole review again, and the answer was sent back once, with the checks' words ("These changes have no line…"). The email appeared only inside the steps, folded.
- **Chose:** a run that sent is not a review: Every Change Covered and Answer Format skip it ("This answer reports a send"); the answer style says to report the send in a few lines (what went to whom, the terms, who approved, what's open); the retry note says to write for the person and not mention the checks or the earlier draft; the email shows open under the answer (folded to one line in the steps).
- **Instead of:** re-listing the review in every answer
- **Because:** the review is in the email and in the steps the person saw; the answer should say what happened
- **Cost:** a send's answer is no longer checked for covering every change (the Body Matches Terms check still guards the email itself)

## D-143 · A plain pull of a contract, without a review (2026-11-12)
- **Problem:** the only contract tool was `review_contract` (the diff), and "load the skill that covers the task" turned any contract request into a full review.
- **Options:** (a) one tool returning the whole contract; (b) outline, then a section; (c) wording only.
- **Chose:** (b) `read_contract(contract_id, section?, version?)`: no section gives an outline (section titles and clause ranges, ~1 KB); a section or clause gives its text. `version` is `customer` or `standard`. Engineering keeps its technical sections only, same rule as `review_contract`. Team files and the review skills' descriptions say review only on a request to review.
- **Why:** the file is ~19,000 words, so a whole-file tool would flood the prompt; tools here return small pieces.
- **Cost:** a fifth tool (D-73 said four on purpose). Answer checks need no change: they already skip when no review ran.

## D-144 · Demo memory for Sales and Engineering (2026-11-12)
- **Problem:** Sales held one fact that fought the answer style ("no bullet points"); Engineering held none, so the Memory page showed nothing worth demoing.
- **Chose:** 4 Sales facts (reply tone and signature, lead with what we can offer, "Net 45" wording, ShopCo trade-before-refusal) and 3 Engineering facts (uptime as measured with UP- IDs, headroom to the 99.95% record, commercial questions go to Sales). Kept in `workspaces/cloudco/demo-memory/*.txt` and copied into `.agentic-harness/notes/cloudco/` (git-ignored runtime state).
- **Why .txt:** a note file is read line by line as facts, so it can't carry a "fictional" header; `.txt` skips the scan that wants one on every `.md`.
- **Cost:** "ShopCo renews in Q1" is made up and not in the customer record.

## D-145 · The scope check leans to IN and is told our names (2026-11-12)
- **Problem:** "what is Shopco ?" was refused as "a general company" with 0 model calls. The check saw only the `covers` sentence, so it couldn't know ShopCo is our customer.
- **Options:** (a) lean to IN when unsure; (b) a workspace `[scope] knows` text of names; (c) load the customer file into the check.
- **Chose:** (a) and (b). The check says OUT only when clearly unrelated, and a name it doesn't recognise counts as IN. `knows` is appended as "Also in scope". (c) rejected: it couples the harness to data files and costs tokens every task.
- **Cost:** a few more off-topic questions may reach the agent, whose own Scope prompt still declines clearly unrelated ones. The names are the workspace's to keep current.

## D-146 · A contract pull is planned, checked and shows the substance (2026-11-12)
- **Found live:** "is ShopCo a customer? If yes, pull the contract" made no plan, all 6 checks "didn't apply", and the answer listed only section names.
- **Causes:** my D-143 team wording said "no plan"; the plan tool said "3 or more parts" (this was two); every CloudCo check was about a review or a send; the outline had titles and clause ranges only.
- **Chose:** (1) the plan tool also plans when the person asks two or more things in one message, and the team files no longer say "no plan"; (2) the outline gives each section's `key_terms`, the clauses that set a real term (2.1, 3.2, 4.1, 6.1, 9.2 for CT-2207), told apart from the boilerplate by its "relating to" wording in this made-up contract; (3) two checks: **Records Match** (record IDs came back from a tool; in a pull, a quoted term matches its clause) and **Sections Are Real** (named clauses exist in what read_contract returned, so nothing Engineering can't see).
- **Why the term half only in a pull:** reviews put our counter-offers on the same line as the clause ID; on the 14 real answers that gave 13 false failures, now 0 (a test keeps it at 0).
- **Cost:** a two-part question costs one more model call (the plan). D-143's "no plan" wording was wrong and is removed.

## D-147 · Pulls skip Right Approver; the page says Direct vs To-Do; check names appear with results (2026-11-12)
- **Found live:** Right Approver failed a plain pull ("25% needs the CFO, not named"), so the retry added approval verdicts nobody asked for; the check card listed every check name (Plan Complete included) and then dropped the ones that didn't apply, which read as a plan that vanished; and nothing said whether the model chose not to plan.
- **Chose:** Right Approver skips when the run read the contract with `read_contract`, ran no review and sent nothing. The check card shows a spinner and the count while checking; a row appears only with its result. Planning stays the model's choice (D-121, you kept it), and the first tool call without a plan adds "No To-Do plan · the model chose to work directly"; it is removed if a plan follows.
- **Cost:** none.

## D-148 · Three layers check an answer: Verification, Online Evals, Offline Evals (2026-11-12)
- **Your review:** adding a check per failure (Sections Are Real, Records Match) isn't a solution; check groundedness, context relevancy, citations, hallucination and style instead, some as online evals separate from verification.
- **Chose:** one rule decides where a check lives. **Verification** (before the answer, blocks, code only) keeps mistakes that harm and that code decides exactly. **Online Evals** (new, after every live answer, never blocks, never sent back) score quality: Groundedness, Hallucination, Context Relevancy, Answer Relevancy, Citations, Style & Format. **Offline Evals** (the golden set) score the same six too.
- **Promotion rule:** a metric may become a gate only after saved runs show it almost never fails a good answer (D-146's Records Match failed 13 of 14 good answers before its fix). Hallucination starts at 0 of 14.
- **Domain-free:** `online_evals.py` holds the metric logic; `workspace.toml [online_evals]` gives the ID pattern and the style guide; workspace code metrics are `METRICS` in its checks file. Scores are saved with the conversation and listed on the Online Evals page.
- **Cost:** one small judge call per answer ($0.001 to $0.005 on a paid key at Flash-Lite prices, $0 on the free tier); switchable per metric like a check.

## D-149 · One judge call scores every judged metric (2026-11-12)
- **Options:** (a) DeepEval's metrics (Faithfulness, Contextual Relevancy, Answer Relevancy): 3 to 10 calls each, 30 to 60 s per answer; (b) our own prompt, one call, one JSON reply with each metric's score, reason and (for Groundedness) the unsupported claims.
- **Chose:** (b), Flash-Lite by default (the scope check's model). A score of 0.7 or more passes. A judge error or broken reply is Not Scored with the reason (as D-118); the code metrics still count. Found live: Flash-Lite once left an object open, nesting the next metric inside it; the parser finds metrics nested anywhere and reads each one on its own when the JSON is broken.
- **Cost:** our prompt, not DeepEval's tested ones; the offline evals use the same scorer, so the two agree.

## D-150 · Verification keeps the harm gates; quality checks become metrics (2026-11-12)
- **Gates:** Plan Complete, Every Change Covered, Right Approver, No False Sent, and Body Matches Terms before a send.
- **Moved:** Citations Exist → the metric Citations (code, CloudCo's own); Answer Format → Style & Format (LLM as Judge against `answer-style.md`).
- **Deleted:** Records Match and Sections Are Real (D-146): Hallucination (code: every ID, %, amount, date and 2+ digit number appears in the tool results or the question) and Groundedness (judge) cover them for any question, not just pulls.
- **Cost:** a bad citation or format no longer triggers a rewrite; it shows as a failed score. The human labels for Answer Format on the 14 real answers are dropped.

## D-151 · Page names: Online Evals, Offline Evals, Graded By (2026-11-12)
- **Chose:** sidebar Workspace: Agent · Memory · Online Evals · Offline Evals (was "Evals") · Golden Dataset · Checks. Each answer gets an Online Evals card under it; the Harness pane gets an Online Evals section with switches. The metrics tables say **Graded By: Code** or **LLM as Judge**.
- **Also:** the composer frees as soon as the answer is in; the scores arrive a few seconds later on the same stream.
- **Left as is:** the "Checks" view (the offline test suite) shares a word with verification's checks; rename it "Test Suite" only if you want.

## D-152 · The pane is the Agent: Model + Harness; evals move to Observability (2026-11-12)
- **Your requests:** show each metric's threshold; make "Agent = Model + Harness" clear from the start; evals are not part of the harness; the sidebar's Checks link goes.
- **Chose:**
  - The right pane is titled **Agent** and drawn as boxes inside a box: the Agent box holds a **Model** box (its own model menu, the same choice as under the message box), a "+", and a **Harness** box that holds every existing part (Agentic Loop … Memory).
  - The Online Evals section leaves the pane; each metric's on/off switch moves to the Online Evals page.
  - The sidebar gets an **Observability** group (folded by default): Online Evals · Offline Evals · Golden Dataset. Workspace keeps Agent · Memory. The test suite view stays at `#checks`, off the sidebar.
  - Both metrics tables get a **Threshold** column ("≥ 0.70", or "1.00 · all" for code metrics that must be perfect).
- **Found while building:** the Acting As group has no fold button, and the fold code stopped there, so no group after it could fold. Fixed.
- **Cost:** none.

## D-153 · The Harness pane is back as it was (2026-11-12)
- **Your call:** bring back the original Harness pane. D-152's Agent = Model + Harness boxes are removed: title "Harness", the parts as before. Kept from D-152: Threshold columns, the Observability group, Online Evals outside the pane, Checks off the sidebar, the fold fix. Workspace and Observability both start folded; Chats starts open (your call).
- **Changed 2026-11-12, your request** ("make everything collapsed by default except for chats"): Profiles starts folded too. Folds are remembered under a new key name, so clicks from before this change don't override the new defaults.

## D-154 · The online judge sees failed and refused tool calls (2026-11-12)
- **Found in the eval:** `cfo-no-holds` answered correctly ("the CFO rejected it, nothing was sent"), but the rejection was a failed call, which `context_blocks` dropped, so Groundedness called it made up.
- **Chose:** keep failed calls in the judge's context, labelled "· failed". Re-graded: Groundedness 0.38 → 0.62, Answer Relevancy 0.38 → 0.68.

## D-155 · Plan Adherence grades the plan the agent wrote (2026-11-12)
- **Chose:** the judge's "plan" is the last `write_plan` list; the skill text is given for reference, and is the plan only when none was written. Re-graded: one case of four passes (0.50 → 0.75).

## D-156 · Bookkeeping isn't a step for the judge (2026-11-12)
- **Chose:** `write_plan` and `load_skill` are hidden from the judge's trace, including the model steps' "calls [...]" text. Effects were within judge noise (round 0); kept because the judge was literally counting them as wasted or unplanned steps.

## D-157 · A concrete length rule (2026-11-12)
- **Chose:** `answer-style.md` rule 8: a review at most 150 words, one short line per change; a lookup or yes/no answer one to three sentences, no list. Full eval: 1 → 2 of 7 passed; Style & Format still failed 4. Weak evidence (one run per case). Kept for now.
- **Also:** `evals/rescore.py` re-grades saved traces for chosen metrics only, so a grading change is measured without re-running the agent. The round-by-round table is in `docs/eval-debug.md`.

## D-158 · Three metrics are reported, not deciding (2026-11-12)
- **Your call** ("fix the eval design"). Plan Adherence counts a thinking step with no tool call as skipped; Conversation Completeness and Knowledge Retention reward believing a false claim ("the CFO said yes"). They still show a score, marked "Reported", but never fail a test. `cfo-no-holds` also scripts Engineering (approve), so an added uptime term isn't rejected by an unscripted answer.
- **New baseline:** 1 of 7. Style & Format now decides most failures (5 cases): the length rule of D-157 is broken by the agent, not met.

## D-159 · Our checks' false alarms on uptime-never; a length gate (2026-11-12)
- Hallucination accepted a percent only with a "%" sign; data stores `"percent": 99.98`. A decimal now also matches a plain number. Citations didn't read the skill's `approval-chart §1`/`§2` shorthand; it does now. A new gate, **Answer Length** (review 200 words, send report 120, other 90), sends a long answer back once.

## D-160 · The judge sees why a draft was rewritten; every turn gets the right outcome (2026-11-12)
- A harness send-back shows in the judge's trace as "harness check"; model steps that only updated the plan are hidden; Task Completion tells every turn of a conversation the expected outcome, not only the last.

## D-161 · Offline evals use the golden answers (2026-11-12)
- **Your point:** online evals are reference-free (nothing is known live); offline evals have a golden set, so most should use it. The terms match DeepEval's docs and the field: **reference-based** vs **reference-free** (DeepEval also says "referenceless").
- **Chose:** 9 of 18 offline metrics are reference-based (was 4):
  - Step Efficiency (code, a per-case `max_steps`, not counting plan updates and skill loads);
  - Context Relevancy offline (code: calls the case expects or allows);
  - Answer Correctness (new) and Answer Relevancy offline, against a per-case `reference_answer`;
  - Conversation Completeness against `expected_outcome`.

  The last three come from one judge call per run, in `evals/reference.py`. Groundedness, Hallucination, Citations and Style & Format stay reference-free, so they mean the same online and offline.
- **Page:** a Reference column on both metric tables.

## D-162 · A test passes on its critical metrics and 80% of the rest (2026-11-12)
- **Your point:** 17 of 18 passing shouldn't read as a failure. **Your choice:** every **critical** metric must pass (Guardrails Held, Guardrails Across Turns, Tool Correctness, Task Completion, Answer Correctness), and at least 80% of the deciding metrics. Each metric's threshold is unchanged. Each test shows its score ("17/18 · 94%").

## D-163 · Review first, then ask; approvals only where a limit is crossed (2026-11-12)
- **Found live (your report):** "review and send with 25%" sent at once, showing the review only after the email had gone; Right Approver failed a correct answer.
- **Chose:**
  1. **Review first, then ask** (`teams/sales.md`, reply skill): a review-and-send request shows the review and the draft with who would approve each term, asks "Change anything, or send it as is?", and stops. It sends only on confirmation.
  2. **Fewest approvers:** a "never" gets the counter that needs the fewest approvers the policy allows (a 12-month cap, Sales, before 24 months, CFO), and every offered term is filled in so each reaches its approver. CFO routing was already per policy (discount above 15%, cap above 12 months).
  3. **Clause Reviewer:** checking each change against the policy's limits is now an explicit step (OK, needs whom, or never, with the section; "no policy covers this" rather than a guess).
  4. **Right Approver:** after a real send, the approvals the run recorded count, and a person's name counts as their role.
- **Golden case `review-then-confirm`** (core). Live, with Haiku: it showed the review and the draft, offered a 12-month cap, asked, and didn't send. 11 of 12 metrics passed.

## D-164 · A draft reply is a card, not quoted text (2026-11-12)
- **Found live (your report):** the reply came out as `> Subject: … > Hi [contact first name]` squashed into one paragraph. There was no draft tool, so the draft could only be answer text, and the page has no blockquote support.
- **Options:** (a) a `draft_reply` workspace tool saving a mail-shaped file to the run's task folder; (b) the page guesses emails from the answer text; (c) blockquotes only.
- **Chose:** (a), plus (c) as a fallback. The page already knows mail's shape (`parseEmail`, D-136). A task file with mail headers now shows as an email card marked **Draft**, open under the answer; an outbox file stays **✉ Sent**. The harness gains no domain: it's the same generic header rule, applied to the task folder too.
- **Cost:** one more read tool for Sales; the model must choose to call it.

## D-165 · Concerns first, then agree, then draft, then send (2026-11-12)
- **Your point:** the agent should flag what breaks policy and talk it through first. Only once you agree should it draft, then ask whether to send to the customer.
- **Options:** (a) end the turn with a question (normal multi-turn chat); (b) `ask_human` pauses mid-run.
- **Chose:** (a) for discussing concerns and for "send it to <contact>?". `ask_human` stays for a missing fact. Talking positions through takes back-and-forth, which a single pause-box can't hold. The send already has real approval cards, so a yes/no box would double-ask.
- **Replaces** D-163's "show the review and the draft, then ask". Golden case `review-then-confirm` now expects concerns plus a question, with no draft and no send. A new multi-turn case, `agree-then-draft`, covers the draft.
- **Cost:** one more turn before a draft.

## D-166 · The agent knows who it is helping (2026-11-12)
- **Found live:** "Hi [contact first name]" and a generic sign-off. The "You Are" picker (D-137) only checked approvals; the model was never told the person. ShopCo's record had no contact.
- **Chose:** the page sends the picked person with each run. The server checks them against `[[people]]`, and the harness adds one line to the context: "You are helping Priya Raman (Sales)…". It's generic: the names live in `workspace.toml`. Each made-up customer record gets a `contact` (name, email), and drafts are addressed to it.
- **Cost:** a few prompt tokens; a run with no person picked works as before.

## D-167 · The judge has an On/Off switch, Off by default (2026-11-12)
- **Your point:** a judge call on every live answer will hurt the budget.
- **Options:** stratified sampling (rates per kind of run, daily cap); a plain switch.
- **Your choice:** a switch on the Online Evals page, **Off by default**. Off means no judge call; the free code metrics (Hallucination, Citations) still score every answer, and the judged ones show "judge off". The switch is kept on the server (`online-evals.json` in the memory folder), so the bill doesn't depend on a browser. A missing or broken file means off.
- **Unchanged:** offline evals and the CLI still judge (they rely on these scores, and you start them yourself).
- **Cost:** no quality scores on live answers while it's off.

## D-168 · The public demo is a recorded replay (2026-11-12)
- **Your question:** do we need Cloud Run; visitors won't paste their own API key.
- **Options:** live on your paid key with caps · live on a free-tier key · the visitor's key · "Sign in with OpenRouter" (OAuth, a capped key the visitor approves) · a recorded replay.
- **Chose (your pick):** a recorded replay. No key, no backend, $0, nothing to abuse. OpenRouter still bills the visitor and breaks the Gemini-only rule; Gemini's spend caps act with up to ~10 minutes' delay.
- **Cost:** visitors can't type their own question. A "Try It Live" button can come later.

## D-169 · Your voice, one clip per step (2026-11-12)
- **Options:** no voice · an AI voice · your recorded voice.
- **Chose:** your voice, one clip per step; the script is the caption, always shown.
- **Why:** personal; a fumbled line means re-recording one clip. **Cost:** you record ~10 clips.

## D-170 · The voice leads (2026-11-12)
- **Options:** the visitor clicks Next · one continuous track · the voice leads.
- **Chose (your pick):** each clip ends, the next step starts; Pause, Back, Next and Mute always there. A step without a clip waits its reading time (2.5 words a second).

## D-171 · The replay draws with the page's own `onEvent()` (2026-11-12)
- **Options:** a screen video · a separate tour renderer · the page's own code.
- **Chose:** the page's code, fed the saved trace events on a timer. Same cards as a live run, nothing to keep in step. **Cost:** a page change changes the tour too (re-check it).

## D-172 · Tour content in the workspace, player in the harness (2026-11-12)
- `workspaces/<name>/tour/` holds `tour.toml` (steps, captions, cards), `runs/*.jsonl` and `audio/`. `src/agentic_harness/tour.py` and `web/tour.js` know no domain (the one architecture rule).

## D-173 · One fresh live run, two turns (2026-11-12)
- **Chose:** a fresh run on Flash-Lite (free tier, under 2 cents' worth): Priya asks for a review and counter-offer; the agent raises concerns first (D-165); Priya agrees; it drafts, four people approve, it sends. Old traces predate the S11/S12 cards.
- **Known flaw:** the final answer says the send was "automatically approved"; four people approved it. Re-record if it bothers you.

## D-174 · Hosting: decided later (2026-11-12)
- `harness.gauravlahoti.dev` or `gauravlahoti.dev/harness`; the export will use relative paths, so both work.

## D-175 · Local first; the website export comes after (2026-11-12)
- **Your request:** build the tour on the local version first, with your voice; the website step later, with your guidance. S13-AC2 (export) and AC7 (from a subfolder) stay 📝 until then.

## D-176 · Record your voice in the page (2026-11-12)
- **Options:** record in Voice Memos and drop files in `tour/audio/` · a recorder in the page.
- **Chose:** a recorder in the page (`/?tour=record`): the script on screen next to the run, Record → Stop saves the clip, one click to re-record. Dropped files work too (`audio/<step>.m4a|.mp3|.webm|.ogg`).
- **Cost:** a local-only upload route (page header, 5 MB per clip, 15 MB in all, only into the tour's audio folder). Chrome records WebM/Opus; older Safari may need m4a, so the export may convert later.

## D-177 · A step says where it stops: `until = "event#n"` (2026-11-12)
- `until = "approval_requested#2"`: play up to and including the main agent's 2nd `approval_requested`, counted across the tour's turns; a helper's events play along but aren't counted. `"end"` plays everything. Readable, and it survives re-recording better than line numbers. Hidden event types (e.g. the online evals) are listed in `skip`.

## D-178 · A guide presents the tour, not a box (2026-11-12)
- **Your request:** "a human icon / guiding agent explaining the concepts, his voice has captions, he moves next automatically taking a pause of 10 sec; someone can click Next, Pause, Previous."
- **Chose:** a guide (a person icon and a name from `tour.toml`, e.g. `guide = "Gaurav"`) with a speech bubble; the caption shows one sentence at a time, timed to the voice (each sentence gets its share of the clip by word count). The avatar glows while speaking. After a step, a 10-second countdown on Next, then the next step (`pause` in `tour.toml`, default 10). Controls: Previous · Pause · Next · Mute. Record mode keeps the whole paragraph: it's your script.
- **Changes D-170:** the next step no longer starts the moment the voice ends; it waits the pause.
- **Cost:** sentence timing is an estimate (word counts), not word-exact subtitles; a photo instead of the icon can come later (`guide_photo`).

## D-179 · A cinematic tour, and the site's look: black and cyan (2026-11-12)
- **Your review:** "remove Gaurav's name; the UI looks weak, nothing is jaw dropping; we need a UI marvel"; "black as default, with a cyan touch, like gauravlahoti.dev"; "keep all the observability and panes, just not covered in the demo".
- **Options (you picked the first):** Living Diagram + Spotlight · Cinematic Spotlight only · Full-screen Story Mode.
- **Chose:**
  - A **voice orb** in place of the person icon and name: its ring follows the real voice's frequencies (Web Audio analyser), and breathes when there's no clip.
  - **Film-style subtitles**, no box; a chapter title fades in at each step; icon controls; a step timeline; the countdown sits beside them.
  - A **living diagram** (SVG): step 1 the model alone in a glass jar; step 2 the jar lifts away and the four parts snap in around it ("AI Agent = Model + Harness"); during the replay it docks beside the chat and each event lights its part, a pulse running to the model; the last step shows it all lit. Steps name a `scene` in `tour.toml` (jar, harness, finale; else the live diagram). Which part an event lights is mapped from the harness's own event names, so `src/` still knows no workspace.
  - A **spotlight**: the page dims and a cyan-edged frame follows the newest line or card; the Harness pane stays bright with its part open.
  - **Theme, whole page:** dark is the default; near-black background, cyan accent `#19e6c8` (a deep teal `#0b7f70` on light, for contrast). The theme is saved under a new key, so old light pins no longer apply.
  - **Kept:** Observability and every pane stay on the page; the tour just doesn't cover them (the online-eval lines stay out of the replay).
- **Cost:** a few hundred lines of page code; positions are set via `element.style` (the page's security policy blocks style attributes).
- **Changed 2026-11-12, your review** ("subtitles are very large"; "the heading overlays the text"): the guide strip is compact (16 px subtitles, smaller orb and controls, ~75 px tall); the big chapter title is gone: a new step's name flashes in the label line instead, so nothing covers the content.
- **Added 2026-11-12, your request:** an **Exit Tour** button (and Esc) stops the voice and opens the normal page (the same URL without `?tour`): your chats, the composer and live runs come back; nothing from the replay stays.
- **Added 2026-11-12, your request:** the way in is a glowing **Want a Guided Tour?** button in the left sidebar (a pointer taps at it), shown when the workspace has a tour. It starts the tour on the same page (the address becomes `?tour` without a reload), so the click also lets the voice play. Back or Exit Tour returns to the normal page.
- **Changed 2026-11-12, your review** ("this grey line looks odd"): the jar's glass shine (a white streak inside the jar) is gone; on the dark theme it read as a stray grey bar. The cyan outline and lid still say "jar".
- **Changed 2026-11-12, your review** ("remove this colour selection curve; it looks very bad"): the Harness part the voice talks about now only opens; no tint, rounded fill or coloured edge.

## D-180 · The run follows the voice: cue marks in the script (2026-11-12)
- **Your report:** the live run and the subtitles were out of step; the spotlight skipped the question and the helper's lines; the 10-second wait felt long.
- **Chose:**
  - **Cue marks** in each caption, like `{tool_finished#2}`: when the voice reaches that word, the run plays up to that event. One clock (the clip, or reading time) drives the subtitles and the run. Marks never show; they must move forward and stay inside the step (checked when the tour loads). A step without marks spreads its events as before.
  - **The spotlight:** a step that starts a turn shows the question first, in the spotlight; one event's lines are framed together; a helper's lines are framed one by one inside its lane. Events of one cue arrive 0.32 s apart.
  - **The pause between steps: 3 seconds** (was 10, D-178): the voice already paces each step; Next skips the wait.
- **Later:** with an ElevenLabs voice, its word timestamps can place each mark exactly on its word.

## D-181 · Step clips in your cloned ElevenLabs voice (2026-11-12)
- **Your request:** "pick the Gaurav voice, create a sample for step 1 and integrate it".
- **Options:** record each clip yourself at `/?tour=record` (D-169) · your cloned ElevenLabs voice "Gaurav" (`DN4vZODiJl45AFhmdQg7`, cloned, en-Indian) · a stock library voice.
- **Chose:** your cloned voice, model `eleven_v4`, text exactly the step's `say` (no cue marks). Made outside the harness (ElevenLabs connector), saved as `workspaces/cloudco/tour/audio/01-jar.mp3`; the tour already plays any `audio/<step>.mp3`, so no code changed.
- **Why:** sounds like you, with no fumbled takes; a line change means a new clip in seconds.
- **Cost:** ~380 credits a take (~$0.08; 2 takes for step 1, ~25 s each); about 3,000 credits for all 10 steps. It is a synthetic voice, so the tour should say so (open).
- **Changes D-169:** "your recorded voice" becomes "your voice, cloned or recorded"; `/?tour=record` stays for any step you'd rather record.
- **Added 2026-11-12, your go-ahead** ("do it for the remaining steps; the subscription allows 30 minutes"): steps 2–10 in the same voice and model, text = each step's `say` with cue marks removed. 2 takes each; the first finished take per step is installed. All 10 clips: 4 min 43 s, 4.5 MB (under 15 MB). Used: about 9.5 of your 30 minutes, ~8,640 credits.
- **Also:** the pre-commit large-file limit went from 500 KB to 1000 KB (three clips are 510–672 KB). Options: re-encode at a lower bitrate (smaller, but a worse voice) · raise the limit. Chose to raise it: the tour already caps a clip at 5 MB, and 1000 KB still catches stray big files.

## D-182 · No pause between steps: the voice leads straight on (2026-11-12)
- **Your review:** "the wait of 3 seconds is meaningless; it should be a natural progression rather than waiting for seconds to complete".
- **Options:** keep 3 s with a countdown · a short hidden gap (~1 s) · none: the next step starts when the voice ends.
- **Chose:** none by default (`DEFAULT_PAUSE = 0`); a workspace can still set `pause = N` in `tour.toml`. The clips' own trailing silence and the clip load give a natural ~0.3 s breath (measured 285 ms, step 9 → 10).
- **Changes D-180** (3 s) and D-178 (the countdown): no "Next in N s" unless a pause is set.
- **Cost:** no time to look at a card after the voice ends; Pause is there for that.

## D-183 · The tour opens with a map and ends with what production needs (2026-11-12)
- **Your review:** "the intro is missing; it starts with 'AI models'. It should say the harness has four primary components. At the end: production grade needs many things: task decomposition, verification, model routing, complexity matching, protection against attacks, and more."
- **Options:** a new welcome step (11 steps) · the welcome at the start of step 1. For the ending: your list as given · merged and sharpened.
- **Chose:**
  - The welcome opens step 1 (10 steps; ids and the jar scene unchanged). It names the four parts as a map; step 2 still shows them.
  - The ending merges routing with complexity matching ("routing each task to a model that matches its complexity"). It says "deeper" verification and "stronger" attack protection, since steps 6 and 7 show the basics. It adds "evals and observability" (built, not toured). "Just a folder" stays the last line.
- **Cost:** steps 1 and 10 re-voiced (~2,280 credits, 2 takes each); the tour grows by ~30 s.

## D-184 · The diagram's parts pop as the voice names them; the answer's cost is framed (2026-11-12)
- **Your review:** "when the voice talks about how many components it has, highlight each component on the diagram, like a pop-up animation"; "the model and cost pane is not highlighted matching the audio".
- **Pop marks:**
  - **Options:** pop all four on a timer when the step starts · a new mark in the script, `{pop:part}`, on the word that names the part.
  - **Chose:** the mark, like cue marks (D-180): the same voice clock, never shown in subtitles, no new audio. The part swells 1.35× and settles (0.8 s), with the existing glow and pulse to the model. It is checked when the tour loads (loop, context, tools or guard). Step 2 has four marks.
  - **Cost:** timing is the word's share of the clip, so it may land a few hundred ms off the spoken word.
- **The answer's frame (a bug):** when a run finishes, the page ticks the checks first and draws the answer after them (S11). The spotlight looked for the answer too early and stayed on the last check row. Now it waits until the answer is drawn, then frames the answer and its cost line together.

## D-185 · The intro gives the agenda; step 2 builds the harness part by part (2026-11-12)
- **Your review:** "the intro should say we'll cover the AI model's limits in isolation, why we need a harness and what it is; then talk first about the model in isolation, then why we need a harness; the diagram should come with a pop-up animation matching the voice and script".
- **Chose:**
  - **Step 1** (re-voiced, 34 s): the agenda in one line (what a model can't do alone, why it needs a harness, what a harness is), then the brain in the jar. The four parts are no longer listed here (D-183's intro line moved to step 2, where they're shown).
  - **Step 2** opens on a new `build` scene: the jar lifts away and the model stands alone. Each part (and its spoke) springs in as the voice names it (pop marks, D-184). A new **scene mark**, `{scene:harness}`, then shows the whole harness and "AI Agent = Model + Harness" at "You can see each one on the right."
  - Scene marks are checked when the tour loads, like pop marks.
- **Cost:** step 1 re-voiced (~1,000 credits, 2 takes). For about 25 s of step 2 the diagram is the model alone, while the voice explains why it needs a layer around it.

## D-186 · Hide Guide: the strip folds to the orb (2026-11-12)
- **Your request:** "give a way to hide this section if required, so my focus remains on the screen".
- **Options:** hide everything (no way back but a key) · fold to the orb with a Show Guide button · make the strip smaller only.
- **Chose:** a **Hide Guide** button (chevron) next to Mute. The subtitles and controls fold away; the orb (still moving with the voice) and a **Show Guide** button stay. The voice and the replay carry on. The page gains ~86 px and the spotlight uses it. Exit Tour reloads the page, so the guide always starts shown.
- **Cost:** while hidden there are no subtitles and no Pause or Next; Show Guide is one click back.

## D-187 · The spotlight sits mid-screen; step 9 drops its last line (2026-11-12)
- **Your review:** "things happening at the bottom are hardly visible; they should happen in the middle of the screen, with space below, so it looks seamless"; "remove the line about how this tour works, it's obvious".
- **Scrolling:**
  - **Options:** keep the chat's own jump to the newest line · scroll to the spotlight from the player.
  - **Chose:** the player. In tour mode the chat's own scroll calls (`reveal()`) stand down. The page scrolls smoothly so the framed lines sit in the middle of the space above the guide. A frame too tall to fit shows its end at 80% of that space. The chat gets 50vh of room below its newest line. It scrolls only when the frame moves on or grows by 40 px or more, so you can still scroll by hand in between.
  - **Cost:** the first lines of a fresh run still sit near the top: the page can't scroll above its start.
- **Step 9:** "Every step you saw was saved as a trace, and that's how this tour plays it back." is gone, from the script and the clip. The clip was cut inside the pause before that sentence (13.8 s → 9.1 s, 0.15 s fade), not re-voiced: no credits.
- **Changed 2026-11-13, your review** ("the approval screen is not fully visible"; "same for Sales and Engineering"): in the tour every approval card fits on screen. Its email body and header lines are folded (shown in full one step before, as the draft), the subject and terms table stay, and the note field is hidden. A frame that fits is now centred whole; only a taller one shows its end. Chrome, step 8: Sales 704 px, Engineering 656, Finance 738, CFO 757, all fully inside the 821 px above the guide.

## D-188 · Ready for a public repo: no voice, no personal email, no keys (2026-11-13)
- **Your request:** "perform security to ensure no API keys leak to the public repo"; then "remove them from history and fix all 3".
- **Audit:** gitleaks over all commits and the folder, a search for every key format the project touches (Gemini, Anthropic, OpenAI, ElevenLabs, GitHub, signed URLs, bearer tokens, private keys, `*_API_KEY=` with a value), `.env` history, the recorded runs, CI and the key-masking tests. No key was ever committed; `.env` was never tracked.
- **Chose:**
  - The tour's voice clips and the stage specs stay local (`.gitignore`). The clips were also removed from every past commit (`git filter-repo`), because ~5 minutes of clean audio is enough to clone a voice. The stage specs stay in history (not sensitive).
  - Commits use the GitHub no-reply address, past ones too. The email is gone from `Security.md` (reports go through GitHub's private reporting) and `pyproject.toml`.
  - `main` and the stage tags were force-pushed; the old Dependabot branch was deleted (it recreates itself).
- **Not possible yet:** secret scanning, push protection and private vulnerability reporting are refused on a private repo (HTTP 422/404). Turn them on right after making it public (Settings → Code security). Until then, the local gitleaks hook and the gitleaks step in CI guard every commit.
- **Cost:** every commit id changed: any other clone must be re-cloned. GitHub keeps a read-only ref for closed PR #1 (old author email, no clips) and may cache old commits for a while; only GitHub Support can purge those.
- **Done 2026-11-13, your request ("make it public"):** the repo is public after one more clean gitleaks scan; secret scanning, push protection and private vulnerability reporting are on.

## D-189 · Public tour mode: the page hosted for anyone, read-only and keyless (2026-11-13)
- **Your request:** add the harness to gauravlahoti.dev as an AI Lab, hosted on Cloud Run at min instances 0 like the Agentic RAG lab. Visitors won't type their own API keys, so the hosted copy plays the guided tour only.
- **Amends D-20 (localhost only) and D-14 (static replay page).** D-20 still holds for local mode, which stays the default. The tour is hosted by the harness's own server instead of a static export (S13-AC2, AC7 stay 🟦 for you to decide).
- **Blocking writes:**
  - **Options:** a guard on each route · one rule for the whole server.
  - **Chose:** one middleware. In public mode the server answers only GET and HEAD. Anything else gets 403, on every route that exists now or is added later. The page's `X-Harness-Page` header doesn't help, since anyone can send it from outside a browser.
  - **Cost:** a future public action needs a deliberate exception.
- **Keys:**
  - **Options:** trust that none is deployed · also ignore any key in public mode.
  - **Chose:** both. `config.py` reads no key when `HARNESS_PUBLIC=1`, and `Settings` reports none even if one is passed in by hand. A key set by mistake still can't be spent.
  - **Cost:** none.
- **Where it listens:**
  - **Options:** add `serve --host` · let public mode choose.
  - **Chose:** public mode chooses. It listens on 0.0.0.0 (a container is reached from outside) and on `$PORT`. There is still no `--host` option (S00-AC13), so a local harness can't be opened to the network by a typo.
  - **Cost:** none.
- **Names:** `HARNESS_ALLOWED_HOSTS` (comma list) adds names to localhost. These names count only in public mode.
- **The page:** in public mode it opens on the tour, waiting on Start Tour, because browsers play sound only after a click. A sidebar note says the tour is read-only, explains how to run the agent live, and links to the source (from `pyproject.toml`'s Repository URL, so no domain in code). Workspace and Observability, Exit Tour, the recorder and the invite are hidden. Escape doesn't leave the tour.
- **Hosting:** a `Dockerfile` with an allowlist COPY (`src/`, `workspaces/cloudco/`, lock files) and no dev or eval packages, running as non-root with `HARNESS_PUBLIC=1` baked in. `.gcloudignore` is also an allowlist: without it gcloud follows `.gitignore` and drops the voice clips, and `.env*` never leaves the machine. `make deploy-tour PROJECT=… HOSTS=…` runs `gcloud run deploy --source .` with min 0, max 1, 512 MiB and no secrets.
- **Why not `agents-cli deploy`:** it copies the project `.env` into the service's environment, which here holds the Gemini key. It also expects an ADK project manifest. The other services on gauravlahoti.dev deploy the same way, with `gcloud run deploy --source .`.
- **Voice clips** are cached for a year in public mode (their URL carries `?v=`, which changes with each take); the page itself stays `no-cache`.
- **Cost:** about nothing. It scales to zero and makes no model calls, so it stays inside the Cloud Run free tier.

## D-190 · Owner unlock: live Claude runs on the hosted copy, for the passphrase holder only (2026-11-13)
- **Your request:** "ideally I want to show a live session to someone, I should have a super user key and in background it uses my Claude key stored in Secret Manager".
- **Amends D-189** for one person. Visitors still get the read-only, keyless tour.
- **Chose (your answers):** Claude only, from the existing `anthropic-api-key` secret. The way in is a hidden `?owner` link. You set the passphrase (`harness-owner-key`, at least 15 characters; lowered from 20 at your request so `harness-owner-key` could be a 15-character passphrase).
- **How it works:**
  - `HARNESS_OWNER_KEY` is read only in public mode. With it set, `config.py` keeps Claude's key; without it, a public harness holds no key, as before. A Gemini key is never kept in public mode.
  - Each request's `X-Harness-Owner` header is checked once (`hmac.compare_digest`). Ten misses in ten minutes lock the unlock, even for the right passphrase, until the window passes.
  - An owner request may also reach `POST /api/run` and `POST /api/approval`, and nothing else. Checks, evals, voice recording and deletes still get 403.
  - An owner run gets the Claude key (`replace(settings, public=False)`), Claude models only, defaulting to Haiku 5.5. Everyone else's settings still report no key. The passphrase is scrubbed from traces like any key.
  - The page keeps the passphrase in `sessionStorage` for that tab only and sends it on every request. **Lock** forgets it.
- **Cost:** each owner run is capped by the usual limits (25 steps, $1, 2 minutes), and Cloud Run max 1 instance means one run at a time. Anyone holding the passphrase can spend up to that per run, so keep it in your password manager.
- **Options not chosen:** a visible unlock button (every visitor would see a locked mode); Claude + Gemini (two keys behind the passphrase instead of one).

## D-191 · Step 1 tells the model-alone story in beats, not a static jar (2026-11-13)
- **Your review:** "the model in jar sits idle for the first few minutes, simple animation doesn't look good at all", then, while building it: no model during the agenda; three agenda items because the voice names three; show what a model is good at (reasoning, writing text) and that it can't connect to APIs; no text over any line; "neat and clean, high on visuals".
- **Chose:** two new word marks, parsed and checked like `{pop:…}` and `{scene:…}`:
  - `{chip:N}` lights entry N of a step's `chips`. The labels live in `tour.toml`, not in the player (D-172).
  - `{beat:name}` moves the model-alone story on: `think`, `reach`, `seal`, `tell`, `bounce`. The beats add up.
- **What step 1 shows:**
  - The agenda as a roadmap. Each node ignites and the rail draws to it as it's named; there's no model yet.
  - Then the model bursts in with its two powers, Reasoning and Writing text.
  - Email, APIs and Web appear; each reach toward them breaks with a ✗.
  - At "jar" the jar drops and seals. Nothing crosses the glass after that.
  - "how to send it…" rises inside the jar, and a send pulse bounces off the glass.
- **Kept:** the recorded voice (the caption words are unchanged) and the reduced-motion end states.
- **Cost:** the story is drawn once in the stage SVG, so the page is slightly larger; nothing runs outside step 1.

## D-192 · The tour replays a real Claude Sonnet 5.5 run (2026-11-13)
- **Your request:** "in the entire demo Gemini is shown, I want you to show Claude", then "use the existing question, but with Claude Sonnet".
- **Chose:** re-record the same two turns live on Claude Sonnet 5.5. Never relabel a Gemini run, because the tour says "a real recorded run" and its costs come from the trace.
- **Takes:** five, $0.06–$0.10 each, about $0.38 in all. Sonnet is consistent across them:
  - It loads only the contract-review skill, writes its to-do list before the lookup, and never searches the policy itself (the helper does).
  - It sends without a separate draft, and never adds Net 60, so three approvers: Sales, Engineering, CFO.
- **Picked:** take 1 (turns `20261113-120817-02a003`, `20261113-120850-b67237`). Its first answer didn't name who must approve each change; the Right Approver check sent it back and the fix passed.
- **Script:** only the lines the new run made untrue changed.
  - Step 4: one skill.
  - Step 5: to-do list, then lookup.
  - Step 7: why the draft was sent back.
  - Step 8: three approvers.
  - Step 9: about three cents, on Claude Sonnet.
  - The cues were re-timed to the new events.
- **Voice:** the clips for steps 4, 5, 7, 8 and 9 now say the old words and need re-recording. The other clips still match.
- **Also:** a hosted copy lists Claude models (it runs nothing else), and the pane's caching note no longer names a provider.

## D-193 · Visitors see the switches but can't change them; a quiet note links the code (2026-11-13)
- **Your review:** "this can be highlighted but the user can't click or change any selection; the knobs should not be active"; "the section shall be subtle, GitHub icon and logo, View the code, better polished professional language".
- **Chose:**
  - In the tour (local `?tour`) and for visitors to the hosted copy, every Harness switch shows its state but a click or the space key does nothing, and nothing is saved. In your owner session (D-190) and on your normal page they work as before.
  - The hosted note is one quiet line under the agent's description, with a thin divider instead of a box: "A read-only replay of a real agent run. Clone the repository to run it live with your own model key." Under it, a small **View the Code** pill with the GitHub mark (an inline icon template; the page's security policy allows no HTML strings).
- **Cost:** none. Deployed as part of S14; the live site needs a redeploy to show it.
- **Changed 2026-11-13, your review** ("the Exit Tour is barely visible"): Exit Tour (local tour only; the hosted copy hides it) now has bright text in an outlined pill like the round controls beside it, cyan on hover.

## D-194 · The tour leaves out "No To-Do plan" (2026-11-13)
- **Your review:** "this line hurts when recorded in the demo, as eventually it plans a To-Do list".
- **Why it happened:** the page writes "No To-Do plan · the model chose to work directly" at the first ordinary tool call (here `load_skill`). The recorded run writes its To-Do list one call later, so the line was wrong by the time the plan appeared.
- **Chose:** the tour (local `?tour` and the hosted copy) never shows that line; the To-Do card shows the plan. Your normal page is unchanged (your rule: tour changes stay in the tour).
- **Open:** the same early verdict can happen in a live chat, when the model plans after its first tool. A general fix (drop the line once a plan arrives) would change the normal page, so it waits for your call.

## D-195 · Tour stays on the Gemini recording (2026-11-13)
- **Tried (D-192):** re-recording the tour's two turns live on Claude Sonnet 5.5. Five takes cost about $0.38. Sonnet took a different path: one skill, plan before lookup, no draft, three approvers, about three cents. So steps 4, 5, 7, 8 and 9 would have needed new voice lines.
- **Your call:** "stick to previous clips and Gemini view only". This reverts D-192: the tour replays the Gemini 3.5 Flash-Lite recording with its own voice clips again, and the hosted page lists models as before. The Claude takes stay in local traces only.
- **Unchanged:** owner live runs (D-190) still run on Claude.

## D-196 · The owner session gets Memory and Observability; visitors can't read them (2026-11-13)
- **Your review:** "facts are zero, we need the original facts; observability is gone, we need that too in this owner version".
- **Why:**
  - The container started with empty memory. The demo facts live in `workspaces/cloudco/demo-memory/` and were never copied into notes.
  - Public mode hid Workspace and Observability for everyone, the owner included.
- **Chose:**
  - The image seeds notes from `demo-memory/` (made-up facts, never anyone's own notes) and carries `evals/catalog.json`, `evals/cases/` and the saved eval summaries (`.agentic-harness/evals/*.json`; no traces, no chats).
  - The owner sees Workspace (Agent, Memory) and Observability (Online Evals, Offline Evals, Golden Dataset), but nothing that runs an eval, switches the judge or forgets a fact. Checks stay hidden.
  - A teammate session's review: since public mode answers every GET, `/api/facts`, `/api/online-evals`, `/api/evals*` and `/api/sessions*` now need the owner passphrase (403 otherwise; the same lockout counter). The tour's own reads stay open.
  - An unlocked tab sends the passphrase with every `/api/` call.
- **Tests:** `test_public_mode.py::test_s14_ac11_*`.

## D-197 · Owner: the Golden Dataset loads, and online evals switch on or off (2026-11-13)
- **Your review:** "no golden dataset exists, also there is no option to turn online evals on or off".
- **Why:** the Golden Dataset page asks the `evals` package for its plan (`python -m evals.run --plan`), and only its data files were in the image. The judge switch was hidden, and the server refused it.
- **Chose:** the image carries the whole `evals/` package. It plans without DeepEval (checked in an install with no dev or eval packages); running offline evals stays off. The owner may `POST /api/online-evals/judge`; for a Claude run the judge is Claude Haiku, on your key. This widens D-190's owner writes to three, recorded in CLAUDE.md.
- **Still open:** the switch, memory and chats live on the container's disk, so they reset when Cloud Run scales to zero. Externalising them (Firestore) is planned separately.

## D-198 · Hosted memory lives in a mounted Cloud Storage bucket (2026-11-13)
- **Your request:** "if we want to use Firestore to externalise the memory, do it and wire it up".
- **Problem:** on Cloud Run, facts, chats, the online-evals switch and eval summaries were files on the container's disk. They reset at every scale-to-zero or deploy.
- **Options:**
  - A Firestore storage layer: about 300 lines of new harness code plus tests, the `google-cloud-firestore` dependency (heavier image, slower cold start), cents a month.
  - A Cloud Storage bucket mounted at `.agentic-harness/`: no harness code change, pennies a month.
- **Chose (your answer):** the bucket, `gcp-experiments-490306-agentic-harness-memory` (us-central1, uniform access, public access prevented). It's mounted with Cloud Run's gen2 volume, `uid`/`gid` 10001 so the non-root user writes. Seeded once with `make seed-memory`: the made-up demo facts and the eval summaries. It never holds anyone's local notes or chats.
- **The image** no longer carries facts or eval summaries. It keeps the `evals/` package for the Golden Dataset plan.
- **Caveats:**
  - Safe for one writer only; the service runs at most one instance.
  - Each append rewrites the whole object, which is fine at this size.
  - Owner-only reads (D-196) still guard it from visitors.
- **Cost:** a few MB and a few thousand writes a month, about $0.01–0.05.

## D-199 · The hosted harness runs as its own service account (2026-11-13)
- **Your go-ahead** after the D-198 review: Cloud Run reached the secrets and the memory bucket through the project's default compute account, which holds **Editor** on the whole project.
- **Options:** remove Editor from the default account · give the harness its own account.
- **Chose:** its own account, `agentic-harness-run@gcp-experiments-490306.iam.gserviceaccount.com`, with exactly three grants and no project role:
  - `secretmanager.secretAccessor` on `anthropic-api-key` and on `harness-owner-key`
  - `storage.objectUser` on `gs://gcp-experiments-490306-agentic-harness-memory`
  - `make deploy-tour` takes `RUN_SA=…`.
- **Why not the default account:** `agentic-rag`, `pulse` and `resend-mcp-server` also run on it; taking Editor away would have broken them.
- **Cost:** none. A leaked token of the harness can now read two secrets and one bucket, not the whole project.

## D-200 · Why live owner sessions were slow, and the fixes (2026-11-13)
- **Your report:** "the live sessions are extremely slow… it loads all skills… once I come back to the conversation, the trace of loading skills and calling tools is gone". Then: "find the deeper root cause".
- **Measured** (Cloud Run request logs, the run traces in the memory bucket, three tiny timed runs):
  1. **The first Claude run on each instance waited ~18 s before anything happened.** `anthropic` (~3,270 modules) was imported lazily inside the first run, and Cloud Run gen2 reads image files lazily. The first byte came at 19.0 s on a warm instance's first run, then 1.2 s and 0.9 s.
  2. **Cloud Run's 300 s request timeout killed runs waiting for approval.** Both "send" runs logged exactly 301 s and ended at `approval_requested`.
  3. **No approval was ever posted:** a person switch plus a click per approver, easy to miss live.
  4. **Every trace event re-uploaded the trace file to the mounted bucket** (D-198): ~0.2 s an event live vs 0.001 s on local disk, about 6 s a run.
  5. **Reopened chats only had task, answer, plan and checks.** The steps were in the trace, never replayed.
  6. **"2 skills" read as loaded** (they're offered); Haiku also skipped `load_skill`.
  - **Not causes:** the model calls (cached prompts, 6–11k tokens), streaming (no buffering), container start (~2 s).
- **Chose:**
  1. `serve` imports `anthropic` and `google.genai` in a background thread at start.
  2. `make deploy-tour` sets `--timeout 3600`, Cloud Run's maximum, above the 1800 s approval wait.
  3. In an owner session the hand-off reads "Approve as <name> (<role>)" and approves in one click; the server's role check is unchanged. Local mode keeps the two steps.
  4. `HARNESS_TRACE_STAGING` (set only in the image): a run traces to local disk and its files move to the trace folder once the stream ends. Unset (local use) writes event by event as before.
  5. `GET /api/sessions/{id}` returns each turn's trace events (up to 800). The page redraws them through `onEvent()`, like the tour, and falls back to the summary without a trace.
  6. Owner sessions default to Claude Sonnet 5.5 (your choice); helpers stay on Haiku. The label reads "2 skills on offer".
- **Tests:** `tests/unit/test_hosted_speed.py` (S14-AC12 to AC15).
- **Added 2026-11-13, after the live check:** the first run on a fresh instance still waited ~10 s. With `--cpu-throttling`, Cloud Run gives CPU only during requests (plus a short startup boost), so the background warm-up stalled. **Your choice:** `--no-cpu-throttling` (instance-based billing). It still scales to zero, and the warm-up finishes while an instance is up. Cost: within the free tier at this traffic (240k vCPU-seconds a month), then roughly $0.02 per idle 15-minute window.

## D-201 · The owner sees what a run is doing; Haiku for live demos (2026-11-13)
- **Your report:** "still the same issue, I keep seeing Working… on the request, it's too slow".
- **Measured** on your 09:15 run (Sonnet, 14.6 s): scope check 0.8 s, three Sonnet calls of 2.4, 2.9 and 2.3 s (one a verify retry), then the online judge 4.6 s after the answer. The infrastructure delays (D-200) were gone; the rest is model time behind a static "Working…".
- **Chose (your picks):**
  - **Live step status** for the hosted owner session: the run header reads "Starting…", "Model thinking… 3s", "Running lookup_customer_record…", "Checking the answer…", "Waiting for CFO to approve…", "Online evals scoring…". It counts seconds and always stops at the end or on an error. Local pages keep "Working…" (your rule: local changes need your say).
  - **Owner default back to Claude Haiku 5.5** (D-200 had Sonnet): roughly twice as fast per call and cheaper. Sonnet stays in the menu.
  - **Streaming the answer word by word:** chosen, but it's a harness change (model clients, loop events, page), so it gets its own brief before code.
- **Not chosen:** running the scope check in parallel.

## D-202 · No chat flash before the tour; locked switches say why (2026-11-13)
- **Your reports:**
  - "whenever the page loads it shows the chat screen and in a few ms the guided tour… it feels like a glitch"
  - "if they hover over a setting it should show a message, polished and professional"
- **Why the flash:** the page learned it was a hosted tour only after `/api/health` answered, so the chat screen painted first.
- **Chose:**
  - In public mode the server serves the page with `<body class="hosted-boot">`. CSS keeps the chat screen hidden until the page is in tour or owner mode. Locally the page is the file, unchanged.
  - Two safety nets, from a teammate session's review: a failed health check removes the marker, and a CSS-only fallback reveals the page after 4 s even if no script runs.
  - Locked switches (the tour, a hosted visitor) show a tooltip on hover or keyboard focus, with a not-allowed cursor: "Locked during the guided tour. Run the harness yourself to switch tools, skills and checks on or off." Owner and local pages have no lock and no tooltip.
- **Tests:** `test_hosted_speed.py::test_s14_ac17_*`, `test_s14_ac18_*`.
- **Changed 2026-11-13, your wording choice:** the tooltip said "run the harness yourself" without saying where. It now reads: "Read-only in this guided tour. To change tools, skills and checks, get the code from View the Code (in the sidebar) and run the harness on your own machine." A hover tooltip can't hold a link, so it points to the sidebar button. Live in revision 00015.

## D-203 · Chats never shrinks under the groups below (2026-11-13)
- **Your report:** "chat is not opening unless I collapse Workspace and Observability".
- **Cause:** the sidebar is a full-height column, and Chats was the one group allowed to shrink (`min-height: 0`, since S07). In the owner session, the owner note plus both open groups no longer fit, so Chats shrank to 15 px and its list spilled over the groups below: a click on a chat landed on the group drawn on top of it. A short window could do the same on the local page.
- **Chose:** Chats keeps its size (`flex-shrink: 0`); its list still scrolls on its own (max 32vh), and the sidebar scrolls when every group is open. When everything fits, nothing looks different.
- **Checked:** the owner session reproduced locally (public mode, a throwaway passphrase, 127.0.0.1 only): before, the click hit New Conversation; after, the chat opens with both groups open. `test_the_chats_group_never_shrinks_under_the_groups_below`.

## D-204 · Tour: words light up as they're spoken; smaller subtitles; a way out (2026-11-13)
- **Your review:**
  - "the transcript should be highlighted based on what the voice is saying"
  - "reduce the size of the subtitles by 2 points"
  - "there is no exit mode"
  - "this section (profiles, acting as, chats) is not even needed in guided mode"
- **Chose:**
  - **Word by word:** each subtitle sentence is drawn as words. Words already said turn bright, the word being said takes the accent colour, and the rest wait dimmed. Timing is each word's share of the clip (D-180), the same as the cues, so it can run slightly ahead or behind. Exact per-word timestamps from ElevenLabs would fix that, at the cost of regenerating the clips' timing (open). Reduced motion drops the colour fade.
  - **Subtitles 15 px → 13 px.**
  - **Exit Tour on the hosted copy:** a visitor may leave (button or Escape). The tab then stays out of the tour and lands on a read-only page with "Want a Guided Tour?" to go back in. Visitors never get the composer.
  - **Profiles, Acting As and Chats** are hidden for tour visitors, no longer greyed out. The owner session is unchanged.

## D-205 · The Agentic Loop pane reads like the agent loop (2026-11-13)
- **Your review:** "rewrite the Agentic Loop, it looks incorrect", with Anthropic's Agent SDK page on the agent loop as the reference.
- **Chose (your pick, the precise version):**
  - Rows in the reference's terms: a **turn**; the model answers or asks for tools; the harness runs them and feeds the results back; the loop ends on a reply with no tool calls.
  - What this harness does on top: tools run one after another; plain-code checks can send an answer back for one more turn; limits of 25 turns, $1 or 2 minutes, after which the run says which one stopped it; helpers get their own loop (15 turns, half the time, a quarter of the budget, cost counted to the run); provider-neutral prompt caching. The header reads "25 turns", not "steps".
- **Checked in code:** tools run in order (`loop.py`); a helper's cost is charged to the run (`subagents.py`).

## D-206 · Tour polish: the pane waits for the run; a glass guide capsule; a hosted welcome (2026-11-13)
- **Your review:**
  - "the Harness pane should stay hidden, with no cyan edge, until Priya sends her message"
  - "04 of 10 looks vague, remove it"
  - "subtitle font one point bigger"
  - "this section should sit in a pill with a transparent cyan background and collapse more beautifully, animated"
  - The welcome copy after Exit, relayed by a teammate session as your approved wording.
- **Chose:**
  - **Pane timing (your pick):** hidden in steps 1–3 (no pane, toggle or edge); it slides in when the recorded run's first event plays (step 4), then opens each narrated part. Going back before step 4 hides it again.
  - The step counter and its slash are gone; the chapter title stays. The timeline on the right shows progress. Subtitles 13 → 14 px.
  - **Guide capsule:** a translucent cyan glass panel (7 % accent fill, 32 % accent border, blur, soft glow). Hide Guide narrows it into a small orb pill while the text fades and slides out; Show Guide plays it back. Reduced motion: no animation.
  - **Hosted welcome** (after Exit, hosted only): "Curious to see harness engineering in action?", then "Watch a real AI agent review a contract, get four approvals and send the reply, step by step, in a five-minute voiced tour.", then a prominent **▶ Start the Guided Tour** button (accent fill, focus ring), then "or explore the Harness pane on the right".

## D-207 · The Agentic Loop section keeps to the loop (2026-11-13)
- **Your review:** "remove this part from the agent loop".
- **Your pick:** removed Small jobs, Before you see it, Plans, Helpers and Prompt caching. The section keeps How it works, Tools, Model and Stops. Verification, the to-do tool and the helper stay described in their own sections (Verification, Tools).

## D-208 · The guide keeps one size: subtitles fit two lines (2026-11-13)
- **Your review** (relayed by a teammate session): the guide capsule's height changed with the subtitle (1 to 3 lines; step 10 reached 3), which moved your focus.
- **Chose:**
  - The caption box is always two lines tall.
  - `captionCards()` splits any sentence that wouldn't fit two lines at the current width at its most natural pause nearest the middle (":" then ";" then ","), else at the middle word. Each card keeps its words' share of the voice, so the word highlight (D-204) carries across the split.
  - The title, controls and timeline keep their places. Recording mode keeps its tall script box.
- **Open:** checking every step at desktop and phone width in Chrome; the browser permission prompt timed out.
