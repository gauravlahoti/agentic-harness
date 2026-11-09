"""The local server and page shell (S00-AC13, S00-AC14, S00-AC15).

Only reachable as 127.0.0.1 or localhost; serves the page; reports its smoke status;
runs the one fixed test command when the page asks.
"""

import json
import textwrap
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_harness.config import Secret, Settings
from agentic_harness.server.app import PAGE_HEADER, create_app

LOCAL = "http://127.0.0.1"


def client(tmp_path: Path, *, key: str | None = None) -> TestClient:
    settings = Settings(api_key=Secret(key) if key else None)
    return TestClient(create_app(settings, project_root=tmp_path), base_url=LOCAL)


def test_s00_ac13_serves_the_page_shell(tmp_path: Path) -> None:
    response = client(tmp_path).get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Run checks" in response.text


def test_s00_ac13_serves_page_assets(tmp_path: Path) -> None:
    web = client(tmp_path)
    assert web.get("/static/app.js").status_code == 200
    assert web.get("/static/app.css").status_code == 200
    assert web.get("/favicon.ico").status_code == 200


def test_s00_ac13_rejects_other_host_names(tmp_path: Path) -> None:
    # Blocks DNS-rebinding: a website that points its own name at 127.0.0.1.
    web = TestClient(create_app(Settings(), project_root=tmp_path), base_url="http://evil.example")
    assert web.get("/").status_code == 400


def test_s00_ac13_sends_strict_security_headers(tmp_path: Path) -> None:
    headers = client(tmp_path).get("/").headers
    assert "default-src 'self'" in headers["content-security-policy"]
    assert "frame-ancestors 'none'" in headers["content-security-policy"]
    assert headers["x-frame-options"] == "DENY"
    assert headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(("key", "expected"), [("AIza-fake", "present"), (None, "missing")])
def test_s00_ac15_smoke_status(tmp_path: Path, key: str | None, expected: str) -> None:
    body = client(tmp_path, key=key).get("/api/health").json()
    assert body["server"] == "up"
    assert body["key"] == expected
    assert "AIza-fake" not in json.dumps(body)


def test_s00_ac14_checks_need_the_page_header(tmp_path: Path) -> None:
    # Another website can send a plain POST to localhost, but not a custom header.
    assert client(tmp_path).post("/api/checks").status_code == 403


def test_s00_ac14_checks_take_no_input(tmp_path: Path) -> None:
    operation = client(tmp_path).app.openapi()["paths"]["/api/checks"]["post"]  # type: ignore[attr-defined]
    assert "parameters" not in operation
    assert "requestBody" not in operation


def test_s00_ac14_one_run_at_a_time(tmp_path: Path) -> None:
    web = client(tmp_path)
    web.app.state.checks_running = True  # type: ignore[attr-defined]
    assert web.post("/api/checks", headers=PAGE_HEADER).status_code == 409


def test_s00_ac14_checks_stream_results(tmp_path: Path) -> None:
    (tmp_path / "test_tiny.py").write_text(textwrap.dedent("def test_ok():\n    assert True\n"))
    web = client(tmp_path)
    response = web.post("/api/checks", headers=PAGE_HEADER)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    events = [json.loads(line) for line in response.text.splitlines()]
    assert [e["type"] for e in events] == ["collected", "result", "finished", "exit"]
    assert web.app.state.checks_running is False  # type: ignore[attr-defined]
