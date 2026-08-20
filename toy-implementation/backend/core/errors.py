"""
Every failure we report, in one place.

Anything that can go wrong raises an AppError carrying a numeric `code` and a
short `title`. Callers catch AppError, store `message()` on the feature, and
never have to stringify a raw exception.

    1xxx  workspace      — preparing a copy of the code
    2xxx  configuration  — how the AI is set up
    3xxx  output         — the AI replied, but not in the shape we asked for
    9xxx  unknown        — anything we did not anticipate
"""


class AppError(Exception):
    """Base for every failure. `detail` adds context beyond the fixed title."""

    code = 9000
    title = "Unexpected error"

    def __init__(self, detail: str = ""):
        super().__init__(detail or self.title)
        self.detail = detail

    def message(self) -> str:
        """One line for the status field: '[2000] Not configured: ...'."""
        return f"[{self.code}] {self.title}" + (f": {self.detail}" if self.detail else "")


# --- 1xxx workspace ---------------------------------------------------------


class WorkspaceExists(AppError):
    code = 1000
    title = "Workspace already exists"


class CopyUnavailable(AppError):
    code = 1001
    title = "Copy-on-write unavailable"


# --- 2xxx configuration -----------------------------------------------------


class ConfigError(AppError):
    """The AI is misconfigured — unknown provider, missing key."""

    code = 2000
    title = "AI not configured"


class ProviderFailed(AppError):
    """The provider ran and reported failure."""

    code = 2001
    title = "AI provider failed"


class TurnTimeout(AppError):
    """The turn outran its time limit and was interrupted."""

    code = 2002
    title = "AI timed out"


# --- 3xxx output ------------------------------------------------------------


class BadOutput(AppError):
    """The reply did not match the schema we asked for."""

    code = 3000
    title = "Unusable AI response"


def wrap(exc: Exception) -> AppError:
    """Turn any exception into an AppError so callers handle only one type."""
    if isinstance(exc, AppError):
        return exc
    return AppError(f"{type(exc).__name__}: {exc}")
