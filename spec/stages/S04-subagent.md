# S04 · Sub-agent

> **Goal:** the agent hands a big, self-contained job to a helper with a clean context, and gets back only the answer.
> **Why it matters:** a raw contract diff is ~60 edits over 40 pages. The helper reads it all; the main agent receives 5 lines. A sub-agent is just the harness calling itself.

**Flow:** the workspace declares a sub-agent → the harness adds a `delegate_task` tool → the main agent calls it → the harness builds a child (empty history, its own instructions and tools, a slice of the budget) → the child runs its own loop → it returns a short, structured result.

**CloudCo's sub-agent: Clause Reviewer**
- **Tools:** `review_contract`, `search_policy` (read-only; D-73)
- **Returns** (≤ 200 words): for each change that matters → clause · their change · our rule · risk. Plus any text that tries to instruct an AI.
- **Model:** Flash-Lite (cheaper), set in `workspace.toml`

**Builds:** `src/agentic_harness/subagents.py` · `[subagents]` in CloudCo's `workspace.toml` · sub-agent lane on the page

## Done when

| ID | Check | How |
|---|---|---|
| S04-AC1 | Sub-agents come from `workspace.toml`; the harness has none built in | 🧪 |
| S04-AC2 | `delegate_task` starts the child with an empty history | 🧪 |
| S04-AC3 | The child has only its declared tools, and none are actions | 🧪 |
| S04-AC4 | The child can't delegate (depth 1) | 🧪 |
| S04-AC5 | Budget slice enforced (50% of the time left, 25% of the money, ≤ 15 steps); out of budget → partial answer + reason | 🧪 |
| S04-AC6 | The child returns the declared short shape | 🧪 |
| S04-AC7 | The parent's history holds only the result, not the 40 pages | 🧪 |
| S04-AC8 | Child events are tagged `agent_id` + `parent_id` | 🧪 |
| S04-AC9 | Page: nested sub-agent lane with its own mini counters | 👀 |
| S04-AC10 | Live: same 5 findings with delegation on and off; the parent uses fewer tokens with it on | 🔑 👀 |
| S04-AC11 | Page: a collapsible Harness pane shows the profile's memory files, skills, tools (risk, description) and sub-agents | 🧪 👀 |
| S04-AC12 | Switching a skill, tool or sub-agent off removes it for the next run only; unknown names are refused; nothing is switched on beyond the workspace | 🧪 |
| S04-AC13 | Each run records what was off (event, trace, "Started a run" line) | 🧪 👀 |

## Key choices

- **Declared by the workspace, run by the harness** → any agent can have helpers; the harness knows none of them. *Cost:* a config section.
- **Read-only helpers** → delegation can never become a way around the gate. *Cost:* actions stay with the main agent.
- **Only the brief goes in, only a summary comes out** → a clean context is the point. *Cost:* the parent must write a complete brief; details can be lost.
- **Depth 1, one at a time** → no runaway trees of agents. *Cost:* slower.
- **A cheaper model for the helper** → reading is easy work. *Cost:* one more setting.

## Without it / with it

- ❌ Delegation off → the main agent reads the whole diff; its context bar fills, and it may miss a change.
- ✅ Delegation on → the sub-agent lane fills instead; the main agent receives 5 findings and its bar stays flat.

## Explain it back

1. If the child reads the same pages, where do the savings come from?
2. Why must a sub-agent never have more rights than the agent that called it?
3. Why limit depth to 1?

## Changes

- 2026-11-10 · Created (v3).
- 2026-11-10 · Brief approved with choices D-55–D-65. You asked for a Harness pane (tools, skills, sub-agents, with switches); add-on brief pending.
- 2026-11-10 · Harness pane add-on approved at your request: S04-AC11–AC13 added (D-66–D-72); D-64 changed (page switch now).
- 2026-11-10 · AC5 changed at your choice: the helper gets 50% of the time left (was 25%), still 25% of the money (D-60). Seen live: the 30 s slice ran out under load.
- 2026-11-10 · Harness pane grouped by part (Context · Tools · Memory · Guardrails · Agentic Loop), collapsed by default, at your request. CloudCo now has four tools (D-73).
