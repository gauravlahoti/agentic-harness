# Stage 0 · Scaffold and setup

> A production-grade, empty-but-safe project: one command to install, one to check, one to open the page.

## What you have now

- `make setup` and `make check`: lint, strict types, 38 offline tests, 99% coverage, in about 5 seconds.
- `uv run agentic-harness serve` opens http://127.0.0.1:8000. **Run checks** runs every offline test and fills one row per test, live.
- The key sits in `.env`, is read by one module, and prints as `***` everywhere.

## How a click on "Run checks" travels

```
browser                  server (app.py)                 child process
───────                  ───────────────                 ─────────────
click ──POST /api/checks──▶ host ok? header ok?
         X-Harness-Page: 1   not already running?
                             run_checks() ──spawn──────▶ pytest -p pytest_stream …
                                                          (no key in its environment)
                             ◀── "HARNESS-CHECK {json}" ─ one line per test
rows fill in ◀── NDJSON ──── forward each event
```

## The files

### `src/agentic_harness/config.py`: the only file that reads `.env`

- `Secret` wraps the key. `str`, `repr` and f-strings all show `***`; only `.reveal()` returns the real value, and only the Gemini client will call it (S01).
- `load_settings()` uses `dotenv_values`, which *returns* the values. The more common `load_dotenv` copies them into `os.environ`, where every child process (like the test run) would inherit the key.
- No key is not an error. `require_key()` raises only when a live call needs one, and the message tells you what to do.

### `src/agentic_harness/cli.py`: the `agentic-harness` command

- `HOST = "127.0.0.1"` is a constant, and `serve` has no `--host` option. A test proves `--host` is refused.
- Heavy imports (`uvicorn`, the app) sit inside `serve()`, so `--version` stays instant.

### `src/agentic_harness/server/app.py`: the web server

- `TrustedHostMiddleware` answers only to `127.0.0.1` and `localhost`. This blocks *DNS rebinding*, where a website points its own name at your machine.
- `POST /api/checks` needs the header `X-Harness-Page: 1`. Another site can send your browser a plain POST, but not a custom header, without a CORS check this server never allows.
- Strict browser headers: the page may load only its own files (`default-src 'self'`) and can't be framed.
- `/api/checks` takes no parameters and no body (a test reads the API schema to prove it). One run at a time (409 otherwise).

### `src/agentic_harness/server/checks.py`: runs the fixed command

- `CHECKS_COMMAND` is a tuple constant: pytest, our plugin, `-m "not live"` (a button never spends money).
- `_child_env()` copies the environment *minus* the key names from `config.SECRET_ENV_NAMES`.
- A 120 s limit kills a stuck run and reports why. `finally` always kills a leftover process.
- It looks for our prefix *anywhere* in a line: in quiet mode pytest prints `.` or `F` just before it (this was a real bug, caught by a test).

### `src/agentic_harness/server/pytest_stream.py`: a small pytest plugin

- Three hooks: `collection_finish` (list every test, so the page draws all rows up front), `runtest_logreport` (one result per test), and `sessionfinish`.
- It writes through pytest's own terminal, so a test's captured output can't swallow the events.

### `src/agentic_harness/web/`: the page (HTML, CSS, JS, no build step)

- Server text is always set with `textContent`, never as HTML, so a test name can't inject code.
- Dark mode follows your system. Rows fade in only if you allow motion.
- The status line is announced to screen readers once at the start and once at the end, not 38 times.

## Verify it yourself

1. `make setup && make check` → all green, 38 passed, coverage shown.
2. `uv run agentic-harness --version` → `agentic-harness 0.1.0`.
3. Rename any file to `TEST.md` and run `make test` → the naming test fails. Undo it.
4. Add the word "contract" to `src/agentic_harness/cli.py` and run `make test` → the domain-free test fails. Undo it.
5. `uv run agentic-harness serve` → open http://127.0.0.1:8000 → the top shows **Server up ✓ · Key present ✓** → click **Run checks** → 38 rows turn green.
6. In another terminal: `curl -X POST http://127.0.0.1:8000/api/checks` → `403`. The page header is required.
7. Optional: break any test on purpose, click **Run checks** again → its row shows ✗ and the summary turns red. Undo it.

## Explain it back

1. Why does CI run `make check` instead of its own list of commands?
2. Why load the key in exactly one place, why `dotenv_values` and not `load_dotenv`, and why bind to `127.0.0.1`?
3. What would the domain-free test catch, and why does it matter for "harness vs agent"?

## Known gap

The CI `secrets` job scans only staged changes, so in CI it checks nothing (found 2026-11-10; a local full-history scan is clean). Commit-time scanning works. A fix is proposed but on hold, so S00-AC6 should not be marked ✅ until it's fixed.
