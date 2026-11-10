"""Evals for agents on the harness (S10): golden cases, code checks and DeepEval metrics.

Not part of the harness: ``src/agentic_harness/`` never imports this package (D-115). The
server starts ``python -m evals.run`` as one fixed command and reads the result files.

DeepEval is told, before it is ever imported, to send no telemetry and to read no ``.env``:
only ``agentic_harness.config`` reads the keys (S00-AC11).
"""

import os
from pathlib import Path

os.environ["DEEPEVAL_TELEMETRY_OPT_OUT"] = "1"  # no usage pings to DeepEval's analytics
os.environ["DEEPEVAL_DISABLE_DOTENV"] = "1"  # DeepEval must not load our .env (keys)
# DeepEval's own scratch folder, kept out of the project root (git-ignored either way).
os.environ["DEEPEVAL_CACHE_FOLDER"] = str(
    Path(__file__).resolve().parent.parent / ".agentic-harness" / "evals" / ".deepeval"
)
