"""Allow ``python -m agentic_harness`` as well as the ``agentic-harness`` command."""

from agentic_harness.cli import main

raise SystemExit(main())
