"""
Harness factory - the single place where configuration selects the active
harness. Swapping harnesses is a settings change, never a change to the
pipeline or the frontend.

Each branch is written out rather than looked up in a table, because harnesses
do not take the same constructor arguments: Codex needs an API key, the mock
needs nothing. A name-to-class table would force them to match.
"""

import os

from core.errors import ConfigError
from settings import SETTINGS

from .codex import CodexHarness
from .mock import MockHarness
from .types import Harness


def create_harness() -> Harness:
    """
    Build the configured harness, defaults to codex SDK
    """
    ai_settings = SETTINGS.ai_code_changes
    requested = ai_settings.harness.strip().lower()

    # Config every harness takes, applied the same way to each.
    # Max timeout we can allow per turn, harnasses need it in seconds so converting here
    timeout = ai_settings.turn_timeout_minutes * 60

    if requested == MockHarness.name:
        return MockHarness(
            timeout=timeout,
            # Env values are text, so "false" or "0" must be read as off, not as set.
            simulate_timeout=os.environ.get("MOCK_TIMEOUT", "").strip().lower()
            in ("1", "true", "yes"),
        )

    if requested == CodexHarness.name:
        # Codex only talks to OpenAI, so any other provider is a misconfiguration.
        if ai_settings.provider != "openai":
            raise ConfigError(
                f"harness {CodexHarness.name} needs provider openai, not {ai_settings.provider!r}"
            )
        if not ai_settings.key:
            raise ConfigError(
                f"harness {CodexHarness.name} but OPENAI_API_KEY is not set"
            )
        return CodexHarness(
            api_key=ai_settings.key,
            model=ai_settings.model,
            timeout=timeout,
            reasoning_effort=ai_settings.reasoning_effort,
        )

    raise ConfigError(f"unknown harness {requested!r}")
