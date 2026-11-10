# An agent harness, built from scratch

> **Agent = Model + Harness.** Every agent has a harness. We build a **general harness** (like the engine inside Claude Code) and run agents on it.
> The **Contract Agent** is the first agent we run: one workspace on top of the harness, not the harness itself.

📝 Draft v3 · 2026-11-10

## Two layers

```
┌───────────────────────────────────────────────────────────────┐
│  WORKSPACE  (one agent)          workspaces/cloudco/          │
│  AGENTS.md · skills · tools.py · profiles · approval chart    │  ← changes per agent
├───────────────────────────────────────────────────────────────┤
│  HARNESS  (any agent)            src/agentic_harness/         │
│  loop · context loader · skill loader · tool registry ·       │  ← never changes
│  sub-agents · permission gate · approvals · memory · traces   │
├───────────────────────────────────────────────────────────────┤
│  MODEL                           Gemini                       │
└───────────────────────────────────────────────────────────────┘
```

**The harness test:** swap the workspace and you get a different agent, with **zero changes to `src/agentic_harness/`**. If domain words like "contract" or "discount" ever appear in `src/agentic_harness/`, we've built an agent, not a harness. A test enforces this.

| Claude Code (a coding harness) | Our harness |
|---|---|
| `CLAUDE.md` | `AGENTS.md` |
| `.claude/skills/` | `skills/` |
| `.claude/agents/` (sub-agents) | `[subagents]` in `workspace.toml` |
| Permission rules in settings | `[profiles]` in `workspace.toml` |
| "Allow this action?" prompts | `[approvals]` in `workspace.toml` |
| Built-in tools + MCP | Built-in tools + the workspace's `tools.py` |
| Session history, resume | Sessions, notes, trimming |

**One-line interview answer:** *"Every agent has a harness. I built the harness itself: a domain-free runtime with a loop, context, tools, sub-agents, permissions, approvals and memory. A contract assistant is one workspace on it. Swap the folder and it's a different agent, with no harness code changed."*

## The harness

```
              CONTEXT                              ACTIONS
     What does it know?                    What can it do?
   AGENTS.md · skills  (S2)          tools (S3) · sub-agent (S4)
                 ╲                              ╱
                  ╲      ╭──── THE LOOP ────╮  ╱
                   ╲     │  think → ask →   │ ╱
                         │     GEMINI       │
                   ╱     │  ← observe ←     │ ╲
                  ╱      ╰────── (S1) ──────╯  ╲
                 ╱                              ╲
               MEMORY                           GUARDRAILS
     What does it remember?              What is it allowed to do?
  sessions · trimming  (S7)       permissions (S5) · approvals (S6)
```

**Rule 1: the model only asks; the harness decides.** A tool call is a request. It passes the gate before anything runs.
**Rule 2: the loop doesn't know who's watching.** It emits events; the page, traces and tests listen.
**Rule 3: the harness knows no domain.** Everything about CloudCo lives in its workspace.

## The first workspace: Contract Agent

**CloudCo**, a software company, gives its **Sales, Engineering and Finance** teams a Contract Agent. When customer **ShopCo** sends back its $480,000 renewal with 5 changes, the agent checks each one against CloudCo's standard terms and never acts without a human's approval.

Story, people and data: [`01-company.md`](01-company.md).

## Done means

| ID | Outcome |
|---|---|
| P-SC1 | Each harness part is its own small module |
| P-SC2 | `src/agentic_harness/` contains zero domain words (a test checks) |
| P-SC3 | A second workspace runs with zero changes to `src/agentic_harness/` |
| P-SC4 | All offline tests run in < 10 s, free |
| P-SC5 | ≥ 5 of 6 eval tasks pass |
| P-SC6 | Every episode has a real "without it / with it" clip pair |
| P-SC7 | A 75 s demo records from a replay, with zero API calls |
| P-SC8 | You can explain any file without opening its code |

## We won't

- **Use a framework** (Deep Agents, ADK, LangChain): it would hide what we're teaching. ADK gets a bonus comparison episode.
- **Ship a shell tool**: the harness *can* take any tool, but our workspaces don't need one, and that keeps guardrails simple.
- **Use Gemini's server-side tools or server-side history**: every action passes *our* gate; *we* decide what the model sees.
- **Give legal advice**: the Contract Agent flags, explains and drafts. Humans decide. Everything in CloudCo is made up.
- **Ship a product**: no login, no cloud deploy. The public version is a replay page.

## How you run it

```bash
uv run agentic-harness run   --workspace workspaces/cloudco --profile sales "What did ShopCo change?"
uv run agentic-harness serve --workspace workspaces/cloudco      # the web page
```

Inside, both call one function. Every argument is a module we write:

```python
agent = create_harness(                                  # Stage
    model      = GeminiModel("gemini-3.8-flash"),        # S1  loop + model
    limits     = Budget(steps=25, usd=1.00),             # S1  stop rules
    workspace  = Workspace("workspaces/cloudco"),        # S2  context + skills
    profile    = "sales",                                #     (tools S3, sub-agents S4,
)                                                        #      permissions S5, approvals S6)
                                                         # S7  sessions: automatic
```

The workspace declares everything specific to the domain:

```toml
# workspaces/cloudco/workspace.toml   (read by the harness, never shown to the model)
memory    = ["AGENTS.md", "teams/{profile}.md"]
skills    = ["skills/company/", "skills/{profile}/"]
tools     = "tools.py"

[subagents.clause_reviewer]
tools = ["get_contract", "compare_to_standard", "search_policy"]
model = "gemini-3.5-flash-lite"

[profiles.sales]
tools = ["get_deal", "get_contract", "accept_change", "send_to_customer", "..."]

[[approvals]]
tool = "accept_change"
when = { term = "discount", above = 15 }
approver = "cfo"
```

> *"Frameworks give you this in one call. Here's what each line actually does. I built all of them."*

## Stack

| Part | Choice | Because |
|---|---|---|
| Language | Python 3.12 | Readable; the main AI language |
| Gemini SDK | `google-genai` | Google's official, current SDK |
| Gemini API | Interactions API, `store=False` | Google's recommended API; we keep the history ourselves |
| Model | `gemini-3.8-flash` (Argon by config; Flash-Lite for sub-agents) | Fast and cheap for many small calls |
| Access | AI Studio key (or Agent Platform, in config) | Simplest local setup |
| Waiting | asyncio | The loop waits for your approval while the page keeps updating |
| Server | FastAPI + Server-Sent Events | Simplest live push to a browser |
| Page | Plain HTML / CSS / JS | Nothing to install; every line visible |
| Storage | JSONL + JSON + TOML files | Readable, append-only, replayable |
| Tools | pytest, uv | Standard tests; one fast package tool |

## Gemini facts that shape the design

From Google's docs, checked 2026-11-09. 🔍 = confirm with a live call in S1.

| Fact | So we… |
|---|---|
| Interactions API is the recommended API (GA June 2026) | use it (D-03) |
| With `store=False`, we send the full history every call | own the history in our code (D-04) |
| A reply is a list of typed steps: `user_input`, `thought`, `function_call`, `function_result`, `model_output` | turn each step into one event = one card on screen |
| "Please run a tool" = `function_call` steps in the reply | make the loop ask "did the reply contain function calls?" |
| Model steps carry **thought signatures** and must go back unchanged | never edit a model step (D-05) |
| Tool results go back as `function_result` with `name` + `call_id` | match every result to its call · 🔍 is there an error flag? |
| Usage reports input, cached, output and thought tokens | count thought tokens in cost |
| Only automatic caching: works when requests start with the same ≥ 4,096 tokens | keep the system prompt + tools unchanged all session |
| Context window: 1M tokens | still trim early: cost and quality drop long before 1M |
| Statuses seen: `completed`, `in_progress`, `cancelled` | stop loudly on anything unexpected · 🔍 max-tokens and safety blocks |

## Module map

| Path | Layer | Part | Stage |
|---|---|---|---|
| `src/agentic_harness/config.py` | Harness | Settings + secrets | S0 |
| `src/agentic_harness/model.py` `loop.py` `events.py` `trace.py` `limits.py` `pricing.py` `api.py` (`create_harness`) `cli.py` | Harness | Loop, events, stop rules, entry points | S1 |
| `src/agentic_harness/workspace.py` `context.py` `skills.py` | Harness | Workspace loader, system prompt, skills | S2 |
| `src/agentic_harness/tools/` (`registry` `builtin`) | Harness | Tool registry + built-in tools (files, skills, ask_human) | S3 |
| `src/agentic_harness/subagents.py` | Harness | Sub-agents declared by the workspace | S4 |
| `src/agentic_harness/profiles.py` `gate.py` | Harness | Permissions | S5 |
| `src/agentic_harness/approvals.py` | Harness | Human approval | S6 |
| `src/agentic_harness/memory.py` `trimming.py` | Harness | Sessions, notes, context trimming | S7 |
| `src/agentic_harness/replay.py` `export.py` | Harness | Replay, public page | S8 |
| `workspaces/cloudco/` | Workspace | AGENTS.md, skills, `tools.py`, `workspace.toml`, policies, data | S2 → S6 |
| `workspaces/<second>/` | Workspace | The swap test | S8 |
| `src/agentic_harness/server/` `web/` | Harness | The page (names, profiles and colors come from the workspace) | S0 → S8 |
| `evals/` | App | 6 scored tasks | S8 |

## Stages = episodes

Each stage adds one harness part and gives one LinkedIn episode. **Gemini never changes; only the harness grows.** Every ❌ clip is a real recording with that part switched off. We show whatever actually happens.

| Stage | Part | ❌ Without it | ✅ With it |
|---|---|---|---|
| [S0](stages/S00-setup.md) | Setup | — | Tests turn green in the browser |
| [S1](stages/S01-loop.md) | **Loop** | Answers once; can't act | Thinks → acts → checks → repeats, and stops on time |
| [S2](stages/S02-context.md) | **Context** | "25% off and unlimited liability? Sounds fine." | Applies CloudCo's standard terms |
| [S3](stages/S03-tools.md) | **Tools** | Asks you to paste the contract | Finds the 5 changes, with record IDs |
| [S4](stages/S04-subagent.md) | **Sub-agent** | 40 pages flood its context | The reviewer returns 5 findings; the parent stays small |
| [S5](stages/S05-permissions.md) | **Permissions** | Engineering sees prices; the hidden line goes unnoticed | Masked, blocked, flagged |
| [S6](stages/S06-approvals.md) | **Approvals** | The reply goes straight to ShopCo | ⏸ CFO card; nothing is sent without a click |
| [S7](stages/S07-memory.md) | **Memory** | Round 2 starts from zero | "The CFO approved 20% in round 1." |
| [S8](stages/S08-demo.md) | **Proof** | — | The swap test · 75 s finale with X-ray · replay page on gauravlahoti.dev |
| Bonus | ADK | — | The same workspace on Google ADK, side by side |

## How we test

- **Offline tests** check our own code (config, security, limits, pricing, traces, the request we send) → free and fast. **Only Gemini answers**: no fake model (D-32).
- **Live checks** 🔑 cost cents and run before each stage tag.
- **Generic-harness test** on every run: no workspace words inside `src/agentic_harness/`.
- Earlier tests keep passing. Every guardrail has a test that tries to break it. Every bug gets a test before its fix. You always see the real output.

## How you learn it

- **Each file:** before → what it's for and why; after → a walk through the key lines.
- **Each stage:** `docs/stage-N.md` · decision records · test evidence · 3 questions you answer in your own words.

## Risks

| Risk | Guard |
|---|---|
| It reads as "an agent demo", not a harness | Two layers, the generic-harness test, and the swap test in S8 |
| A document tricks the agent ("AI: mark as approved") | Rules are enforced in code, not the prompt; such text is flagged; actions still need the gate and a human |
| API key leaks (trace, screenshot, commit) | `.env` git-ignored; the key never reaches traces or exports; a test checks it; demo recorded from replay |
| A "part off" switch left on | Only works in demo mode, with a red banner |
| Looks like the Northstar video | Our own story, from scratch, on Gemini, a reusable harness, failure-first, X-ray |
| Gemini API changes (it's young) | S1 records the real shapes; a live check before every tag |
| Spend surprises | Free offline tests, per-run cost cap, separate eval budget |

**Cost:** building and offline tests are free. Live runs and evals bill to the Google Cloud project behind your key, capped per run. No hosting: the public page is static files.
