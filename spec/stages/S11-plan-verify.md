# S11 · Plan and Verify

> **Goal:** on a task with several parts, the agent keeps a to-do list and can't finish with items open; before you see an answer, the harness checks it and sends failures back once.
> **Why it matters:** the loop had no "is this correct?" step. Failures we have already seen (missing clause IDs, S04-AC10; "still needs approval" after everyone approved, D-120; the wrong approver) reach the person unchecked. Guardrails ask "is this allowed?"; verification asks "is this correct?".

**Builds:** the `update_plan` tool and its stop rule · a VERIFY step in the loop · CloudCo's four code checks (`workspaces/cloudco/checks.py`) · a **Plan & Verify** pane section · live **To-Do** and **Checks** cards in the chat · 3 eval cases.

**Not built:** a model-based check (a judge reading the draft against the tool results): code checks first (D-126). Helpers don't plan.

## How it works

```
steps = [user_input(task)]
while no limit is exceeded:
    reply = model.create(system, steps, tools)     # may call update_plan with other tools
    if reply has tool calls: run them; continue
    # the model drafted an answer: VERIFY
    failures = run the checks on (answer, this run's tool calls, the plan)
               # "Plan Complete" (the stop rule) is one of them
    if failures and retries left:  send the failures back as a [Harness check] note; continue
    finish(answer, checks)         # a second failure → "Not verified"
```

- **Where the plan lives:** in run state while running (`plan_updated` events), and as ordinary steps (`update_plan` call + result) in the conversation file. Resume, replay, the trace and evals get it for free. Not in long-term memory: a plan belongs to one task.
- **Who decides to plan:** the model, from the tool's description ("for tasks with 3 or more distinct parts"). The harness only enforces the stop rule once a plan exists.
- **Keeping the plan in view:** trimming never stubs the newest `update_plan` result. The system prompt stays fixed (prompt caching, S02-AC8).
- **The harness knows no domain:** it runs whatever checks the workspace's `checks.py` defines, plus one of its own: "plan complete".

## CloudCo's checks (made up, like all CloudCo data)

| Check | Passes when |
|---|---|
| Every Change Covered | each clause ID in `review_contract` / the clause-reviewer's result appears in the answer |
| Citations Exist | each `standard-terms §N` / `approval-chart §N` in the answer appears in a tool result this run |
| Right Approver | a line with a discount %, Net N, uptime % or liability months names the decider that `[[approvals]]` / `[[rules]]` give |
| No False "Sent" | the answer says sent only if a `send_to_customer` call succeeded this run |

## Page

- **Harness pane:** a **Plans** row in Agentic Loop; `update_plan` under **Tools → Harness Tools** (with its switch); a **Verification** section after Guardrails: each check with an on/off switch, retries: 1.
- **Chat:** a live **To-Do** card in Activity that ticks off; a **Checks** card before the answer ("4/4 Passed", "1 Failed → Retried → Passed" with the first draft folded, or "Not Verified: …"). Old conversations rebuild both from the saved steps.

## Done when

| ID | Check | How |
|---|---|---|
| S11-AC1 | `update_plan` stores the list in run state and emits `plan_updated`; helpers don't get it | 🧪 |
| S11-AC2 | The plan is saved as steps; Resume and replay rebuild it | 🧪 |
| S11-AC3 | Trimming never stubs the newest plan result | 🧪 |
| S11-AC4 | An answer with open items gets one reminder; the second time it finishes, the plan shown incomplete | 🧪 |
| S11-AC5 | Skipped needs a note, or the tool returns an error | 🧪 |
| S11-AC6 | VERIFY runs the workspace's checks after the draft, before `run_finished` | 🧪 |
| S11-AC7 | A failed check sends the failures back once; a second failure → the answer plus "Not verified" | 🧪 |
| S11-AC8 | CloudCo's four checks, each with a pass and a fail case | 🧪 |
| S11-AC9 | `src/agentic_harness/` stays domain-free (existing test) | 🧪 |
| S11-AC10 | Pane: Plans row, `update_plan` under Harness Tools, Verification section with check switches; a switched-off check doesn't run | 🧪 👀 |
| S11-AC11 | Chat: live To-Do card and Checks card; old conversations show both | 👀 |
| S11-AC12 | Live: "Is Net 60 OK?" makes no plan; "review ShopCo's contract and send it" plans and finishes every item | 🔑 👀 |

Evals: golden set 16 → 19: `light-question-no-plan`, `review-and-send-plans`, `wrong-approver-caught` (offline stand-in: the draft says Finance approves 25% → Right Approver fails → the retry names the CFO; the demo).

## Key choices (D-121–D-128)

- **The model decides when to plan** (D-121) → no extra call. *Cost:* a small model may plan when it needn't; evals catch it.
- **One tool that rewrites the whole list** (D-122) → one thing to explain; status changes ride along with real tool calls. *Cost:* the list is resent each time.
- **Pin the newest plan in trimming** (D-123) → the prompt stays fixed. *Cost:* the plan sits where it was written, not at the end.
- **One reminder, then finish** (D-124) → never loops; a skip needs a reason. *Cost:* a stubborn model finishes with open items (shown).
- **Checks live in the workspace** (D-125) → the harness stays domain-free. *Cost:* each workspace writes its own.
- **Code checks only, for now** (D-126) → free, exact, never flaky. *Cost:* free-text claims aren't checked.
- **One retry, then show the failure** (D-127) → you always get an answer, and know when to doubt it. *Cost:* one more round on a failure.
- **Pane and chat** (D-128) → the pane says what the harness will do; the chat shows what it did. *Cost:* one more pane section.

## Explain it back

1. Why does the harness, not the model, enforce the stop rule?
2. Why pin the plan in trimming instead of adding it to the prompt each turn?
3. Why are CloudCo's checks plain code, and what would a model-based check add?
4. Verification vs. guardrails: which question does each answer?

## Changes

- 2026-11-12 · Built: the stop rule and VERIFY are one mechanism. "Plan Complete" is a check, so the one reminder is that check's one retry; same behaviour (D-124), one thing to explain instead of two.
- 2026-11-12 · Built: the note sent back is a normal `user_input` step whose text starts with `[Harness check]`, not a mark outside the step (D-127 updated). Simpler, and the model can see the harness is speaking; the scope check skips it.
- 2026-11-12 · Built: No False "Sent" also fails when a send worked but the answer doesn't say so (the D-120 bug).
- 2026-11-12 · Your review: Plan and Verify split by when they happen (D-128 changed). Plans row in Agentic Loop; `update_plan` and the harness's other own tools listed under Tools → Harness Tools; Verification its own section after Guardrails. AC10 reworded; re-checked in Chrome.
- 2026-11-12 · Golden set 16 → 18, not 19: `wrong-approver-caught` is an offline test (`test_s11_ac7_wrong_approver_is_caught_and_corrected`), because a live agent can't be made to get it wrong on cue.
