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
from ...utils import readable_duration
from .types import MAX_TURN_TIMEOUT, Provider, TurnOutcome


NOTE_FILE = "MOCK_CHANGE.md"  # what the mock writes, so the diff has something real


class MockProvider(Provider):
    name = "mock"

    def __init__(
        self,
        timeout: float = MAX_TURN_TIMEOUT,
        simulate_timeout: bool = False,
    ):
        # No model: there is no real one to pick, so it stays None on the base.
        super().__init__(timeout=timeout)
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
            raise self.tag(
                TurnTimeout(f"no result after {readable_duration(self.timeout)} (mock)")
            )

        # Reuse whichever session we were given so resume/fork behave believably.
        session = session_id or fork_from or f"mock-{uuid.uuid4().hex[:8]}"

        # A real edit, so snapshot/diff sees an actual change.
        note = Path(workspace) / NOTE_FILE
        previous = note.read_text() if note.exists() else ""
        note.write_text(f"{previous}- {prompt.splitlines()[-1][:80]}\n")

        return TurnOutcome(text=self._placeholder(output_schema), session_id=session)

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
