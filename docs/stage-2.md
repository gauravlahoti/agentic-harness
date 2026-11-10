# Stage 2 · Context

> The agent now knows who it works for, the rules it must follow, and how each team does its work.
> Nothing new in the loop. Only what goes **into** the prompt changed, and one built-in tool.

## What you have now

- `agentic-harness serve --workspace workspaces/cloudco` opens the **Contract Assistant**. Pick a team in the sidebar (Sales, Engineering, Finance, CFO). Switching clears the thread, because a new team means a new prompt.
- Every run starts with a **CONTEXT** line: "Loaded context · Sales · 2 files · 2 skills". Open it to see each file, its token estimate, every skill offered, and the prompt ID.
- When the model reads a skill, a second CONTEXT line says "Read skill contract-review". The skill's path then shows up in the answer's **Sources**.
- CloudCo answers in a fixed shape: **Summary → Needs a human decision → Sources**.
- `agentic-harness run --workspace workspaces/cloudco --profile finance "…"` does the same in the terminal.
- A failed model call now says why at once ("Gemini 429: … 20 requests per day … retry in 40m"), instead of a silent wait until the time limit (D-42).

## Two kinds of context

| | Loaded | Holds | Cost |
|---|---|---|---|
| **Memory files** (`AGENTS.md`, `teams/{profile}.md`) | Every call | Who we are, rules that always apply, the answer format | Tokens on every call, so a size budget warns (D-38) |
| **Skills** (`SKILL.md`) | On demand. Only `name: description` sits in the prompt | One task, step by step | One extra model call when used |

Measured on CloudCo (estimate: characters ÷ 4):

| Profile | Files | Skills offered | Prompt tokens | Prompt ID |
|---|---|---|---|---|
| Sales | `AGENTS.md` 308 + `teams/sales.md` 135 | contract-review, reply-to-customer | 634 | `77e41f5c0001` |
| Engineering | `AGENTS.md` + `teams/engineering.md` 123 | contract-review, uptime-check | 626 | `f3a7c3d169e7` |
| Finance | `AGENTS.md` + `teams/finance.md` 121 | contract-review, payment-terms-check | 629 | `a14350ca52a1` |
| CFO | `AGENTS.md` only (no team file: skipped, not an error) | contract-review | 457 | `453f750ea655` |

## The prompt in one picture

```
workspace.toml ──▶ Workspace ──(profile)──▶ build_context ──▶ Context
                    memory = [AGENTS.md, teams/{profile}.md]      │
                    skills = [skills/company, skills/{profile}]   │
                                                                  ▼
   system prompt (built ONCE per run, same on every call):
   ┌──────────────────────────────────────────────────────────┐
   │ 1. harness base prompt          (loop.py, no domain)     │
   │ 2. ## From AGENTS.md                                     │
   │ 3. ## From teams/sales.md                                │
   │ 4. Skills you can load with load_skill:                  │
   │    - contract-review: … (skills/company/…/SKILL.md)      │
   │    - reply-to-customer: …                                │
   └──────────────────────────────────────────────────────────┘
   prompt_id = first 12 hex of sha256(prompt)  → on every model_called event
```

The order never changes and the prompt is built once. Every call in a run sends the same bytes, which is what lets Gemini cache it (S02-AC8). The prompt ID in the trace proves it.

## The files

| File | Job | Key lines |
|---|---|---|
| `workspace.py` | Reads `workspace.toml` | Every field is optional (D-41); wrong types are clear errors. `check_profile(None)` picks the first profile; an unknown one is an error. `{profile}` in a path is filled in: a missing profile file is skipped, a missing fixed file is an error. |
| `skills.py` | The open `SKILL.md` format | Frontmatter must hold `name` and `description` only, and `name` must match its folder (D-35). The same name twice is an error. `load_skill_tool` offers only the visible names (an `enum`), and returns the body plus its source path so the answer can cite it. |
| `context.py` | Builds the prompt | `build_context(workspace, profile)` puts the parts in a fixed order, estimates tokens, warns when memory is over budget, and returns a `summary()` for the page and trace. |
| `api.py` | Wiring | `create_harness(..., profile=…)` builds the context, adds `load_skill` if there are skills, and passes the prompt to `Harness`. |
| `loop.py` | Unchanged loop | Only new: `prompt_id` on `model_called`, `context` on `run_started`, and `part` on tool events ("context" for `load_skill`). |
| `model.py` | Error fix (D-42) | `MAX_ATTEMPTS = 1`: the SDK never retries on its own. Errors read as `Gemini 429: <Gemini's sentence>`. |
| `web/app.js` | The page | Profile picker in the sidebar (saved per workspace). A CONTEXT line from `run_started.context`; `load_skill` lines say "Read skill X". |
| `workspaces/cloudco/` | The first real agent (made-up data) | `AGENTS.md` with rules and answer format; 3 team files; 4 skills; 2 policies (read by tools in S03). `domain_words` lists words the harness must never contain (D-40). |

## What real Gemini taught us

1. **Free tier limits are per model and per day.** 3.6 Flash allows 20 requests a day. When they run out, Gemini answers within a second with a 429 "retry in 41m43s".
2. **The SDK sleeps on that `Retry-After`, uncapped.** One "harmless" retry turned a clear error into a two-minute spinner. Retries are now off (D-42).
3. **Flash-Lite follows the format well.** With only names and one-line descriptions, it chose `contract-review` by itself for the ShopCo question.

## Verify it yourself

1. `make check` → all green (123 passed, coverage ≥ 75%).
2. `make live` → 2 passed, including `test_s02_ac11_answer_follows_cloudco_format` (Summary → Needs a human decision → Sources, the CFO named, the same prompt ID on every call). Use a model with quota left: `HARNESS_MODEL=gemini-3.5-flash-lite make live`.
3. `uv run agentic-harness serve --workspace workspaces/cloudco` → http://127.0.0.1:8000. As **Sales**, on **Gemini 3.5 Flash-Lite**, send "ShopCo wants 25% off and unlimited liability. Can we agree?". You should see:
   - "Loaded context · Sales · 2 files · 2 skills" then "Read skill contract-review", both tagged CONTEXT.
   - An answer naming the CFO for 25% (standard-terms §2) and refusing unlimited liability (§5).
   - `skills/company/contract-review/SKILL.md` under Sources.
4. Switch to **CFO**: the thread clears, and the next CONTEXT line says 1 file, 1 skill.
5. Open the two model lines ("Decided to use load_skill", "Wrote the answer"), then **Raw event**: the `prompt_id` is the same in both.
6. Make a memory file too big: set `memory_budget_tokens = 100` in `workspaces/cloudco/workspace.toml`, restart the server and run again. The CONTEXT line ends with "⚠ over budget", and opening it shows which file is over. Put it back.
7. Pick a model whose daily quota is used up: the run fails within seconds with Gemini's own sentence, not "hit the time limit".

## Explain it back

1. What belongs in `AGENTS.md`, and what belongs in a skill?
2. Why are skills loaded on demand, and what does that cost?
3. Why must the prompt order never change? How does the trace prove it didn't?
4. Why does `workspace.toml` go to the harness but never to the model?
