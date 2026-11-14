"""The guided tour: recorded runs replayed step by step, with a voice (S13, D-168 to D-177).

No model is called: the tour plays saved trace events. These tests check the tour file,
the JSON the page plays, the clip rules and the local routes.
"""

import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_harness.config import Settings
from agentic_harness.server.app import create_app
from agentic_harness.tour import (
    DEFAULT_PAUSE,
    MAX_CLIP_BYTES,
    WORDS_PER_SECOND,
    TourError,
    load_tour,
    save_clip,
    tour_payload,
)
from agentic_harness.workspace import Workspace

CLOUDCO = Path(__file__).parents[2] / "workspaces" / "cloudco"
PAGE = {"X-Harness-Page": "1"}


@pytest.fixture
def ws_copy(tmp_path: Path) -> Path:
    """A copy of the workspace, so a test may break its tour or save clips."""
    copy = shutil.copytree(CLOUDCO, tmp_path / "cloudco", ignore=shutil.ignore_patterns("audio"))
    (copy / "tour" / "audio").mkdir()
    return copy


def edit_tour(ws: Path, old: str, new: str) -> None:
    file = ws / "tour" / "tour.toml"
    text = file.read_text()
    assert old in text, old
    file.write_text(text.replace(old, new, 1))


def test_s13_ac1_the_workspace_tour_loads_and_every_step_is_complete() -> None:
    tour = load_tour(CLOUDCO)
    assert tour is not None
    assert len(tour.steps) >= 5
    ids = [s.id for s in tour.steps]
    assert len(ids) == len(set(ids))
    for step in tour.steps:
        assert step.title, step.id
        assert step.say.strip(), step.id
    # Each step stops at or after the one before: the replay only moves forward.
    ends = [s.upto for s in tour.steps]
    assert ends == sorted(ends)
    assert ends[-1] == len(tour.sequence)  # the last live step plays the run to its end
    assert tour.turns
    assert all(t.task for t in tour.turns)


def test_s13_ac1_a_step_must_have_a_caption(ws_copy: Path) -> None:
    edit_tour(ws_copy, 'say = """', 'said = """')
    with pytest.raises(TourError, match="say"):
        load_tour(ws_copy)


def test_s13_ac1_until_must_name_an_event_that_happens(ws_copy: Path) -> None:
    edit_tour(ws_copy, 'until = "tool_finished#2"', 'until = "tool_finished#99"')
    with pytest.raises(TourError, match="tool_finished#99"):
        load_tour(ws_copy)
    edit_tour(ws_copy, 'until = "tool_finished#99"', 'until = "no_such_event#1"')
    with pytest.raises(TourError, match="no_such_event#1"):
        load_tour(ws_copy)


def test_s13_ac1_steps_may_not_go_backwards(ws_copy: Path) -> None:
    edit_tour(ws_copy, 'until = "tool_finished#4"', 'until = "run_started#1"')
    with pytest.raises(TourError, match="before"):
        load_tour(ws_copy)


def test_s13_ac1_a_missing_run_file_is_named(ws_copy: Path) -> None:
    (ws_copy / "tour" / "runs" / "2-send.jsonl").unlink()
    with pytest.raises(TourError, match=r"2-send\.jsonl"):
        load_tour(ws_copy)


def test_s13_ac1_a_workspace_without_a_tour_has_none(ws_copy: Path) -> None:
    shutil.rmtree(ws_copy / "tour")
    assert load_tour(ws_copy) is None


def test_s13_ac1_helper_events_play_but_are_not_counted(ws_copy: Path) -> None:
    tour = load_tour(ws_copy)
    assert tour is not None
    helpers = [e for e in tour.sequence if e.get("data", {}).get("agent_id")]
    assert helpers, "the recorded run hands work to a helper"
    # model_replied#4 is the main agent's 4th reply, after the helper's own replies.
    main_replies = [
        i
        for i, e in enumerate(tour.sequence)
        if e.get("type") == "model_replied" and not e["data"].get("agent_id")
    ]
    helper_at = tour.sequence.index(helpers[0])
    assert main_replies[2] < helper_at < main_replies[3]


def test_s13_ac1_skipped_event_types_never_reach_the_page() -> None:
    tour = load_tour(CLOUDCO)
    assert tour is not None
    assert tour.skip  # the online evals are not part of a harness tour
    assert not [e for e in tour.sequence if e.get("type") in tour.skip]


def test_s13_ac8_a_step_without_a_clip_waits_its_reading_time(ws_copy: Path) -> None:
    tour = load_tour(ws_copy)
    assert tour is not None
    payload = tour_payload(tour, audio_url=lambda step, version: f"a/{step}?v={version}")
    first = payload["steps"][0]
    assert first["audio"] is None
    words = len(tour.steps[0].say.split())
    assert first["seconds"] == pytest.approx(words / WORDS_PER_SECOND, abs=0.1)


def test_s13_ac8_a_saved_clip_is_used_and_replaces_the_old_one(ws_copy: Path) -> None:
    tour = load_tour(ws_copy)
    assert tour is not None
    step = tour.steps[0].id
    save_clip(tour, step, b"x" * 100, "audio/webm;codecs=opus")
    save_clip(tour, step, b"y" * 50, "audio/mp4")
    files = sorted(p.name for p in (ws_copy / "tour" / "audio").iterdir())
    assert files == [f"{step}.m4a"]  # one clip per step, the newest
    payload = tour_payload(tour, audio_url=lambda s, v: f"a/{s}?v={v}")
    assert payload["steps"][0]["audio"].startswith(f"a/{step}?v=")


def test_s13_ac8_clips_are_checked(ws_copy: Path) -> None:
    tour = load_tour(ws_copy)
    assert tour is not None
    step = tour.steps[0].id
    with pytest.raises(TourError, match="step"):
        save_clip(tour, "../../evil", b"x", "audio/webm")
    with pytest.raises(TourError, match="type"):
        save_clip(tour, step, b"x", "text/html")
    with pytest.raises(TourError, match="MB"):
        save_clip(tour, step, b"x" * (MAX_CLIP_BYTES + 1), "audio/webm")


def test_s13_ac8_all_clips_together_stay_under_the_budget(ws_copy: Path) -> None:
    tour = load_tour(ws_copy)
    assert tour is not None
    big = b"x" * (MAX_CLIP_BYTES - 10)
    for step in tour.steps[:3]:  # three near-5 MB clips fit under 15 MB
        save_clip(tour, step.id, big, "audio/webm")
    with pytest.raises(TourError, match="15 MB"):
        save_clip(tour, tour.steps[3].id, big, "audio/webm")


def app_for(ws: Path, tmp_path: Path) -> TestClient:
    settings = Settings()
    app = create_app(settings, workspace=Workspace.load(ws), memory_dir=tmp_path / "mem")
    return TestClient(app, base_url="http://127.0.0.1")


def test_s13_ac1_the_server_serves_the_tour(ws_copy: Path, tmp_path: Path) -> None:
    client = app_for(ws_copy, tmp_path)
    body = client.get("/api/tour").json()
    for key in ("title", "steps", "turns", "profile", "person"):
        assert body[key], key
    assert all("upto" in s for s in body["steps"])
    # The page plays exactly the saved events: same shape as the live stream.
    first = body["turns"][0]["events"][0]
    assert first["type"] == "run_started"
    assert "data" in first


def test_s13_ac1_no_tour_is_a_404(ws_copy: Path, tmp_path: Path) -> None:
    shutil.rmtree(ws_copy / "tour")
    assert app_for(ws_copy, tmp_path).get("/api/tour").status_code == 404


def test_s13_ac8_recording_a_clip_needs_the_page_and_a_real_step(
    ws_copy: Path, tmp_path: Path
) -> None:
    client = app_for(ws_copy, tmp_path)
    step = client.get("/api/tour").json()["steps"][0]["id"]
    clip = {"content": b"voice", "headers": {"Content-Type": "audio/webm"}}
    assert client.put(f"/api/tour/audio/{step}", **clip).status_code == 403  # type: ignore[arg-type]
    headers = {**PAGE, "Content-Type": "audio/webm"}
    assert client.put("/api/tour/audio/nope", content=b"v", headers=headers).status_code == 400
    saved = client.put(f"/api/tour/audio/{step}", content=b"voice", headers=headers)
    assert saved.status_code == 200
    url = client.get("/api/tour").json()["steps"][0]["audio"]
    got = client.get(url)
    assert got.status_code == 200
    assert got.content == b"voice"
    assert got.headers["content-type"].startswith("audio/webm")


def test_s13_ac5_the_page_has_a_tour_mode_that_writes_nothing() -> None:
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    html = (web / "index.html").read_text()
    js = (web / "app.js").read_text()
    tour_js = (web / "tour.js").read_text()
    assert 'id="tour-bar"' in html
    assert "/static/tour.js" in html
    for label in (">Start Tour<", ">Previous<", ">Next<", ">Mute<"):
        assert label in html, label
    assert 'let TOUR = new URLSearchParams(location.search).get("tour")' in js
    assert "if (TOUR) return; // the tour sends nothing" in js  # approvals
    assert "if (TOUR) return renderWork(); // the tour's own chat only" in js
    assert "onEvent(" in tour_js  # the page's own drawing code (D-171)
    assert 'fetch("/api/run"' not in tour_js
    assert '"/api/tour"' in tour_js


def test_s13_ac5_the_tour_pauses_between_steps(ws_copy: Path) -> None:
    """D-182: the next step starts when the voice ends; a pause only if the tour sets one."""
    tour = load_tour(ws_copy)
    assert tour is not None
    payload = tour_payload(tour, audio_url=lambda s, v: f"a/{s}?v={v}")
    assert payload["pause"] == DEFAULT_PAUSE == 0
    assert "guide" not in payload  # your call: no name on the guide
    edit_tour(ws_copy, 'chat = "', 'pause = 4\nchat = "')
    tour = load_tour(ws_copy)
    assert tour is not None
    assert tour.pause == 4
    edit_tour(ws_copy, "pause = 4", "pause = 600")
    with pytest.raises(TourError, match="pause"):
        load_tour(ws_copy)


def test_s13_ac6_steps_name_their_scene(ws_copy: Path) -> None:
    """D-179, D-185: the brain in a jar, the harness built part by part, the finale; else the
    live diagram."""
    tour = load_tour(ws_copy)
    assert tour is not None
    scenes = [s["scene"] for s in tour_payload(tour, audio_url=lambda s, v: "")["steps"]]
    assert scenes[0] == "jar"
    assert scenes[1] == "build"
    assert scenes[-1] == "finale"
    assert "hud" in scenes  # the replay steps show the small live diagram
    edit_tour(ws_copy, 'scene = "jar"', 'scene = "fireworks"')
    with pytest.raises(TourError, match="scene"):
        load_tour(ws_copy)


def test_s13_ac5_the_page_shows_a_voice_orb_diagram_and_spotlight() -> None:
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    html = (web / "index.html").read_text()
    tour_js = (web / "tour.js").read_text()
    assert 'id="guide-avatar"' in html  # the voice orb
    assert 'id="guide-name"' not in html  # no name (your call)
    assert 'id="tour-stage"' in html  # the living diagram
    assert 'id="tour-spot"' in html  # the spotlight
    assert "createAnalyser" in tour_js  # the orb moves with the real voice
    assert "function sentences(" in tour_js  # captions one sentence at a time
    assert "Next in" in tour_js  # the countdown before the next step


def test_s13_dark_is_the_default_theme_with_the_sites_cyan() -> None:
    """D-179: black by default with a cyan accent, like gauravlahoti.dev; light stays."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    assert '<meta name="color-scheme" content="dark">' in (web / "index.html").read_text()
    assert 'const DEFAULT_SCHEME = "dark";' in (web / "theme.js").read_text()
    assert "--accent: light-dark(#0b7f70, #19e6c8)" in (web / "app.css").read_text()


def test_s13_ac5_the_tour_can_be_left_for_the_normal_page() -> None:
    """Your request: an option to exit the tour and go back to the normal page (Esc too)."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    assert ">Exit Tour<" in (web / "index.html").read_text()
    tour_js = (web / "tour.js").read_text()
    assert "function exitTour(" in tour_js
    assert '"Escape"' in tour_js


def test_s13_ac5_a_button_in_the_sidebar_starts_the_tour() -> None:
    """Your request: the tour starts from a highlighted "Want a Guided Tour?" in the left pane."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    html = (web / "index.html").read_text()
    sidebar = html[html.index('<aside class="sidebar"') : html.index("</aside>")]
    assert 'id="tour-invite"' in sidebar
    assert "Want a Guided Tour?" in sidebar
    tour_js = (web / "tour.js").read_text()
    assert "async function startTour(" in tour_js
    assert 'history.pushState(null, "", ' in tour_js  # same page: the click lets the voice play


def test_s13_ac5_cue_marks_tie_events_to_the_words(ws_copy: Path) -> None:
    """D-180: `{event#n}` in a caption plays the run up to that event when the voice gets there."""
    tour = load_tour(ws_copy)
    assert tour is not None
    steps = tour_payload(tour, audio_url=lambda s, v: "")["steps"]
    context = next(s for s in steps if s["id"] == "04-context")
    assert "{" not in context["say"]  # the marks never show in the subtitles
    assert context["cues"], "the context step ties its events to its words"
    words = [c["word"] for c in context["cues"]]
    ends = [c["upto"] for c in context["cues"]]
    assert words == sorted(words)
    assert ends == sorted(ends)
    assert ends[-1] <= context["upto"]
    assert all(c["word"] <= len(context["say"].split()) for c in context["cues"])


def test_s13_ac5_a_cue_must_name_a_real_event_within_its_step(ws_copy: Path) -> None:
    edit_tour(ws_copy, "{tool_finished#1}", "{tool_finished#99}")
    with pytest.raises(TourError, match="tool_finished#99"):
        load_tour(ws_copy)


def test_s13_ac5_a_cue_may_not_play_past_its_step(ws_copy: Path) -> None:
    edit_tour(ws_copy, "{tool_finished#1}", "{run_finished#2}")
    with pytest.raises(TourError, match="past"):
        load_tour(ws_copy)


def test_s13_ac6_pop_marks_pop_each_part_as_the_voice_names_it(ws_copy: Path) -> None:
    """D-184: `{pop:part}` in a caption pops that diagram part when the voice reaches the word."""
    tour = load_tour(ws_copy)
    assert tour is not None
    steps = tour_payload(tour, audio_url=lambda s, v: "")["steps"]
    harness = next(s for s in steps if s["id"] == "02-harness")
    assert "{" not in harness["say"]  # the marks never show in the subtitles
    assert [p["part"] for p in harness["pops"]] == ["loop", "context", "tools", "guard"]
    words = harness["say"].split()
    names = ["agentic", "context", "tools,", "guardrails."]
    for pop, name in zip(harness["pops"], names, strict=True):
        assert words[pop["word"]] == name  # each pop sits on the word that names its part
    assert all(s["pops"] == [] for s in steps if s["id"] != "02-harness")


def test_s13_ac6_the_harness_is_built_part_by_part_then_shown_whole(ws_copy: Path) -> None:
    """D-185: step 1 is the model alone (the jar). Step 2 starts bare; each part pops in as
    the voice names it; then a scene mark shows the whole harness and its equation."""
    tour = load_tour(ws_copy)
    assert tour is not None
    intro, harness = tour_payload(tour, audio_url=lambda s, v: "")["steps"][:2]
    assert intro["scene"] == "jar"
    assert intro["pops"] == []
    assert intro["scenes"] == []
    assert intro["say"].startswith("Welcome.")
    assert harness["scene"] == "build"
    words = harness["say"].split()
    assert [(s["scene"], words[s["word"]]) for s in harness["scenes"]] == [("harness", "You")]
    assert harness["scenes"][0]["word"] > harness["pops"][-1]["word"]  # the parts, then the whole


def test_s13_ac6_a_scene_mark_must_name_a_scene(ws_copy: Path) -> None:
    edit_tour(ws_copy, "{scene:harness}", "{scene:moon}")
    with pytest.raises(TourError, match="moon"):
        load_tour(ws_copy)


def test_s13_ac6_a_pop_must_name_a_diagram_part(ws_copy: Path) -> None:
    edit_tour(ws_copy, "{pop:tools}", "{pop:wheels}")
    with pytest.raises(TourError, match="wheels"):
        load_tour(ws_copy)


def test_s13_ac5_the_guide_can_be_hidden_and_shown_again() -> None:
    """D-186, your request: hide the guide strip to keep your focus on the page; the voice
    and the replay carry on, and Show Guide brings it back."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    page = (web / "index.html").read_text()
    assert 'id="tour-hide"' in page
    assert ">Hide Guide<" in page
    assert 'id="tour-show"' in page
    assert ">Show Guide<" in page
    tour_js = (web / "tour.js").read_text()
    assert "function tuckGuide(" in tour_js
    assert ".is-tucked" in (web / "app.css").read_text()


# ── D-191: the model-alone story, in beats, and the agenda chips ───────────────────────────


def test_s13_ac6_step_one_tells_the_model_alone_story_in_beats() -> None:
    tour = load_tour(CLOUDCO)
    assert tour is not None
    first = tour.steps[0]
    words = first.say.split()
    beats = [(b, words[i]) for i, b in first.beats]
    assert beats == [
        ("think", "AI"),
        ("reach", "But"),
        ("seal", "jar:"),
        ("tell", "It"),
        ("bounce", "it"),
    ]
    assert [n for _, n in first.chip_marks] == [1, 2, 3]
    assert len(first.chips) == 3  # the voice names three things, so the screen shows three
    assert "{" not in first.say  # marks never show in the subtitles


def test_s13_ac6_beats_and_chips_reach_the_page(ws_copy: Path) -> None:
    tour = load_tour(ws_copy)
    assert tour is not None
    step = tour_payload(tour, audio_url=lambda s, v: "")["steps"][0]
    assert [b["beat"] for b in step["beats"]] == ["think", "reach", "seal", "tell", "bounce"]
    assert step["chips"][0]
    assert [c["chip"] for c in step["chip_marks"]] == [1, 2, 3]


def test_s13_ac6_a_beat_must_be_known(ws_copy: Path) -> None:
    edit_tour(ws_copy, "{beat:tell}", "{beat:dance}")
    with pytest.raises(TourError, match="dance"):
        load_tour(ws_copy)


def test_s13_ac6_a_chip_mark_needs_its_chip(ws_copy: Path) -> None:
    edit_tour(ws_copy, "{chip:3}", "{chip:4}")
    with pytest.raises(TourError, match="3 chips"):
        load_tour(ws_copy)


def test_s13_ac6_chips_stay_short_and_few(ws_copy: Path) -> None:
    edit_tour(ws_copy, '"What a harness is"', '"' + "x" * 41 + '"')
    with pytest.raises(TourError, match="40 characters"):
        load_tour(ws_copy)


def test_s13_ac6_the_stage_has_the_story_and_the_chips() -> None:
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    page = (web / "index.html").read_text()
    script = (web / "tour.js").read_text()
    for part in (
        "stage-story",
        "story-skills",
        "story-actions",
        "story-bubble",
        "story-bounce",
        "stage-chips",
    ):
        assert part in page, part
    assert "dataset.beat" in script


def test_s14_switches_are_shown_but_locked_for_visitors_and_the_note_links_the_code() -> None:
    """D-193, your review: in the tour and on the hosted copy the Harness switches show their
    state but can't be changed (the owner's session still can); the hosted note is quiet,
    with the GitHub mark and View the Code."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    app_js = (web / "app.js").read_text()
    switch = app_js.split("function switchFor")[1].split("\nfunction ")[0]
    assert '".tour-mode, .public-mode:not(.owner-mode)"' in switch
    assert "event.preventDefault()" in switch
    page = (web / "index.html").read_text()
    assert 'id="tpl-github"' in page
    public = app_js.split("function showPublicMode")[1].split("\nfunction ")[0]
    assert 'fromTemplate("tpl-github"), "View the Code"' in public


def test_s14_the_tour_never_claims_no_plan_before_the_plan_arrives() -> None:
    """D-194, your review: "No To-Do plan" showed at the first tool call, then the recorded
    run wrote its To-Do list. The tour leaves that line out; the normal page is unchanged."""
    app_js = (Path(__file__).parents[2] / "src" / "agentic_harness" / "web" / "app.js").read_text()
    assert "if (turn.planOn && !turn.todo && !turn.direct && !TOUR) {" in app_js


def test_s13_ac6_the_hosted_welcome_comes_from_the_tour(ws_copy: Path) -> None:
    """D-206: the welcome after Exit is workspace words, so the player knows no domain."""
    tour = load_tour(ws_copy)
    assert tour is not None
    welcome = tour_payload(tour, audio_url=lambda s, v: "")["welcome"]
    assert welcome["start"] == "Start the Guided Tour"
    assert welcome["title"].endswith("?")
    edit_tour(ws_copy, 'aside = "', 'colour = "')
    with pytest.raises(TourError, match="colour"):
        load_tour(ws_copy)


def test_s13_ac5_the_guide_keeps_one_size() -> None:
    """D-208, your review: the capsule's height moved with the subtitle. The caption is always
    two lines tall, and long sentences split into cards that fit those two lines."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    script = (web / "tour.js").read_text()
    css = (web / "app.css").read_text()
    assert "function captionCards(text)" in script
    assert "const parts = captionCards(step.say);" in script
    caption = css.split(".guide-caption {")[1].split("}")[0]
    assert "height: 3em;" in caption
    assert "overflow: hidden;" in caption


def test_s13_ac6_the_pane_never_gets_a_cyan_outline() -> None:
    """D-209, your review: no cyan highlight round the Harness pane at any step."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    assert "tour-whole" not in (web / "tour.js").read_text()
    assert "tour-whole" not in (web / "app.css").read_text()


def test_s13_ac7_the_pane_spotlights_the_part_being_explained() -> None:
    """Your request: when the voice explains a part (context, memory, verification...), that
    pane section stays bright and the other sections grey out. A whole-pane step greys nothing,
    and leaving the tour clears it."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    script = (web / "tour.js").read_text()
    css = (web / "app.css").read_text()
    assert "is-dimmed" in script
    assert "tour-pane-focus" in script
    assert ".tour-pane-focus .pane-part.is-dimmed" in css
    dim = css.split(".tour-pane-focus .pane-part.is-dimmed {")[1].split("}")[0]
    assert "opacity" in dim
    assert "grayscale" in dim
    # The pane never gets a cyan outline (D-209): the dim is the only cue.
    assert "tour-whole" not in script


def test_s13_ac7_the_sidebar_can_be_collapsed_like_the_harness_pane() -> None:
    """Your request: a toggle hides the sidebar and a button brings it back."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    html = (web / "index.html").read_text()
    css = (web / "app.css").read_text()
    js = (web / "app.js").read_text()
    for piece in ('id="sidebar-close"', 'id="sidebar-toggle"', 'aria-controls="sidebar"'):
        assert piece in html
    assert "function setSidebarOpen(" in js
    assert "SIDEBAR_OPEN" in js
    assert "body.sidebar-collapsed" in css


def test_s14_no_step_reopens_a_pane_part_already_explained(ws_copy: Path) -> None:
    """Your review: "The Answer" reopened the Agentic Loop that step 5 had already covered.
    Each pane part is the spotlight of one step; later steps ask for another part or none."""
    tour = load_tour(ws_copy)
    assert tour is not None
    steps = tour_payload(tour, audio_url=lambda s, v: "")["steps"]
    parts = [s["show"] for s in steps if s["show"] not in (None, "pane")]
    assert len(parts) == len(set(parts)), parts


def test_s14_lit_marks_name_the_pane_row_the_voice_is_explaining(ws_copy: Path) -> None:
    """Voice highlight: `{lit:row}` lights that Harness pane row when the voice reaches the word."""
    tour = load_tour(ws_copy)
    assert tour is not None
    steps = tour_payload(tour, audio_url=lambda s, v: "")["steps"]
    context = next(s for s in steps if s["id"] == "04-context")
    assert "{" not in context["say"]  # the marks never show in the subtitles
    assert [m["row"] for m in context["lits"]] == [
        "files",
        "skills",
        "window",
        "summarize",
        "prune",
    ]
    words = context["say"].split()
    sits_on = ["the", "Skills", "When", "summarises", "prunes"]
    for mark, word in zip(context["lits"], sits_on, strict=True):
        assert words[mark["word"]] == word  # each mark sits on the word that names its row
    assert all(s["lits"] == [] for s in steps if s["id"] != "04-context")


def test_s14_a_lit_mark_must_name_a_known_row(ws_copy: Path) -> None:
    edit_tour(ws_copy, "{lit:skills} Skills", "{lit:nonsense} Skills")
    with pytest.raises(TourError, match="nonsense"):
        load_tour(ws_copy)


def test_s14_the_pane_rows_carry_the_names_the_marks_use() -> None:
    """The page tags each row with data-lit, lights it only in the tour, and clears it after."""
    web = Path(__file__).parents[2] / "src" / "agentic_harness" / "web"
    app_js = (web / "app.js").read_text()
    for row in ("files", "skills", "window", "prune", "summarize"):
        assert f'"{row}"' in app_js, row
    assert "data-lit" in app_js or "dataset.lit" in app_js
    tour_js = (web / "tour.js").read_text()
    assert "function lightRow(" in tour_js
    assert "step.lits" in tour_js
    css = (web / "app.css").read_text()
    assert ".tour-mode [data-lit].is-lit" in css  # never lit in the normal app
