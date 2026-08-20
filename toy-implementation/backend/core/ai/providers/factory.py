"""
Provider factory — the single place where configuration selects the active
provider. Swapping providers is an environment change, never a change to the
pipeline or the frontend.

Each branch is written out rather than looked up in a table, because providers
do not take the same constructor arguments: Codex needs an API key, the mock
needs nothing. A name-to-class table would force them to match.
"""

import os
from typing import Mapping

from ...errors import ConfigError
from .types import DEFAULT_TIMEOUT_SECONDS, Provider
from .codex import CodexProvider
from .mock import MockProvider


def create_provider(env: Mapping[str, str] | None = None) -> Provider:
    """
    Build the configured provider, defaults to codex.
    """
    env = os.environ if env is None else env
    requested = (env.get("AI_PROVIDER") or "codex").strip().lower()

    # Config every provider takes, applied the same way to each.
    timeout = float(DEFAULT_TIMEOUT_SECONDS)
    model = env.get("AI_MODEL")

    if requested == MockProvider.name:
        return MockProvider(
            model=model,
            timeout=timeout,
            simulate_timeout=bool(env.get("MOCK_TIMEOUT")),
        )

    if requested == CodexProvider.name:
        api_key = (env.get("OPENAI_API_KEY") or "").strip()
        if not api_key:
            raise ConfigError("AI_PROVIDER=codex but OPENAI_API_KEY is not set")
        return CodexProvider(api_key=api_key, model=model, timeout=timeout)

    raise ConfigError(f"unknown AI_PROVIDER {requested!r}")
