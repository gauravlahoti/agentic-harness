# Stage 6 · Approvals: the right person decides

> Some actions are allowed, but not without a person. The harness makes that pause impossible
> to skip, says who must decide, and writes down who did.

## What you have now

- **Several approvals per action.** CloudCo's chart (§1, §3) is in `workspace.toml`. A 20% discount asks the **CFO**, then **Sales**. A Net 60 offer asks **Finance**, then Sales. A plain message asks only Sales. Hard limits still block first and can't be approved.
- **A card for each approval.** It names who must decide ("Needs CFO · 1 of 2"), the rule, the values, a countdown to the time-out, a reason box, and **Approve as CFO** / **Reject**. After a rejection it says "Nothing ran. The agent has been told why."
- **Rejection is feedback.** The reason goes back to the model, later approvals are not asked, and the agent can try again with less.
- **`ask_human`.** The agent can pause and ask you a question ("Which customer?") in a card with a text box. Your answer goes back as the tool's result. Skip it and the agent is told you didn't answer.
- **An audit trail.** The outbox file ends with `Approved by:` and one line per approver: role, time, rule.
- **No logins.** You play each role by clicking. The card says so ("Demo: you are acting as CFO"). It teaches *who must decide* and *who did*, not security (D-87).

## How one send goes

```
model asks to send a 20% offer
  ① allowed for Sales?                      yes
  ② a hard limit (above 25%)?               no
  ③ approvals that match, in order:
       Discount over 15%   → CFO            ⏸ card 1 of 2 → Approve as CFO
       Any message         → Sales          ⏸ card 2 of 2 → Approve as Sales
  tool runs → outbox file lists both approvals
  (a rejection at any card stops here: the reason goes back to the model)
```

## The files

| File | Job | Key lines |
|---|---|---|
| `gate.py` | Which approvals match | `Approval` has `approver`, `label`, and an optional condition (`arg` + `above` / `equals`); `check()` returns all that match, in order |
| `loop.py` | Asks them one by one | `_run_tool` loops over `decision.approvals`; `_pause` emits `approval_requested` / `approval_decided` and keeps the wait out of the time limit; `_question` serves `ask_human` |
| `approvals.py` | The `ask_human` tool | Its description tells the model when *not* to use it |
| `workspace.py` | Reads the rules | `[[approvals]]` with `approver`, `label`, `arg`, `above`; `ask_human = true` |
| `tools/__init__.py` | `ToolContext.approvals` | A tool can write down who approved |
| `workspaces/cloudco/workspace.toml` | CloudCo's chart | 5 approvals; specialists first, Sales last |
| `workspaces/cloudco/tools.py` | Audit lines | `send_to_customer` writes `Approved by:` |
| `web/app.js` | The cards | `approvalCard`: role, step, countdown, reason box, question box |

## Honest limits

- Not real authentication: anyone at the keyboard can click as any role (D-87).
- A restart of the server cancels pending approvals.
- Not run live yet when this was written: the Gemini free-tier quota was spent. The loop is tested offline with people played by functions; `tests/live/test_live_approvals.py` holds the real-model checks (AC9, AC12).

## Verify it yourself

1. `make check` → all green (243 passed).
2. Open **Harness → Guardrails** as Sales: **Human in the loop** lists five rules, each `rule → role`.
3. As Sales: "Send ShopCo (CUS-0042) a short note offering a 20% discount. Send it now." Expect card **1 of 2 · Needs CFO**. Type "max 15%" in the reason box and **Reject**: the agent is told, and nothing is sent.
4. Ask again; this time **Approve as CFO**, then **Approve as Sales** on card 2. Open the new file in `workspaces/cloudco/outbox/`: the end lists CFO and Sales with the time.
5. As Sales: "Pull in the customer details." The agent should ask which customer. Answer "ShopCo".
6. When the quota is back: `make live` runs `test_live_approvals.py`.

## Explain it back

1. What's the difference between a permission and an approval?
2. Why does a rejection go back to the model instead of ending the run?
3. Why is "no answer" treated as "no"?
4. Why isn't "Approve as CFO" real security, and what would be?
