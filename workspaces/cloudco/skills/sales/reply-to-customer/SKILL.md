---
name: reply-to-customer
description: Draft a reply to a customer's contract changes, and send it when the person asks (a person approves every send).
---

# Reply to a customer

> Fictional, for a demo.

## Steps

1. Start from the contract review: what is OK, what needs a decision, what is never possible.
2. Draft a short, friendly reply:
   - thank them and confirm what CloudCo can accept;
   - for each "never", offer the counter-proposal (for example a 24-month liability cap instead of unlimited);
   - for each item still waiting for a decision, say we will come back on it. Never promise an outcome.
3. If the person asked you to send it, call `send_to_customer` with every offered term filled in (discount, payment days, uptime, liability). The harness asks the right people to approve before anything goes (`approval-chart §3`). Otherwise show the draft and stop.
4. Cite the policy section behind each counter-proposal.
