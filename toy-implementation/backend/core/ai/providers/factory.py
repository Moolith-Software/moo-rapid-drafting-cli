"""
Provider factory - the single place where configuration selects the active
provider. Swapping providers is an environment change, never a change to the
pipeline or the frontend.

Each branch is written out rather than looked up in a table, because providers
do not take the same constructor arguments: Codex needs an API key, the mock
needs nothing. A name-to-class table would force them to match.
"""

import os
from collections.abc import Mapping

from core.errors import ConfigError

from .codex import CodexProvider
from .mock import MockProvider
from .types import MAX_TURN_TIMEOUT, Provider


def create_provider(env: Mapping[str, str] | None = None) -> Provider:
    """
    Build the configured provider, defaults to codex.
    """
    env = os.environ if env is None else env
    requested = (env.get("AI_PROVIDER") or CodexProvider.name).strip().lower()

    # Config every provider takes, applied the same way to each.
    timeout = float(MAX_TURN_TIMEOUT)

    if requested == MockProvider.name:
        return MockProvider(
            timeout=timeout,
            simulate_timeout=bool(env.get("MOCK_TIMEOUT")),
        )

    if requested == CodexProvider.name:
        api_key = (env.get("OPENAI_API_KEY") or "").strip()
        model = "gpt-5.6"
        if not api_key:
            raise ConfigError(
                f"AI_PROVIDER={CodexProvider.name} but OPENAI_API_KEY is not set"
            )
        return CodexProvider(api_key=api_key, model=model, timeout=timeout)

    raise ConfigError(f"unknown AI_PROVIDER {requested!r}")
