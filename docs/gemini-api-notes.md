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
| Models listed include `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-4-argon` | 📄 API reference | D-07 |

## Still to confirm live 🔴

- Does a reply that asks for tools end `requires_action` or `completed`? (The loop must not treat it as "unexpected".)
- Does a saved-and-reloaded step (`model_dump(mode="json")`) keep working when sent back? (D-22)
- What does a safety block look like with the Interactions API?
- What exception and code does an API error raise? Seen so far: `google.genai._gaos.lib.compat_errors.APIStatusError`, **402** `RESOURCE_EXHAUSTED` "prepayment credits are depleted" (2026-11-10).

## Sources

- `documents/aistudio.google.com/docs/function-calling`
- `documents/aistudio.google.com/docs/get-started`
- `documents/aistudio.google.com/docs/thinking`
- `documents/ai.google.dev/api/interactions-api-v1`
- `documents/docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/interactions-api`
- SDK: `google/genai/_gaos/types/interactions/{functioncallstep,functionresultstep,thoughtstep}.py`
