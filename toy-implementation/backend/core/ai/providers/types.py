"""
What every provider must look like.

A provider runs one turn against a workspace and returns whatever the model
finally said. It knows nothing about features, prompts, or what the text means —
that belongs to the operation asking for it (see core/ai/operations).

Providers are classes rather than modules so more than one can exist at a time:
two features can run side by side on different providers, and a caller can pass
the one it wants instead of the whole process sharing a single choice.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


@dataclass
class TurnOutcome:
    """The raw result of one turn."""

    ok: bool
    text: str  # the model's final response, unparsed
    session_id: str  # store this to resume or fork later
    usage: dict = field(default_factory=dict)
    error: str | None = None


# How long a single turn may run before it is interrupted. A backstop for a hung
# turn, not a target — big refactors legitimately run for many minutes.
MAX_TURN_TIMEOUT = 20 * 60


class Provider(ABC):
    """The one thing every provider does."""

    name: str  # how the factory refers to it, e.g. "codex"

    def __init__(
        self,
        model: str | None = None,
        timeout: float = MAX_TURN_TIMEOUT,
    ):
        self.model = model  # None means the provider's own default
        self.timeout = timeout  # seconds a single turn may run

    @abstractmethod
    def run_turn(
        self,
        workspace: Path,
        prompt: str,
        output_schema: dict,
        on_progress: Callable[[str], None],
        session_id: str | None = None,
        fork_from: str | None = None,
    ) -> TurnOutcome:
        """
        Run one turn over `workspace`.

        Pass `fork_from` to branch a parent's session, `session_id` to continue
        an existing one, or neither to start fresh. Blocks until the turn
        finishes, so call it from a background thread.
        """
