# S09 · Production readiness

> **Goal:** a busy model doesn't end the run, a crash doesn't lose it, and the Harness pane answers the questions an enterprise reviewer asks.
> **Why it matters:** on the free tier a 429 ended run after run. And "where does it run, what can it touch, what happens if it dies?" should have an answer on screen, honest about what is enforced and what is only convention.

**What a reviewer asks, and where the pane answers it**

| Section | Answers |
|---|---|
| Agentic Loop | When it stops; the output contract (none: plain prose, D-82) |
| **Models** (new) | Which model runs the loop and where it's set; each role's model and effort; the fallback chain |
| Context | What it knows (unchanged) |
| Tools | + the hand-off: what a helper gets, what it doesn't, the guardrails and budget slice it inherits |
| **Environment** (new) | Where tools run; what it can read and write; network; what resets and what persists |
| Guardrails | Unchanged |
| **State & Memory** (renamed) | Run state (conversation file, trace, checkpoint, Resume) apart from long-term memory (notes, files, window) |

**Builds:** model fallback · run checkpoint + Resume · **Claude Haiku 5.5 and Sonnet 5.5 as a second provider** · Models, Environment, State & Memory sections

**Not built, and the pane says so:** network or file sandbox for workspace code (no container in this local project) · per-role effort · an output schema (D-100).

## Done when

| ID | Check | How |
|---|---|---|
| S09-AC1 | A 429/503 on the main model moves the run to the next fallback model at once; the event names both models and the error | 🧪 |
| S09-AC2 | Each call is priced by the model that answered; other errors still fail the run | 🧪 |
| S09-AC3 | Every step writes a checkpoint (steps, cost, time) to the conversation file | 🧪 |
| S09-AC4 | A conversation whose last turn never finished can be resumed; the step count and cost carry on from the checkpoint | 🧪 👀 |
| S09-AC5 | Resume never re-runs a tool call that had no result (it stays "cancelled") | 🧪 |
| S09-AC6 | Harness pane has 7 sections; Models shows every role's model, effort and the fallback chain | 🧪 👀 |
| S09-AC7 | Environment shows where tools run, read/write paths, network, what persists, and says "by convention" / "not restricted" where true | 👀 |
| S09-AC8 | State & Memory separates run state from long-term memory; Tools shows what a helper gets and doesn't | 👀 |
| S09-AC9 | Live: with the main model out of quota, a run finishes on the fallback | 🔑 👀 |
| S09-AC10 | Claude Haiku 5.5 and Sonnet 5.5 are in the model menu when `ANTHROPIC_API_KEY` is set; a run on either works through the same loop, tools, gate and approvals | 🧪 👀 |
| S09-AC11 | The loop's steps translate to Claude's messages and back; Claude's thinking blocks are kept exactly as received; switching provider mid-conversation drops only the other provider's thinking | 🧪 |
| S09-AC12 | The effort menu maps to Claude's `output_config.effort` (Auto sends nothing); each Claude call is priced from `pricing.toml` | 🧪 |
| S09-AC13 | On a Claude run, the helper, off-topic check, titles and summaries use Claude Haiku 5.5 | 🧪 |
| S09-AC14 | No test and no `make live` run calls Anthropic: the key is used only for runs the person starts on the page or with the CLI | 🧪 |

## Key choices

- **Fall back at once, for the rest of the run** (D-97) → no hidden sleeps (D-42 stays) and no flip-flopping between models mid-task. *Cost:* the rest of the run uses the smaller model.
- **Only 429 and 503 fall back** → a bad request or a missing key still fails loudly. *Cost:* other transient errors still end the run.
- **A checkpoint line per step** (D-98) → Resume knows the step count and cost so far; the file stays append-only. *Cost:* one more line per step.
- **Resume continues, it doesn't redo** → a tool call with no result stays "cancelled"; the model decides what to do next. *Cost:* the model may repeat a lookup.
- **Claude through the same boundary** (D-102) → one loop, one gate, one approval channel for both providers; the translation lives in one file. *Cost:* thinking doesn't cross providers.
- **A Claude run's small calls use Haiku** (D-103, your pick) → it works when Gemini is out of quota. *Cost:* a little more per run.
- **The person pays, so nothing automatic uses Claude** (D-104) → offline tests use a recorded stand-in; `make live` stays on Gemini. *Cost:* Claude is checked live only when you run it.
- **Seven sections, honest labels** (D-99) → every reviewer question has one home; "by convention" and "not restricted" say what isn't enforced. *Cost:* a longer pane (all sections start collapsed).

## Explain it back

1. Why fall back for the rest of the run instead of retrying the same model?
2. Why does Resume not re-run a cancelled tool call?
3. What does "by convention" mean for a workspace's Python tools, and what would enforce it?
4. Why is run state kept apart from long-term memory?

## Changes

- 2026-11-10 · Created after your gap review (15 questions on models, environment, state, orchestration). You chose: build fallback + Resume, a 7-section pane, this stage after S08 (D-97–D-100).
- 2026-11-10 · Claude Haiku 5.5 and Sonnet 5.5 added to this stage at your request; background calls on a Claude run use Haiku (your pick). AC10–AC14 (D-102–D-104).
