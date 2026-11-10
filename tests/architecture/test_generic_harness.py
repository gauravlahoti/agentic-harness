"""The harness knows no domain (S00-AC5, S02-AC9).

If a business word shows up in ``src/agentic_harness/``, we built an agent, not a harness.
Each workspace declares its own words in ``workspace.toml`` (D-40); this test checks every
text file of the harness (Python, page, data) against all of them.
"""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HARNESS_SRC = ROOT / "src" / "agentic_harness"
TEXT_FILES = {".py", ".js", ".html", ".css", ".toml", ".md"}

# Words from the first workspace, kept so the guard works even if its toml changes.
BASELINE_WORDS = {"cloudco", "shopco", "contract", "discount", "liability", "renewal", "redline"}


def workspace_words() -> dict[str, set[str]]:
    words = {}
    for toml in sorted(ROOT.glob("workspaces/*/workspace.toml")):
        declared = tomllib.loads(toml.read_text()).get("domain_words", [])
        words[toml.parent.name] = {w.lower() for w in declared}
    return words


def test_s02_ac9_workspaces_declare_their_words() -> None:
    words = workspace_words()
    assert words.get("cloudco"), "cloudco must declare its domain words"
    assert words["cloudco"] >= BASELINE_WORDS


def test_s00_ac5_s02_ac9_harness_source_has_no_domain_words() -> None:
    every_word = BASELINE_WORDS.union(*workspace_words().values())
    pattern = re.compile(r"\b(" + "|".join(map(re.escape, sorted(every_word))) + r")\b", re.I)
    hits = [
        f"{path.relative_to(HARNESS_SRC)}:{number}: {line.strip()}"
        for path in HARNESS_SRC.rglob("*")
        if path.suffix in TEXT_FILES
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]
    assert hits == [], "Domain words inside the harness:\n" + "\n".join(hits)


def test_s03_ac3_harness_names_no_workspace_tool() -> None:
    """The harness may run ``review_contract`` but must never mention it (spec rule 1)."""
    names = set()
    for tools_file in ROOT.glob("workspaces/*/tools.py"):
        names |= set(
            re.findall(r"^(?:async )?def ([a-z][a-z0-9_]*)\(", tools_file.read_text(), re.M)
        )
    names -= {"main"}
    assert names, "expected workspace tools to check against"
    pattern = re.compile(r"\b(" + "|".join(sorted(names)) + r")\b")
    hits = [
        f"{path.relative_to(HARNESS_SRC)}:{number}: {line.strip()}"
        for path in HARNESS_SRC.rglob("*")
        if path.suffix in TEXT_FILES
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]
    assert hits == [], "Workspace tool names inside the harness:\n" + "\n".join(hits)
