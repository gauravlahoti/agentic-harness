# Stage 3 · Tools

> The agent stops asking you to paste things. It looks up CloudCo's records, compares the
> contract itself, cites IDs, and saves drafts. This is the "give it power" stage:
> actions run without asking, but they only ever write to a local `outbox/`.

## What you have now

- As **Sales**, ask "What did ShopCo change in CT-2207, and what can I agree to?". The agent runs `compare_to_standard`, finds the 5 changes that matter among 61 edits, checks the policies, and answers with clause IDs (2.1, 3.2, 4.1, 6.1, 9.2) and record IDs.
- Every tool line on the page has a **risk tag**: `read` (grey), `write` (amber), `action` (red). Open it to see each argument on its own row, the output, and the call ID.
- A file a tool saves becomes a **file card** under the answer: "Draft" for `tasks/<run-id>/`, "Outbox · not sent" for actions. It opens to the text.
- `hello` still works; its `get_time` is now a three-line `@tool`.

## One tool, start to finish

```
@tool(risk="read")                         ← risk is required (D-44)
def get_deal(customer_id: Annotated[str, "The customer's ID, e.g. 'CUS-0042'"]):
    """List a customer's deals … Use it to find which contract …"""   ← the model's instructions
        │
        ▼  @tool reads the function (D-43)
Tool(name="get_deal", description=<docstring>, risk="read",
     parameters={"type":"object","properties":{"customer_id":{"type":"string",…}},"required":[…]})
        │
        ▼  Gemini sees only name + description + parameters
model asks: function_call get_deal {"customer_id": "CUS-0042"}
        │
        ▼  call_tool (registry.py)
   1. check arguments (required, types, enums)  ── problem ──▶ error text back to the model (D-49)
   2. add ctx if the function asks for it        ── the model never sees ctx (D-48)
   3. run it; any exception                      ──────────▶ error text back to the model
   4. JSON, then cut at 20,000 chars with a note (D-50)
        │
        ▼
function_result {"call_id": …, "result": [{"text": "[{\"id\": \"DL-3108\", …}]"}]}
```

Nothing a tool does can crash the loop. The model always gets text back, and an error is marked `is_error` so it can correct itself.

## Two kinds of tools

| | Owned by | Here | Risk |
|---|---|---|---|
| **Built-in** | The harness, for any workspace that asks (`builtins = [...]`, D-45) | `read_file` (only `readable` folders; never `.env` or `workspace.toml`), `write_file` (this run's folder), `load_skill` (automatic with skills) | read · write · read |
| **Workspace** | `workspaces/cloudco/tools.py` | `get_customer`, `get_deal`, `get_contract`, `compare_to_standard`, `search_policy`, `get_uptime`, `get_payment_history` | read |
| | | `accept_change`, `send_to_customer` | action |

The harness never names a workspace tool. A test reads every workspace's `tools.py` and fails if one of those names appears in `src/` (S03-AC3).

## The data

`make_data.py` writes everything in `data/` from a fixed seed (D-52), and a test checks that the committed files match it. All of it is made up:

| File | Holds |
|---|---|
| `customers.json` · `deals.json` · `contracts.json` | ShopCo `CUS-0042`, renewal `DL-3108` ($480,000/year), contract `CT-2207` |
| `uptime.json` | 12 months, `UP-2025-11`…`UP-2026-10`, average 99.95% |
| `payments.json` | 12 invoices `INV-4100`…, on average 9 days late |
| `contracts/CT-2207-standard.md` | Our agreement: 168 clauses, ~19,000 words (~38 pages) |
| `contracts/CT-2207-shopco-redline.md` | ShopCo's markup: 61 edits. 55 are wording, 5 matter, and 1 is a planted instruction in appendix B.7 |

`compare_to_standard` diffs the two versions clause by clause in code (D-51), so each of the 61 edits comes with its clause ID and the exact words removed and added. The model only judges which ones matter.

## The files

| File | Job | Key lines |
|---|---|---|
| `tools/__init__.py` | The `Tool` record and `ToolContext` | `risk` has no default. `ToolContext.save_task_file` / `save_outbox_file` accept a plain file name only, write it, and emit `file_saved` (D-53). |
| `tools/registry.py` | `@tool`, `check_arguments`, `call_tool` | `_json_type` maps `str/int/float/bool/Literal/list` and `Annotated` descriptions; anything else fails at load. `_is` checks `bool` before `int` (in Python, `True` is an int). `_cap` adds the visible cut note. |
| `tools/builtin.py` | `read_file`, `write_file` | `resolve()` follows `..` and links to the real place, *then* we check it is inside a readable folder. Reading a folder lists it. |
| `loop.py` | Unchanged loop | `_run_tool` now builds a `ToolContext` per call and hands everything to `call_tool`; tool events carry `risk`. |
| `workspace.py` · `api.py` | Wiring | `builtins` and `readable` from `workspace.toml`; unknown built-ins and duplicate tool names are errors at startup. |
| `server/app.py` | Fix (D-54) | `Cache-Control: no-cache`, so the browser never runs an old page script. |
| `web/app.js` | The page | Risk tag, one fact row per argument, short labels, and `fileCard()` for each `file_saved` event. |
| `workspaces/cloudco/tools.py` | CloudCo's tools | Docstrings say *when* to use each tool. The contract comes as an outline, then one clause at a time. Actions write through `ctx` only, and the file has no network imports (a test checks). |

## What real Gemini did (3.5 Flash-Lite, today)

| Run | Calls · time · cost | Result |
|---|---|---|
| CLI, Sales, the story question | 2 · 13 s · $0.004 | Ran 5 tools in parallel. All 5 changes with clause IDs; flagged the B.7 injection and ignored it |
| `make live` (`test_s03_ac11_*`) | passed | All 5 clause IDs in the answer |
| Page, "…and save a draft reply" | 3 · 22 s · $0.005 | All 5 changes, injection flagged, draft saved as a file card, record IDs in Sources |

Honest misses, for the S08 evals to measure:
- In one page run it called our uptime record "99.9%" (it is 99.95%) because it never called `get_uptime`.
- In another it cited policy sections (§1, §2) where it meant clause IDs.
- The B.7 instruction was ignored in every run, but the only guard today is one line in `AGENTS.md`. S05 and S06 add real gates.

## Verify it yourself

1. `make check` → all green (168 passed).
2. `HARNESS_MODEL=gemini-3.5-flash-lite make live` → 3 passed.
3. `uv run agentic-harness serve --workspace workspaces/cloudco` → http://127.0.0.1:8000, **Sales**, **Gemini 3.5 Flash-Lite**. Ask: "What did ShopCo change in CT-2207? Also save a short draft reply to ShopCo as a file." Check:
   - green TOOL lines with `read` tags, and `write_file` with an amber `write` tag;
   - the answer lists 2.1, 3.2, 4.1, 6.1, 9.2 and mentions the appendix B instruction;
   - a "Draft" file card under the answer that opens to the reply.
4. Open `compare_to_standard`'s line: Output starts with `"count": 61`.
5. Ask: "Send ShopCo a short note that we are reviewing their changes." (Each task is a fresh run until S07, so give it the whole request.) You get a red `action` tag and an "Outbox · not sent" card. The file is in `workspaces/cloudco/outbox/`. Nothing was emailed, and nothing asked you first. That is S05/S06's job.
6. `uv run python workspaces/cloudco/make_data.py`, then `git status`: no changes, because the data is reproducible.

## Explain it back

1. Why does the harness own `read_file`, while CloudCo owns `get_contract`?
2. Why return errors instead of raising them?
3. What would happen with a tool described as "does contract stuff"?
4. Why does the model never see `ctx` or a tool's risk?
