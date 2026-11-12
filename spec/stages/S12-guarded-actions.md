# S12 · Guarded actions and identity

> **Goal:** an action is checked before it happens, and its guardrails are visible: hard limits, a check of the email itself, and approvals that only the right person can give.
> **Why it matters:** external feedback on the S11 run. The email went out before anything checked it (the checks read only the final answer), the hard limits were invisible, and one person approved as Sales, Engineering and the CFO.

## Part A · Check the action before it happens

**A1 · Action checks (harness, domain-free).** A workspace can attach a check to a tool: `@action_check("send_to_customer", "Body Matches Terms", "…")`, `fn(arguments, record) → passed / failed / skipped`. In `_run_tool` the order becomes:
```
① profile allows?  ② hard limits (never rules)  ③ action checks  ④ people approve  ⑤ run
```
- A failure stops the call before anyone is asked: the tool returns "Not sent: <reasons>. Fix it and call again." as an error the model reads. One fix, like answer checks.
- Events: `action_checked` (each check's result). The pane's Verification section lists action checks under "Before an action".

**A2 · CloudCo's "Body Matches Terms"** (`workspaces/cloudco/checks.py`): every term in the arguments (15%, Net 45, 99.9%, 12 months) is stated in the body, and the body offers no other value for the same term. A refusal in the body ("we can't accept 99.99%") doesn't count as an offer; that reuses the claims and hold-back words from Right Approver. Tested on the real emails in `outbox/`.
- "Every term within the approver's authority" needs no new check: the gate already routes each term to its approver (approval-chart §1).

**A3 · Hard limits shown.** `Gate.limits(tool, args)` returns each never-rule with the value and the line. Event `limits_checked`, then a GUARD step before the approval card: *"Hard limits held · discount 15 ≤ 25 · Net 45 ≤ 60 · uptime 99.9 ≤ 99.95 · liability capped"*. On a block, the same step in red, naming the rule.

**A4 · The email at its send step.** The email card moves into the run's activity, directly under its send step, after its hard limits, action checks and approvals. It no longer floats below the answer. The run reads in order:
`limits held → body checked → Sales ✓ Engineering ✓ CFO ✓ → ✉ Sent → … → Checks card → answer`.

**A5 · Injection response stated.** *"⚠ Flagged · review_contract returned text that tries to instruct the AI → fenced as data for the model; any action it asks for still needs a person."* No claim that the model ignored it: the harness can't promise that.

**A6 · Memory shown.** A step after "Loaded context": *"Read 2 facts from long-term memory (Sales)"*, opening to the facts. A `save_note` call reads *"Saved a fact to long-term memory"*.

## Part B · Identity: an approval comes from its role
- **Personas** in `workspace.toml` (made-up people): `[[people]]` name + role, e.g. Priya (Sales), Dana (CFO), Farid (Finance), Elena (Engineering). The harness reads them; nothing domain-specific goes in `src/`.
- **"You are" picker** at the top of the sidebar (remembered per browser). The person running the chat is who they picked.
- **The server enforces it.** An approval answer carries the persona; the server refuses it unless that persona's role matches the card's approver. The page can't bypass that.
- **The card:** *"Needs the CFO · You are Priya (Sales): you can't approve this one."* with **Switch to Dana (CFO)**. The run keeps waiting while you switch: the thread stays, and the profile doesn't change. The approval timeout grows from 10 to 30 minutes so a hand-off fits.
- **Self-approval:** allowed only where the rule says so. CloudCo's "Any message to a customer" (Sales) is the sender's own sign-off, and the feedback agrees that's fine. The CFO, Finance and Engineering rules need that person.
- **The record:** the outbox and the trace keep *who* (Dana, CFO), not just the role.
- **Pane:** an **Identity** row: "You are Priya (Sales) · approvals are checked on the server against your role · personas are role-played; no logins".
- **Demo scenario:** "Send ShopCo a 25% discount offer": Priya can't approve the CFO card; switching to Dana can.

## Choices (D-134 to D-139)
| # | Choice | Chosen | Why | Cost |
|---|---|---|---|---|
| D-134 | Where action checks live | Workspace code attached to a tool; the harness runs them between the hard limits and the people | The body is CloudCo's business; the hook is generic | A failed check costs a model call |
| D-135 | Hard limits visible | One GUARD step per action, passes included | A reviewer must *see* the limits held, not infer it | One more line per send |
| D-136 | Where the email shows | Inline, under its send step | The order of events stays true | — |
| D-137 | Identity | Personas, enforced on the server | Separation of duties you can demo; the page can't fake it | Not real authentication (said in the pane) |
| D-138 | Self-approval | Only for the sender's own "any message" sign-off | Matches the feedback; the specialists must be someone else | One more config flag |
| D-139 | Approval timeout | 30 minutes | Time to switch persona and decide | A stuck run waits longer (Stop still works) |

## Done when (S12)
| ID | Check | How |
|---|---|---|
| AC1 | An action check runs after the hard limits and before anyone is asked; a failure returns "Not sent: …" and no one is asked | 🧪 |
| AC2 | Body Matches Terms passes the real outbox emails and fails a body saying 20% when the argument says 15%; a refusal in the body isn't an offer | 🧪 |
| AC3 | A hard-limits step shows each rule with its value and line, before the approval card | 🧪 👀 |
| AC4 | The email card appears under its send step, in run order | 👀 |
| AC5 | The injection step names the response; the memory step lists the facts read | 🧪 👀 |
| AC6 | Personas from `workspace.toml`; the server refuses an approval from the wrong role | 🧪 |
| AC7 | The card offers "Switch to <persona>"; the run keeps waiting; the thread stays | 👀 |
| AC8 | The sender can give the "any message" sign-off; the CFO card needs the CFO | 🧪 |
| AC9 | The outbox and trace record the person and the role | 🧪 |
| AC10 | Live: a 25% discount send waits for Dana (CFO); Priya can't approve it | 🔑 👀 |

## Changes
- 2026-11-12 · Part B built as planned, except D-138: no per-rule "sender may" flag; a person's role must equal the card's role, which already lets Sales give the "send" sign-off.
