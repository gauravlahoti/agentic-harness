# Rules for coding agents

This project's rules live in one file: **[CLAUDE.md](CLAUDE.md)**. Read it before any change and follow it exactly. It applies to every coding agent (Codex, Antigravity, Claude Code and others), not only Claude.

The most important rules:

- Never read or print `.env`. The user fills it in.
- `src/agentic_harness/` knows no domain. A test enforces this.
- Work on the current stage only, and present the stage brief before writing code.
- `make check` must pass before anything is marked built.
