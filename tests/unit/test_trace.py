"""Trace files (S01-AC11): every event saved as one JSON line; the key never written."""

import json
from pathlib import Path

from agentic_harness.events import Event
from agentic_harness.trace import TraceWriter

KEY = "fake-value-for-trace-test"  # not a real key: proves traces scrub secrets


def event(seq: int, **data: object) -> Event:
    return Event(type="model_replied", run_id="run-1", seq=seq, time=1.0, data=dict(data))


def test_s01_ac11_one_json_line_per_event(tmp_path: Path) -> None:
    writer = TraceWriter(tmp_path)
    writer(event(1, status="completed"))
    writer(event(2, status="completed"))
    lines = writer.path_for("run-1").read_text().splitlines()
    assert [json.loads(line)["seq"] for line in lines] == [1, 2]
    assert json.loads(lines[0])["data"] == {"status": "completed"}


def test_s01_ac11_key_never_reaches_the_trace(tmp_path: Path) -> None:
    writer = TraceWriter(tmp_path, secrets=[KEY, ""])  # an empty secret must not blank everything
    writer(event(1, tool_output=f"oops, a tool echoed {KEY}", nested={"deep": [KEY]}))
    text = writer.path_for("run-1").read_text()
    assert KEY not in text
    assert "***" in text
    assert "oops, a tool echoed" in text


def test_s01_ac11_trace_folder_is_created(tmp_path: Path) -> None:
    writer = TraceWriter(tmp_path / "a" / "b")
    writer(event(1))
    assert writer.path_for("run-1").exists()
