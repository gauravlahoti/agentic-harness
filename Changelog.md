# Changelog

Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) · versions follow [SemVer](https://semver.org).

## [Unreleased]

### Added
- Production scaffold: `src/` layout, uv + lockfile, ruff, mypy strict, pytest + coverage, Makefile, pre-commit (gitleaks), GitHub Actions CI, Dependabot ([Scaffold.md](Scaffold.md)).
- `agentic-harness` command with `--version`.
- Architecture tests: naming convention, domain-free harness.
- Spec v3: general harness + CloudCo Contract Assistant workspace, 9 stages.

### Changed
- Project named `agentic-harness` (package `agentic_harness`).
- Root documents renamed to Title case (`Decisions.md`, `Tracker.md`); `spec/README.md` → `spec/how-we-build.md`.
- `Readme.md` rewritten as a short project-level overview: what it is, start steps, what the harness does (with status), building an agent, scope.
