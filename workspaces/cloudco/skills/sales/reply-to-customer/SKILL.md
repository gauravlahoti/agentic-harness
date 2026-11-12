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
3. "Send the contract" means send this reply with the counter-offer, never the customer's markup. If the person asked you to send it, call `send_to_customer` with every offered term filled in (discount, payment days, uptime, liability), even when a term needs someone's approval (for example a discount the CFO decides). Don't hold it back yourself: the harness asks the right people to approve before anything goes, and tells you their answer (`approval-chart §3`). If they reject, say so and that nothing was sent. If the person didn't ask to send, show the draft and stop.
4. Cite the policy section behind each counter-proposal.
