"""The hosted tour on a phone (S14, D-214). Your review, 2026-11-13: "mobile users are our
primary audience". At 390 px the sidebar stacked above the page and took 40% of the screen,
the story graphic sat under it or off the right edge, the page scrolled sideways, and the
guide capsule took a quarter of the screen with Exit Tour on a row of its own.

- AC28: on a phone a visitor's sidebar is one slim top bar: logo, name, Code, theme.
- AC29: the guide is compact: the orb in the title line, the timeline over one row of
  36 px controls, Exit as an icon.
- AC30: the story graphic fits between the top bar and the guide; nothing scrolls sideways.
"""

from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "src" / "agentic_harness" / "web"
CSS = (WEB / "app.css").read_text()
TOUR = (WEB / "tour.js").read_text()
PHONE = CSS[CSS.index("/* ── Phones (D-214)") :]


def test_s14_ac28_a_visitors_sidebar_is_a_slim_top_bar_on_a_phone() -> None:
    assert "@media (max-width: 720px)" in PHONE
    assert ".public-mode:not(.owner-mode) .sidebar {" in PHONE
    assert "position: sticky;" in PHONE
    # Only the brand, the Code link and the theme switch stay.
    assert ".sidebar > :not(.org, .public-note, .sidebar-foot) { display: none; }" in PHONE
    assert ".public-text { display: none; }" in PHONE
    assert ".version { display: none; }" in PHONE


def test_s14_ac29_the_guide_is_compact_on_a_phone() -> None:
    assert "@media (max-width: 600px)" in PHONE
    assert ".guide-orb { position: absolute;" in PHONE
    assert ".tour-timeline { order: -1; flex: 0 0 100%;" in PHONE
    assert ".tour-icon { width: 36px; height: 36px; }" in PHONE
    assert ".tour-exit { width: 36px; height: 36px;" in PHONE  # an icon, the words hidden
    assert ".tour-countdown:empty { display: none; }" in PHONE


def test_s14_ac30_the_story_fits_between_bar_and_guide_and_nothing_scrolls_sideways() -> None:
    assert "html, body { overflow-x: clip; }" in PHONE
    assert "main { min-width: 0; }" in PHONE  # the column shrinks; it isn't just clipped
    assert ".thread { min-width: 0; overflow-wrap: anywhere; }" in PHONE
    assert ".public-mode:not(.owner-mode) .pane-toggle { display: none; }" in PHONE
    assert ".welcome-aside { display: none; }" in PHONE
    assert "function phoneStage(" in TOUR
    assert 'const guide = $("tour-bar").getBoundingClientRect().top;' in TOUR
    assert 'const bar = $("sidebar").getBoundingClientRect().bottom;' in TOUR


def test_s14_ac31_below_the_pane_width_the_lit_row_shows_as_a_card_above_the_guide() -> None:
    """Your review: on a phone the Harness pane isn't visible, so the voice highlight showed
    nothing. The lit row's own words float above the guide, with its part's name over them.
    The guide keeps its fixed height (D-208): the card is positioned, never in the flow."""
    html = (WEB / "index.html").read_text()
    guide = html[html.index('id="tour-bar"') : html.index('id="tour-show"')]
    assert 'id="tour-lit"' in guide
    assert 'class="guide-lit-part"' in guide
    assert 'class="guide-lit-text"' in guide
    assert "function showLitCard(" in TOUR
    assert "if (roomForPane() || !nodes?.length)" in TOUR  # a visible pane glows itself; no card
    assert 'closest(".pane-part")' in TOUR  # the part's name comes from the row's own part
    lit_rule = CSS[CSS.index(".tour-mode .guide-lit {") :]  # tour only
    lit_rule = lit_rule[: lit_rule.index("}")]
    assert "position: absolute;" in lit_rule
    assert "bottom: calc(100% + 8px);" in lit_rule
