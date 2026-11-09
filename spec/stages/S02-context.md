# S02 · Context

> **Goal:** the agent knows who it works for, the rules it must follow, and how each team does its work.
> **Why it matters:** a smart model that doesn't know your company gives confident, wrong answers.

**Two kinds of context**

| | Loaded | Holds | CloudCo example |
|---|---|---|---|
| **Memory files** (`AGENTS.md` + team file) | **Every call**, so keep them short | Who we are, rules that always apply, answer format | "Never agree to terms. Cite record IDs." |
| **Skills** (`SKILL.md`) | **On demand.** Only name + one line sit in the prompt; `load_skill` reads the rest | How we do one task, step by step | `contract-review`, `payment-terms-check` |

**System prompt order:** harness base → `AGENTS.md` → team file → skill list. The order never changes, so Gemini can cache it.

**Builds:** `src/agentic_harness/workspace.py` (reads `workspace.toml`) · `context.py` · `skills.py` · `load_skill` · the CloudCo context files · profile switcher
**Not yet:** data tools (S3)

## Done when

| ID | Check | How |
|---|---|---|
| S02-AC1 | The harness reads `workspace.toml`: memory files, skill folders, tools file | 🧪 |
| S02-AC2 | System prompt is built in a fixed order: base → memory files → skill list | 🧪 |
| S02-AC3 | `{profile}` in a path picks the active profile's file | 🧪 |
| S02-AC4 | Only skill names + descriptions go in the prompt; `load_skill` returns the full text | 🧪 |
| S02-AC5 | Skills use the open `SKILL.md` format (name, description) and are checked on load | 🧪 |
| S02-AC6 | Each profile sees only its own skill folders | 🧪 |
| S02-AC7 | A memory file over its size budget gives a warning | 🧪 |
| S02-AC8 | The prompt is identical on every call in a session | 🧪 |
| S02-AC9 | The domain-free test (from S00) also checks each workspace's own words, declared in its `workspace.toml` | 🧪 |
| S02-AC10 | CloudCo files written: `AGENTS.md`, 3 team files, 4 skills, 2 policies | 📄 |
| S02-AC11 | Answers follow: Summary → Needs a human decision → Sources | 🔑 👀 |
| S02-AC12 | Page: profile switcher, Context tags, the skill listed in Sources | 👀 |

## Key choices

- **Skills load on demand** → the prompt stays small; the agent reads a procedure only when it needs it. *Cost:* one extra tool call.
- **Same `SKILL.md` format as Claude Code and Google ADK** → skills move between harnesses unchanged. *Cost:* we follow someone else's format.
- **`workspace.toml` is read by the harness, never shown to the model** → configuration isn't something the model can talk its way around. *Cost:* none.
- **A size budget for memory files** → they cost tokens on every call. *Cost:* a warning to act on.

## Without it / with it

Ask (pasting the changes in): *"ShopCo wants 25% off and unlimited liability. OK?"*
- ❌ No context → *"Sounds reasonable,"* plus an acceptance email.
- ✅ With context → applies CloudCo's terms: 25% needs the CFO; unlimited liability is never allowed.

## Explain it back

1. What belongs in `AGENTS.md`, and what belongs in a skill?
2. Why are skills loaded on demand?
3. Why must the prompt order never change?

## Changes

- 2026-11-10 · Created (v3).
- 2026-11-10 · Brief approved with choices D-34–D-41. No Fake recordings (D-32). Each model call carries a prompt ID so S02-AC8 can be checked in the trace.
