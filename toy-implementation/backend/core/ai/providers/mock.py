"""
A fake provider: no API calls, no cost.

It makes a real (small) edit to the workspace, so change detection has something
genuine to find and the whole pipeline — clone, turn, diff, summary, status — can
be exercised end to end offline.

Set `simulate_timeout` to make it raise TurnTimeout instead, so the timeout path
can be tested without spending API calls on a turn we mean to kill.
"""

import json
import time
import uuid
from pathlib import Path
from typing import Callable

from ...errors import TurnTimeout
from .types import DEFAULT_TIMEOUT_SECONDS, Provider, TurnOutcome


class MockProvider(Provider):
    name = "mock"

    def __init__(
        self,
        model: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        note_file: str = "MOCK_CHANGE.md",
        simulate_timeout: bool = False,
    ):
        super().__init__(model=model, timeout=timeout)
        self.note_file = note_file
        self.simulate_timeout = simulate_timeout

    def run_turn(
        self,
        workspace: Path,
        prompt: str,
        output_schema: dict,
        on_progress: Callable[[str], None],
        session_id: str | None = None,
        fork_from: str | None = None,
    ) -> TurnOutcome:
        on_progress("Mock provider is working…")

        if self.simulate_timeout:
            time.sleep(1)
            raise TurnTimeout(f"no result after {self.timeout:.0f}s")

        # Reuse whichever session we were given so resume/fork behave believably.
        session = session_id or fork_from or f"mock-{uuid.uuid4().hex[:8]}"

        # A real edit, so snapshot/diff sees an actual change.
        note = Path(workspace) / self.note_file
        previous = note.read_text() if note.exists() else ""
        note.write_text(f"{previous}- {prompt.splitlines()[-1][:80]}\n")

        return TurnOutcome(
            ok=True, text=self._placeholder(output_schema), session_id=session
        )

    def _placeholder(self, schema: dict) -> str:
        """
        Build a reply that satisfies whatever schema was asked for.

        The mock has no idea what the fields mean, so every required property
        gets a stand-in value of the right type. That keeps it usable by any
        operation.
        """
        properties = schema.get("properties", {})
        reply = {}
        for key in schema.get("required", []):
            kind = properties.get(key, {}).get("type")
            reply[key] = [] if kind == "array" else f"mock {key}"
        return json.dumps(reply)
