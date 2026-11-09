# agentic-harness

> **Agent = Model + Harness.** A general agent harness built from scratch in Python on Gemini. Agents run on it as **workspaces**.
> First workspace: CloudCo's **Contract Assistant** (all data made up).

**Status:** scaffold built · Stage S00 in progress · see [Tracker.md](Tracker.md)

## Quick start

```bash
make setup      # install exactly what uv.lock says
make check      # lint + types + tests (offline, free)
make help       # every command
```

Live Gemini checks need a key: copy `.env.example` to `.env`, fill it in, then `make live`.

## What's where

| Path | What |
|---|---|
| `src/agentic_harness/` | The harness. Knows no business domain (a test enforces this). |
| `workspaces/` | Agents that run on the harness (from S01) |
| `tests/` | `unit/` · `architecture/` (naming, domain-free harness) · more per stage |
| `spec/` | What we build and why: product, company, UI, one file per stage |
| [Scaffold.md](Scaffold.md) | The production baseline and every choice behind it |
| [Decisions.md](Decisions.md) | Why X over Y |
| [Tracker.md](Tracker.md) | What's done, pending, waiting on you |
| [Security.md](Security.md) · [Contributing.md](Contributing.md) · [Changelog.md](Changelog.md) | Policies, workflow, history |

## How it's built

Spec first, one stage at a time, every file explained. See [spec/how-we-build.md](spec/how-we-build.md).
