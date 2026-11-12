# Gemini API notes

> Shapes the harness depends on, checked against Google's docs and the installed SDK (`google-genai` 3.0.0).
> 📄 = from the docs or SDK types · 🔴 = seen in a live call (filled in by `scripts/record_gemini_shapes.py`).

## Verified from docs and SDK · 2026-11-10

| Fact | Source | We use it in |
|---|---|---|
| Call: `client.interactions.create(model=…, store=False, system_instruction=…, input=[steps], tools=[…], generation_config={…})` | 📄 function-calling, API reference | `GeminiModel` |
| Stateless: send the whole history every call; never `previous_interaction_id` | 📄 get-started, thinking | D-04 |
| Google's own sample stores each reply step as `step.model_dump()` and sends it back unchanged | 📄 function-calling | D-22 (plain dicts) |
| Model steps must be resent exactly as received; thought **signatures** sit on `thought` steps (`signature`, encoded text) | 📄 thinking · SDK `ThoughtStep` | D-05 |
| Input step: `{"type": "user_input", "content": [{"type": "text", "text": …}]}` | 📄 | loop |
| Tool declaration: `{"type": "function", "name", "description", "parameters": <JSON schema>}` | 📄 | tool format (S03) |
| Tool call step: `{"type": "function_call", "id", "name", "arguments": {…}}` | SDK `FunctionCallStep` | loop |
| Tool result step: `{"type": "function_result", "call_id", "name", "result": [{"type": "text", "text": …}], "is_error"?: bool}` | SDK `FunctionResultStep` | loop · S03 tool errors |
| Several `function_call` steps can come in one reply (parallel calls) | 📄 | S01-AC7 |
| Statuses: `in_progress`, `requires_action`, `completed`, `failed`, `cancelled`, `incomplete` | 📄 API reference | S01-AC10 |
| `incomplete` = hit `max_output_tokens` (which includes thought tokens); output may be empty, thinking is still billed | 📄 thinking | stop rules |
| Usage: `total_input_tokens`, `total_output_tokens`, `total_thought_tokens`, `total_cached_tokens`, `total_tool_use_tokens`, `total_tokens` | 📄 API reference | `pricing.py`, cost limit |
| `generation_config`: `max_output_tokens`, `thinking_level` (`minimal`…`high`), `thinking_summaries`, `tool_choice` (`auto`, `any`, `none`, `validated`) | 📄 API reference | config |
| Effort is `generation_config.thinking_level`: `minimal`, `low`, `medium`, `high`. Defaults: `medium` on 3.5 / 3.6 Flash, `minimal` on 3.5 Flash-Lite. `minimal` is missing on 3.7 / 3.8 Flash and Pro, so the page offers low / medium / high. Never mix with the old `thinking_budget` (400) | 📄 thinking · what's new in 3.5 (checked 2026-11-10) | D-85 |
| Signature validation covers the model's steps in the *current* turn (since the last user message that is not a function result); older turns: send consistently, all of it or none. So trimming may stub old tool results and summarize whole earlier turns, but never edits model steps | 📄 thought signatures (checked 2026-11-10) | D-95 |
| Models listed include `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-4-argon` | 📄 API reference | D-07 |
| Function parameters may nest: an `array` whose `items` is an `object` with `properties` and a string `enum`. Not supported: `default`, `optional`, `maximum`, `oneOf`; avoid `minItems`/`maxItems` (they blow up the schema). Interactions API uses standard JSON Schema (`$defs`, `$ref`) | 📄 function-calling (checked 2026-11-12) | `write_plan` (S11) |

## Seen in live calls 🔴 · 2026-11-10

Recorded by `scripts/record_gemini_shapes.py` into `tests/fixtures/gemini/` (model `gemini-3.5-flash-lite`: 3.8 and 3.6 Flash were overloaded on the free tier that day; the API shape is the same for all models).

| Case | Status | Steps in the reply | What it tells us |
|---|---|---|---|
| 01 plain answer | `completed` | `thought`, `model_output` | Even a plain answer carries a `thought` step with a `signature` (0 thought tokens) |
| 02 tool call | **`requires_action`** | `thought`, `function_call` | A tool request is **not** `completed`; the loop must accept `requires_action` |
| 03 round trip | `completed` | `thought`, `model_output` | Steps stored as `model_dump(mode="json", exclude_none=True)` and sent back work: **D-22 confirmed** |
| 04 two calls | `requires_action` | `thought`, `function_call` ×2 | Parallel calls; IDs are unique (`call_1905…6024`, `call_1905…4249`) |
| 05 two results | `requires_action` | `thought`, `function_call` ×2 | Unhelpful results → the model calls again. The step limit matters |
| 06–07 tool error | `requires_action` → `completed` | | A result with `"is_error": true` → the model explains the problem instead of crashing |
| 08 output limit | **`incomplete`** | `thought`, `model_output` | Answer cut off mid-sentence at `max_output_tokens=16` |
| 09 strict safety | `completed` | | A harmless prompt was not blocked even at `block_low_and_above`. A real block was **not** captured (we don't provoke harmful output); the loop treats any unknown status as a named error |

**Reply fields:** `id`, `model`, `status`, `steps`, `usage`, `output_text`, `created`, `updated`, `object`, `service_tier`, `continuation_ids`.
**Usage:** `total_input_tokens`, `total_output_tokens`, `total_thought_tokens`, `total_cached_tokens`, `total_tool_use_tokens`, `total_tokens`, `initial_input_tokens`. Output excludes thoughts: 26 in + 5 out + 158 thought = 189 total (3.8 Flash).
**Safety settings shape:** `{"type": "harassment", "threshold": "block_low_and_above"}` (not `category`).

### Errors (all subclasses in `google.genai._gaos.lib.compat_errors`)

| Seen | Class | Code | Meaning for the loop |
|---|---|---|---|
| Billing | `APIStatusError` | 402 `RESOURCE_EXHAUSTED` | Stop: "prepayment credits are depleted" |
| Overload | `InternalServerError` | 503 `service_unavailable` | "high demand … try again later". The SDK retried this **silently for ~5 min** |
| Slow | `APITimeoutError` | – | Client-side timeout |
| Bad model | `NotFoundError` | 404 `not_found` | Configuration error |

### SDK behaviour to switch off (D-29)

- `automatic_continuation` defaults to `True`: the SDK makes extra billed calls on its own when a reply is cut by the server's per-request limit. We pass `False`.
- Retries: by default the SDK retries 429/5xx with no visible sign, and on a 429 it sleeps for the server's `Retry-After` uncapped (seen: "retry in 41m43s" on the free tier's 20-a-day limit). We set `attempts=1` (D-42) and bound each call by the run's time left.
- Errors carry `status_code` and `body = {"error": {"message", "code"}}`; we show `Gemini <code>: <message>`.

### Prices (paid tier, per 1M tokens, checked 2026-11-10)

| Model | Input | Output (incl. thinking) | Cached input |
|---|---|---|---|
| `gemini-3.8-flash` | $0.75 | $3.75 | $0.075 (all double from 2027-01-01) |
| `gemini-3.5-flash-lite` | $0.30 | $2.50 | $0.03 |

## Sources

- `documents/aistudio.google.com/docs/function-calling`
- `documents/aistudio.google.com/docs/get-started`
- `documents/aistudio.google.com/docs/thinking`
- `documents/ai.google.dev/api/interactions-api-v1`
- `documents/docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api`
- `documents/aistudio.google.com/docs/pricing`, `documents/aistudio.google.com/docs/billing`
- SDK: `google/genai/_gaos/types/interactions/{functioncallstep,functionresultstep,thoughtstep,safetysetting}.py`, `google/genai/_gaos/google_genai.py` (continuation, retries)

## Claude (Anthropic), from S09 (D-102)

Checked 2026-11-10 against the `claude-api` reference (SDK `anthropic` 2.8.0).

| Fact | Used in |
|---|---|
| Models `claude-haiku-5-5` ($0.10 / $0.50 per 1M, ≤100K-token prompts), `claude-sonnet-5-5` ($2 / $10; cache reads $0.20) | `pricing.toml` |
| Effort: `output_config.effort` = low · medium · high (also xhigh, max); defaults: Haiku medium, Sonnet high. Thinking is adaptive and always on; `budget_tokens` is a 400 | `anthropic_model.py` |
| Tool use: assistant `tool_use` {id, name, input}; reply with user `tool_result` {tool_use_id, content, is_error}; all results of one turn in one user message | `to_messages` |
| Thinking blocks go back unchanged; a model that can't read a block drops it, unbilled | `to_messages` |
| `stop_reason`: end_turn, tool_use, max_tokens, pause_turn, refusal | `STOP_TO_STATUS` |
| Cache: top-level `cache_control: {type: "ephemeral"}`; writes 1.25× input, reads ~0.1×; minimum prefix 512 tokens on these models | `create`, `pricing.py` |
| SDK retries 429/5xx twice by default → `max_retries=0` (D-42) | `_make_client` |
