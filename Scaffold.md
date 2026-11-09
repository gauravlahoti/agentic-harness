# Scaffold

> The production baseline everything else is built on. Built as if for an enterprise client: reproducible installs, strict quality gates, CI, secret scanning, and clear conventions, with nothing added that we can't explain.

🟨 Built 2026-11-10 · waiting for your verification

## Names

| Thing | Name | Why |
|---|---|---|
| Project, repo, command | `agentic-harness` | Your choice |
| Python package (import name) | `agentic_harness` | Python import names can't contain hyphens |
| Runtime data folder | `.agentic-harness/` | Sessions, traces, notes (git-ignored) |

## Naming convention (enforced by `tests/architecture/test_naming.py`)

| Rule | Example |
|---|---|
| No ALL-CAPS file names | ~~`DECISIONS.md`~~ → `Decisions.md` |
| Root documents: Title case | `Readme.md` · `Scaffold.md` · `Decisions.md` · `Tracker.md` · `Security.md` · `Contributing.md` · `Changelog.md` · `Makefile` |
| Everything else: lowercase | `spec/00-product.md` · `src/agentic_harness/cli.py` · `tests/unit/` |
| Python files: lowercase_snake | `test_generic_harness.py` |

**Exceptions:** names an outside tool or standard requires exactly. Each is listed in the test with its reason.

| Name | Required by |
|---|---|
| `CLAUDE.md` | Claude Code loads project rules only from this name |
| `AGENTS.md` | Open convention many agent tools read (our workspaces use it) |
| `SKILL.md` | Agent Skills format; Google ADK validates the name |

## Layout

```
agentic-harness/
├── src/agentic_harness/      # THE HARNESS: domain-free (test-enforced)
│   ├── __init__.py           #   version
│   ├── __main__.py           #   python -m agentic_harness
│   ├── cli.py                #   the `agentic-harness` command
│   └── py.typed              #   "this package ships type hints"
├── tests/
│   ├── unit/                 # one behaviour at a time
│   └── architecture/         # rules about the codebase itself
├── workspaces/               # agents on the harness            (from S01)
├── docs/                     # stage walkthroughs, API notes    (from S00/S01)
├── evals/                    # scored tasks                     (S08)
├── spec/                     # product, company, UI, stages
├── .github/                  # CI, Dependabot, PR template
├── pyproject.toml · uv.lock · .python-version
├── Makefile · .pre-commit-config.yaml · .editorconfig · .gitattributes · .gitignore · .env.example
└── Readme.md · Scaffold.md · Decisions.md · Tracker.md · Security.md · Contributing.md · Changelog.md · CLAUDE.md
```

Folders are created when their first real file arrives: no empty placeholders.

## Choices

| Area | Chosen | Instead of | Because | Cost |
|---|---|---|---|---|
| Layout | **`src/` layout** | Package at the repo root | Tests run against the *installed* package, so packaging bugs surface early | One extra folder level |
| Packages + Python | **uv** + `uv.lock` | pip + requirements.txt | One fast tool; the lockfile makes every install identical | Team must use uv |
| Build backend | **`uv_build`** | hatchling, setuptools | Native to uv, zero config for a `src/` package | Ties the build to uv |
| Dependency bounds | **Lower bounds + lockfile; `google-genai` capped below v4** | Pinning everything in `pyproject.toml` | The lock gives exact versions; the cap stops a breaking Gemini SDK release slipping in | A deliberate bump for v4 |
| Lint + format | **ruff** (incl. security, naming, async, docstring rules) | flake8 + black + isort + bandit | One fast tool replaces five | Rule set to maintain |
| Types | **mypy, strict** | No type checking · pyright | Catches whole classes of bugs before runtime; the standard in Python teams | More annotations to write |
| Tests | **pytest + pytest-asyncio + coverage ≥ 75%** (D-33; 85% again with the evals) | unittest | The standard; async support for the loop; coverage keeps tests honest | A coverage floor to keep |
| Live tests | **`live` marker, off by default** | Live calls in every run | Offline tests stay free and deterministic; live runs on purpose | Live breakage found later |
| Task runner | **Makefile** | justfile, scripts folder | Already on every Mac and CI runner; one command per task | Make syntax is quirky |
| Commit hooks | **pre-commit**: file hygiene, **gitleaks**, ruff, mypy | No hooks | Problems stop at the commit, not in review. Local hooks use `uv run`, so versions match `uv.lock`. | ~2 s per commit |
| CI | **GitHub Actions**: `make check` + secret scan of full history | Separate CI scripts | CI runs the exact local command; never "works on my machine" | Needs a GitHub repo to run |
| CI security | **Read-only token, actions pinned to exact commit SHAs, timeouts, cancel superseded runs** | Defaults · version tags (`@v10`) | Least privilege; a tag can be moved or not exist, a commit can't; no hung or duplicate runs | SHAs are unreadable, so each has a version comment; Dependabot updates them |
| Updates | **Dependabot** weekly, grouped (Python + Actions) | Manual updates | Security fixes arrive as reviewed PRs | Weekly PRs to merge |
| Editors | **.editorconfig + .gitattributes** (UTF-8, LF) | Editor defaults | Same whitespace and line endings on every machine | — |
| Secrets | **`.env` git-ignored, `.env.example` committed, gitleaks in hooks + CI** | Trusting care | Three layers between a key and a commit | — |
| Architecture guard | **Tests for naming + domain-free harness** | Code review only | Rules that matter are checked by machines, every run | False positives possible |

## Quality gates: what blocks a change

| Gate | Where it runs |
|---|---|
| ruff lint + format check | pre-commit · `make check` · CI |
| mypy strict | pre-commit · `make check` · CI |
| pytest + coverage ≥ 75% (incl. naming + domain-free tests; D-33) | `make check` · CI |
| gitleaks secret scan | pre-commit · CI (full history) |

## Not included yet (on purpose)

| Item | When |
|---|---|
| Dockerfile / container image | Only if we deploy; the plan has no cloud deploy |
| License file | When you decide public vs private repo |
| `CODEOWNERS` | When there's a team (it would also need an upper-case exception) |
| Structured app logging | S00 config + S01 events (events are our logging) |

## Commands

| Command | Does |
|---|---|
| `make setup` | Install exactly what `uv.lock` says |
| `make hooks` | Install the git hooks (once) |
| `make check` | Lint + types + tests: everything CI runs |
| `make format` | Auto-fix formatting |
| `make live` | Live Gemini tests (needs `.env`, costs cents) |
| `make help` | List all commands |

## Verify it yourself

1. `make setup && make check` → all green, coverage shown.
2. `uv run agentic-harness --version` → `agentic-harness 0.1.0`.
3. Rename any file to `TEST.md` and run `make test` → the naming test fails. Undo it.
4. Add the word "contract" to `src/agentic_harness/cli.py` and run `make test` → the domain-free test fails. Undo it.
