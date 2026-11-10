"""``create_harness``: the one call that wires a harness together (S01-AC12).

Harness part: the entry point. The CLI and the web server both use it, the
same way a framework gives you one call. Here every argument is a module we
wrote, so each line can be explained.

Does not: read settings or files itself; the caller passes everything in.
"""

from collections.abc import Iterable
from pathlib import Path

from agentic_harness.context import build_context
from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.model import ModelClient
from agentic_harness.pricing import Prices, load_prices
from agentic_harness.skills import load_skill_tool
from agentic_harness.tools.builtin import builtin_tools
from agentic_harness.trace import TraceWriter
from agentic_harness.workspace import Workspace, WorkspaceError

DEFAULT_TRACE_DIR = Path(".agentic-harness") / "traces"  # git-ignored


def create_harness(
    model: ModelClient,
    limits: Limits,
    workspace: Workspace,
    *,
    profile: str | None = None,
    trace_dir: Path | None = DEFAULT_TRACE_DIR,
    secrets: Iterable[str] = (),
    prices: Prices | None = None,
) -> Harness:
    """A harness for this model, workspace and profile.

    The context (memory files + skill list) is built here, once, before any call (D-37).
    Every run is traced unless ``trace_dir`` is None.
    """
    prices = prices or load_prices()
    prices.for_model(model.name)  # no price → fail now, not after the first call (D-25)
    context = build_context(workspace, workspace.check_profile(profile))
    # The workspace's own tools, then the built-ins it asked for (D-45), then load_skill.
    tools = [*workspace.tools, *builtin_tools(workspace.builtins)]
    if context.skills:
        tools.append(load_skill_tool(context.skills))  # built in: reads a skill on demand
    names = [t.name for t in tools]
    if clash := sorted({n for n in names if names.count(n) > 1}):
        raise WorkspaceError(f"Two tools are named {clash[0]!r}; tool names must be unique.")
    harness = Harness(
        model,
        limits,
        tools,
        prices=prices,
        system=context.system,
        context=context.summary(),
        root=workspace.path,  # where tools may read (readable) and write (tasks/, outbox/)
        readable=workspace.readable,
    )
    if trace_dir is not None:
        harness.subscribe(TraceWriter(trace_dir, secrets))
    return harness
