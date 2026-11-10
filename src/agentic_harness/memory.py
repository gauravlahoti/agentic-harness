"""Conversations that last: saved task history (S07-AC1, AC2, AC3, AC11; D-90, D-91).

Harness part: memory. Every API call starts from zero, so remembering is the harness's job.
A conversation is one append-only file, ``sessions/<workspace>/<profile>/<id>.jsonl``:

    {"kind": "session", "id", "profile", "created"}       a header
    {"kind": "step", "step": {...}}                        a user input, model step or tool
                                                           result, exactly as it happened
    {"kind": "turn", "task", "answer", ...}                one finished task: what the page lists
    {"kind": "title", "title"}                             the topic (last one wins)

A crash loses at most one line, and you can read the file with ``cat``. Model steps are kept
byte for byte, because Gemini needs their thought signatures back (D-05).

On load, a tool call with no result (the server stopped mid-call) gets a "cancelled"
result. It is never run again: it might have been an action.

Notes (S07-AC4, D-92): ``save_note`` appends one dated line to
``notes/<workspace>/<profile>.md``. They are read once, when a task starts, and put at the end
of the system prompt, newest kept, capped. A note saved mid-task therefore shows up from the
next task: the prompt stays identical for the whole task and keeps caching.

Does not: trim what is sent to the model (``trimming.py``) or decide what a title says
beyond one small model call and a plain fallback.
"""

import json
import re
import secrets
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Annotated, Any

from agentic_harness.model import ModelClient, Step
from agentic_harness.tools import Tool
from agentic_harness.tools.registry import tool

CANCELLED = "Cancelled: the server stopped before this finished. It was not run again."
NOTES_BUDGET_TOKENS = 2000  # about 4 characters a token
NOTE_MAX_CHARS = 500
TITLE_WORDS = 6
TITLE_CHARS = 48
SESSION_ID = re.compile(r"^[0-9a-z-]{8,40}$")

TITLE_PROMPT = (
    "Give a short title for the topic of this conversation: three to six words, no quotes, "
    "no full stop. Reply with the title only."
)


@dataclass(frozen=True, slots=True)
class Turn:
    """One finished task in a conversation."""

    task: str
    answer: str
    outcome: str
    usd: float
    seconds: float
    run_id: str
    at: float = field(default_factory=time.time)


@dataclass(slots=True)
class Session:
    id: str
    profile: str
    title: str = ""
    steps: list[Step] = field(default_factory=list)
    turns: list[Turn] = field(default_factory=list)
    updated: float = 0.0
    repaired: list[Step] = field(default_factory=list)  # "cancelled" results added on load


@dataclass(frozen=True, slots=True)
class SessionInfo:
    id: str
    title: str
    turns: int
    updated: float


class SessionStore:
    """The conversations of one workspace, kept under ``root/sessions/<workspace>/``."""

    def __init__(self, root: Path, workspace: str) -> None:
        self._base = root / "sessions" / workspace

    def create(self, profile: str | None) -> Session:
        session = Session(
            id=time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3), profile=profile or "_"
        )
        self._append(session.id, profile, {"kind": "session", "id": session.id, "profile": profile})
        session.updated = time.time()
        return session

    def append_steps(self, session_id: str, profile: str | None, steps: Sequence[Step]) -> None:
        self._append(session_id, profile, *({"kind": "step", "step": step} for step in steps))

    def finish_turn(self, session_id: str, profile: str | None, turn: Turn) -> None:
        self._append(session_id, profile, {"kind": "turn", **asdict(turn)})

    def set_title(self, session_id: str, profile: str | None, title: str) -> None:
        self._append(session_id, profile, {"kind": "title", "title": title})

    def load(self, session_id: str, profile: str | None) -> Session:
        file = self._file(session_id, profile)
        if not file.is_file():
            raise KeyError(session_id)
        session = Session(id=session_id, profile=profile or "_", updated=file.stat().st_mtime)
        for line in file.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue  # the line the crash cut short
            kind = row.get("kind")
            if kind == "step" and isinstance(row.get("step"), dict):
                session.steps.append(row["step"])
            elif kind == "title":
                session.title = str(row.get("title", ""))
            elif kind == "turn":
                session.turns.append(_turn(row))
        session.repaired = _cancelled(session.steps)
        session.steps.extend(session.repaired)
        return session

    def list(self, profile: str | None) -> list[SessionInfo]:
        folder = self._base / (profile or "_")
        found = []
        for file in folder.glob("*.jsonl") if folder.is_dir() else []:
            session = self.load(file.stem, profile)
            found.append(
                SessionInfo(
                    session.id,
                    session.title or "New conversation",
                    len(session.turns),
                    session.updated,
                )
            )
        return sorted(found, key=lambda item: (item.updated, item.id), reverse=True)

    def delete(self, session_id: str, profile: str | None) -> None:
        file = self._file(session_id, profile)
        if not file.is_file():
            raise KeyError(session_id)
        file.unlink()

    # -- inside -----------------------------------------------------------------------

    def _file(self, session_id: str, profile: str | None) -> Path:
        # The ID names a file, so only the characters we make IDs from are allowed.
        if not SESSION_ID.match(session_id):
            raise KeyError(session_id)
        return self._base / (profile or "_") / f"{session_id}.jsonl"

    def _append(self, session_id: str, profile: str | None, *rows: dict[str, Any]) -> None:
        file = self._file(session_id, profile)
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("a", encoding="utf-8") as out:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")


def _turn(row: dict[str, Any]) -> Turn:
    return Turn(
        task=str(row.get("task", "")),
        answer=str(row.get("answer", "")),
        outcome=str(row.get("outcome", "")),
        usd=float(row.get("usd", 0.0)),
        seconds=float(row.get("seconds", 0.0)),
        run_id=str(row.get("run_id", "")),
        at=float(row.get("at", 0.0)),
    )


def _cancelled(steps: Sequence[Step]) -> list[Step]:
    """A "cancelled" result for every tool call that never got one."""
    answered = {s.get("call_id") for s in steps if s.get("type") == "function_result"}
    return [
        {
            "type": "function_result",
            "name": s.get("name", ""),
            "call_id": s.get("id"),
            "result": [{"type": "text", "text": CANCELLED}],
            "is_error": True,
        }
        for s in steps
        if s.get("type") == "function_call" and s.get("id") not in answered
    ]


def fallback_title(task: str) -> str:
    """The first words of the task: what a title is when the small model can't be asked."""
    words = task.split()[:TITLE_WORDS]
    return " ".join(words)[:TITLE_CHARS].strip() or "New conversation"


async def make_title(model: ModelClient, task: str) -> str:
    """A short topic for a conversation: one small model call, never an error."""
    try:
        reply = await model.create(
            TITLE_PROMPT, [{"type": "user_input", "content": [{"type": "text", "text": task}]}], []
        )
    except Exception:  # a title must never break a run
        return fallback_title(task)
    title = reply.text.strip().strip("\"'“”").rstrip(".").strip()
    return title[:TITLE_CHARS] if title else fallback_title(task)


# ── Notes ────────────────────────────────────────────────────────────────────────


def note_path(root: Path, workspace: str, profile: str | None) -> Path:
    return root / "notes" / workspace / f"{profile or '_'}.md"


def load_notes(file: Path, budget_tokens: int = NOTES_BUDGET_TOKENS) -> str:
    """The notes for the prompt: whole lines, the newest that fit the budget."""
    if not file.is_file():
        return ""
    kept: list[str] = []
    used = 0
    for line in reversed(file.read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        used += len(line) + 1
        if used > budget_tokens * 4:
            break
        kept.append(line)
    return "\n".join(reversed(kept))


def list_notes(file: Path) -> list[str]:
    """Every saved fact, oldest first: for the page (the prompt gets ``load_notes``)."""
    if not file.is_file():
        return []
    return [line for line in file.read_text(encoding="utf-8").splitlines() if line.strip()]


def forget_note(file: Path, line: str) -> bool:
    """Remove one saved fact, chosen by the person on the page. False if it isn't there.

    The one place a memory file is rewritten rather than appended to: forgetting on request
    is the person's control over what the agent keeps (D-101).
    """
    lines = list_notes(file)
    if line not in lines:
        return False
    lines.remove(line)
    file.write_text("".join(f"{kept}\n" for kept in lines), encoding="utf-8")
    return True


def save_note_tool(file: Path) -> Tool:
    """``save_note``: the only way the agent keeps something for next time (D-92)."""

    @tool(risk="write")
    def save_note(
        note: Annotated[str, "One short fact worth remembering, in a sentence"],
    ) -> str:
        """Save one short note for yourself that you will see at the start of future tasks.
        Use it for a decision, a limit someone set, or a fact about the person's work that
        you could not look up again. Not for the conversation itself (that is kept already),
        and not for anything you can find with your tools."""
        text = " ".join(note.split())
        if not text:
            raise ValueError("The note is empty.")
        if len(text) > NOTE_MAX_CHARS:
            raise ValueError(f"A note is one short fact: at most {NOTE_MAX_CHARS} characters.")
        file.parent.mkdir(parents=True, exist_ok=True)
        with file.open("a", encoding="utf-8") as out:
            out.write(f"- {time.strftime('%Y-%m-%d')} · {text}\n")
        return "Saved. You will see it at the start of future tasks."

    return save_note
