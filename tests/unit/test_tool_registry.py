"""``@tool`` and calling a tool safely (S03-AC1, S03-AC8; D-43, D-44, D-48, D-49, D-50).

Tools here are tiny made-up functions: the harness is checked against the *shape* of a
tool, never against a workspace's tools.
"""

from pathlib import Path
from typing import Annotated, Literal

import pytest

from agentic_harness.tools import Tool, ToolContext
from agentic_harness.tools.registry import call_tool, check_arguments, tool
from agentic_harness.trimming import OUTPUT_LIMIT_CHARS


@tool(risk="read")
def look_up(
    item_id: Annotated[str, "The record's ID, e.g. 'IT-1'"],
    kind: Literal["small", "large"] = "small",
    limit: int = 5,
    tags: list[str] | None = None,
    exact: bool = False,
    weight: float = 1.0,
) -> dict[str, object]:
    """Look up one record by ID. Use it when the task names a record."""
    return {"id": item_id, "kind": kind, "limit": limit, "tags": tags or [], "exact": exact}


@tool(risk="action")
def act(note: str, ctx: ToolContext) -> str:
    """Do something with side effects."""
    return ctx.save_outbox_file("note.txt", note)


def test_s03_ac1_tool_records_name_description_risk() -> None:
    assert isinstance(look_up, Tool)
    assert look_up.name == "look_up"
    assert look_up.description == "Look up one record by ID. Use it when the task names a record."
    assert look_up.risk == "read"
    assert look_up.function("IT-1")["id"] == "IT-1"  # still a plain, testable function


def test_s03_ac1_schema_comes_from_type_hints() -> None:
    schema = look_up.parameters
    assert schema["type"] == "object"
    assert schema["required"] == ["item_id"]  # only parameters without a default
    props = schema["properties"]
    assert props["item_id"] == {"type": "string", "description": "The record's ID, e.g. 'IT-1'"}
    assert props["kind"] == {"type": "string", "enum": ["small", "large"]}
    assert props["limit"] == {"type": "integer"}
    assert props["tags"] == {"type": "array", "items": {"type": "string"}}
    assert props["exact"] == {"type": "boolean"}
    assert props["weight"] == {"type": "number"}


def test_s03_ac1_ctx_is_hidden_from_the_model() -> None:
    assert act.takes_ctx
    assert "ctx" not in act.parameters["properties"]
    assert act.parameters["required"] == ["note"]


def test_s03_ac1_outputs_geminis_function_format() -> None:
    assert look_up.declaration() == {
        "type": "function",
        "name": "look_up",
        "description": look_up.description,
        "parameters": look_up.parameters,
    }


def test_s03_ac1_risk_is_required_and_checked() -> None:
    with pytest.raises(ValueError, match="risk"):
        tool(risk="dangerous")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        tool()  # type: ignore[call-arg]


def test_s03_ac1_a_tool_needs_a_docstring_and_simple_types() -> None:
    def no_doc(x: str) -> str:
        return x

    with pytest.raises(ValueError, match="docstring"):
        tool(risk="read")(no_doc)

    def odd_type(x: dict[str, str]) -> str:
        """Odd."""
        return ""

    with pytest.raises(ValueError, match="x"):
        tool(risk="read")(odd_type)

    def no_hint(x) -> str:  # type: ignore[no-untyped-def]
        """No hint."""
        return ""

    with pytest.raises(ValueError, match="type hint"):
        tool(risk="read")(no_hint)


def test_s03_ac8_arguments_are_checked_before_running() -> None:
    assert check_arguments(look_up, {"item_id": "IT-1"}) == []
    assert check_arguments(look_up, {}) == ["item_id is required"]
    problems = check_arguments(look_up, {"item_id": 7, "kind": "huge", "zzz": 1, "tags": [1]})
    assert "item_id must be a string" in problems
    assert "kind must be one of: small, large" in problems
    assert "unknown argument: zzz" in problems
    assert "tags must be a list of strings" in problems
    assert check_arguments(look_up, {"item_id": "x", "limit": True}) == ["limit must be an integer"]
    assert check_arguments(look_up, {"item_id": "x", "limit": 3.0}) == []  # JSON may send 3.0


async def test_s03_ac8_bad_arguments_go_back_as_an_error() -> None:
    result = await call_tool(look_up, {"kind": "huge"}, None)
    assert result.is_error
    assert "item_id is required" in result.output


async def test_s03_ac8_a_raising_tool_becomes_an_error_result() -> None:
    @tool(risk="read")
    def broken(x: str) -> str:
        """Always fails."""
        raise RuntimeError(f"no record {x}")

    result = await call_tool(broken, {"x": "IT-9"}, None)
    assert result.is_error
    assert result.output == "RuntimeError: no record IT-9"


async def test_s03_ac8_async_tools_and_json_output() -> None:
    @tool(risk="read")
    async def later(x: str) -> dict[str, str]:
        """Async."""
        return {"echo": x, "section": "§2"}

    result = await call_tool(later, {"x": "a"}, None)
    assert not result.is_error
    assert result.output == '{"echo": "a", "section": "§2"}'  # readable, not \\u00a7


async def test_s03_ac8_big_output_is_cut_with_a_visible_note() -> None:
    @tool(risk="read")
    def huge() -> str:
        """Too much."""
        return "x" * (OUTPUT_LIMIT_CHARS + 500)

    result = await call_tool(huge, {}, None)
    assert len(result.output) < OUTPUT_LIMIT_CHARS + 100
    assert "cut from the middle" in result.output  # start and end stay (S07-AC5)


async def test_s03_ac8_ctx_is_passed_in_and_writes_are_announced(tmp_path: Path) -> None:
    seen: list[tuple[str, dict[str, object]]] = []
    ctx = ToolContext("run-1", tmp_path, emit=lambda type_, **data: seen.append((type_, data)))
    result = await call_tool(act, {"note": "hello"}, ctx)
    assert not result.is_error
    assert result.output == "outbox/note.txt"
    assert (tmp_path / "outbox" / "note.txt").read_text() == "hello"
    assert seen == [
        (
            "file_saved",
            {"path": "outbox/note.txt", "folder": "outbox", "text": "hello", "call_id": ""},
        )
    ]


async def test_s03_ac8_a_ctx_tool_without_a_workspace_is_an_error() -> None:
    result = await call_tool(act, {"note": "x"}, None)
    assert result.is_error
    assert "workspace" in result.output


def test_s03_ac7_files_are_saved_only_by_plain_name(tmp_path: Path) -> None:
    ctx = ToolContext("run-1", tmp_path)
    assert ctx.save_task_file("draft.md", "hi") == "tasks/run-1/draft.md"
    for bad in ("../escape.md", "a/b.md", ".env", "", "x" * 200):
        with pytest.raises(ValueError, match="file name"):
            ctx.save_task_file(bad, "no")
    assert not (tmp_path / "escape.md").exists()
