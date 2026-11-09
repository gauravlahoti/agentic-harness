# Stage 1 · The loop

> The smallest loop that calls Gemini, runs a tool, sends the result back, and stops on time.
> This loop turns a model into an agent. Every later stage wraps one of its lines.

## What you have now

- `agentic-harness run --workspace workspaces/hello "What time is it in Tokyo?"` runs a real agent in the terminal.
- The page's **Agent** view: a calm chat. Your task in a bubble, then the agent's **Activity**: one line per harness step (model steps grey, tool steps green, tagged LOOP or TOOL), live counters (calls · tokens · $ · s), the answer as prose, and "✓ Run complete". Click any line to see its facts and the raw event. **Fake** replays a recorded Gemini run (free); **Live** calls Gemini.
- Every run is saved to `.agentic-harness/traces/<run>.jsonl`, one event per line, key scrubbed.
- 96 offline tests (6 s) built on **real** Gemini replies, plus one live test (`make live`).

## The loop in one picture

```
task ─▶ steps = [user_input]
          │
          ▼
   ┌─ limits ok? ──no──▶ stopped: step_limit | cost_limit | time_limit
   │      │yes
   │      ▼
   │  model.create(system, steps, tools)      ← whole history, store=False
   │      │
   │      ▼
   │  steps += reply.steps                    ← exactly as received (signatures!)
   │      │
   │      ├─ status incomplete ─────────────▶ stopped: output_limit
   │      ├─ completed, no calls ───────────▶ completed: the answer
   │      ├─ anything else odd ─────────────▶ failed: unexpected_status
   │      ▼
   │  run each function_call, in order
   │  steps += all results together           ← each with its call_id
   └──────┘
```

Gemini has no "tool_use" stop reason. A reply asks for tools by **containing** `function_call` steps. We saw live that such a reply has status `requires_action`, not `completed`.

## The files

| File | Job | Key lines |
|---|---|---|
| `model.py` | The only door to the model | `ModelClient` has one method. `GeminiModel` sends `store=False`, the whole history, `automatic_continuation=False`. Any SDK error becomes a `ModelError` with the key removed. `FakeModel` replays recordings and remembers what it was sent. |
| `loop.py` | The loop itself | `steps.extend(reply.steps)` never edits a model step. `asyncio.timeout(budget.seconds_left())` makes the time limit cover the wait for Gemini too. A broken tool becomes a result with `is_error`, not a crash. |
| `limits.py` | The brakes | `Budget.exceeded()` returns a *named* reason or `None`. |
| `pricing.py` + `pricing.toml` | Cost | Thought tokens are billed as output. Prices live in a data file; an unknown model stops the harness at startup, so the cost limit can't silently count $0. |
| `events.py` | What happened | One `Event` per step, numbered. Listeners subscribe; the loop never knows who listens. |
| `trace.py` | The record | One listener: appends each event as a JSON line, after replacing any secret with `***`. |
| `tools/`, `workspace.py` | What the agent can do | A `Tool` is name + description + schema + function. The model sees only the first three. A workspace's `tools.py` defines `TOOLS`. |
| `api.py` | One call to wire it all | `create_harness(model, limits, workspace)`, used by both the CLI and the page. |
| `server/runs.py`, `web/app.js` | The page | The server forwards events as NDJSON; the page turns each into an activity line. Every element is built in code and all text goes in as text, so model output can't inject HTML. |
| `scripts/record_gemini_shapes.py` | Ground truth | Ten small live calls saved as fixtures. Refuses to write any file that contains the key. |

## What real Gemini taught us (not in the docs)

1. A tool request ends `requires_action`. A loop that only accepted `completed` would have "failed" on every tool call.
2. The SDK quietly retried a 503 "high demand" for about **5 minutes**, and can make extra billed calls by itself. Both are now off (D-29).
3. A key exported in your shell beats `.env`. That's normal, but it hid your new key once.

## Verify it yourself

1. `make check` → all green, 96 passed.
2. `uv run agentic-harness run --workspace workspaces/hello --fake "What time is it?"` → 2 calls, a `get_time` row, `completed`.
3. `uv run agentic-harness serve --workspace workspaces/hello` → http://127.0.0.1:8000 → click an example → send (Fake) → watch the activity lines fill in, then the answer and "✓ Run complete".
4. Switch to **Live**, pick a model in the menu next to it, and send a task. You need a key in `.env`. If a model is busy (503 "high demand"), pick another one. Try "who is the prime minister of India": the model should answer without calling `get_time` (D-30).
5. Click an activity line: a model step shows tokens in / out / thinking and cost; a tool step shows arguments, output and call ID. **Raw event** shows the exact event, including the thought `signature` (shortened).
6. Open the newest file in `.agentic-harness/traces/` and search it for your key. It isn't there.
7. Try a limit: `uv run agentic-harness run --workspace workspaces/hello --fake --max-steps 1 "Time?"` → `stopped … step_limit`.

## Explain it back

1. Why does the loop look for `function_call` steps instead of a stop reason?
2. What breaks if a result goes missing, or a model step is edited?
3. Why is the model never given the Python function itself?
