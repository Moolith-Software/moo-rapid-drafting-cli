"""
Every failure we report, in one place.

Anything that can go wrong raises an AppError carrying a numeric `code` and a
short `title`, plus a `message` from the raise site saying which path, which id,
which reply. Callers catch AppError, store `status_line()` on the feature, and
never have to stringify a raw exception.

    1xxx  workspace  — preparing a copy of the code
    2xxx  the AI     — configuring it, running it, waiting for it
    3xxx  output     — it replied, but not in the shape we asked for
    9xxx  unknown    — anything we did not anticipate
"""


class AppError(Exception):
    """
    Base for every failure.

    The class supplies the fixed half — `code` and `title`. The raise site
    supplies the variable half, `message`.
    """

    code = 9000
    title = "Unexpected error"

    def __init__(self, message: str = ""):
        super().__init__(message or self.title)
        self.message = message

    def status_line(self) -> str:
        """One line for the feature's status: '[2000] AI not configured: ...'."""
        suffix = f": {self.message}" if self.message else ""
        return f"[{self.code}] {self.title}{suffix}"


class WorkspaceExists(AppError):
    code = 1000
    title = "Workspace already exists"


class CopyUnavailable(AppError):
    code = 1001
    title = "Copy-on-write unavailable"


class ConfigError(AppError):  # unknown provider, or a missing key
    code = 2000
    title = "AI not configured"


class ProviderFailed(AppError):  # ran, but did not finish cleanly
    code = 2001
    title = "AI provider failed"


class TurnTimeout(AppError):
    code = 2002
    title = "AI timed out"


class BadOutput(AppError):  # reply did not match the schema we asked for
    code = 3000
    title = "Unusable AI response"


def wrap(exc: Exception) -> AppError:
    """Turn any exception into an AppError so callers handle only one type."""
    if isinstance(exc, AppError):
        return exc
    return AppError(f"{type(exc).__name__}: {exc}")
