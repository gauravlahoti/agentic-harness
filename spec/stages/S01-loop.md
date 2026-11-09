# S01 · The loop

> **Goal:** the smallest loop that calls Gemini, runs a tool, sends the result back, and stops on time.
> **Why it matters:** this loop turns a model into an agent. Every later stage wraps one of its lines.

```python
async def run(self, task):
    steps = [user_input(task)]                    # the history we own
    while not self.limits.exceeded():             # stop rules
        reply = await self.model.create(system, steps, tools)
        steps.extend(reply.steps)                 # exactly as received
        if not reply.tool_calls:
            return self.finish(reply)             # done
        results = [await self.run_tool(c) for c in reply.tool_calls]
        steps.extend(function_result(r) for r in results)
    return self.stop(self.limits.reason)          # step_limit, cost_limit, …
```

**Gemini difference:** there is no "tool_use" stop reason. Gemini puts `function_call` steps in its reply, so the loop asks: *did this reply contain function calls?*

**Builds:** API test script · `model.py` (`ModelClient`, `GeminiModel`) · `loop.py` · `events.py` · `trace.py` · `limits.py` · `pricing.py` · `api.py` (`create_harness`) · `agentic-harness run` · timeline on the page
**Toy tool:** `get_time` in `workspaces/hello/`, the smallest possible workspace
**Not yet:** context files, real tools, guardrails

## Done when

| ID | Check | How |
|---|---|---|
| S01-AC1 | A test script records Gemini's real reply shapes in `docs/gemini-api-notes.md` (text, tool call, result, statuses, usage, max-tokens, safety block) | 🔑 📄 |
| S01-AC2 | `ModelClient` has one method: `create(system, steps, tools)` | 🧪 |
| S01-AC3 | `GeminiModel` sends the full history with `store=False`, never `previous_interaction_id` | 🧪 |
| S01-AC4 | ~~`FakeModel` replays scripted replies~~ Removed: only Gemini answers (D-32) | – |
| S01-AC5 | Plain answer → 1 call, ends `completed` | 🧪 |
| S01-AC6 | Tool round trip → 2 calls; the result carries the matching `call_id` | 🧪 |
| S01-AC7 | Two calls in one reply → both run in order, results sent together | 🧪 |
| S01-AC8 | Model steps are kept exactly as received | 🧪 |
| S01-AC9 | Stop rules (steps, cost, time) end the run with a named reason; cost counts thought tokens | 🧪 |
| S01-AC10 | An unexpected status ends the run with a named error, never a silent loop | 🧪 |
| S01-AC11 | Every step emits an event and is saved to a trace file; the key never appears in it | 🧪 |
| S01-AC12 | `create_harness(model, limits, workspace)` and `agentic-harness run "…"` both work | 🧪 |
| S01-AC13 | Page: input box, activity timeline, status line, model menu | 👀 |
| S01-AC14 | A real tool round trip works on Gemini (thought signatures survive) | 🔑 🧪 |

## Key choices

- **One interface for any model** (`ModelClient`) → a new provider is one new class. *Cost:* one extra layer.
- **History in Gemini's own step format** → no translation code. *Cost:* another provider needs an adapter.
- **We run the tools; the SDK never does** (no automatic function calling) → the loop is the lesson. *Cost:* we write the dispatch.
- **Stop rules from day one** → a loop without brakes is a bug, not a feature. *Cost:* a few lines.
- **Events, not prints** → the page, traces and tests all read the same stream. *Cost:* a little more code.

## Without it / with it

- ❌ **Model alone:** "What did ShopCo change in their contract?" → it can't see anything, so it refuses or guesses.
- ✅ **With the loop + a toy tool:** cards appear: model call → tool call → result → answer. Badge: *completed in 2 calls*.

## Explain it back

1. Why does the loop look for `function_call` steps instead of a stop reason?
2. What breaks if a result goes missing, or a model step is edited?
3. Why is the model never given the Python function itself?

## Changes

- 2026-11-10 · Created (v3). Stop rules moved here from a later stage; `create_harness` and the CLI start here.
- 2026-11-10 · Built. Live facts changed the loop's details, not its shape: a tool request ends `requires_action` (not `completed`); the SDK's automatic continuation and silent retries are switched off (D-29). Recordings use `gemini-3.5-flash-lite` (3.8/3.6 Flash overloaded on the free tier). Fake mode replays `workspaces/hello/fake_replies.json`.
- 2026-11-10 · At your request: Fake mode, `FakeModel` and the replay-based loop tests removed; only Gemini answers (D-32). AC4 dropped; AC5–AC10 back to 📝 until the S08 evals re-prove them; AC13's Fake/Live switch replaced by the model menu (D-31). Coverage gate 75% (D-33).
