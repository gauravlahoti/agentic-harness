# S06 · Approvals

> **Goal:** high-stakes actions pause the loop until the right human decides.
> **Why it matters:** some actions are allowed, but not without a person. The harness makes that pause impossible to skip.

**How an interrupt works**

```
model asks to act → gate: allowed → approval rule matches? ── no ──→ run
                                          │ yes
                                          ▼
                      ⏸ loop pauses · card shown · waits for the right person
                         Approve → run → result back to model
                         Reject  → reason back to model → it adapts
                         No reply in time → treated as Reject
```

**The approval card**

```
⏸ APPROVAL NEEDED · accept_change
  Discount 25% on CT-2207 (ShopCo renewal)
  Why:      ShopCo asked in redline §3.2
  Rule:     discount 15–25% → CFO (standard terms §2)
  Approver: CFO
            [ Approve ]   [ Reject with reason… ]
```

**Two kinds of interrupt**
- **The harness forces it:** a rule in `[[approvals]]` matches. This is control.
- **The model chooses it:** it calls `ask_human` when it's unsure. This is humility.

**Builds:** `src/agentic_harness/approvals.py` · `ask_human` · `[[approvals]]` for CloudCo · approval cards · approver check

## Done when

| ID | Check | How |
|---|---|---|
| S06-AC1 | Approval rules come from `workspace.toml` and match CloudCo's approval chart | 🧪 |
| S06-AC2 | A matching action pauses the loop until a human decides | 🧪 |
| S06-AC3 | The card shows the action, values, reason, evidence IDs, rule and approver | 🧪 👀 |
| S06-AC4 | Approve → it runs; the result goes back to the model | 🧪 |
| S06-AC5 | Reject → the reason goes back to the model, and it adapts | 🧪 |
| S06-AC6 | No answer in time → treated as Reject | 🧪 |
| S06-AC7 | Only someone with the authority can approve (CFO items need the CFO profile) | 🧪 |
| S06-AC8 | Sending anything to a customer always needs approval | 🧪 |
| S06-AC9 | `ask_human` lets the model pause to ask a question | 🧪 |
| S06-AC10 | The outbox records who approved what, and when | 🧪 |
| S06-AC11 | Page: approval cards, "Waiting for CFO", "nothing was sent" | 👀 |
| S06-AC12 | Live: the CFO rejects 25% ("max 20%") → the agent proposes 20% → approved → the reply is sent after Sales approves | 🔑 👀 |

## Key choices

- **Rules decide when to ask, not the model** → a high-stakes action can't skip the pause. *Cost:* the chart must be kept current.
- **A rejection is feedback, not a crash** → the agent learns the limit and tries again. *Cost:* one more loop turn.
- **Silence means no** → nothing happens by default. *Cost:* slow approvers stall tasks.
- **The approver must have the authority** → a Sales click can't approve a CFO item. *Cost:* switching profiles in the demo.
- **The pause is an `asyncio.Future` the click resolves** → the loop code reads like a normal function call. *Cost:* a server restart cancels pending approvals.

## Without it / with it

- ❌ Approvals off (red banner) → the 25% discount is accepted and the reply goes straight to ShopCo.
- ✅ On → ⏸ CFO card → rejected "max 20%" → the agent adapts → approved → sent only after Sales approves sending.

## Explain it back

1. What's the difference between a permission and an approval?
2. Why does a rejection go back to the model instead of ending the run?
3. Why is "no answer" treated as "no"?

## Changes

- 2026-11-10 · Created (v3).
