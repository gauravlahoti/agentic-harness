# S13 · Guided Tour

> **Goal:** a public, voice-led tour of the harness on gauravlahoti.dev: real recorded runs replay in the real page, step by step, with your voice and captions explaining each harness part.
> **Why it matters:** people can watch the harness work without a key, a backend or a cost per visitor. It's the "Replay" proof S08 planned (S08-AC2, S08-AC9), now with a guide.
> **Scope:** harness engineering only. The tour covers Loop, Context, Tools, Guardrails, Verification and Memory. Observability and every pane stay on the page; the tour just doesn't cover them (your call, D-179).

## What we'll have at the end
- `uv run agentic-harness export-tour --workspace workspaces/cloudco --out dist/tour` builds one folder of static files.
- Open it anywhere (a subdomain, a path, or `python -m http.server`) and press **Start Tour**:
  - The real page replays a recorded CloudCo run.
  - Each step plays your clip, shows its caption, and opens and highlights the Harness pane section it talks about.
  - When the clip ends, the next step starts. **Pause**, **Back**, **Next** and **Mute** are always there.
- No model calls, no `/api/` calls and no key in any file.

## How it works
```
workspaces/cloudco/tour/           ← the content (domain): script, recorded runs, your clips
  tour.toml                          steps: which events to play, what to open, what to say
  runs/<name>.jsonl                  copied from .agentic-harness/traces/
  audio/NN-<id>.m4a                  your voice, one clip per step (optional at first)

src/agentic_harness/export.py      ← general: tour.toml + runs + page → dist/tour/
src/agentic_harness/web/tour.js    ← general: plays events through the page's own onEvent()
```
- **Replay uses the live code.** The page already draws a run from a list of events (`onEvent`). Every run is already saved as exactly that list, with secrets masked. The player feeds a step's events in on a timer, so the tour shows the same cards a live run does.
- **What the player adds itself:**
  - the `session_started` and `session_titled` events, which traces don't have
  - the approval decision, taken from the trace's `approval_decided` event (no click needed)
- **Tour mode:** the page's four load-time reads (`health`, `sessions`, `harness`, `logo`) come from `data/*.json`. Every write (run, approval, delete, evals) is switched off.
- **Before you record:** a step with no clip advances after its caption's reading time (about 2.5 words a second), so the tour works from day one.
- **Back** clears the chat and replays every earlier step at once.

## Proposed tour (10 steps, about 5 minutes)
The story follows your notes: the model alone (a brain in a jar) → why we need a harness → Agent = Model + Harness → the use case (CloudCo's contract renewal) → each part, shown live → why the harness matters.

| # | Step | Shows | Harness pane |
|---|---|---|---|
| 1 | Brain in a jar | The empty page, the model menu | — |
| 2 | Why we need a harness | The four parts; Agent = Model + Harness | Whole pane |
| 3 | The use case | CloudCo, ShopCo's renewal, the five changes that matter, who approves what | Sidebar: Acting As |
| 4 | The agentic loop | Run starts: plan → act → observe → repeat; when it stops | Agentic Loop |
| 5 | Context | Instructions, skills on demand, facts read; summarise vs prune | Context |
| 6 | Tools | Tool calls; a helper agent with its own slice of budget | Tools |
| 7 | Guardrails | Hard limits held; the email checked; only the CFO can approve | Guardrails |
| 8 | Verification | Checks on the drafted answer, one chance to fix | Verification |
| 9 | Answer and memory | Answer, run cost; a fact saved for next time | Memory |
| 10 | Why the harness matters | The agent is a folder; same harness, another agent | — |

**Run to record:** Priya (Sales) asks "Send ShopCo a 25% discount offer". It touches every part, including the CFO approval.

### Script draft (from your notes; the lines get adjusted to the recorded run, then you edit and record)
1. **Brain in a jar.** AI models are very good at reasoning and writing. But on their own, they can't take actions. Think of a brain in a jar: capable, but trapped. It can tell you how to send a proposal; it can't send it. This tour shows what we build around the model so it can do the work. Everything here is a real recorded run of an agent I built from scratch. The company and its data are made up.
2. **Why we need a harness.** As models get more powerful, we expect more than answers in a chat window. We want them to finish whole tasks: build a customer proposal, pull in the right information, and send it once it's approved. For that, the model needs a layer around it, like an operating system. That layer is the harness. An AI agent is the model plus the harness. Ours has four parts: an agentic loop, context and memory, tools, and guardrails. You can see each one on the right.
3. **The use case.** Here's the job this agent does. CloudCo is a made-up software company of about 200 people; it sells inventory software to retail chains. Two days before quarter end, its customer ShopCo sends back a $480,000-a-year renewal with about 60 edits. Five of them matter: a three-year price lock, a 25% discount, Net 60 payment, 99.99% uptime and unlimited liability. Any software company with a deal desk knows this moment: what can Sales agree to, and who must sign off? The Contract Agent finds the changes that matter, checks each against CloudCo's standard terms, says who must approve, and drafts the reply. People decide; the agent never agrees on its own. We follow one short slice: Priya from Sales wants to send ShopCo a 25% discount offer.
4. **The agentic loop.** First, the loop. The model plans, acts with a tool, reads the result, and repeats until the goal is met. The harness runs this loop, not the model. It also decides when to stop: when there's an answer, or after 25 steps, one dollar or two minutes, whichever comes first.
5. **Context.** Next, context. Context engineering decides what goes into the model's window for this task, and what stays out. The harness loads the company's instructions, the skills it needs only when it needs them, and what it remembers about Priya. The window is finite. When it fills up, the harness either summarises older turns, which is shorter but loses detail, or prunes stale tool output and keeps the important turns word for word.
6. **Tools.** Now tools. With tools, the model can do things in the world. Here it reads the ShopCo contract and checks the discount against the pricing policy. It can also hand part of the work to a helper agent, which gets its own slice of time and budget. The model only asks for a tool; the harness runs it and sends back the result.
7. **Guardrails.** Then guardrails. Different people get different access, and some actions need approval before they happen. Hard limits come first: lines the company never crosses. Then the email itself is checked against the terms. And 25% is above what Sales may approve, so the harness stops and asks the CFO. Priya can't approve it alone: the server checks who's answering.
8. **Verification.** Before the answer reaches you, the harness checks it. Plain code reads the draft: are the numbers grounded in the data, are sources cited, is the right approver named. If a check fails, the model gets one chance to fix it. That's self-verification, built into the loop.
9. **Answer and memory.** Here's the answer, with what the run cost: model calls, tokens, dollars and seconds. And memory: storage that lasts beyond the context window. The agent saves a fact for next time, so the next conversation starts knowing what was decided today. Longer tasks need this to keep track of work and pick up where they left off.
10. **Why the harness matters.** So that's the harness: a loop to pursue the goal, context and memory to stay grounded, tools to act, and guardrails to stay in control. How well you build it matters as much as which model you pick. And this agent is just a folder: its instructions, tools and skills. Point the same harness at another folder, and you have another agent.

About 770 words: roughly 5 minutes of voice.

**Step 3 also shows a card** on top of the chat while you speak, so the case is seen as well as heard:

| ShopCo asks for | CloudCo's rule | Who decides |
|---|---|---|
| 3-year price lock | Up to 3 years | Sales |
| 25% discount | ≤ 15% Sales · 15–25% CFO · > 25% never | CFO |
| Net 60 | Net 45 Sales · Net 60 Finance | Finance |
| 99.99% uptime | Up to our record, 99.95% | Blocked → counter 99.95% |
| Unlimited liability | Up to 24 months of fees | Blocked → counter 24 months |

The card's text lives in `tour.toml` (a `card` field, Markdown); the player only draws it, so `src/` stays domain-free. All values are made up (`spec/01-company.md`).

## Choices (D-168 to D-174)
| # | Choice | Options | Chosen | Why | Cost |
|---|---|---|---|---|---|
| D-168 | How visitors run it | Live on your paid key with caps · live on a free-tier key · visitor's own key · "Sign in with OpenRouter" · recorded replay | **Recorded replay** | No key, no backend, $0, nothing to abuse. Visitors won't paste keys. OpenRouter still bills the visitor and breaks Gemini-only. Gemini spend caps apply with up to ~10 min delay. | Visitors can't type their own question. A "Try It Live" button can come later. |
| D-169 | Voice | No voice · AI voice · your recorded voice | **Your voice, one clip per step** | Personal, and one fumbled line means re-recording one clip, not the whole tour | You record about 9 clips; I write the script |
| D-170 | Pacing | Visitor clicks Next · one continuous track · voice leads | **Voice leads, with Pause / Back / Next / Mute** (your pick) | Feels like a talk and stays in the visitor's control | — |
| D-171 | How the replay draws | Screen video · a separate tour renderer · the page's own `onEvent()` | **The page's own `onEvent()`** | Same cards as live, stays true as the page changes, no second copy to maintain | A page change also changes the tour (re-check it) |
| D-172 | Where the tour lives | In `src/` · in the workspace | **Content in the workspace, player and export in `src/`** | The one architecture rule: `src/` knows no domain | — |
| D-173 | Which runs | Existing traces · fresh live runs | **One fresh live run** (Flash-Lite, free tier) | Old traces predate the S11/S12 cards (to-do, checks, hard limits, identity) | One live run, $0. Re-run if it wanders. |
| D-174 | Hosting | `harness.gauravlahoti.dev` · `gauravlahoti.dev/harness` | **Your call.** The export uses relative paths, so both work. | A subdomain is one DNS record. A path goes inside your site's build. | — |

**Not in S13:** Cloud Run, any backend, live typing, the S08 swap test, X-ray and demo-mode checks (they stay in S08).

## Done when (S13)
| ID | Check | How |
|---|---|---|
| AC1 | `tour.toml` loads; every step has an id, a caption and a valid "play until" event; every run and clip it names exists | 🧪 |
| AC2 | The export is one folder: relative asset paths, no `/api/` call in tour mode, nothing key-shaped in any file | 🧪 |
| AC3 | `tour.js`, `export.py` and the player know no domain (the existing domain test) | 🧪 |
| AC4 | The replay draws the same cards as the live run: tools, helper, hard limits, approval, checks, answer, run summary | 👀 |
| AC5 | Voice leads: a clip ends and the next step starts. Pause, Back, Next and Mute work, and the caption is always shown | 👀 |
| AC6 | Each step opens and highlights its Harness pane section | 👀 |
| AC7 | It plays from a subfolder (`python -m http.server`), and the network panel shows zero model or API calls | 👀 |
| AC8 | Audio total ≤ 15 MB; a step without a clip advances on reading time | 🧪 |
| AC9 | It works at phone width | 👀 |

## Explain it back
1. Why is the public demo a replay and not a live agent?
2. Why does the replay go through `onEvent()` and not a separate renderer?
3. What would have to change before visitors could type their own question?

## Changes
- 2026-11-12 · Created at your request (public demo, voice-led). Takes over S08-AC2 (replay) and S08-AC9 (static export).
- 2026-11-12 · Your request: a use-case step (3) explains CloudCo, the ShopCo renewal and what the agent is expected to do, framed as the deal-desk case every B2B software company has. Tour is 10 steps.
- 2026-11-12 · Script drafted from your notes: brain in a jar, why we need a harness, Agent = Model + Harness, context engineering (summarise vs prune), memory beyond the window.
- 2026-11-12 · Approved (your go-ahead). Local first: the export (AC2) and subfolder check (AC7) wait for the hosting step (D-175). Voice recorded in the page (D-176). The run has two turns: the agent raises concerns first, Priya agrees, four people approve the send; step 9 shows memory being read, as this run saved no new fact.
- 2026-11-12 · Your review: a guide presents the tour (person icon, name, speech bubble), captions one sentence at a time with the voice, a 10-second pause before the next step; controls Previous · Pause · Next · Mute (D-178; D-170 changed). AC5 re-checked → 🟦 until shown again.
- 2026-11-12 · Your review: the guide's name removed; a cinematic tour (voice orb, subtitles, chapter titles, living diagram with jar/harness/finale scenes, spotlight); dark + cyan theme for the whole page, like gauravlahoti.dev; Observability kept on the page (D-179).
- 2026-11-12 · Your request: step 1's clip made in your cloned ElevenLabs voice "Gaurav" (`audio/01-jar.mp3`, 25 s); D-169 changed (D-181). AC5 and AC8 stay as they were; re-check step 1 with its clip.
- 2026-11-12 · Your go-ahead: steps 2–10 voiced the same way; every step now has a clip (4 min 43 s, 4.5 MB). Re-check AC5 with the clips.
