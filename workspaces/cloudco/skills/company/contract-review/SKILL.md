---
name: contract-review
description: Check each change a customer made to a contract against CloudCo's standard terms, and say who must decide.
---

# Contract review

> Fictional terms, for a demo.

## Steps

1. List every change the customer asked for. Ignore pure wording changes.
   If you can delegate to `clause-reviewer`, hand it the whole markup (give it the contract ID) and work from its findings; otherwise use `review_contract` yourself.
2. For each change, find the matching row below and decide:
   - **OK**: within standard terms, or within what the person you're helping may approve.
   - **Needs a decision**: name who decides (Sales, Finance, Engineering or the CFO) and why.
   - **Never**: say so plainly and propose the best counter-offer CloudCo *can* make.
3. Answer plainly, one short line per change, starting with its clause ID (for example 3.2), including the changes that are OK: what they asked, then OK, who decides, or never with the counter-offer.
4. Cite the policy section next to each line.

## Standard terms at a glance

| Term | Standard | Who can approve more | Never | Policy |
|---|---|---|---|---|
| Contract length | Up to 3 years (Sales) | – | – | `standard-terms §1` |
| Discount | Up to 15% (Sales) | 15–25%: CFO | Above 25% | `standard-terms §2` |
| Payment | Net 30; Net 45 (Sales) | Net 60: Finance | Beyond Net 60 | `standard-terms §3` |
| Uptime | 99.9% | Up to 99.95% (our 12-month record): Engineering | Above 99.95% → counter with 99.95% | `standard-terms §4` |
| Liability cap | 12 months of fees | Up to 24 months: CFO | Unlimited → counter with 24 months | `standard-terms §5` |
| Sending anything to the customer | – | Always a person (Sales approves sending) | Sending without approval | `approval-chart §3` |
