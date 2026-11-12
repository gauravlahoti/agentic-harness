"""Public tour mode: the page, hosted for anyone, read-only and keyless (S14, D-189).

Public mode turns the server into a showcase: it answers to the names it is given,
refuses every request that would change or run something, and never holds a key.
Local mode (the default) stays exactly as it was: localhost only.
"""

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agentic_harness.cli import main
from agentic_harness.config import Secret, Settings, load_settings
from agentic_harness.server.app import PAGE_HEADER, create_app
from agentic_harness.workspace import Workspace

ROOT = Path(__file__).resolve().parents[2]
CLOUDCO = ROOT / "workspaces" / "cloudco"
HOST = "tour.example"
FAKE_KEY = "AIza-fake-key-for-tests-0123456789"


def public_client(tmp_path: Path, **settings: object) -> TestClient:
    config = Settings(public=True, allowed_hosts=(HOST,), **settings)  # type: ignore[arg-type]
    app = create_app(
        config, project_root=tmp_path, workspace=Workspace.load(CLOUDCO), memory_dir=tmp_path
    )
    return TestClient(app, base_url=f"https://{HOST}")


# ── S14-AC1: nothing that changes or runs anything ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/run"),
        ("POST", "/api/checks"),
        ("POST", "/api/approval"),
        ("POST", "/api/evals/run"),
        ("POST", "/api/evals/stop"),
        ("POST", "/api/online-evals/judge"),
        ("POST", "/api/facts/forget"),
        ("PUT", "/api/tour/audio/01-jar"),
        ("DELETE", "/api/sessions/anything"),
        ("DELETE", "/api/evals/anything"),
        ("PATCH", "/"),
    ],
)
def test_s14_ac1_public_mode_refuses_every_change(tmp_path: Path, method: str, path: str) -> None:
    # The page's own header doesn't help: anyone can send it from outside a browser.
    response = public_client(tmp_path).request(method, path, headers=PAGE_HEADER, content=b"x")
    assert response.status_code == 403
    assert "read-only" in response.json()["detail"]


def test_s14_ac1_a_refused_clip_leaves_the_voice_alone(tmp_path: Path) -> None:
    web = public_client(tmp_path)
    before = web.get("/api/tour/audio/01-jar")
    web.put("/api/tour/audio/01-jar", headers={**PAGE_HEADER, "content-type": "audio/mpeg"})
    after = web.get("/api/tour/audio/01-jar")
    assert before.status_code == after.status_code
    assert before.content == after.content


# ── S14-AC2: the tour plays, under the names it was given ──────────────────────────────────


def test_s14_ac2_public_mode_serves_the_page_and_the_tour(tmp_path: Path) -> None:
    web = public_client(tmp_path)
    assert web.get("/").status_code == 200
    assert web.get("/static/tour.js").status_code == 200
    tour = web.get("/api/tour")
    assert tour.status_code == 200
    assert tour.json()["steps"]
    assert web.head("/").status_code in {200, 405}  # HEAD is a read: never refused as a change


def test_s14_ac2_voice_clips_are_cached_by_version(tmp_path: Path) -> None:
    """A clip's URL changes with every new take (?v=), so the browser may keep it."""
    web = public_client(tmp_path)
    step = next((s for s in web.get("/api/tour").json()["steps"] if s["audio"]), None)
    if step is None:
        pytest.skip("The voice clips are kept local, out of git: none in this checkout.")
    clip = web.get(step["audio"])
    assert clip.status_code == 200
    assert "immutable" in clip.headers["cache-control"]
    assert web.get("/").headers["cache-control"] == "no-cache"  # the page is still rechecked


def test_s14_ac2_public_mode_answers_only_its_own_names(tmp_path: Path) -> None:
    app = public_client(tmp_path).app
    assert TestClient(app, base_url="https://evil.example").get("/").status_code == 400
    assert TestClient(app, base_url="http://localhost").get("/").status_code == 200


def test_s14_ac2_local_mode_ignores_extra_names(tmp_path: Path) -> None:
    """Allowed hosts only count in public mode: local mode stays localhost only (D-20)."""
    settings = Settings(allowed_hosts=(HOST,))
    web = TestClient(create_app(settings, project_root=tmp_path), base_url=f"https://{HOST}")
    assert web.get("/").status_code == 400


# ── S14-AC3: no key, ever ──────────────────────────────────────────────────────────────────


def test_s14_ac3_public_mode_drops_every_key(tmp_path: Path) -> None:
    env = {
        "HARNESS_PUBLIC": "1",
        "GEMINI_API_KEY": FAKE_KEY,
        "ANTHROPIC_API_KEY": FAKE_KEY,
        "HARNESS_ALLOWED_HOSTS": f" {HOST} , ,other.example ",
        "PORT": "8080",
    }
    settings = load_settings(tmp_path / "missing.env", environ=env)
    assert settings.public is True
    assert not settings.has_key
    assert not settings.has_anthropic_key
    assert settings.allowed_hosts == (HOST, "other.example")
    assert settings.port == 8080


def test_s14_ac3_local_mode_is_the_default(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.env", environ={"GEMINI_API_KEY": FAKE_KEY})
    assert settings.public is False
    assert settings.has_key
    assert settings.allowed_hosts == ()
    assert settings.port is None


@pytest.mark.parametrize("value", ["yes", "true", "2"])
def test_s14_ac3_public_switch_must_be_clear(tmp_path: Path, value: str) -> None:
    with pytest.raises(ValueError, match="HARNESS_PUBLIC"):
        load_settings(tmp_path / "missing.env", environ={"HARNESS_PUBLIC": value})


def test_s14_ac3_bad_port_is_explained(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="PORT"):
        load_settings(tmp_path / "missing.env", environ={"PORT": "eighty"})


def test_s14_ac3_a_key_given_directly_is_still_never_used(tmp_path: Path) -> None:
    """Even a Settings built by hand with a key reports none to the page in public mode."""
    web = public_client(tmp_path, api_key=Secret(FAKE_KEY))
    assert web.get("/api/health").json()["key"] == "missing"


# ── S14-AC4: where the server listens ──────────────────────────────────────────────────────


def run_serve(monkeypatch: pytest.MonkeyPatch, settings: Settings, *args: str) -> dict[str, object]:
    calls: list[dict[str, object]] = []
    monkeypatch.setattr("uvicorn.run", lambda _app, **kwargs: calls.append(kwargs))
    monkeypatch.setattr("agentic_harness.config.load_settings", lambda: settings)
    assert main(["serve", *args]) == 0
    return calls[0]


def test_s14_ac4_public_mode_listens_on_every_address(monkeypatch: pytest.MonkeyPatch) -> None:
    bound = run_serve(monkeypatch, Settings(public=True, port=8080))
    assert bound["host"] == "0.0.0.0"  # noqa: S104 (public mode is for a container)
    assert bound["port"] == 8080


def test_s14_ac4_local_mode_stays_on_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    bound = run_serve(monkeypatch, Settings(port=8080))
    assert bound["host"] == "127.0.0.1"
    assert bound["port"] == 8080  # $PORT is only a port: it never widens the address


def test_s14_ac4_port_flag_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_serve(monkeypatch, Settings(port=8080), "--port", "8123")["port"] == 8123


# ── S14-AC5: the page knows which mode it is in ────────────────────────────────────────────


def test_s14_ac5_health_reports_public_mode(tmp_path: Path) -> None:
    body = public_client(tmp_path).get("/api/health").json()
    assert body["mode"] == "public"
    assert body["key"] == "missing"
    assert body["repository"] is None or body["repository"].startswith("https://")


def test_s14_ac5_health_reports_local_mode(tmp_path: Path) -> None:
    web = TestClient(create_app(Settings(), project_root=tmp_path), base_url="http://127.0.0.1")
    assert web.get("/api/health").json()["mode"] == "local"


def test_s14_ac5_page_has_the_public_note(tmp_path: Path) -> None:
    page = public_client(tmp_path).get("/").text
    assert 'id="public-note"' in page


def test_s14_ac6_the_server_starts_without_dev_tools() -> None:
    """The hosted image ships no pytest or DeepEval; importing the app must not need them."""
    code = (
        "import sys, agentic_harness.server.app, agentic_harness.cli; "
        "print(sorted(m for m in ('pytest', 'deepeval', 'httpx') if m in sys.modules))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=ROOT
    )
    assert out.stdout.strip() == "[]"
