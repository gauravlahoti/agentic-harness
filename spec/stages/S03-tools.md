# S03 · Tools

> **Goal:** the agent can pull in real company data and take actions, through tools the workspace provides.
> **Why it matters:** without tools it can only talk. With them it can look things up, write drafts, and act.

**Two kinds of tools**

| | Owned by | Examples |
|---|---|---|
| **Built-in** | The harness (any agent) | `read_file`, `write_file` (task folder), `load_skill` |
| **Workspace** | `workspaces/cloudco/tools.py` | Lookups: `get_customer`, `get_deal`, `get_contract`, `get_uptime`, `get_payment_history`, `compare_to_standard`, `search_policy` · Actions: `accept_change`, `send_to_customer` |

Each tool declares a **risk**: `read`, `write` or `action`. Permissions (S5) and approvals (S6) build on it.

**Builds:** `src/agentic_harness/tools/registry.py` (`@tool`) · `builtin.py` · CloudCo `tools.py` · CloudCo's made-up data
**Not yet: guardrails.** Actions run without asking. They only write to a local `outbox/`, but this is the "give it power" stage; S5 and S6 rein it in.

## Done when

| ID | Check | How |
|---|---|---|
| S03-AC1 | `@tool` records name, description, schema and risk, and outputs Gemini's tool format | 🧪 |
| S03-AC2 | Built-in tools work for any workspace | 🧪 |
| S03-AC3 | Workspace tools load from `tools.py`; the harness knows none of them by name | 🧪 |
| S03-AC4 | CloudCo lookups return records with IDs | 🧪 |
| S03-AC5 | `compare_to_standard` returns every edit (~60) with clause IDs | 🧪 |
| S03-AC6 | `search_policy` returns the rule and its section number | 🧪 |
| S03-AC7 | Actions write only to the local outbox, never to real email | 🧪 |
| S03-AC8 | Tool errors go back to the model; the loop never crashes | 🧪 |
| S03-AC9 | CloudCo data is made up and labelled fictional | 📄 |
| S03-AC10 | Page: tool steps, record IDs in Sources, file cards | 👀 |
| S03-AC11 | Live: finds all 5 changes that matter, with IDs | 🔑 👀 |

## Key choices

- **Specific tools, not open database queries** → safer, easier for the model to pick correctly, simple to gate by profile. *Cost:* a new question type needs a new tool.
- **Errors go back to the model, not raised** → it reads them and corrects itself. *Cost:* a buggy tool can look like a model mistake, so tests check errors.
- **Descriptions are instructions to the model** (when to use, when not to) → tool choice depends mostly on these words. *Cost:* a longer prompt.
- **Risk label on every tool** → guardrails key off it without knowing each tool.

## Without it / with it

- ❌ No tools → *"Please paste the contract."*
- ✅ With tools → compares the contract to standard terms and lists the 5 changes, each with a clause ID.

## Explain it back

1. Why does the harness own `read_file`, while CloudCo owns `get_contract`?
2. Why return errors instead of raising them?
3. What would happen with a tool described as "does contract stuff"?

## Changes

- 2026-11-10 · Created (v3).
- 2026-11-10 · Brief approved with choices D-43–D-53. Files are written only through the harness's `ctx` and shown via a `file_saved` event.
- 2026-11-10 · Built: S03-AC1–AC11 → 🟨. Found while checking the page: the browser ran an old `app.js`; the server now sends `Cache-Control: no-cache` (D-54). No change to the checks.
