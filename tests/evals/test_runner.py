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
    assert [a["approver"] for a in tool["approvals"]] == ["CFO"]  # Sales never asked after a no
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
    busy, _ = await go(suite, tmp_path, factory=factory(fail="Gemini 429: quota exceeded"))
    assert "out of quota" in busy["stop_reason"]
    judged, _ = await go(
        suite, tmp_path, cases=["lookup"], judge=StandInJudge(JudgeUnavailableError("no judge"))
    )
    assert judged["stop_reason"] == "no judge"
    assert judged["cases"][0]["status"] == "incomplete"


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
