"""Online evals: every live answer scored after it is shown, never blocking (D-148 to D-150).

The judge is a stand-in model here (no key, no cost). The facts come from CloudCo's real
tools on its made-up data, so Hallucination is tested against what the agent really sees.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from agentic_harness.api import Off, create_harness, describe_harness
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.memory import SessionStore, Turn
from agentic_harness.model import ModelReply, Step
from agentic_harness.online_evals import (
    DEFAULT_IDS,
    JUDGE_SYSTEM,
    OnlineEvals,
    facts,
    hallucination,
    read_judge,
)
from agentic_harness.pricing import load_prices
from agentic_harness.server.runs import ends_stream
from agentic_harness.tools import ToolContext
from agentic_harness.verify import Call, Record
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).parents[2] / "workspaces" / "cloudco"
WS = Workspace.load(ROOT)
TOOLS = {t.name: t for t in WS.tools}
CTX = ToolContext("t", ROOT, profile="sales")
IDS = WS.online.ids if WS.online else DEFAULT_IDS


def out(name: str, **args: Any) -> Call:
    tool = TOOLS[name]
    value = tool.function(**args, ctx=CTX) if tool.takes_ctx else tool.function(**args)
    return Call(name, args, json.dumps(value, ensure_ascii=False), False)


PULL = Record(
    (
        out("lookup_customer_record", record="customer", customer="ShopCo"),
        out("read_contract", contract_id="CT-2207"),
    )
)
# Your real pull answer (2026-11-12), shortened.
PULLED = """Yes, ShopCo is an existing customer `CUS-0042`, with one contract, `CT-2207`.
- **2 · Term and renewal**: 2.1 three years, prices fixed.
- **3 · Fees and discounts**: 3.2 a 25% discount.
- **4 · Invoicing and payment**: 4.1 Net 60.
- **6 · Service levels**: 6.1 99.99% uptime.
- **9 · Liability**: 9.2 unlimited."""
QUESTION = "what is shopco, is it an existing customer? If yes, pull the contract details."


def context(record: Record) -> str:
    return "\n".join(c.output for c in record.calls)


def reply(text: str) -> ModelReply:
    step = {"type": "model_output", "content": [{"type": "text", "text": text}]}
    return ModelReply([step], "completed", {"total_input_tokens": 1000}, "gemini-3.5-flash-lite")


class Judge:
    """A stand-in for the judge model: says what it was told to, remembers what it was sent."""

    name = "gemini-3.5-flash-lite"

    def __init__(self, text: str = "", error: Exception | None = None) -> None:
        self.text, self.error = text, error
        self.calls: list[tuple[str, list[Step]]] = []

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        self.calls.append((system, list(steps)))
        if self.error:
            raise self.error
        return reply(self.text)


GRADES = json.dumps(
    {
        "groundedness": {"score": 0.9, "reason": "All but one claim.", "unsupported": ["x"]},
        "context_relevancy": {"score": 0.8, "reason": "Mostly needed."},
        "answer_relevancy": {"score": 0.5, "reason": "Sections named, no details."},
        "style_format": {"score": 1, "reason": "Bottom line first."},
    }
)


def evals(judge: Judge, **kw: Any) -> OnlineEvals:
    style = WS.online.style if WS.online else ""
    return OnlineEvals(
        judge, load_prices(), ids=IDS, style=style, workspace_metrics=WS.metrics, **kw
    )


# ── Hallucination: code ─────────────────────────────────────────────────────────────────


def test_d148_hallucination_passes_your_real_pull() -> None:
    got = hallucination(PULLED, context(PULL), IDS)
    assert got.status == "passed", got.reason
    assert got.score == 1.0
    kinds = dict(facts(PULLED, IDS))
    assert {"CUS-0042", "CT-2207"} <= {t for k, t in facts(PULLED, IDS) if k == "id"}
    assert "percent" in kinds


def test_d148_hallucination_names_an_invented_id_and_a_wrong_percent() -> None:
    bad = PULLED.replace("`CT-2207`", "`CT-9999`").replace("a 25% discount", "a 20% discount")
    got = hallucination(bad, context(PULL), IDS)
    assert got.status == "failed"
    assert set(got.unsupported) == {"CT-9999", "20%"}
    assert "CT-9999" in got.reason
    assert got.score is not None
    assert 0 < got.score < 1


def test_d148_hallucination_skips_an_answer_with_no_facts_and_ignores_clause_numbers() -> None:
    assert hallucination("Hello! How can I help?", "").status == "skipped"
    # "3.2" and "§2" are where things are, not values: never counted as facts.
    assert facts("Clause 3.2 needs the CFO (standard-terms §2).") == []


def test_d148_hallucination_never_fails_the_14_real_answers() -> None:
    """The lesson of D-146: a new metric is tried on real answers first. 0 false failures."""
    review = Record(
        (
            out("review_contract", contract_id="CT-2207"),
            out("search_policy", query="discount payment uptime liability term"),
            out("lookup_customer_record", record="customer", customer="ShopCo"),
            out("lookup_customer_record", record="uptime"),
            out("lookup_customer_record", record="payments", customer="ShopCo"),
        )
    )
    answers = sorted((Path(__file__).parents[1] / "fixtures" / "answers").glob("*.md"))
    assert len(answers) == 14
    for file in answers:
        got = hallucination(file.read_text(), context(review), IDS)
        assert got.status == "passed", f"{file.name}: {got.reason}"


# ── The judge: one call, four metrics ───────────────────────────────────────────────────


async def test_d149_one_judge_call_scores_every_metric_in_order() -> None:
    judge = Judge(GRADES)
    scored = await evals(judge).score(QUESTION, PULLED, PULL)
    assert len(judge.calls) == 1  # one call per answer, not one per metric (D-149)
    system, steps = judge.calls[0]
    assert system == JUDGE_SYSTEM
    prompt = steps[0]["content"][0]["text"]
    for part in ("QUESTION:", "CONTEXT (what the tools returned)", "STYLE GUIDE:", "ANSWER:"):
        assert part in prompt
    names = [r.name for r in scored.results]
    assert names == [
        "groundedness",
        "hallucination",
        "context_relevancy",
        "answer_relevancy",
        "citations",
        "style_format",
    ]
    by = {r.name: r for r in scored.results}
    assert by["groundedness"].unsupported == ("x",)
    assert by["answer_relevancy"].status == "failed"  # 0.5 < 0.7
    assert by["style_format"].status == "passed"
    assert by["hallucination"].graded_by == "code"
    assert by["citations"].status == "skipped"  # the answer cites no policy section
    assert scored.judge == "gemini-3.5-flash-lite"


async def test_d149_no_tool_call_means_nothing_to_be_grounded_in() -> None:
    judge = Judge(json.dumps({"answer_relevancy": {"score": 1}, "style_format": {"score": 1}}))
    scored = await evals(judge).score("hi", "Hello! How can I help with a contract?", Record())
    by = {r.name: r for r in scored.results}
    assert by["groundedness"].status == "skipped"
    assert by["context_relevancy"].status == "skipped"
    assert "CONTEXT" not in judge.calls[0][1][0]["content"][0]["text"]
    assert by["answer_relevancy"].status == "passed"


async def test_d149_a_judge_failure_is_not_scored_and_the_code_metrics_still_count() -> None:
    scored = await evals(Judge(error=RuntimeError("503 busy"))).score(QUESTION, PULLED, PULL)
    by = {r.name: r for r in scored.results}
    assert by["groundedness"].status == "not_scored"
    assert "503" in by["groundedness"].reason
    assert by["hallucination"].status == "passed"
    assert "503" in scored.error


def test_d149_a_bad_reply_is_not_scored_and_scores_are_kept_in_range() -> None:
    from agentic_harness.online_evals import ANSWER_RELEVANCY, GROUNDEDNESS

    broken = read_judge([GROUNDEDNESS], "I think it is fine.")
    assert broken["groundedness"].status == "not_scored"
    assert "not JSON" in broken["groundedness"].reason
    fenced = '```json\n{"groundedness": {"score": 7, "reason": "r"}}\n```'
    got = read_judge([GROUNDEDNESS, ANSWER_RELEVANCY], fenced)
    assert got["groundedness"].score == 1.0
    assert got["answer_relevancy"].status == "not_scored"  # missing from the reply


def test_d149_a_reply_with_one_object_left_open_still_scores_every_metric() -> None:
    """Found live (Flash-Lite): answer_relevancy's object was never closed, so style_format
    sat inside it; the whole reply failed to parse and all four metrics were lost."""
    from agentic_harness.online_evals import ANSWER_RELEVANCY, GROUNDEDNESS, STYLE_FORMAT

    text = (
        '```json\n{"groundedness": {"score": 1.0, "reason": "All \\"claims\\" supported.", '
        '"unsupported": []}, "answer_relevancy": {"score": 1.0, "reason": "Fully.", '
        '"style_format": {"score": 0.6, "reason": "No sources in backticks."}}}\n```'
    )
    got = read_judge([GROUNDEDNESS, ANSWER_RELEVANCY, STYLE_FORMAT], text)
    assert [got[n].status for n in ("groundedness", "answer_relevancy", "style_format")] == [
        "passed",
        "passed",
        "failed",
    ]
    assert got["groundedness"].reason == 'All "claims" supported.'
    assert got["style_format"].score == 0.6
    # Not valid JSON at all (a quote left open): each metric is read on its own.
    cut = text.replace('"Fully."', '"Fully.')
    salvaged = read_judge([GROUNDEDNESS, ANSWER_RELEVANCY, STYLE_FORMAT], cut)
    assert salvaged["groundedness"].status == "passed"
    assert salvaged["style_format"].score == 0.6


def test_d148_a_metric_switched_off_is_not_scored_and_all_off_means_no_online_evals() -> None:
    assert "groundedness" not in [m.name for m in evals(Judge(), off=("groundedness",)).metrics()]
    every = [m.name for m in evals(Judge()).metrics()]
    h = create_harness(
        Judge(),
        Limits(),
        WS,
        profile="sales",
        trace_dir=None,
        memory_dir=None,
        off=Off(checks=tuple(every)),
    )
    assert h.online is None


# ── In the harness: after the answer, never sent back ───────────────────────────────────


class Agent:
    """The run's model: answers once; the judge (the same stand-in here) grades after."""

    name = "gemini-3.5-flash-lite"

    def __init__(self) -> None:
        self.systems: list[str] = []

    async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
        self.systems.append(system)
        return reply(GRADES if system == JUDGE_SYSTEM else "ShopCo is customer `CUS-0042`.")


async def test_d148_the_harness_scores_after_run_finished_and_never_retries() -> None:
    model = Agent()
    h: Harness = create_harness(
        model, Limits(), WS, profile="sales", trace_dir=None, memory_dir=None
    )
    h.scope_check = None  # the scope check would call the model too
    events: list[Any] = []
    h.subscribe(events.append)
    result = await h.run("is ShopCo a customer?")
    types = [e.type for e in events if not e.data.get("agent_id")]
    assert types[-3:] == ["run_finished", "online_evals_started", "online_evals_finished"]
    finished = next(e for e in events if e.type == "run_finished")
    assert finished.data["online_evals"] is True
    assert result.answer == "ShopCo is customer `CUS-0042`."
    assert model.systems.count(JUDGE_SYSTEM) == 1  # one judge call; the agent is never re-asked
    scores = events[-1].data["results"]
    assert {s["name"] for s in scores} >= {"groundedness", "hallucination", "style_format"}
    # No tool ran, so CUS-0042 is in no tool result: a real hallucination, caught and named.
    hall = next(s for s in scores if s["name"] == "hallucination")
    assert hall["status"] == "failed"
    assert hall["unsupported"] == ["CUS-0042"]


def test_d148_the_stream_waits_for_the_scores() -> None:
    def ev(type_: str, **data: Any) -> dict[str, Any]:
        return {"type": type_, "data": data}

    assert not ends_stream(ev("run_finished", online_evals=True))
    assert ends_stream(ev("run_finished", online_evals=False))
    assert ends_stream(ev("run_finished"))  # an old event, or a crash
    assert ends_stream(ev("online_evals_finished"))
    assert not ends_stream(ev("run_finished", agent_id="h1"))  # a helper's finish


def test_d148_a_conversation_keeps_each_turns_scores(tmp_path: Path) -> None:
    store = SessionStore(tmp_path, "cloudco")
    s = store.create("sales")
    store.finish_turn(s.id, "sales", Turn("q", "a", "completed", 0.0, 1.0, "run-1"))
    store.finish_turn(s.id, "sales", Turn("q2", "a2", "completed", 0.0, 1.0, "run-2"))
    store.save_scores(s.id, "sales", "run-1", {"results": [{"name": "groundedness"}], "usd": 0.0})
    turns = store.load(s.id, "sales").turns
    assert turns[0].online == {"results": [{"name": "groundedness"}], "usd": 0.0}
    assert turns[1].online is None


def test_d148_the_pane_lists_six_metrics_with_who_grades_them() -> None:
    info = describe_harness(WS, "sales")["online_evals"]
    graded = {m["label"]: m["graded_by"] for m in info["metrics"]}
    assert graded == {
        "Groundedness": "judge",
        "Hallucination": "code",
        "Context Relevancy": "judge",
        "Answer Relevancy": "judge",
        "Citations": "code",
        "Style & Format": "judge",
    }
    assert info["style"] == "answer-style.md"
    assert info["judge"] == "gemini-3.5-flash-lite"


@pytest.mark.parametrize("table", ["[online_evals]\non = false\n", ""])
def test_d148_a_workspace_without_online_evals_scores_nothing(tmp_path: Path, table: str) -> None:
    (tmp_path / "workspace.toml").write_text(f'name = "Plain"\n{table}')
    (tmp_path / "tools.py").write_text("TOOLS = []\n")
    assert Workspace.load(tmp_path).online is None


def test_d148_the_page_stream_saves_the_scores_and_lists_them(tmp_path: Path) -> None:
    """Through the real server: the stream ends with the scores, the conversation keeps
    them, and the Online Evals page lists the answer. Any workspace can switch it on."""
    import shutil

    from fastapi.testclient import TestClient

    from agentic_harness.config import Secret, Settings
    from agentic_harness.server.app import PAGE_HEADER, create_app

    hello = shutil.copytree(ROOT.parent / "hello", tmp_path / "hello")
    toml = hello / "workspace.toml"
    toml.write_text(toml.read_text() + "\n[online_evals]\n")

    class Model:
        def __init__(self, settings: Settings) -> None:
            self.name = settings.model

        async def create(self, system: str, steps: Any, tools: Any) -> ModelReply:
            if system == JUDGE_SYSTEM:
                return reply(json.dumps({"answer_relevancy": {"score": 0.9, "reason": "ok"}}))
            return reply("It is 10:00 in Tokyo.")

    app = create_app(
        Settings(api_key=Secret("test-value-not-a-real-key")),
        project_root=tmp_path,
        workspace=Workspace.load(hello),
        trace_dir=tmp_path / "traces",
        model_factory=Model,
    )
    web = TestClient(app, base_url="http://127.0.0.1")
    response = web.post("/api/run", headers=PAGE_HEADER, json={"task": "Time in Tokyo?"})
    events = [json.loads(line) for line in response.text.splitlines()]
    types = [e["type"] for e in events]
    assert types.index("run_finished") < types.index("online_evals_finished")
    listed = web.get("/api/online-evals").json()["answers"]
    assert len(listed) == 1
    assert listed[0]["task"] == "Time in Tokyo?"
    names = {r["name"]: r for r in listed[0]["results"]}
    assert names["answer_relevancy"]["status"] == "passed"
    assert names["hallucination"]["status"] == "failed"  # "10" and "00": no tool ran
    session = events[0]["data"]["session_id"]
    turn = web.get(f"/api/sessions/{session}").json()["turns"][0]
    assert turn["online"]["results"] == listed[0]["results"]


def test_d154_a_refused_call_is_context_for_the_judge() -> None:
    """Found in the eval of 2026-11-12 (cfo-no-holds): the send was rejected by the CFO and
    the agent said so, but the judge never saw the rejection and called it made up."""
    from agentic_harness.online_evals import context_blocks

    rejected = Call("send_to_customer", {}, "Not sent: the CFO rejected it.", True)
    blocks = context_blocks(Record((rejected,)))
    assert blocks == ["[send_to_customer · failed] Not sent: the CFO rejected it."]
