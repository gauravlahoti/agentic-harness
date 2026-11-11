"""The page's design baseline stays in place (spec/02-ui.md → Design baseline; S01-AC13).

New stages add to the page; they must not drop what we agreed. If one of these fails,
a change removed part of the baseline: put it back, or change the baseline with you first.
"""

from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "src" / "agentic_harness" / "web"
HTML = (WEB / "index.html").read_text()
CSS = (WEB / "app.css").read_text()
JS = (WEB / "app.js").read_text()


def test_s01_ac13_agent_view_pieces_are_present() -> None:
    for piece in (
        'id="thread"',  # the conversation
        'id="composer"',  # the docked input box
        'class="dock"',
        'id="model"',  # the model menu
        "<selectedcontent>",  # customizable select
        'id="send"',
        'id="tpl-chevron"',  # activity lines open
        'id="theme-toggle"',
        'id="view-checks"',
        'id="profile"',  # profile menu (S02)
    ):
        assert piece in HTML, f"baseline piece missing from index.html: {piece}"


def test_s01_ac13_styles_keep_the_agreed_look() -> None:
    for rule in (
        "appearance: base-select",  # animated model menu
        "@starting-style",  # its opening animation
        "light-dark(",  # one colour pair per token (theme toggle)
        "position: sticky",  # pinned sidebar and docked input box
        "prefers-reduced-motion",
        ".act-tag",  # part tags on activity lines
        ".run-foot",
        ".part-context",  # blue CONTEXT lines (S02)
    ):
        assert rule in CSS, f"baseline style missing from app.css: {rule}"


def test_s01_ac13_no_fake_mode_and_no_helper_phrases() -> None:
    assert "fake" not in HTML.lower()
    assert "fake" not in JS.lower()
    for phrase in ("Runs on the chosen", "select a model", "Fresh run", "fresh run"):
        assert phrase not in HTML, f"helper phrase is back in index.html: {phrase}"
        assert phrase not in JS, f"helper phrase is back in app.js: {phrase}"


def test_s01_ac13_text_is_never_inserted_as_html() -> None:
    for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write"):
        assert sink not in JS, f"{sink} lets model text inject HTML"


def test_s03_ac10_tool_lines_show_risk_and_saved_files() -> None:
    assert '"file_saved"' in JS  # a card for every file a tool saved
    assert "d.risk" in JS  # the risk tag on tool lines
    for rule in (".file-card", ".act-risk", ".risk-action"):
        assert rule in CSS, f"S03 style missing from app.css: {rule}"


def test_s04_ac11_harness_pane_and_switches() -> None:
    assert 'id="harness-pane"' in HTML  # the right pane (D-66)
    assert 'id="pane-toggle"' in HTML
    assert "/api/harness" in JS  # built from what a run uses (D-68)
    assert "off:" in JS  # switches travel with the run request (D-70)
    for rule in (".harness-pane", ".switch", ".lane", ".off-chip"):
        assert rule in CSS, f"S04 style missing from app.css: {rule}"


def test_s04_ac9_subagent_lane_and_ac13_off_on_the_started_line() -> None:
    assert "agent_id" in JS  # child events go to their lane
    assert "d.off" in JS  # the Started line says what was off


def test_s05_ac10_ac12_ac13_guardrails_on_the_page() -> None:
    for piece in (
        '"approval_requested"',
        "/api/approval",
        "⛔ Blocked",
        "⚠ Flagged",
        "Human in the loop",
    ):
        assert piece in JS, f"S05 piece missing from app.js: {piece}"
    for rule in (".approval-card", ".part-guard", ".is-locked"):
        assert rule in CSS, f"S05 style missing from app.css: {rule}"


def test_s05_ac12_approval_card_scrolls_above_the_input_box() -> None:
    assert "scroll-margin-bottom" in CSS  # the docked composer must not cover Approve


def test_s05_ac14_scope_guard_on_the_page() -> None:
    assert '"scope_checked"' in JS
    assert "Outside scope" in JS


def test_s10_ac9_ac10_evals_view_on_the_page() -> None:
    assert 'data-view="evals"' in HTML  # a sidebar entry, added next to the others
    assert 'id="view-evals"' in HTML
    assert 'id="evals-dialog"' in HTML  # Run opens an in-page dialog, never a browser pop-up
    for piece in (
        "/api/evals",
        "/api/evals/plan",
        "/api/evals/run",
        "/api/evals/stop",
        "showModal",
    ):
        assert piece in JS, f"S10 piece missing from app.js: {piece}"
    for rule in (".eval-cat", ".metric-chip", ".evals-grid", ".evals-dialog"):
        assert rule in CSS, f"S10 style missing from app.css: {rule}"
    assert "confirm(" not in JS
    assert "alert(" not in JS
