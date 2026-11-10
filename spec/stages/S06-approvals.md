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
| S06-AC1 | Approval rules come from `workspace.toml`: several per tool, each with an approver role and an optional condition; CloudCo's match the approval chart (§1, §3) | 🧪 |
| S06-AC2 | A matching action pauses the loop until a person decides, once for each approval it needs | 🧪 |
| S06-AC3 | The card shows the action's values, the reason, the rule and the approver role, and counts down to the timeout | 🧪 👀 |
| S06-AC4 | Approve → it runs; the result goes back to the model | 🧪 |
| S06-AC5 | Reject → the reason goes back to the model, it adapts, and approvals still to come are not asked | 🧪 |
| S06-AC6 | No answer in time → treated as Reject | 🧪 |
| S06-AC7 | Each card names who must decide ("Approve as CFO") and the answer is recorded with that role. A demo of the mechanism, not a login (D-87) | 🧪 👀 |
| S06-AC8 | Sending anything to a customer always needs the Sales approval, on top of any other | 🧪 |
| S06-AC9 | `ask_human` lets the model pause to ask a question; the answer goes back to it | 🧪 👀 |
| S06-AC10 | The outbox file records who approved (role), when, and which rule asked | 🧪 |
| S06-AC11 | Page: "Waiting for CFO", the card after the answer, and "Nothing ran" after a rejection | 👀 |
| S06-AC12 | Live: 25% discount → CFO rejects ("max 20%") → the agent proposes 20% → CFO approves → Sales approves the send | 🔑 👀 |

## Key choices

- **Rules decide when to ask, not the model** → a high-stakes action can't skip the pause. *Cost:* the chart must be kept current.
- **Several approvals per action, in order** (D-88) → a 25% discount needs the CFO, then Sales to send. *Cost:* a rule's condition is plain numbers, not wording.
- **The approver is a named role, answered by role-play** (D-87) → no logins in this project. *Cost:* anyone at the keyboard can click; the page says so.
- **A rejection is feedback, not a crash** → the agent learns the limit and tries again. *Cost:* one more loop turn.
- **Silence means no** → nothing happens by default. *Cost:* slow approvers stall tasks.
- **`ask_human` reuses the approval channel** (D-89) → one pause mechanism, one card style. *Cost:* the "answer" travels as the note of an approval.

## Explain it back

1. What's the difference between a permission and an approval?
2. Why does a rejection go back to the model instead of ending the run?
3. Why is "no answer" treated as "no"?

## Changes

- 2026-11-10 · Created (v3).
- 2026-11-10 · Human approval for `send_to_customer` moved to S05 at your request (D-79). S06 to be re-briefed with what's left.
- 2026-11-10 · S06 re-briefed and approved ("A looks good"): approvals stay as in S05 and gain approver roles, conditions, an audit trail, `ask_human` and card polish (D-87–D-89). AC7 reworded (no CFO profile, role-play approver); AC12 kept with Sales + CFO roles.
