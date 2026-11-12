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
    # one metrics table (Metric · What it checks · Graded By · Score, D-151), case rows, past evals
    for piece in ('id="evals-metrics"', 'id="evals-cases"', 'id="evals-history"'):
        assert piece in HTML, f"S10 piece missing from index.html: {piece}"
    assert '"Metric", "What It Checks", "Graded By", "Reference", "Threshold", "Score"' in JS
    assert "agent_switched" in JS  # the live view says when Claude Haiku takes over (D-116)
    assert 'id="evals-core"' in HTML  # the dialog starts on the core set
    assert 'id="evals-judge"' in HTML  # the judge is picked too, in the same animated menu
    assert 'id="evals-next"' in HTML  # both menus sit on the summary card, for the next run
    for card in ('id="cost-agent"', 'id="cost-judge"', 'id="cost-total"'):  # D-117 cost panel
        assert card in HTML
    assert "on a paid key" in JS  # Gemini: $0 on the free tier, and what a paid key would cost
    assert "prefers-reduced-motion" in JS  # the count-up snaps when motion is reduced
    assert 'class="synthetic-tag"' in HTML  # the workspace says its data is synthetic
    assert "/api/evals/follow" in JS  # a reloaded page picks the running eval back up (D-119)
    assert "Waiting on" in JS  # a stalled run says what it is waiting on
    assert "Tests Ready to Run" in JS  # no verdict until an eval is run or opened
    assert 'data-view="golden"' in HTML  # the golden dataset, on its own page
    assert 'id="view-golden"' in HTML
    for heading in (">Profiles <", ">Chats <", ">Workspace <"):  # foldable sidebar groups
        assert heading in HTML
    assert "Cost to you" in JS  # what Claude may cost, before Start
    assert "Tests Completed" in JS  # how many of the eval's tests finished
    assert "Claude Paid, Gemini Free Tier" in JS  # who pays, read from the models used
    assert "Safety Rules Held" in JS  # the hero: ring, one sentence, three numbers
    for rule in (".evals-metrics", ".case-row", ".evals-hero", ".evals-dialog"):
        assert rule in CSS, f"S10 style missing from app.css: {rule}"
    for gone in (".metric-chip", ".evals-grid", "Not covered:"):  # the clumsy parts, removed
        assert gone not in CSS + JS
    assert "confirm(" not in JS
    assert "alert(" not in JS


def test_s11_ac15_answers_render_headings_nested_lists_and_source_badges() -> None:
    assert '"prose-h"' in JS  # # and ### headings
    assert "lastElementChild ?? container" in JS  # an indented item nests under the last one
    assert 'SOURCE.test(inner) ? "cite"' in JS  # a source in backticks becomes a badge
    for rule in (".reply .prose-h", ".reply li > ul", ".reply code.cite"):
        assert rule in CSS, f"S11 answer style missing from app.css: {rule}"


def test_s06_an_outbox_email_shows_as_the_email_that_went() -> None:
    """Your request (2026-11-12): an outbox file with mail headers is shown as an email."""
    assert "function parseEmail" in JS
    assert "function emailCard" in JS
    assert "Outbox · not sent" not in JS  # the send tool says "sent" since D-120
    for rule in (".email-head", ".email-subject", ".email-body", ".email-foot"):
        assert rule in CSS, f"email style missing from app.css: {rule}"


def test_s12_ac3_ac4_ac5_guarded_action_steps_are_on_the_page() -> None:
    assert 'ev.type === "limits_checked"' in JS  # "Hard limits held · discount 15 ≤ 25 …"
    assert 'ev.type === "action_checked"' in JS  # "Checked before send_to_customer …"
    assert '"act file-row"' in JS  # the email sits under its send step (D-136)
    assert "fenced as data; any action it asks for still needs a person" in JS
    assert "from long-term memory" in JS
    assert '"Before an action"' in JS  # the pane lists checks on actions


def test_an_approval_card_shows_the_message_and_its_terms_open() -> None:
    """Your request (2026-11-12): the approver must see the message and its terms without
    unfolding anything; "See what will be sent" is gone."""
    assert '"Message to approve"' in JS
    assert '"Terms in this message"' in JS
    assert "See what will be sent" not in JS
    assert ".approval-table tr.is-mine" in CSS  # this approver's own terms are marked


def test_d141_an_approval_card_shows_where_each_term_started() -> None:
    """Your request: the approver sees today's contract, the customer's ask and the move."""
    assert "d.context_labels?.current" in JS  # column titles come from the workspace
    assert '"We offer"' in JS
    assert ".approval-change.is-up" in CSS


def test_the_sent_email_shows_under_the_answer() -> None:
    """Your request (2026-11-12): the email that went is shown with the final answer.
    A draft email shows there too (D-164)."""
    assert "for (const mail of turn.mail ?? []) turn.files.append(fileCard(mail));" in JS


def test_s12_ac7_the_page_has_you_are_and_the_switch_on_a_card_you_cant_answer() -> None:
    assert 'id="people-list"' in HTML  # the "Acting As" picker
    assert "function setPerson" in JS
    assert "`Switch to ${roleOf(p)}`" in JS  # "Switch to Dana Whitfield (CFO)"
    assert "person: currentPerson()?.id" in JS  # the server is told who answers
    assert ".approval-handoff" in CSS


def test_d147_the_page_says_when_the_model_works_without_a_plan() -> None:
    """Direct or To-Do: a missing plan reads as the model's choice (your request)."""
    assert "the model chose to work directly" in JS
    assert "rowFor(check, x)" in JS  # check rows appear with results, not as names first


def test_d151_online_and_offline_evals_on_the_page() -> None:
    """D-148, D-151: online evals on every answer and on their own page; "Evals" is now
    "Offline Evals"; every metric says who grades it: Code or LLM as Judge."""
    assert ">Online Evals</a>" in HTML
    assert ">Offline Evals</a>" in HTML
    assert ">Evals</a>" not in HTML
    assert 'id="view-online"' in HTML
    assert ">Offline Evals <span" in HTML  # the page's heading
    for piece in (
        "online_evals_started",
        "online_evals_finished",
        "function qualityCard",
        "/api/online-evals",
        'judge: "LLM as Judge"',
        'code: "Code"',
        "never sent back to the agent",
    ):
        assert piece in JS, f"online evals piece missing from app.js: {piece}"
    # The composer frees at the answer, not after the scores.
    assert 'if (ev.type === "run_finished" && !ev.data.agent_id) free();' in JS


def test_each_metric_shows_its_threshold() -> None:
    """Your request: each metric shows its threshold (the Agent pane was reverted, D-153)."""
    assert "function thresholdCell" in JS


def test_online_and_offline_evals_sit_under_observability_not_the_harness() -> None:
    """Your request: evals watch the agent from outside, so they are not a harness part."""
    group = HTML[HTML.index('data-group="observability"') :]
    assert 'data-collapsed="1"' in group[:80]  # folded by default
    assert (
        group.index(">Online Evals<")
        < group.index(">Offline Evals<")
        < group.index(">Golden Dataset<")
    )
    assert 'data-view="checks"' not in HTML  # the test suite is off the sidebar
    assert 'paneSection("online"' not in JS
    assert 'switchFor("checks", id)' in JS  # each metric's switch is on the Online Evals page


def test_sidebar_groups_start_folded_except_chats() -> None:
    """Your request (2026-11-12): every sidebar group starts folded except Chats."""
    for name in ("profiles", "views", "observability"):
        group = HTML[HTML.index(f'data-group="{name}"') :]
        assert 'data-collapsed="1"' in group[:80], f"{name} should start folded"
        assert 'aria-expanded="false"' in group[:600], f"{name} toggle says open"
    work = HTML[HTML.index('data-group="work"') :]
    assert 'data-collapsed="1"' not in work[:80]  # Chats starts open
    # New storage key: folds clicked before this change don't override the new defaults.
    assert "`side-fold-${group.dataset.group}`" in JS


def test_new_or_opened_conversation_goes_to_the_agent_page() -> None:
    """Your request: from Memory or the evals, a chat click shows the chat, no detour."""
    assert JS.count("toAgent();") >= 2


def test_online_evals_card_is_folded_by_default() -> None:
    """Your request (2026-11-12): the scores show folded; the header says "3 of 6 passed"."""
    card = JS.split("function qualityCard")[1].split("\n}\n")[0]
    assert 'el("details", "todo-card check-card quality-card' in card
    assert 'el("summary", "card-head")' in card
    assert ".open = true" not in card


def test_approval_card_header_terms_and_buttons_in_view() -> None:
    """Your report (2026-11-12): the card's header shows the workspace's facts (customer,
    contract) with its values lined up; every offered term is in the table; after an approval,
    the next card scrolls to its buttons, not its top."""
    card = JS.split("function approvalCard")[1].split("\nfunction ")[0]
    assert "(d.context ?? []).filter((r) => r.fact)" in card
    assert 'owner.get(k) ?? "Within limits"' in card
    assert 'scrollIntoView({ block: "center"' in card
    assert "card.scrollIntoView" not in card
    assert ".approval-mail-line { display: contents; }" in CSS
