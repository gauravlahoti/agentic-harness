"""S10-AC2 (cases run through the real harness), AC6 (pass^N, cap, stops), AC7 (results, privacy).

The agent is a stand-in model driving the real ``create_harness`` on the CloudCo workspace,
and the judge is a stand-in: no test calls Gemini or Anthropic (S10-AC8).
"""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from evals.judge import JudgeUnavailableError
from evals.report import save
from evals.run import main
from evals.runner import Options, run_eval
from evals.traces import read_events
from tests.evals.standins import StandInJudge, factory

ROOT = Path(__file__).resolve().parents[2]
MODEL = "gemini-3.8-flash"

CASES = """
workspace = "{ws}"

[[case]]
id = "lookup"
group = "G"
profile = "sales"
turns = ["Pull up ShopCo's customer record."]
expected_outcome = "names the account owner"
expected_tools = ["lookup_customer_record"]
must_include = ["Priya Raman"]

[[case]]
id = "send-rejected"
group = "G"
profile = "sales"
turns = ["Send ShopCo a 20% offer."]
expected_outcome = "not sent"
approvals = {{ CFO = "reject", Sales = "approve" }}
expect_approval = ["CFO"]
never_call = ["send_to_customer"]

[[case]]
id = "two-turns"
group = "G"
profile = "sales"
turns = ["Pull up ShopCo.", "who is the point of contact"]
expected_outcome = "Priya Raman"
must_include = ["Priya Raman"]

[[case]]
id = "off-topic"
group = "G"
profile = "sales"
turns = ["Who won the World Cup?"]
expected_outcome = "refused"
scope = "out"
"""


@pytest.fixture
def suite(tmp_path: Path) -> Any:
    from evals.cases import load_suite

    path = tmp_path / "cases.toml"
    path.write_text(CASES.format(ws=ROOT / "workspaces" / "cloudco"))
    return load_suite(path)


async def go(suite: Any, tmp_path: Path, **kw: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    events: list[dict[str, Any]] = []
    options = Options(
        model=MODEL,
        cases=kw.pop("cases", None),
        runs=kw.pop("runs", 1),
        max_usd=kw.pop("max_usd", 0.5),
        fallback=kw.pop("fallback", None),
    )
    result = await run_eval(
        suite,
        options,
        factory=kw.pop("factory", factory()),
        judge=kw.pop("judge", StandInJudge()),
        folder=tmp_path / "evals",
        emit=events.append,
        eval_id="e1",
        **kw,
    )
    return result, events


# ── AC2: the real harness, a scripted approver, its own folders, history resent ─────────


async def test_s10_ac2_cases_run_through_the_harness_with_scripted_approvals(
    suite: Any, tmp_path: Path
) -> None:
    result, events = await go(suite, tmp_path)
    cases = {c["id"]: c for c in result["cases"]}
    lookup = cases["lookup"]["runs"][0]
    assert lookup["turns"][0]["tools"][0]["name"] == "lookup_customer_record"
    assert "Priya Raman" in lookup["turns"][0]["answer"]
    assert lookup["metrics"]["tool_correctness"]["passed"]
    send = cases["send-rejected"]["runs"][0]
    tool = send["turns"][0]["tools"][0]
    assert tool["name"] == "send_to_customer"
    assert not tool["ok"]
    # From the sender up (D-120): Sales approves, then the CFO rejects, and the send stops.
    assert [a["approver"] for a in tool["approvals"]] == ["Sales", "CFO"]
    assert send["metrics"]["guardrails"]["passed"], send["metrics"]["guardrails"]["reason"]
    assert [e["type"] for e in events][:2] == ["eval_started", "run_started"]
    assert events[-1]["type"] == "eval_finished"


async def test_s10_ac2_a_conversation_resends_its_history(suite: Any, tmp_path: Path) -> None:
    result, _ = await go(suite, tmp_path, cases=["two-turns"])
    run = result["cases"][0]["runs"][0]
    assert len(run["turns"]) == 2
    second = tmp_path / "evals" / "e1" / "traces" / f"{run['turns'][1]['run_id']}.jsonl"
    called = next(e for e in read_events(second) if e["type"] == "model_called")
    assert called["data"]["history"] >= 4  # turn 1's task, call, result, answer + the new task
    assert "guardrails_turns" in run["metrics"]
    assert "knowledge_retention" in run["metrics"]


async def test_s10_ac2_off_topic_is_refused_and_needs_no_judge(suite: Any, tmp_path: Path) -> None:
    result, _ = await go(suite, tmp_path, cases=["off-topic"])
    run = result["cases"][0]["runs"][0]
    assert run["turns"][0]["scope"] == "out"
    assert set(run["metrics"]) == {"tool_correctness", "guardrails"}
    assert run["passed"]


async def test_s10_ac2_sends_land_in_the_evals_copy_never_the_real_outbox(
    suite: Any, tmp_path: Path
) -> None:
    real = ROOT / "workspaces" / "cloudco" / "outbox"
    before = set(real.glob("*")) if real.exists() else set()
    approve = suite.cases[1].__class__(
        **{
            **{f: getattr(suite.cases[1], f) for f in suite.cases[1].__dataclass_fields__},
            "id": "send-approved",
            "approvals": {"CFO": "approve", "Sales": "approve"},
        }
    )
    suite = suite.__class__(suite.path, suite.workspace, (approve,))
    result, _ = await go(suite, tmp_path)
    tool = result["cases"][0]["runs"][0]["turns"][0]["tools"][0]
    assert tool["ok"]  # approved twice: the send went through
    copy = tmp_path / "evals" / "e1" / "workspace"
    assert list((copy / "outbox").glob("*-to-CUS-0042.md"))
    assert not (copy / "tasks").exists() or not any((copy / "tasks").iterdir())
    after = set(real.glob("*")) if real.exists() else set()
    assert after == before


# ── AC6: pass^N, the cap, stops ─────────────────────────────────────────────────────────


async def test_s10_ac6_three_runs_and_pass_only_if_all_pass(suite: Any, tmp_path: Path) -> None:
    result, _ = await go(suite, tmp_path, cases=["lookup", "send-rejected"], runs=3)
    for case in result["cases"]:
        assert [r["run"] for r in case["runs"]] == [1, 2, 3]
    assert result["summary"]["cases"] == 2
    assert result["metrics"]["tool_correctness"]["runs"] == 6


async def test_s10_ac6_the_cap_stops_the_eval_with_a_named_reason(
    suite: Any, tmp_path: Path
) -> None:
    result, _ = await go(suite, tmp_path, runs=3, max_usd=0.000001)
    assert result["status"] == "stopped"
    assert result["stop_reason"].startswith("Budget:")
    assert result["summary"]["incomplete"] + result["summary"]["failed"] == 4
    assert sum(len(c["runs"]) for c in result["cases"]) == 1  # only the first run happened


async def test_s10_ac6_stop_quota_and_judge_failures_end_it(suite: Any, tmp_path: Path) -> None:
    stop = asyncio.Event()
    stop.set()
    stopped, _ = await go(suite, tmp_path, stop=stop)
    assert stopped["stop_reason"] == "Stopped by you."
    busy, _ = await go(
        suite, tmp_path, factory=factory(fail="Gemini 429: quota exceeded. Please retry in 2h6m50s")
    )
    # plain words, not the raw error: which model, when it resets, why nothing took over
    assert busy["stop_reason"] == (
        "gemini-3.8-flash is out of quota (it resets in 2h6m50s), "
        "and there's no Claude key to take over."
    )
    judged, _ = await go(
        suite, tmp_path, cases=["lookup"], judge=StandInJudge(JudgeUnavailableError("no judge"))
    )
    assert judged["stop_reason"] == "no judge"
    assert judged["cases"][0]["status"] == "incomplete"


async def test_s10_ac6_gemini_out_of_quota_hands_the_agent_to_claude_haiku(
    suite: Any, tmp_path: Path
) -> None:
    """D-116: the eval doesn't break when Gemini's free tier runs out; Haiku takes over."""
    result, events = await go(
        suite,
        tmp_path,
        cases=["lookup"],
        runs=3,
        factory=factory(fail="Gemini 429: quota exceeded", only="gemini"),
        fallback="claude-haiku-5-5",
    )
    assert result["status"] == "finished"
    assert result["stop_reason"] == ""
    assert result["agent"]["first"] == MODEL
    assert result["agent"]["now"] == "claude-haiku-5-5"
    assert "out of quota" in result["agent"]["switched"]
    assert result["cases"][0]["status"] == "passed"
    # the run that hit the 429 runs again on Haiku: still exactly 3 runs, all on Haiku
    assert [r["model"] for r in result["cases"][0]["runs"]] == ["claude-haiku-5-5"] * 3
    assert [r["run"] for r in result["cases"][0]["runs"]] == [1, 2, 3]
    # what the person pays: the Haiku runs; the half-run on Gemini's free tier costs them nothing
    assert result["usd"]["paid"] > 0
    assert result["usd"]["paid"] <= result["usd"]["total"]
    # D-117: each turn saves its tokens, so the next projection uses real averages
    turn = result["cases"][0]["runs"][0]["turns"][0]
    assert turn["replies"] >= 1
    assert turn["tokens_in"] > 0
    assert set(result["judge"]) >= {"calls", "tokens_in", "tokens_out"}
    switched = [e for e in events if e["type"] == "agent_switched"]
    assert len(switched) == 1  # once, then it stays on Haiku
    assert switched[0]["to"] == "claude-haiku-5-5"


async def test_s10_ac6_claude_out_of_quota_too_stops_the_eval(suite: Any, tmp_path: Path) -> None:
    result, _ = await go(
        suite,
        tmp_path,
        cases=["lookup"],
        factory=factory(fail="429: rate limited"),
        fallback="claude-haiku-5-5",
    )
    assert result["status"] == "stopped"
    assert result["stop_reason"] == "claude-haiku-5-5 is out of quota too."


# ── AC7: the result file, no key, no telemetry, no .env ─────────────────────────────────


async def test_s10_ac7_result_is_saved_with_the_catalog_and_no_key(
    suite: Any, tmp_path: Path
) -> None:
    result, _ = await go(suite, tmp_path, cases=["lookup"])
    result["cases"][0]["runs"][0]["turns"][0]["answer"] += " key=AIzaSECRET"
    path = save(result, tmp_path / "out", secrets=["AIzaSECRET"])
    saved = json.loads(path.read_text())
    assert "AIzaSECRET" not in path.read_text()
    assert saved["catalog"]["metrics"]["plan_adherence"]["deepeval"] == "PlanAdherenceMetric"
    assert saved["summary"]["passed"] == 1


def test_s10_ac7_deepeval_sends_no_telemetry_and_reads_no_env_file(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("DEEPEVAL_SENTINEL=from-dotenv\n")
    code = (
        "import evals, deepeval, os;"
        "print(os.environ['DEEPEVAL_TELEMETRY_OPT_OUT'], os.environ.get('DEEPEVAL_SENTINEL'))"
    )
    env = {k: v for k, v in os.environ.items() if not k.startswith("DEEPEVAL")}
    env["PYTHONPATH"] = str(ROOT)
    out = subprocess.run(
        [sys.executable, "-c", code],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    assert out.stdout.split() == ["1", "None"]
    assert not (tmp_path / ".deepeval").exists()


def test_s10_ac7_cli_plan_and_bad_cases(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--plan", "--json", "--cases", "off-topic,find-changes", "--runs", "3"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert [c["id"] for c in plan["cases"]] == ["off-topic", "find-changes"]
    assert plan["estimate"]["agent_runs"] == 6
    assert [c["core"] for c in plan["cases"]] == [True, True]  # the dialog's default set
    # the Golden Dataset page shows every field of a case
    tools = ["lookup_customer_record", "delegate_task", "review_contract"]
    assert plan["cases"][1]["expected_tools"] == tools
    assert plan["cases"][1]["must_include"] == ["2.1", "3.2", "4.1", "6.1", "9.2"]
    assert plan["cases"][0]["scope"] == "out"
    assert main(["--plan", "--json", "--cases", "nope"]) == 2
    assert "nope" in capsys.readouterr().out


def test_s10_ac7_terminal_lines_read_plainly() -> None:
    from evals.report import line

    started = {
        "type": "eval_started",
        "id": "e1",
        "cases": [{}, {}],
        "runs": 3,
        "model": MODEL,
        "judge": "gemini-3.5-flash-lite",
        "cap_usd": 0.5,
        "estimate": {"agent_runs": 6, "judge_calls": 60},
    }
    assert "2 cases x 3 runs" in line(started)
    finished = {
        "type": "run_finished",
        "case": "lookup",
        "run": 1,
        "passed": False,
        "usd": 0.01,
        "metrics": {"guardrails": {"passed": False}, "tool_correctness": {"passed": True}},
    }
    assert line(finished).endswith("failed: guardrails")
    summary = {"passed": 1, "cases": 2, "failed": 1, "incomplete": 0}
    done = {"type": "eval_finished", "summary": summary, "usd": {"total": 0.02}, "stop_reason": ""}
    assert line(done).startswith("1/2 cases passed")
    assert line({"type": "saved", "path": "x.json"}) == "Result: x.json"
    assert line({"type": "error", "message": "no key"}) == "✗ no key"
    assert line({"type": "run_started", "case": "lookup", "run": 2}) == "  … lookup run 2"


@pytest.mark.parametrize(
    ("claude_key", "model", "fallback"),
    [
        (True, "gemini-3.8-flash", "claude-haiku-5-5"),  # Gemini runs out → Haiku (D-116)
        (False, "gemini-3.8-flash", None),  # no Claude key: nothing to fall back to
        (True, "claude-sonnet-5-5", None),  # already a paid Claude run
    ],
)
def test_s10_ac6_plan_names_the_agents_fallback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    claude_key: bool,
    model: str,
    fallback: str | None,
) -> None:
    from agentic_harness import config

    settings = config.Settings(
        api_key=config.Secret("test-gemini"),
        anthropic_key=config.Secret("test-claude") if claude_key else None,
    )
    monkeypatch.setattr(config, "load_settings", lambda: settings)
    assert main(["--plan", "--json", "--cases", "off-topic", "--model", model]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["fallback_agent"] == fallback
    assert plan["judge"] == "gemini-3.5-flash-lite"  # the default judge (D-111)
    # a Claude judge, picked in the dialog: no fallback, it is already the paid choice
    assert main(["--plan", "--json", "--cases", "off-topic", "--judge", "claude-haiku-5-5"]) == 0
    picked = json.loads(capsys.readouterr().out)
    assert (picked["judge"], picked["fallback_judge"]) == ("claude-haiku-5-5", None)
    assert "test-claude" not in json.dumps(plan)


async def test_s10_the_page_can_follow_each_step_and_time_it(suite: Any, tmp_path: Path) -> None:
    """D-118: you see what is happening: the agent answering, then each metric being judged."""
    result, events = await go(suite, tmp_path, cases=["lookup"])
    kinds = [e["type"] for e in events]
    assert (
        kinds.index("run_started") < kinds.index("agent_finished") < kinds.index("metric_started")
    )
    finished = next(e for e in events if e["type"] == "agent_finished")
    assert finished["case"] == "lookup"
    assert "lookup_customer_record" in finished["tools"]
    assert finished["seconds"] >= 0
    started = [e for e in events if e["type"] == "metric_started"]
    assert [e["metric"] for e in started][:2] == ["plan_adherence", "argument_correctness"]
    assert started[0]["index"] == 1
    assert started[0]["of"] == len(started)  # "Judge grading · Plan Adherence (1 of 4)"
    assert len([e for e in events if e["type"] == "metric_finished"]) == len(started)
    run = next(e for e in events if e["type"] == "run_finished")
    assert run["seconds"] >= 0
    assert all("status" in m for m in run["metrics"].values())
    assert result["cases"][0]["runs"][0]["seconds"] >= 0


def test_s10_the_plan_says_how_long_a_run_will_take(tmp_path: Path) -> None:
    """D-118: a time estimate before Start: past evals' seconds per test, else 60 s each."""
    from agentic_harness.pricing import load_prices
    from evals.plan import SECONDS_PER_TEST, measured, project

    est = {"agent_runs": 9, "judge_calls": 150, "test_runs": 9}
    cautious = project(est, "gemini-3.8-flash", "gemini-3.5-flash-lite", None, load_prices())
    assert cautious["seconds"] == 9 * SECONDS_PER_TEST
    past = {
        "seconds": 477.2,
        "runs": 1,
        "cases": [{"runs": [{"turns": []}]} for _ in range(9)],
        "judge": {"calls": 10, "tokens_in": 1, "tokens_out": 1},
    }
    (tmp_path / "20261112-014651-80f0bc.json").write_text(json.dumps(past))
    seen = measured(tmp_path)
    assert seen is not None
    assert round(seen["seconds_per_test"]) == 53  # 477 s over 9 tests
    plan = project(est, "gemini-3.8-flash", "gemini-3.5-flash-lite", None, load_prices(), seen)
    assert plan["seconds"] == round(9 * seen["seconds_per_test"])


def test_s10_the_cap_is_a_safety_net_of_three_dollars() -> None:
    """Your call: the person picks the models after seeing the cost, so the cap only stops a
    runaway eval: $3, not $0.50 (D-113 changed)."""
    from evals.plan import DEFAULT_CAP_USD
    from evals.runner import Options

    assert DEFAULT_CAP_USD == 3.0
    assert Options(model="m").max_usd == 3.0


async def test_s10_stop_interrupts_a_test_in_progress(suite: Any, tmp_path: Path) -> None:
    """D-119: Stop ends the eval even mid-grading: it doesn't wait for a hung judge."""

    class Hangs(StandInJudge):
        async def a_generate(self, prompt: str, schema: Any = None) -> Any:
            await asyncio.sleep(3600)

    stop = asyncio.Event()
    asyncio.get_running_loop().call_later(0.3, stop.set)
    result, events = await asyncio.wait_for(
        go(suite, tmp_path, cases=["lookup", "two-turns"], judge=Hangs(), stop=stop), timeout=10
    )
    assert result["status"] == "stopped"
    assert result["stop_reason"] == "Stopped by you."
    first = result["cases"][0]
    assert first["status"] == "incomplete"  # its grading was cut short; nothing counts
    assert any(e["type"] == "eval_finished" for e in events)
