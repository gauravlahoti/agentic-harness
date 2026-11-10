"""Built-in tools work for any workspace (S03-AC2; D-45, D-46, D-47).

Each test uses a throwaway folder as the workspace: built-ins know no workspace.
"""

from pathlib import Path

import pytest

from agentic_harness.tools import ToolContext
from agentic_harness.tools.builtin import BUILTINS, builtin_tools
from agentic_harness.tools.registry import call_tool


def make(tmp_path: Path) -> ToolContext:
    (tmp_path / "docs" / "sub").mkdir(parents=True)
    (tmp_path / "docs" / "rules.md").write_text("Rule one.\n")
    (tmp_path / "docs" / "sub" / "more.md").write_text("More.\n")
    (tmp_path / "private.md").write_text("Not listed as readable.\n")
    (tmp_path / "workspace.toml").write_text('name = "x"\n')
    (tmp_path / ".env").write_text("SECRET=1\n")
    return ToolContext("run-7", tmp_path, readable=("docs",))


def test_s03_ac2_builtins_are_declared_with_risks() -> None:
    assert BUILTINS["read_file"].risk == "read"
    assert BUILTINS["write_file"].risk == "write"
    assert [t.name for t in builtin_tools(["write_file"])] == ["write_file"]
    with pytest.raises(ValueError, match="run_shell"):
        builtin_tools(["run_shell"])


async def test_s03_ac2_read_file_reads_inside_readable_folders(tmp_path: Path) -> None:
    ctx = make(tmp_path)
    result = await call_tool(BUILTINS["read_file"], {"path": "docs/rules.md"}, ctx)
    assert not result.is_error
    assert result.output == "Rule one.\n"


async def test_s03_ac2_read_file_on_a_folder_lists_it(tmp_path: Path) -> None:
    result = await call_tool(BUILTINS["read_file"], {"path": "docs"}, make(tmp_path))
    assert not result.is_error
    assert "docs/rules.md" in result.output
    assert "docs/sub/more.md" in result.output


@pytest.mark.parametrize(
    "path",
    ["private.md", "../outside.md", "docs/../private.md", "workspace.toml", ".env", "/etc/hosts"],
)
async def test_s03_ac2_read_file_refuses_everything_else(tmp_path: Path, path: str) -> None:
    result = await call_tool(BUILTINS["read_file"], {"path": path}, make(tmp_path))
    assert result.is_error
    assert "SECRET" not in result.output
    assert "Not listed" not in result.output


async def test_s03_ac2_read_file_refuses_a_link_out(tmp_path: Path) -> None:
    ctx = make(tmp_path)
    (tmp_path / "docs" / "link.md").symlink_to(tmp_path / ".env")
    result = await call_tool(BUILTINS["read_file"], {"path": "docs/link.md"}, ctx)
    assert result.is_error
    assert "SECRET" not in result.output


async def test_s03_ac2_read_file_missing_file_is_a_clear_error(tmp_path: Path) -> None:
    result = await call_tool(BUILTINS["read_file"], {"path": "docs/nope.md"}, make(tmp_path))
    assert result.is_error
    assert "docs/nope.md" in result.output


async def test_s03_ac2_write_file_writes_only_to_the_run_folder(tmp_path: Path) -> None:
    ctx = make(tmp_path)
    result = await call_tool(BUILTINS["write_file"], {"name": "draft.md", "text": "# Draft\n"}, ctx)
    assert not result.is_error
    assert "tasks/run-7/draft.md" in result.output
    assert (tmp_path / "tasks" / "run-7" / "draft.md").read_text() == "# Draft\n"
    bad = await call_tool(BUILTINS["write_file"], {"name": "../x.md", "text": "no"}, ctx)
    assert bad.is_error
    assert not (tmp_path / "tasks" / "x.md").exists()
