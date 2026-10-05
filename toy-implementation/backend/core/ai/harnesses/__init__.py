"""
Who does the work.

A harness runs one turn against a workspace and returns whatever the model
finally said. It knows nothing about features, prompts, or what the text means -
that belongs to the operation asking for it (see core/ai/operations).

    types.py     the Harness contract, HarnessName and TurnOutcome
    factory.py   create_harness() - builds the harness settings.py names
    codex.py     the real OpenAI Codex agent
    mock.py      a fake one for offline work (the default)
"""

from .factory import create_harness
from .types import Harness, HarnessName, TurnOutcome

__all__ = ["Harness", "HarnessName", "TurnOutcome", "create_harness"]
