"""Repository naming convention (S00-AC4). See Scaffold.md → Naming.

- No ALL-CAPS file names. Docs use Title case (``Decisions.md``) or lowercase.
- Exceptions: names an outside tool or standard requires exactly.
- Folders and Python files: lowercase.
"""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Each exception is required by something outside our control.
REQUIRED_EXACT_NAMES = {
    "CLAUDE.md",  # Claude Code loads project instructions from this exact name
    "AGENTS.md",  # open convention many agent tools read
    "SKILL.md",  # Agent Skills format (also validated by Google ADK)
}

PYTHON_FILE = re.compile(r"^[a-z0-9_]+\.py$")
FOLDER = re.compile(r"^[a-z0-9._-]+$")


def repo_files() -> list[Path]:
    """Files git would track: committed + new, minus anything in .gitignore."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [Path(line) for line in out.splitlines() if line]


def test_s00_ac4_no_all_caps_file_names() -> None:
    offenders = [
        str(path)
        for path in repo_files()
        if path.name not in REQUIRED_EXACT_NAMES
        and len(path.stem) > 1
        and path.stem.replace("_", "").replace("-", "").isupper()
    ]
    assert offenders == [], f"ALL-CAPS names (use Title case or lowercase): {offenders}"


def test_s00_ac4_python_files_are_lowercase() -> None:
    offenders = [
        str(path)
        for path in repo_files()
        if path.suffix == ".py" and not PYTHON_FILE.match(path.name)
    ]
    assert offenders == [], f"Python files must be lowercase_snake: {offenders}"


def test_s00_ac4_folders_are_lowercase() -> None:
    offenders = sorted(
        {part for path in repo_files() for part in path.parts[:-1] if not FOLDER.match(part)}
    )
    assert offenders == [], f"Folders must be lowercase: {offenders}"
