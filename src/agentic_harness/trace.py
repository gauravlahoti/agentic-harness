"""Trace files: every event of a run, one JSON line each (S01-AC11).

Harness part: the loop's record. A trace is append-only and readable, so a
run can be inspected or replayed later (S08). It is just one more event
listener.

Does not: decide what to record (the loop's events do), or let the key in:
every line is scrubbed of known secrets before it is written.
"""

import json
from collections.abc import Iterable
from pathlib import Path

from agentic_harness.events import Event


class TraceWriter:
    def __init__(self, directory: Path, secrets: Iterable[str] = ()) -> None:
        self.directory = directory
        self._secrets = [s for s in secrets if s]  # an empty string would match everywhere

    def path_for(self, run_id: str) -> Path:
        return self.directory / f"{run_id}.jsonl"

    def __call__(self, event: Event) -> None:
        line = json.dumps(event.to_dict(), ensure_ascii=False)
        for secret in self._secrets:
            line = line.replace(secret, "***")
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.path_for(event.run_id).open("a", encoding="utf-8") as file:
            file.write(line + "\n")
