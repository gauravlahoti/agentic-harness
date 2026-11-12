---
name: technical-review
description: Review the technical clauses of a customer's contract (service levels, support, data protection, security) and say what Engineering can approve. Only when asked to review or check; not for just showing a contract.
---

# Technical review

> Fictional terms, for a demo.

Engineering reviews the technical side of a contract. Prices, payment, term, liability and sending are Sales' job: you don't see them, and you don't comment on them.

## Steps

1. Get the contract ID from the customer's record (`lookup_customer_record`).
2. Give `clause-reviewer` just that ID. You will get back only the technical clauses: services, service levels, support, data protection, and the service and security appendices.
3. For each change that matters, say in one short line: the clause ID, what they asked, and one of:
   - **OK**: within our standard (`standard-terms §4`).
   - **Engineering can approve**: uptime above 99.9%, up to our 12-month record of 99.95% (`approval-chart §1`). Check the record with `lookup_customer_record(record="uptime")`.
   - **Never**: more uptime than we have delivered. Counter with 99.95%.
4. End with one line: "Commercial and legal clauses are for Sales."
