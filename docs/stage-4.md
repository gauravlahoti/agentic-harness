# Stage 4 · Sub-agent, and the Harness pane

> The agent hands a big, self-contained job to a helper with a clean context and gets back
> only a short result. A sub-agent is just the harness calling itself.
> The page gained a **Harness** pane: every part of the harness, with switches.

## What you have now

- As **Sales**, ask "What did ShopCo change in CT-2207, and what can I agree to?". The main agent calls `delegate_task`, and the **clause-reviewer** runs its own loop on Flash-Lite with two read-only tools. It returns ≤ 200 words. The main agent never sees the 61-edit diff.
- On the page, the helper gets its own **lane** under "Handed the job to clause-reviewer", with its own counters.
- The **Harness** pane (right, collapsed by default): Agentic Loop · Context · Tools · Guardrails · Memory, in plain words. Switch a skill, tool or sub-agent off for the next run; a "1 off" chip in the input box reminds you.
- CloudCo now has **four tools** (D-73): `lookup`, `review_contract`, `search_policy`, `send_to_customer`.
- `agentic-harness run … --no-delegation` runs without helpers.

## A sub-agent in one picture

```
main agent ── delegate_task(agent="clause-reviewer", brief="Review CT-2207 …")
                 │
                 ▼  Delegator (subagents.py)
   child = Harness(own model, own instructions file, only its read-only tools,
                   limits = ½ of the time left · ¼ of the money · ≤ 15 steps)
   child.run(brief)            ← empty history: the brief is its only message
     ├─ review_contract  → 61 edits      (stays in the child's history)
     ├─ search_policy    → rules
     └─ answer, ≤ 200 words
                 │  every child event → parent's events, tagged agent_id/parent_id
                 ▼
main agent's history gets ONE function_result: the short answer (cost charged to the run)
```

## Switches: what they can and can't do

- The page sends `off: {tools, skills, subagents}` with the run. The server checks every name exists for this profile, and can only **remove**, never add (D-70).
- Knock-on effects: no skills means no `load_skill`; no sub-agents means no `delegate_task`, and `review_contract` returns to the main agent.
- `run_started` records what was off, so every answer is tied to the harness that produced it (D-72).

## The files

| File | Job | Key lines |
|---|---|---|
| `subagents.py` | Helpers | `child_limits` (½ time, ¼ money, ≤ 15 steps) · `cap_words` · `result_text` (partial answer + reason) · `tag_events` · `Delegator.__call__` runs the child and charges its cost to the parent |
| `workspace.py` | Config | `[subagents.<name>]`: instructions file must exist; every tool must be `read`; `delegate_only` must be some helper's tool |
| `api.py` | Wiring | `create_harness(..., model_factory, delegation, off)`; `describe_harness` feeds the pane from the same pieces |
| `server/app.py` · `runs.py` | Page API | `GET /api/harness`; `off` in the run request; **only the main agent's `run_finished` ends the stream** (`ends_stream`) |
| `web/app.js` · `app.css` | Page | `renderPane()`, `switchFor()`, `newLane()` / `onLaneEvent()` |

## What real Gemini taught us

1. **Time is the scarce budget on the free tier.** A busy Flash-Lite took 11 s for one call; a 25% time slice (~30 s) ran out. Now ½ the time, ¼ the money (D-60, your choice).
2. **A helper's "finished" is not the run's "finished".** The server stopped streaming at the first `run_finished`, which was the helper's, and cancelled the main run mid-call. Fixed, with a test.
3. **Delegation changes what the main agent can cite.** Without the raw diff it named every change but dropped the clause IDs. That is still open as S04-AC10: one line in the contract-review skill is proposed, awaiting your yes.

## Verify it yourself

1. `make check` → all green (193 passed).
2. Server on, hard reload (Cmd+Shift+R) once. Open the **Harness** pane: five parts, all collapsed; Tools shows 4 local tools, "Remote tools · MCP · None connected", and `clause-reviewer`.
3. As Sales on Flash-Lite, ask the ShopCo question. You get a lane under "Handed the job to clause-reviewer" with its own counters, then "✓ Run complete".
4. Switch `clause-reviewer` off (a "1 off" chip appears) and ask again. There is no lane, the main agent calls `review_contract` itself, and "Started a run · 1 off" lists what was off.
5. `uv run agentic-harness run --workspace workspaces/cloudco --profile sales "What did ShopCo change in CT-2207?"`: the helper's steps print indented with `┆ clause-reviewer`.

## Explain it back

1. If the helper reads the same pages, where do the savings come from?
2. Why must a sub-agent never have more rights than the agent that called it?
3. Why can a switch remove a tool but never add one?
