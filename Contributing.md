# Contributing

> Spec first, one stage at a time, every change proven.

## Workflow

1. **Stage brief:** goal, outcomes and every design choice (options → chosen → why → cost), agreed before code.
2. **Tests first**, named after the checks they prove (`test_s05_ac4_…`).
3. **Build**, keeping `src/agentic_harness/` free of domain words.
4. **`make check`** green, with real output shown.
5. **Update** `Tracker.md` (evidence) and `Decisions.md` (if a choice changed).
6. **Verify** live; only the owner marks ✅.

Full process: [spec/how-we-build.md](spec/how-we-build.md).

## Setup

```bash
make setup && make hooks
```

## Conventions

| Topic | Rule |
|---|---|
| File names | No ALL-CAPS; root docs Title case; everything else lowercase ([Scaffold.md](Scaffold.md#naming-convention-enforced-by-testsarchitecturetest_namingpy)) |
| Code | Typed (mypy strict), formatted by ruff, a docstring on every module (purpose · harness part · what it does *not* do) |
| Comments | Say *why*, not *what* |
| Branches | `stage-N/short-topic` |
| Commits | [Conventional Commits](https://www.conventionalcommits.org): `feat(s01): add stop rules (S01-AC9)` |
| Tags | `stage-N` after the owner verifies the stage |

## Definition of done (every change)

- [ ] `make check` passes
- [ ] Each changed behaviour has a test linked to a check ID
- [ ] No domain words in `src/agentic_harness/`
- [ ] `Tracker.md` updated with evidence
- [ ] `Decisions.md` updated if a design choice changed
- [ ] Secrets never touched or printed
