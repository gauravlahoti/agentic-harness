"""The guided tour: recorded runs replayed on the page, step by step, with a voice (S13).

Harness part: the page (a demo of every other part, D-168). Reads
``<workspace>/tour/tour.toml`` and the recorded runs it names, checks every step, and builds
the JSON the page plays through its own ``onEvent()`` (D-171). Saves a voice clip for a step.

Does not: call a model, record sound (the browser does), or know any workspace's words:
captions, cards and runs all live in the workspace (D-172).
"""

import json
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

TOUR_DIR = "tour"
TOUR_FILE = "tour.toml"
AUDIO_DIR = "audio"
# What a browser records (Chrome: WebM/Opus, Safari: MP4/AAC) or a person drops in (D-176).
AUDIO_TYPES = {
    "audio/webm": ".webm",
    "audio/mp4": ".m4a",
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
}
MEDIA_TYPES = {ext: kind for kind, ext in AUDIO_TYPES.items()}
MAX_CLIP_BYTES = 5_000_000  # one step: several minutes of voice
MAX_AUDIO_BYTES = 15_000_000  # all clips together; the page must stay quick to load
WORDS_PER_SECOND = 2.5  # a calm speaking pace: a step with no clip waits this long (D-170)
DEFAULT_PAUSE = 0  # seconds between steps: the voice paces the tour, so none by default (D-182)
MAX_PAUSE = 60
# Harness pane parts a step may open; "pane" opens the pane with every part.
PARTS = {"pane", "loop", "context", "tools", "guard", "verify", "memory"}
# The diagram's big scenes (D-179); a step without one shows the small live diagram, "hud".
SCENES = {"jar", "harness", "finale", "hud"}
STEP_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
UNTIL = re.compile(r"([a-z_]+)#([1-9]\d*)")
# A cue mark in a caption: play the run up to this event when the voice gets here (D-180).
CUE = re.compile(r"\{([a-z_]+#[1-9]\d*)\}")

Event = dict[str, Any]


class TourError(ValueError):
    """The tour file, a run or a clip is wrong; the message says which and how."""


@dataclass(frozen=True)
class TourTurn:
    task: str  # what the person typed: the bubble the page shows
    events: tuple[Event, ...]


@dataclass(frozen=True)
class TourStep:
    id: str
    title: str
    say: str  # the caption, and the script you record
    show: str | None  # which Harness pane part opens
    card: str | None  # Markdown shown over the chat
    scene: str  # the diagram: a big scene, or the small live one (D-179)
    upto: int  # play the tour's events up to here (exclusive), counted over all turns
    cues: tuple[tuple[int, int], ...] = ()  # (word, upto): events released at that word (D-180)


@dataclass(frozen=True)
class Tour:
    folder: Path
    title: str
    chat: str
    profile: str | None
    person: str | None
    pause: int  # seconds between steps
    skip: frozenset[str]
    turns: tuple[TourTurn, ...]
    steps: tuple[TourStep, ...]

    @property
    def sequence(self) -> tuple[Event, ...]:
        """Every event the tour plays, all turns in order: what ``upto`` counts."""
        return tuple(e for turn in self.turns for e in turn.events)


def load_tour(workspace: Path) -> Tour | None:
    """The workspace's tour, checked; None if it has none."""
    folder = workspace / TOUR_DIR
    file = folder / TOUR_FILE
    if not file.is_file():
        return None
    try:
        config = tomllib.loads(file.read_text())
    except tomllib.TOMLDecodeError as error:
        raise TourError(f"{file}: {error}") from None
    skip = frozenset(_strings(config, "skip"))
    turns = tuple(_turn(folder / name, skip) for name in _strings(config, "runs"))
    sequence = [e for turn in turns for e in turn.events]
    steps: list[TourStep] = []
    for raw in config.get("steps", []):
        step = _step(raw, sequence, steps[-1] if steps else None)
        if any(s.id == step.id for s in steps):
            raise TourError(f"Two steps are called {step.id!r}.")
        steps.append(step)
    if not steps:
        raise TourError(f"{file}: add at least one [[steps]].")
    return Tour(
        folder=folder,
        title=_text(config, "title"),
        chat=str(config.get("chat") or config.get("title", "")),
        profile=config.get("profile"),
        person=config.get("person"),
        pause=_pause(config),
        skip=skip,
        turns=turns,
        steps=tuple(steps),
    )


def clip_for(tour: Tour, step_id: str) -> Path | None:
    """The step's recorded clip, whichever kind it is, or None."""
    for ext in MEDIA_TYPES:
        clip = tour.folder / AUDIO_DIR / f"{step_id}{ext}"
        if clip.is_file():
            return clip
    return None


def save_clip(tour: Tour, step_id: str, data: bytes, content_type: str) -> Path:
    """Save a step's clip, replacing any earlier one. Only into the tour's audio folder."""
    if step_id not in {s.id for s in tour.steps}:
        raise TourError(f"No step {step_id!r} in this tour.")
    ext = AUDIO_TYPES.get(content_type.split(";")[0].strip().lower())
    if ext is None:
        raise TourError(f"A clip's type must be one of {', '.join(AUDIO_TYPES)}.")
    if len(data) > MAX_CLIP_BYTES:
        raise TourError(f"A clip may be at most {MAX_CLIP_BYTES // 1_000_000} MB.")
    others = sum(
        clip.stat().st_size
        for s in tour.steps
        if s.id != step_id and (clip := clip_for(tour, s.id)) is not None
    )
    if others + len(data) > MAX_AUDIO_BYTES:
        raise TourError(f"All clips together may be at most {MAX_AUDIO_BYTES // 1_000_000} MB.")
    (tour.folder / AUDIO_DIR).mkdir(exist_ok=True)
    while (old := clip_for(tour, step_id)) is not None:
        old.unlink()  # one clip per step: a new take replaces the old, whatever its kind
    clip = tour.folder / AUDIO_DIR / f"{step_id}{ext}"
    clip.write_bytes(data)
    return clip


def tour_payload(tour: Tour, *, audio_url: Callable[[str, int], str]) -> dict[str, Any]:
    """What the page plays. ``audio_url(step, version)`` says where each clip is served:
    the local server here, a static file once exported."""
    first = next((e for e in tour.sequence if e.get("type") == "run_started"), {})
    steps = []
    for s in tour.steps:
        clip = clip_for(tour, s.id)
        steps.append(
            {
                "id": s.id,
                "title": s.title,
                "say": s.say,
                "show": s.show,
                "card": s.card,
                "scene": s.scene,
                "cues": [{"word": w, "upto": u} for w, u in s.cues],
                "upto": s.upto,
                # The version changes with every new take, so the browser fetches the new one.
                "audio": audio_url(s.id, clip.stat().st_mtime_ns) if clip else None,
                "seconds": round(len(s.say.split()) / WORDS_PER_SECOND, 1),
            }
        )
    return {
        "title": tour.title,
        "chat": tour.chat,
        "profile": tour.profile,
        "person": tour.person,
        "pause": tour.pause,
        "model": first.get("data", {}).get("model"),
        "turns": [{"task": t.task, "events": list(t.events)} for t in tour.turns],
        "steps": steps,
    }


def _turn(file: Path, skip: frozenset[str]) -> TourTurn:
    """One recorded run: its trace lines, minus the hidden kinds of event."""
    if not file.is_file():
        raise TourError(f"The tour names a run that isn't there: {file}")
    try:
        events = [json.loads(line) for line in file.read_text().splitlines() if line.strip()]
    except json.JSONDecodeError as error:
        raise TourError(f"{file}: not a trace ({error})") from None
    task = next(
        (
            e["data"].get("task", "")
            for e in events
            if e.get("type") == "run_started" and not e.get("data", {}).get("agent_id")
        ),
        "",
    )
    if not task:
        raise TourError(f"{file}: no run_started with a task; is it a trace?")
    return TourTurn(task=task, events=tuple(e for e in events if e.get("type") not in skip))


def _step(raw: Any, sequence: list[Event], before: TourStep | None) -> TourStep:
    if not isinstance(raw, dict):
        raise TourError("Each [[steps]] must be a table.")
    step_id = str(raw.get("id", ""))
    if not STEP_ID.fullmatch(step_id):
        raise TourError(f"Step id {step_id!r}: use lowercase letters, digits and dashes.")
    say = raw.get("say")
    if not isinstance(say, str) or not say.strip():
        raise TourError(f"Step {step_id}: add `say`, the caption you record.")
    show = raw.get("show")
    if show is not None and show not in PARTS:
        raise TourError(f"Step {step_id}: `show` must be one of {', '.join(sorted(PARTS))}.")
    start = before.upto if before else 0
    until = raw.get("until")
    upto = start if until is None else _position(step_id, str(until), sequence)
    if upto < start:
        raise TourError(f"Step {step_id} stops before the step ahead of it: steps only go forward.")
    text, cues = _cues(step_id, say, sequence, start, upto)
    card = raw.get("card")
    scene = raw.get("scene", "hud")
    if scene not in SCENES:
        raise TourError(f"Step {step_id}: `scene` must be one of {', '.join(sorted(SCENES))}.")
    return TourStep(
        id=step_id,
        title=str(raw.get("title") or step_id),
        say=text,
        show=show,
        card=card.strip() if isinstance(card, str) and card.strip() else None,
        upto=upto,
        scene=scene,
        cues=cues,
    )


def _cues(
    step_id: str, say: str, sequence: list[Event], start: int, upto: int
) -> tuple[str, tuple[tuple[int, int], ...]]:
    """Take the cue marks out of a caption: each becomes (the word it sits before, how far
    the run plays). They only move forward and stay inside the step (D-180)."""
    words: list[str] = []
    cues: list[tuple[int, int]] = []
    last = start
    for piece in CUE.split(say):
        if CUE.fullmatch("{" + piece + "}") and UNTIL.fullmatch(piece):
            at = _position(step_id, piece, sequence)
            if at < last:
                raise TourError(f"Step {step_id}: cue {{{piece}}} goes back in the run.")
            if at > upto:
                raise TourError(f"Step {step_id}: cue {{{piece}}} plays past the step's `until`.")
            cues.append((len(words), at))
            last = at
        else:
            words.extend(piece.split())
    return " ".join(words), tuple(cues)


def _position(step_id: str, until: str, sequence: list[Event]) -> int:
    """``"tool_finished#2"`` → just after the main agent's 2nd tool_finished (D-177)."""
    if until == "end":
        return len(sequence)
    match = UNTIL.fullmatch(until)
    if match is None:
        raise TourError(
            f'Step {step_id}: until {until!r} must look like "tool_finished#2" or "end".'
        )
    kind, nth = match[1], int(match[2])
    seen = 0
    for i, event in enumerate(sequence):
        # A helper's events play along but aren't counted: its numbering would be confusing.
        if event.get("type") == kind and not event.get("data", {}).get("agent_id"):
            seen += 1
            if seen == nth:
                return i + 1
    raise TourError(f"Step {step_id}: until {until!r}, but the runs have only {seen} of those.")


def _pause(config: dict[str, Any]) -> int:
    value = config.get("pause", DEFAULT_PAUSE)
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= MAX_PAUSE:
        raise TourError(f"`pause` must be whole seconds from 0 to {MAX_PAUSE}.")
    return value


def _text(config: dict[str, Any], key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TourError(f"The tour needs `{key}`.")
    return value.strip()


def _strings(config: dict[str, Any], key: str) -> list[str]:
    value = config.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise TourError(f"`{key}` must be a list of strings.")
    return value
