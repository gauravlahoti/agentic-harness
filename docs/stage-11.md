# Stage 11 · Plan and Verify: a to-do list, and a check before you see the answer

> Guardrails ask "is this allowed?" before a tool runs. Verification asks "is this correct?"
> after the model drafts its answer. The loop had the first; now it has both.

## What you have now

- **A to-do list, when the task needs one.** For a task with 3 or more parts ("review ShopCo's contract, then send a reply"), the agent writes a list with `update_plan` and ticks it off. A light question ("Is Net 60 OK?") gets a direct answer and no list. **The model decides**; the harness only holds it to the list.
- **A check before every answer.** The harness runs CloudCo's four checks plus its own "Plan Complete" on the draft. A failure goes back to the agent **once**, with the reasons. If it fails again, you still get the answer, marked **Not Verified**.
- **On the page.** The Harness pane has a **Plan & Verify** section: the plan tool and each check, each with a switch. A run's Activity shows a live **To-Do** card and a **Checks** card, with the first draft folded away when it was sent back. Old conversations show both.

## How one task goes

```
model replies
  tool calls (update_plan may ride along)  → run them, loop
  an answer (the draft)                     → VERIFY:
      run every check on (draft, this run's tool calls, the plan)
      all pass (or none apply)  → finish
      a failure, 1 retry left   → "[Harness check] Your answer did not pass…" → loop
      a failure, none left      → finish, marked Not Verified
```

## The files

| File | What it does | Harness part |
|---|---|---|
| `src/agentic_harness/planning.py` | `update_plan`: one tool that rewrites the whole list; checks items (a skip needs a note); shows the list back; rebuilds it from saved steps | Loop |
| `src/agentic_harness/verify.py` | What a check is (`@check`), the `Record` it reads, the built-in Plan Complete, running checks, the note sent back, loading a workspace's `checks.py` | Loop |
| `src/agentic_harness/loop.py` | Intercepts `update_plan` (like `ask_human`); keeps every tool call of the run (helpers' too); the VERIFY step | Loop |
| `src/agentic_harness/trimming.py` | Never stubs the newest plan | Context |
| `workspaces/cloudco/checks.py` | CloudCo's four checks | Workspace, not harness |

## Key lines, in simple words

- `run.record(self.profile)`: a snapshot of every tool call this run (name, arguments, output, error, which agent). `_Run.emit` fills it as events pass, so a helper's calls are in it too: they are forwarded through the same `emit`.
- `retrying = bool(failures) and rounds <= self.retries`: one retry, then stop. Never a loop.
- `Result.status == "error"`: a check that crashes is shown, never sent back. A bug in a check must not make the agent rewrite a good answer.
- `matters(edit)` in CloudCo's checks: an edit matters when its numbers change, or a sentence is added or removed. Of ShopCo's 61 edits that leaves 6 (2.1, 3.2, 4.1, 6.1, 9.2, B.7); "shall" → "will" doesn't count.
- `right_approver` reads `[[approvals]]` and `[[rules]]` from `workspace.toml`, the same tables the gate uses. One source of truth for who decides.

## Where things live

| What | Where |
|---|---|
| The plan, while running | run state (`_Run.plan`), `plan_updated` events |
| The plan, after | the conversation file, as ordinary `update_plan` steps; the turn record keeps the last list for the page |
| Check results | `verify_finished` events, `run_finished.checks`, the turn record |
| The checks themselves | the workspace's `checks.py`, named in `[verify]` |

## Verify it yourself

1. `make check`: everything passes.
2. Open http://127.0.0.1:8000 → Harness pane → **Plan & Verify**: the plan tool and 5 checks, each with a switch.
3. Ask (Sales): *"ShopCo asks for Net 45 payment terms. Is that OK?"* → no To-Do card; a Checks card only if a check applies.
4. Ask: *"Review ShopCo's contract changes, then send ShopCo (CUS-0042) a short reply saying we'll come back with a counter-offer this week."* → a To-Do card that ticks off, a Sales approval card, then a Checks card.
5. Switch off **Right Approver**, ask again: it isn't in the Checks card.

## Explain it back

1. Why does the harness, not the model, enforce "no open items"?
2. Why pin the plan in trimming instead of adding it to the prompt each turn?
3. Why are CloudCo's checks plain code, and what would a model-based check add?
4. Verification vs. guardrails: which question does each answer?
