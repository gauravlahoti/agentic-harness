# How we build: spec first, then code

> Write down what "done" looks like → build it → prove it → you confirm it.

## Map

| File | Answers |
|---|---|
| `Scaffold.md` | What is the production baseline, and why each tool? |
| `spec/00-product.md` | What are we building, and why this way? |
| `spec/01-company.md` | Who is CloudCo, and what is the ShopCo contract story? |
| `spec/02-ui.md` | What does the page look like, and how does it grow? |
| `spec/stages/SNN-*.md` | What does this stage add, and how do we know it works? |
| `Tracker.md` | Where are we? What's waiting on me? |
| `Decisions.md` | Why did we choose X over Y? |
| `docs/stage-N.md` | How does the code from stage N work? (written after each stage) |

## The unit of work: a check

Each stage has numbered checks like `S05-AC4` ("rules files are read-only"). Code, tests and the tracker all point to these IDs, so any line of code traces back to its reason.

| Icon | How a check is proven |
|---|---|
| 🧪 | Automated test |
| 👀 | You watch it work in the browser |
| 📄 | Look at a file |
| 🔑 | Needs your Gemini API key (costs cents) |

## Status

| | Status | Set by |
|---|---|---|
| 📝 | Drafted | AI |
| 🟦 | You approved the plan | You |
| 🟨 | Built: code + passing tests | AI, with evidence |
| ✅ | Verified: you saw it work and can explain it | **Only you** |
| ⛔ | Blocked (reason noted) | AI |

**Built ≠ Verified.** Tests prove the code matches the tests. Verified means *you* understand it.

## Every stage, same 7 steps

1. **Agree** on the stage plan → 🟦
2. **Tests first**, from the checks (guardrail tests before anything)
3. **Build**, explaining each file before and after
4. **Prove**: real test output, failures included → 🟨
5. **Hand over**: walkthrough + decision records
6. **You verify**: run it live, answer 3 questions → ✅
7. **Tag** `stage-N`, save the run for its LinkedIn clip

## Changing the plan

Allowed, never silent: a dated line under the stage's **Changes**, a decision record if a choice changed, and affected checks go back to 📝.
