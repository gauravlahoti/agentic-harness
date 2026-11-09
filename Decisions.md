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
📝 Proposed · S01
- **Chose:** `client.interactions.create` with the official SDK
- **Instead of:** `generateContent` (now "legacy") · raw HTTP · LiteLLM
- **Because:** Google recommends it (GA June 2026); its typed steps map 1:1 onto our events and cards
- **Cost:** a young API, with automatic caching only → the S01 test script checks real shapes first
- **Revisit if:** we need guaranteed cache discounts

### D-04 · We keep the history, not Google (`store=False`)
📝 Proposed · S01, S07
- **Chose:** send the full step list on every call
- **Instead of:** server-side history via `previous_interaction_id`
- **Because:** memory and trimming are core lessons. If the server holds the history, we can't trim it. Also, nothing is stored at Google.
- **Cost:** bigger requests; maybe fewer cache hits → we measure cached tokens
- **Revisit if:** we want a "stateless vs stateful" cost post

### D-05 · Model steps are kept exactly as received
📝 Proposed · S01, S07
- **Chose:** never edit, merge or split a model step; only our own tool results can be trimmed
- **Instead of:** converting everything into our own format
- **Because:** model steps carry thought signatures; changing them can break the next call
- **Cost:** trimming has fewer options
- **Revisit if:** the S01 test script shows otherwise

### D-06 · Only our own tools; no Gemini server-side tools
📝 Proposed · S03
- **Chose:** tools that run in our process, through our gate
- **Instead of:** Gemini's built-in search, code execution, managed agents
- **Because:** rule 1: the model asks, the harness decides. Server-side tools would skip our gate and traces.
- **Cost:** no free web search
- **Revisit if:** a workspace needs search; we'd add it as our own gated tool

### D-07 · Models: 3.8 Flash by default, Argon by config, Flash-Lite for sub-agents
📝 Proposed · S01, S04
- **Chose:** `gemini-3.8-flash` · `gemini-4-argon` for demo takes · `gemini-3.5-flash-lite` for the Clause Reviewer
- **Instead of:** one model for everything
- **Because:** many small calls → cheap and fast; reading for a sub-agent is easy work
- **Cost:** model choice becomes a setting to explain
- **Revisit if:** the eval pass rate is below target

### D-08 · AI Studio key by default; Agent Platform optional
📝 Proposed · S00, S01 · **⚠ needs your answer**
- **Chose:** support both through config; start with an AI Studio API key
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
