---
name: reply-to-customer
description: Draft a reply to a customer's contract changes once the person has agreed the positions, and send it when they say so (a person approves every send).
---

# Reply to a customer

> Fictional, for a demo.

## Steps

1. Start from the contract review and what the person agreed. If you haven't raised the concerns with them yet, do that first and stop (teams file: concerns first).
2. Get the contact from the customer record (`lookup_customer_record`). Draft a short, friendly reply with `draft_reply`: "Hi <contact's first name>,". End with a sign-off on its own lines: "Best regards," then the person's full name, then "CloudCo Sales", each on a new line. Never use a placeholder like [name].
   - thank them and confirm what CloudCo can accept;
   - for each "never", offer the counter-proposal that needs the fewest approvers the policy allows (a 12-month liability cap, which Sales may offer, before a 24-month one, which needs the CFO); name the bigger option only if the person asks for it;
   - for each item still waiting for a decision, say we will come back on it. Never promise an outcome.
3. After drafting, don't repeat the draft: the page shows it. Say in one line what it offers, then ask "Send it to <contact's first name>?" and stop.
4. "Send the contract" means send this reply with the counter-offer, never the customer's markup. Once the person confirms, call `send_to_customer` with every offered term filled in (discount, payment days, uptime, liability: a term left out isn't sent to its approver), even when a term needs someone's approval (for example a discount the CFO decides). Don't hold it back yourself: the harness asks the right people to approve before anything goes, and tells you their answer (`approval-chart §3`). If they reject, say so and that nothing was sent.
5. Cite the policy section behind each counter-proposal.
