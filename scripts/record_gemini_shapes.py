"""Record Gemini's real reply shapes as test fixtures (S01-AC1, D-22, D-23).

Harness part: the model boundary. Makes a handful of small live calls with
``store=False`` and saves each request and reply as JSON under
``tests/fixtures/gemini/``. FakeModel replays these, so offline tests match reality.

Run: ``uv run python scripts/record_gemini_shapes.py``. Needs a key; costs about a cent.

Does not: run in CI or ``make check``, write the key anywhere (every file is checked
for it before writing), or use server-side history (never ``previous_interaction_id``).
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from google import genai

from agentic_harness.config import load_settings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "tests" / "fixtures" / "gemini"

GET_TIME = {
    "type": "function",
    "name": "get_time",
    "description": "Returns the current time in a time zone, as ISO 8601.",
    "parameters": {
        "type": "object",
        "properties": {
            "timezone": {"type": "string", "description": "IANA name, e.g. 'UTC' or 'Asia/Tokyo'"}
        },
        "required": ["timezone"],
    },
}
SYSTEM = "You are a terse assistant. Use tools when they help. Answer in one sentence."


def user(text: str) -> dict[str, Any]:
    return {"type": "user_input", "content": [{"type": "text", "text": text}]}


def result_for(call: dict[str, Any], payload: object, *, is_error: bool = False) -> dict[str, Any]:
    step: dict[str, Any] = {
        "type": "function_result",
        "name": call["name"],
        "call_id": call["id"],
        "result": [{"type": "text", "text": json.dumps(payload)}],
    }
    if is_error:
        step["is_error"] = True
    return step


class Recorder:
    def __init__(self, client: genai.Client, model: str, secret: str) -> None:
        self.client, self.model, self.secret = client, model, secret
        self.summary: list[str] = []

    def call(self, steps: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        reply = self.client.interactions.create(
            model=self.model, store=False, system_instruction=SYSTEM, input=steps, **extra
        )
        # mode="json" gives exactly what we would store in a trace file (D-22).
        return reply.model_dump(mode="json", exclude_none=True)

    def save(self, name: str, request: dict[str, Any], reply: dict[str, Any]) -> None:
        text = json.dumps({"request": request, "reply": reply}, indent=2) + "\n"
        if self.secret in text:  # never write the key, whatever happens
            raise SystemExit(f"{name}: the key appeared in the output; nothing written.")
        (OUT / f"{name}.json").write_text(text)
        kinds = [s.get("type") for s in reply.get("steps", [])]
        usage = reply.get("usage", {})
        self.summary.append(
            f"{name:<22} status={reply.get('status')!s:<16} steps={kinds} "
            f"in={usage.get('total_input_tokens')} out={usage.get('total_output_tokens')} "
            f"thought={usage.get('total_thought_tokens')}"
        )

    def case(self, name: str, steps: list[dict[str, Any]], **extra: Any) -> dict[str, Any]:
        reply = self.call(steps, **extra)
        self.save(name, {"input": steps, **extra}, reply)
        return reply


def calls_in(reply: dict[str, Any]) -> list[dict[str, Any]]:
    return [s for s in reply.get("steps", []) if s.get("type") == "function_call"]


def main() -> int:
    settings = load_settings(ROOT / ".env")
    secret = settings.require_key()
    client = genai.Client(api_key=secret)
    OUT.mkdir(parents=True, exist_ok=True)
    rec = Recorder(client, settings.model, secret)
    tools = {"tools": [GET_TIME]}

    # 1. Plain answer, no tools.
    rec.case("01_text", [user("Say hello in exactly three words.")])

    # 2. A tool call, then 3. the round trip: model steps go back exactly as dumped.
    first = [user("What time is it in UTC right now?")]
    reply = rec.case("02_tool_call", first, **tools)
    calls = calls_in(reply)
    if calls:
        history = first + reply["steps"] + [result_for(calls[0], "2026-11-10T09:30:00Z")]
        rec.case("03_tool_round_trip", history, **tools)

    # 4. Two calls in one reply (if the model chooses to).
    both = [user("What time is it in UTC and in Asia/Tokyo? Call the tool once per zone.")]
    reply = rec.case("04_two_calls", both, **tools)
    calls = calls_in(reply)
    if len(calls) >= 2:
        results = [result_for(c, f"time in {c['arguments'].get('timezone')}") for c in calls]
        rec.case("05_two_results", both + reply["steps"] + results, **tools)

    # 6. A tool error goes back with is_error; the model should cope.
    ask = [user("What time is it in Mars/Olympus?")]
    reply = rec.case("06_tool_error_call", ask, **tools)
    calls = calls_in(reply)
    if calls:
        error = result_for(calls[0], {"error": "Unknown time zone: Mars/Olympus"}, is_error=True)
        rec.case("07_tool_error_reply", ask + reply["steps"] + [error], **tools)

    # 8. Output limit hit: expect status "incomplete".
    rec.case(
        "08_max_tokens",
        [user("List the first 200 prime numbers, comma separated.")],
        generation_config={"max_output_tokens": 16},
    )

    # 9. Strict safety setting on a harmless prompt: shows the shape if anything is blocked.
    strict = [
        {"category": c, "threshold": "block_low_and_above"}
        for c in ("harassment", "hate_speech", "dangerous_content", "sexually_explicit")
    ]
    try:
        rec.case(
            "09_safety_strict",
            [user("Write a one-line playful roast of a fictional pirate named Bob.")],
            safety_settings=strict,
        )
    except Exception as error:
        rec.summary.append(f"09_safety_strict       raised {type(error).__name__}: {error}")

    # 10. A bad model name: what does an API error look like?
    try:
        client.interactions.create(model="no-such-model", store=False, input=[user("hi")])
    except Exception as error:
        text = f"{type(error).__module__}.{type(error).__name__}: {error}"
        rec.summary.append(f"10_bad_model           raised {text.replace(secret, '***')[:300]}")

    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    print(f"Recorded with {settings.model} at {stamp}:")
    print("\n".join(rec.summary))
    return 0


if __name__ == "__main__":
    sys.exit(main())
