"""``@tool`` and ``call_tool``: declare a tool from a plain function, and run it safely.

Harness part: actions (S03-AC1, AC8).

``@tool(risk=...)`` reads the function itself (D-43):
- its name → the tool name; its docstring → the description (the model's instructions);
- each parameter's type hint → the JSON schema: ``str`` ``int`` ``float`` ``bool``,
  ``Literal[...]`` (an enum), ``list[...]`` of those; ``Annotated[T, "text"]`` adds a
  description; a default value makes it optional;
- a parameter named ``ctx`` is filled in by the harness and never shown to the model (D-48).

``call_tool`` checks the arguments first (D-49), never lets an exception escape (a broken
tool is news for the model, not a crash), and cuts long output with a visible note (D-50).

Does not: decide whether a tool *may* run. That is the gate's job (S05, S06).
"""

import inspect
import json
import types
import typing
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Annotated, Any, Literal, Union, get_args, get_origin

from agentic_harness.tools import RISKS, Risk, Tool, ToolContext

MAX_OUTPUT_CHARS = 20_000
JSON_TYPES = {str: "string", int: "integer", float: "number", bool: "boolean"}


def tool(*, risk: Risk, name: str | None = None) -> Callable[[Callable[..., Any]], Tool]:
    """Turn a function into a Tool. ``risk`` is required: read, write or action (D-44)."""
    if risk not in RISKS:
        raise ValueError(f"risk must be one of {', '.join(RISKS)}, not {risk!r}.")

    def wrap(function: Callable[..., Any]) -> Tool:
        description = inspect.getdoc(function)
        if not description:
            raise ValueError(
                f"{function.__name__} needs a docstring: it is the model's instructions."
            )
        parameters, takes_ctx = _schema(function)
        return Tool(
            name=name or function.__name__,
            description=description,
            risk=risk,
            parameters=parameters,
            function=function,
            takes_ctx=takes_ctx,
        )

    return wrap


def _schema(function: Callable[..., Any]) -> tuple[dict[str, Any], bool]:
    hints = typing.get_type_hints(function, include_extras=True)
    properties: dict[str, Any] = {}
    required: list[str] = []
    takes_ctx = False
    for param in inspect.signature(function).parameters.values():
        if param.name == "ctx":
            takes_ctx = True  # the harness fills it in; the model never sees it
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            raise ValueError(f"{function.__name__}: *args and **kwargs can't be described.")
        if param.name not in hints:
            raise ValueError(f"{function.__name__}: parameter {param.name} needs a type hint.")
        properties[param.name] = _json_type(hints[param.name], f"{function.__name__}.{param.name}")
        if param.default is inspect.Parameter.empty:
            required.append(param.name)
    return {"type": "object", "properties": properties, "required": required}, takes_ctx


def _json_type(hint: Any, where: str) -> dict[str, Any]:
    origin, args = get_origin(hint), get_args(hint)
    if origin is Annotated:
        schema = _json_type(args[0], where)
        notes = [a for a in args[1:] if isinstance(a, str)]
        return {**schema, "description": notes[0]} if notes else schema
    if origin in (Union, types.UnionType) and type(None) in args:
        rest = [a for a in args if a is not type(None)]
        if len(rest) == 1:  # "X | None": optional X (it must also have a default)
            return _json_type(rest[0], where)
    if origin is Literal:
        kinds = {type(a) for a in args}
        if len(kinds) == 1 and (kind := kinds.pop()) in (str, int):
            return {"type": JSON_TYPES[kind], "enum": list(args)}
    if origin is list and len(args) == 1:
        return {"type": "array", "items": _json_type(args[0], where)}
    if hint in JSON_TYPES:
        return {"type": JSON_TYPES[hint]}
    raise ValueError(
        f"{where}: type {hint!r} is not supported (use str, int, float, bool, Literal, list)."
    )


def check_arguments(tool: Tool, arguments: Mapping[str, Any]) -> list[str]:
    """Problems with the model's arguments, in words it can act on. Empty = fine."""
    properties = tool.parameters.get("properties", {})
    problems = [
        f"{name} is required"
        for name in tool.parameters.get("required", [])
        if name not in arguments
    ]
    for name, value in arguments.items():
        if name not in properties:
            problems.append(f"unknown argument: {name}")
        else:
            problems.extend(_check_value(name, value, properties[name]))
    return problems


def _check_value(name: str, value: Any, schema: Mapping[str, Any]) -> list[str]:
    kind = schema.get("type")
    if "enum" in schema:
        options = schema["enum"]
        return (
            [] if value in options else [f"{name} must be one of: {', '.join(map(str, options))}"]
        )
    if kind == "array":
        item_kind = schema.get("items", {}).get("type", "")
        ok = isinstance(value, list) and all(_is(item, item_kind) for item in value)
        return [] if ok else [f"{name} must be a list of {item_kind}s"]
    if not _is(value, kind or ""):
        article = "an" if (kind or "").startswith(("a", "e", "i", "o", "u")) else "a"
        return [f"{name} must be {article} {kind}"]
    return []


def _is(value: Any, kind: str) -> bool:
    if isinstance(value, bool):  # in Python, True is also an int: check it first
        return kind == "boolean"
    if kind == "integer":
        return isinstance(value, int) or (isinstance(value, float) and value.is_integer())
    if kind == "number":
        return isinstance(value, int | float)
    return kind == "string" and isinstance(value, str)


@dataclass(frozen=True, slots=True)
class ToolResult:
    output: str
    is_error: bool


async def call_tool(
    tool: Tool, arguments: Mapping[str, Any], ctx: ToolContext | None
) -> ToolResult:
    """Run one tool. Whatever happens, the model gets text back, never an exception."""
    problems = check_arguments(tool, arguments)
    if problems:
        return ToolResult(_cap("Invalid arguments: " + "; ".join(problems) + "."), is_error=True)
    kwargs = {
        key: int(value) if _whole_float(value, tool, key) else value
        for key, value in arguments.items()
    }
    if tool.takes_ctx:
        if ctx is None:
            return ToolResult(f"{tool.name} needs a workspace folder, and this run has none.", True)
        kwargs["ctx"] = ctx
    try:
        value = tool.function(**kwargs)
        if inspect.isawaitable(value):
            value = await value
    except Exception as error:  # a broken tool is news for the model, not a crash
        return ToolResult(_cap(f"{type(error).__name__}: {error}"), is_error=True)
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return ToolResult(_cap(text), is_error=False)


def _whole_float(value: Any, tool: Tool, key: str) -> bool:
    """JSON may send 3.0 for an integer; the function should still get 3."""
    kind = tool.parameters.get("properties", {}).get(key, {}).get("type")
    return kind == "integer" and isinstance(value, float)


def _cap(text: str) -> str:
    if len(text) <= MAX_OUTPUT_CHARS:
        return text
    more = len(text) - MAX_OUTPUT_CHARS
    return f"{text[:MAX_OUTPUT_CHARS]}\n[cut: {more} more characters; ask for a smaller part]"
