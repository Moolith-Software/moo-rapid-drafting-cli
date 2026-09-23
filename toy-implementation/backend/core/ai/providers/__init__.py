"""
Who does the work.

A provider runs one turn against a workspace and returns whatever the model
finally said. It knows nothing about features, prompts, or what the text means —
that belongs to the operation asking for it (see core/ai/operations).

    types.py     the Provider contract and TurnOutcome
    factory.py   create_provider() — the one place configuration is read
    codex.py     the real OpenAI Codex agent
    mock.py      a fake one for offline work (the default)
"""

from .factory import create_provider
from .types import Provider, TurnOutcome

__all__ = ["Provider", "TurnOutcome", "create_provider"]
