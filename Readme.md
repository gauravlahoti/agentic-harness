<!--
Keeping this file current:
- Change a row's Status in "What the harness does" when that part works end to end.
- Keep it project-level and short. Per-check progress lives in Tracker.md.
-->

# agentic-harness

An agent harness built from scratch in plain Python on Gemini. No agent framework.

**▶ [Watch the guided tour](https://agentic-harness.gauravlahoti.dev/)**: five minutes, voiced, with a real recorded run. No sign-up, no key.

**Docs:** [Product](spec/00-product.md) · [Decisions](Decisions.md) · [Progress](Tracker.md) · [Security](Security.md)

## The idea

**Agent = model + harness.** The model only decides what to do next. The harness does the rest: it builds the context, runs the tools, enforces the rules, asks a person when it matters, and checks the answer.

An agent is a **workspace**: a folder of instructions, skills, tools and rules. Swap the folder and you have a different agent, with no harness code changed.

The first agent is the **CloudCo Contract Agent**. It reviews a customer's changes to a renewal contract, says who must approve each one, and drafts the reply. It never acts without a person's approval. CloudCo and all its data are made up.

## What the harness does

| Part | What it handles | CloudCo example | Status |
|---|---|---|---|
| Loop | Calls the model, runs the tools it asks for, repeats; stops at step, cost or time limits | A run that hits its $1 budget stops and says why | Available |
| Context | Standing instructions, team files, skills loaded on demand | Checks each change against CloudCo's standard terms | Available |
| Tools | Workspace tools, built-in tools, sub-agents with a clean history | A reviewer sub-agent reads the 40-page contract | Available |
| Guardrails | Tools and fields per profile, hard limits, human approvals | Engineering never sees prices; sending to ShopCo waits for sign-off | Available |
| Verification | Plain-code checks on the draft; a failed draft goes back once | A draft that misses two changes is sent back and fixed | Available |
| Memory | Saved tasks you can resume, per-profile notes, context trimming | In round 2 it recalls that the CFO approved 20% in round 1 | Planned |

## Run it

You need [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/gauravlahoti/agentic-harness && cd agentic-harness
make setup                     # install the locked dependencies
make check                     # lint, types, offline tests: free, no key
cp .env.example .env           # then add your AI Studio key: https://aistudio.google.com/apikey
uv run agentic-harness serve --workspace workspaces/cloudco
```

Open http://127.0.0.1:8000, pick a team, give the agent a task. The guided tour is in the sidebar.

**Using a coding agent?** Open the repo in Claude Code, Codex or Antigravity and ask it to set up and check the project. It follows [CLAUDE.md](CLAUDE.md) ([AGENTS.md](AGENTS.md) for the others). Add the key to `.env` yourself: agents are told never to read it.

## Build your own agent

The harness reads `workspace.toml`. The model never sees it.

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

## Safety

- **Local by default.** The server answers on `127.0.0.1` only.
- **One place for the key.** Only `config.py` reads it, and it never reaches logs, traces or the page.
- **No real side effects.** Actions write to a local outbox, never real email.
- **Hosted tour is read-only.** `HARNESS_PUBLIC=1` answers reads only and holds no key. Deploy it with `make deploy-tour PROJECT=<project> HOSTS=<names>` (Cloud Run, scales to zero, no secrets).

More in [Security](Security.md). `make help` lists every command.

## License

No license yet. Until one is added, all rights are reserved.
