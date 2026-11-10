# S07 · Memory

> **Goal:** the agent remembers across turns, restarts and days, and forgets on purpose when its context gets full.
> **Why it matters:** every API call starts from zero. Memory is something the harness adds, and so is smart forgetting.

**Three kinds of memory**

| Kind | Lives in | Lasts | CloudCo example |
|---|---|---|---|
| **Task history** | `.agentic-harness/sessions/<task>.jsonl` | Until deleted; resumable | Round 1 of the ShopCo review |
| **Notes** | `.agentic-harness/notes/<profile>.md`, via `save_note` | Across tasks | "CFO capped ShopCo at 20%. Finance rejected Net 60 (late payer)." |
| **Memory files** | `AGENTS.md` + team file (from S2) | While the file exists | "Never agree to terms." |

**Forgetting on purpose (context trimming), cheapest first**

| # | Technique | When | Extra model call? |
|---|---|---|---|
| 1 | **Trim** big output: keep start + end + "how to see more" | Output over ~10,000 chars | No |
| 2 | **Prune** old tool results to a one-line stub | Past 50% of the working window, in batches | No |
| 3 | **Summarize** older turns | Still past 70% after pruning | Yes, one |

Model steps are never edited (thought signatures). A call never loses its result. The start of the prompt never changes, so Gemini keeps caching it.

**Builds:** `src/agentic_harness/memory.py` · `trimming.py` · `save_note` · "Your work" sidebar · context fill bar

## Done when

| ID | Check | How |
|---|---|---|
| S07-AC1 | Each task is saved as an append-only file; model steps are saved exactly | 🧪 |
| S07-AC2 | The sidebar lists the profile's conversations, newest first, each titled by its topic: open, continue, delete | 🧪 👀 |
| S07-AC3 | After a server restart the task resumes; an unfinished tool call is marked cancelled, not re-run | 🧪 |
| S07-AC4 | `save_note` keeps notes per profile; they enter the prompt next time (capped at ~2,000 tokens) | 🧪 |
| S07-AC5 | Big tool output → start + end + marker | 🧪 |
| S07-AC6 | Old tool results → one-line stubs, in batches past 50% | 🧪 |
| S07-AC7 | Summarize only if still past 70% after pruning | 🧪 |
| S07-AC8 | Model steps are never edited; a call never loses its result | 🧪 |
| S07-AC9 | Page: context fill bar, trimming card, cached tokens shown | 👀 |
| S07-AC10 | Live: in round 2 the agent recalls round 1's decisions | 🔑 👀 |
| S07-AC11 | A conversation gets a short topic title from a small model call; if that fails, the first words of the task | 🧪 🔑 |

## Key choices

- **Append-only task files** → a crash loses at most one line; readable with `cat`. *Cost:* a summary means a new file.
- **Notes only through `save_note`** → you can see every note it keeps. *Cost:* it forgets what it didn't save.
- **Prune before summarizing** → free, and nothing is invented. *Cost:* shrinks less.
- **Conversations are listed by topic** (D-91) → "ShopCo discount and liability" beats "What did ShopCo change…". *Cost:* one tiny Flash-Lite call per conversation.
- **Notes are read once, at the start of a task** (D-92) → the prompt stays identical for the whole task and keeps caching. *Cost:* a note shows up from the next task.
- **A small working window** (configurable, well below Gemini's 1M) → cost and quality drop long before 1M, and the demo can show trimming. *Cost:* trims earlier than strictly needed.

## Without it / with it

- ❌ Memory off → round 2 starts from zero; the agent proposes Net 60 again.
- ✅ On → *"Finance rejected Net 60 yesterday (late payments). The CFO's limit was 20%. Propose Net 45."*

## Explain it back

1. What's the difference between task history and notes?
2. Why prune before summarizing?
3. Why must model steps never be edited on Gemini?

## Changes

- 2026-11-10 · Created (v3).
- 2026-11-10 · Brief approved ("go ahead and build") with your addition: conversations appear in the left pane, titled by topic. AC2 reworded, AC11 added (D-90–D-95).
