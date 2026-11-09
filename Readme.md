<!--
Keeping this file current:
- Update the Status line and the "Status" column in "Harness parts" when a part starts working.
- Move a command out of "Planned" in Usage once it runs.
- Keep it project-level: build process and per-check progress live in Tracker.md, not here.
-->

# agentic-harness

[![CI](https://github.com/gauravlahoti/agentic-harness/actions/workflows/ci.yml/badge.svg)](https://github.com/gauravlahoti/agentic-harness/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)

A general agent harness, built from scratch in plain Python on Gemini.

**Agent = Model + Harness.** The harness runs everything around the model: the loop, context, tools, sub-agents, permissions, approvals and memory. An agent is a **workspace**: a folder of instructions, skills, tools and rules. Swap the folder and you get a different agent, with no harness code changed.

> **Status: early development.** The project scaffold and quality gates work. The harness parts are being built. See [Tracker.md](Tracker.md) for detailed progress.

## How it works

```
┌──────────────────────────────────────────────────────────────┐
│  WORKSPACE   one agent             workspaces/<name>/        │  changes per agent
│  AGENTS.md · skills · tools.py · workspace.toml              │
├──────────────────────────────────────────────────────────────┤
│  HARNESS     any agent             src/agentic_harness/      │  never changes per agent
│  loop · context · tools · sub-agents · permissions ·         │
│  approvals · memory · traces                                 │
├──────────────────────────────────────────────────────────────┤
│  MODEL       Gemini                                          │
└──────────────────────────────────────────────────────────────┘
```

Three rules hold everywhere:

1. **The model asks; the harness decides.** A tool call is a request. It passes the permission gate before anything runs.
2. **The harness knows no domain.** Nothing about any one agent lives in `src/agentic_harness/`. A test fails if it does.
3. **The loop doesn't know who's watching.** It emits events; the web page, traces and tests all listen.

### Harness parts

| Part | What it does | Status |
|---|---|---|
| Loop | Calls the model, runs requested tools, repeats; stops on step, cost or time limits | Planned |
| Context | Builds the system prompt from the workspace's memory files and skill list | Planned |
| Tools | Registers built-in and workspace tools; returns errors to the model instead of crashing | Planned |
| Sub-agents | Runs a child agent with a clean history, limited tools and its own budget | Planned |
| Permissions | Per-profile tools, masked fields, protected files, "never" rules | Planned |
| Approvals | Pauses risky actions until a person with the right authority decides | Planned |
| Memory | Saved and resumable tasks, per-profile notes, context trimming | Planned |
| Traces and replay | Records every step; replays a saved run with zero model calls | Planned |

## Quick start

**Requirements:** [uv](https://docs.astral.sh/uv/), `make`, `git`. uv installs Python 3.12 for you.

```bash
git clone https://github.com/gauravlahoti/agentic-harness.git
cd agentic-harness
make setup    # install exactly what uv.lock pins
make check    # lint, types, tests: offline and free
make hooks    # optional: git pre-commit hooks (secret scan, lint, types)
```

**Gemini access** is only needed for live runs. Copy `.env.example` to `.env` and add your [AI Studio](https://aistudio.google.com/apikey) key. Offline commands never need it.

## Usage

Works today:

```bash
uv run agentic-harness --version
```

Planned. Run an agent from the terminal, or open the local web page:

```bash
uv run agentic-harness run   --workspace workspaces/cloudco --profile sales "What did ShopCo change?"
uv run agentic-harness serve --workspace workspaces/cloudco    # http://127.0.0.1:8000
```

Both call one Python function:

```python
agent = create_harness(
    model     = GeminiModel(...),                 # model name comes from config
    limits    = Budget(steps=25, usd=1.00),       # hard stop rules
    workspace = Workspace("workspaces/cloudco"),
    profile   = "sales",                          # who is using it
)
```

## Building an agent

An agent is a folder. The harness reads `workspace.toml`; the model never sees it.

```
workspaces/<name>/
├── workspace.toml     # wiring: memory, skills, tools, profiles, approvals
├── AGENTS.md          # standing instructions for the agent
├── skills/            # SKILL.md folders, loaded on demand
└── tools.py           # the agent's own tools
```

```toml
memory = ["AGENTS.md", "teams/{profile}.md"]      # {profile} = the active user profile
skills = ["skills/company/", "skills/{profile}/"]
tools  = "tools.py"

[profiles.sales]
tools = ["get_deal", "get_contract", "accept_change", "send_to_customer"]

[[approvals]]
tool     = "accept_change"
when     = { term = "discount", above = 15 }
approver = "cfo"
```

**First workspace:** the CloudCo Contract Assistant. It reviews a customer's changes to a renewal contract against company standards and never acts without human approval. CloudCo and all its data are fictional.

## Configuration

Set in `.env`. Only `src/agentic_harness/config.py` reads these values.

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | Live runs only | none | AI Studio API key |
| `HARNESS_BACKEND` | No | `gemini_api` | `gemini_api` or `agent_platform` |
| `HARNESS_MODEL` | No | set in config | Model for the main agent |
| `GOOGLE_CLOUD_PROJECT` | `agent_platform` only | none | Google Cloud project |
| `GOOGLE_CLOUD_LOCATION` | No | `global` | Google Cloud region |

## Development

| Command | Does |
|---|---|
| `make setup` | Install locked dependencies |
| `make check` | Everything CI runs: ruff lint + format, mypy strict, pytest with ≥ 85% coverage |
| `make test` | Offline tests only (free, no key) |
| `make live` | Tests against real Gemini (needs a key, costs cents) |
| `make format` | Auto-fix formatting and simple lint issues |
| `make help` | List every command |

CI runs `make check` and a full-history secret scan on every push. Workflow and conventions: [Contributing.md](Contributing.md).

## Project layout

```
src/agentic_harness/   the harness: domain-free
workspaces/            agents that run on the harness
tests/                 unit/ · architecture/ (naming, domain-free harness)
spec/                  product, company, UI and design specs
```

## Security

- The API key lives only in `.env` (git-ignored), is read in one module, and is never logged, traced or shown.
- The local server binds to `127.0.0.1` only.
- Agent actions write to a local outbox. Nothing is ever sent as real email.
- gitleaks scans every commit and the full history in CI.

Full policy and how to report a problem: [Security.md](Security.md).

## Documentation

| Document | Contents |
|---|---|
| [spec/00-product.md](spec/00-product.md) | Product vision, architecture, stack |
| [Decisions.md](Decisions.md) | Every design choice and its trade-off |
| [Scaffold.md](Scaffold.md) | Tooling baseline and why |
| [Tracker.md](Tracker.md) | Detailed progress |
| [Changelog.md](Changelog.md) | Release history |

## License

Not licensed yet. A license will be added before the repository is made public.
