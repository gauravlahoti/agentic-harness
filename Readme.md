<!--
Keeping this file current:
- Change a row's Status in "What the harness does" when that part works end to end.
- Remove "(coming next)" from a step once it runs.
- Keep it project-level and short. Per-check progress lives in Tracker.md.
-->

# agentic-harness

A general agent harness, built from scratch in plain Python on Gemini.

**Docs:** [Product](spec/00-product.md) · [Decisions](Decisions.md) · [Progress](Tracker.md) · [Security](Security.md)

The model only decides what to do next. The harness does everything else: it gives the model the right context, runs its tools, checks what it's allowed to do, asks a human when it matters, and remembers the work. An agent is a **workspace**, a folder of instructions, skills, tools and rules. Swap the folder and you get a different agent, with no harness code changed.

The first agent is the **CloudCo Contract Assistant**. It reviews a customer's changes to a renewal contract for Sales, Engineering and Finance, and never acts without a human's approval.

## Start with the code

1. Install [uv](https://docs.astral.sh/uv/), then clone this repository.
2. Run `make setup` to install the locked dependencies, then `make check` to run the offline tests. Both are free and need no key.
3. For live runs, copy `.env.example` to `.env` and add your [AI Studio](https://aistudio.google.com/apikey) key.
4. Run `uv run agentic-harness serve --workspace workspaces/cloudco`, open http://127.0.0.1:8000, pick a team in the sidebar and give the agent a task. Pick the Gemini model in the input box.

**Using a coding agent?** Open the repository in Claude Code, Codex or Antigravity and ask it to set up and check the project. It follows the steps above and the project rules in [CLAUDE.md](CLAUDE.md) (Codex and Antigravity reach them through [AGENTS.md](AGENTS.md)). Add the key to `.env` yourself; agents are told never to read it.

## What the harness does

| Part | What it handles | CloudCo example | Status |
|---|---|---|---|
| Loop | Calls the model, runs the tools it asks for, repeats; stops at step, cost or time limits | A run that hits its $1 budget stops and says why | Available |
| Context | Standing instructions, team files, and skills loaded on demand | Checks each change against CloudCo's standard terms | Available |
| Actions | Workspace tools, built-in tools, and sub-agents with a clean history | Finds ShopCo's 5 contract changes, with record IDs; a reviewer sub-agent reads the 40 pages | Available |
| Guardrails | Tools and fields per profile, hard limits, a person approves sends | Engineering never sees prices; sending to ShopCo waits for you | Available |
| Memory | Saved tasks you can resume, per-profile notes, context trimming | In round 2 it recalls that the CFO approved 20% in round 1 | Planned |

## Build your own agent

A workspace declares everything domain-specific. The harness reads `workspace.toml`; the model never sees it.

```
workspaces/<name>/
├── workspace.toml     # wiring: memory, skills, tools, profiles, approvals
├── AGENTS.md          # standing instructions
├── skills/            # SKILL.md folders, loaded on demand
└── tools.py           # the agent's own tools
```

```toml
memory = ["AGENTS.md", "teams/{profile}.md"]
skills = ["skills/company/", "skills/{profile}/"]
tools  = "tools.py"

[profiles.sales]
tools = ["get_deal", "get_contract", "accept_change", "send_to_customer"]

[[approvals]]
tool     = "accept_change"
when     = { term = "discount", above = 15 }
approver = "cfo"
```

## Scope

A local learning project, not a product. CloudCo and all its data are fictional. Actions write to a local outbox, never real email. The server binds to `127.0.0.1` only, and the API key is read in one module and never logged. Built without an agent framework, so every part is plain code you can read. Run `make help` for every command.

Not licensed yet. A license will be added before the repository is made public.
