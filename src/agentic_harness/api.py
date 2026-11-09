"""``create_harness``: the one call that wires a harness together (S01-AC12).

Harness part: the entry point. The CLI and the web server both use it, the
same way a framework gives you one call. Here every argument is a module we
wrote, so each line can be explained.

Does not: read settings or files itself; the caller passes everything in.
"""

from collections.abc import Iterable
from pathlib import Path

from agentic_harness.limits import Limits
from agentic_harness.loop import Harness
from agentic_harness.model import ModelClient
from agentic_harness.pricing import Prices, load_prices
from agentic_harness.trace import TraceWriter
from agentic_harness.workspace import Workspace

DEFAULT_TRACE_DIR = Path(".agentic-harness") / "traces"  # git-ignored


def create_harness(
    model: ModelClient,
    limits: Limits,
    workspace: Workspace,
    *,
    trace_dir: Path | None = DEFAULT_TRACE_DIR,
    secrets: Iterable[str] = (),
    prices: Prices | None = None,
) -> Harness:
    """A harness for this model and workspace. Every run is traced unless trace_dir is None."""
    prices = prices or load_prices()
    prices.for_model(model.name)  # no price → fail now, not after the first call (D-25)
    harness = Harness(model, limits, workspace.tools, prices=prices)
    if trace_dir is not None:
        harness.subscribe(TraceWriter(trace_dir, secrets))
    return harness
