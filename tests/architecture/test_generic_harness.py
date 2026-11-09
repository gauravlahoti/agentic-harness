"""The harness knows no domain (S00-AC5, extended in S02-AC9).

If a business word shows up in ``src/agentic_harness/``, we built an agent, not a harness.
Domain-specific code belongs in a workspace under ``workspaces/``.
"""

import re
from pathlib import Path

HARNESS_SRC = Path(__file__).resolve().parents[2] / "src" / "agentic_harness"

# Words from the first workspace (CloudCo). S02 adds words each workspace declares.
DOMAIN_WORDS = ["cloudco", "shopco", "contract", "discount", "liability", "renewal", "redline"]


def test_s00_ac5_harness_source_has_no_domain_words() -> None:
    pattern = re.compile(r"\b(" + "|".join(DOMAIN_WORDS) + r")\b", re.IGNORECASE)
    hits = [
        f"{path.relative_to(HARNESS_SRC)}:{number}: {line.strip()}"
        for path in HARNESS_SRC.rglob("*.py")
        for number, line in enumerate(path.read_text().splitlines(), start=1)
        if pattern.search(line)
    ]
    assert hits == [], "Domain words inside the harness:\n" + "\n".join(hits)
