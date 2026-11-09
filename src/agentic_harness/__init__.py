"""Agent harness: a domain-free runtime that turns a model into an agent.

The harness knows no business domain. Everything specific to one agent
(rules, skills, tools, profiles, approvals) lives in a workspace under
``workspaces/``. Architecture tests enforce this.
"""

from importlib.metadata import version

__version__ = version("agentic-harness")
