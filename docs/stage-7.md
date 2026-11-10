# Stage 7 · Memory: remember, and forget on purpose

> Every API call starts from zero. Memory is something the harness adds, and so is smart
> forgetting.

## What you have now

- **Conversations.** Ask a follow-up and the agent remembers the earlier tasks. Each conversation is one file of exact steps in `.agentic-harness/sessions/`, so it survives a restart.
- **Your work (left pane).** This profile's conversations, newest first, each **titled by its topic** ("ShopCo discount and liability"). Open one to carry on, **New** for a fresh one, **×** then **Delete?** to remove one. The title comes from one tiny Flash-Lite call; if that fails it is the first words of your question.
- **Two kinds of memory.** Short-term: the conversation, resent with each task. Long-term: facts the agent keeps with `save_note` ("The CFO capped ShopCo at 20%"), per profile, in its instructions from the next task on. The left lane's **Memory** page lists every profile's facts, with **Forget**.
- **Forgetting on purpose**, cheapest first, inside a small working window (20,000 tokens for CloudCo):
  1. a tool result over 10,000 characters keeps its start and end, with a marker;
  2. past 50% of the window, old tool results become one-line stubs (the newest two stay whole);
  3. still past 70% after that: one small model call summarizes older tasks.
- **You can see it.** A "Trimmed context" line in the activity list, a **Context 8,200 / 20,000 (41%)** bar and **Cached** tokens in the run summary.
- **A line under the agent's name** saying what it does (`description` in `workspace.toml`).

## What forgetting never does

The model's own steps (its thoughts, tool calls and answers) are never edited or removed, because Gemini needs the thought signatures back exactly. A tool call never loses its result. Only whole earlier tasks are summarized, never the one in progress. The saved file keeps everything; only what is *sent* shrinks.

## How a follow-up goes

```
you ask a follow-up
  load the conversation file (a tool call with no result gets "cancelled", never re-run)
  fit: measured fill < 50%   → send as is
       ≥ 50%                 → stub old tool results
       still ≥ 70% (estimate)→ summarize older tasks (one small call)
  send the history + your question → the model answers
  every step is appended to the file as it happens
```

## The files

| File | Job |
|---|---|
| `memory.py` | Sessions (append-only files, titles, cancelled repair) and notes (`save_note`, caps) |
| `trimming.py` | `cut_output`, `prune`, `fit` (the order of the three), the summarizer |
| `loop.py` | `run(history=, record=)`; calls `fit` before each model call; reports `context_trimmed` |
| `server/app.py` | `/api/sessions` (list, open, delete); `/api/run` continues a conversation and titles a new one |
| `workspace.toml` | `[trimming]` (window and lines), `[conversations]` (title model), `notes = true`, `description` |
| `web/app.js` | Your work, past turns, the trimming card, the Context bar |

## Honest limits

- Not run on real Gemini yet when this was written (the free-tier quota was spent). The loop, trimming and storage are tested offline with a scripted model; `tests/live/test_live_memory.py` holds the real checks (AC10, AC11).
- The 50% / 70% lines are my choice; they are tunable in `workspace.toml`.
- After pruning, the fill is an estimate (characters ÷ 4); the measured count comes with the next reply.
- Opening a past conversation shows each task's question and answer, not its activity lines (those are in the trace).

## Verify it yourself

1. `make check` → all green (284 passed).
2. Reload. Under the agent's name: a one-line description. Under it, **Your work**.
3. Ask: "What did ShopCo change in CT-2207?" then, in the same thread: "And which of those need the CFO?" The second answer should use the first. A conversation appears in the left pane with a topic title.
4. Click **New**, then click the conversation: its tasks come back. Restart the server (`Ctrl-C`, then serve again) and open it again: still there.
5. **Harness → Context → Context management**: the window and its two lines. **Harness → Memory**: short-term and long-term. Left lane **Memory**: Sales and Engineering facts side by side.
6. Ask the agent to "remember that the CFO capped ShopCo at 20%". Check **Memory → Notes**; start **New** and ask what the CFO capped.
7. Run many tool-heavy questions in one conversation until the **Context** bar passes 50%: a "Trimmed context" line appears.
8. When the quota is back: `make live` runs `test_live_memory.py`.

## Explain it back

1. What's the difference between task history and notes?
2. Why prune before summarizing?
3. Why must model steps never be edited on Gemini?
4. Why are notes added only when a task starts?
