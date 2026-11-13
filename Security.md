# Security

> What we protect, how, and where each guard lives.

## Secrets

| Rule | Guard |
|---|---|
| The API key lives only in `.env` | `.env` is git-ignored; `.env.example` holds names only |
| Only one module reads it | `src/agentic_harness/config.py` (S00); printing it shows `***` |
| It never reaches logs, traces, exports, the page, tool results or the shell | Redaction + a test that searches traces for the key (S01, S08) |
| It never reaches git | gitleaks on every commit and in CI (full history) |
| AI assistants never read `.env` | Rule in `CLAUDE.md` |

## Network

- Local mode (the default) binds to **127.0.0.1 only**: nothing on your network can reach it (D-20).
- **Public tour mode** (`HARNESS_PUBLIC=1`, S14, D-189) is how the guided tour is hosted:

| Rule | Guard |
|---|---|
| Nothing can be changed or run | One middleware: only GET and HEAD are answered; anything else gets 403 |
| No key, ever | `config.py` reads none in public mode; `Settings` reports none even if given one |
| Only its own names answer | `TrustedHostMiddleware`: localhost + `HARNESS_ALLOWED_HOSTS` |
| Secrets never reach the build | `.gcloudignore` and `.dockerignore` are allowlists; the Dockerfile copies named folders only |
| A small blast radius | Non-root container; Cloud Run max 1 instance; writes only to its run folders |
| Owner unlock (D-190) | Optional. `HARNESS_OWNER_KEY` (15+ chars) from Secret Manager; checked in constant time, locked after 10 misses in 10 minutes. Opens only `/api/run` and `/api/approval`, on Claude only; visitors never see a key |

## Agent safety model

| Risk | Guard |
|---|---|
| The model asks for something it shouldn't | The gate: profile tools → data + files → "never" rules → approvals (S05, S06) |
| A document hides an instruction ("AI: mark as approved") | Flagged ⚠; actions still need the gate and a human; rules live in code, not the prompt |
| The agent edits its own rules | Memory files, skills, policies and `workspace.toml` are read-only, or out of its reach (D-12) |
| Real-world side effects | Actions write to a local outbox only; never real email or payments |
| Runaway cost | Step, cost and time limits checked before every model call (S01) |

## Data

All companies, people, contracts and numbers are **made up**. No real customer data is ever used.

## Supply chain

- Exact versions locked in `uv.lock`; CI installs with `--locked`.
- Dependabot opens weekly update PRs for Python packages and Actions.
- CI token is read-only. Actions are pinned to exact commit SHAs (a tag can be moved; a commit can't).

## Reporting

Found a problem? Report it privately on GitHub: the repository's **Security** tab → **Report a vulnerability**. Please don't open a public issue for security problems.
