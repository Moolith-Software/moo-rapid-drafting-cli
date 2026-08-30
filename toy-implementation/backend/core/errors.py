"""
Every failure we report, in one place.

Anything that can go wrong raises an AppError carrying a numeric `code` and a
short `title`, plus a `message` from the raise site saying which path, which id,
which reply. Callers catch AppError, store `status_line()` on the feature, and
never have to stringify a raw exception.

    1xxx  workspace + setup      — the feature and its workspace
    2xxx  AI integration     — configuring it, running it, waiting for it, and output issues
    9xxx  unknown    — anything we did not anticipate

General title and error code, with granular information inside the message, passed from the
provider.  Every AI provider must map/flatten its exceptions to these error codes.
"""

import traceback


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
        """
        One line for the feature's status:

            [2003] [codex_sdk] [gpt-5.6] AI credentials rejected: 401 invalid_api_key
            [1000] Workspace already exists: /tmp/ws
        """
        suffix = f": {self.message}" if self.message else ""
        return f"[{self.code}] {self.title}{suffix}"


class WorkspaceExists(AppError):
    code = 1000
    title = "Workspace already exists"


class CopyUnavailable(AppError):
    code = 1001
    title = "Copy-on-write unavailable"


class InvalidFeature(AppError):  # asked to do something its state does not allow
    code = 1002
    title = "Invalid feature state"


class ConfigError(AppError):
    code = 2000
    title = "AI not configured"


class TurnFailed(AppError):
    code = 2001
    title = "AI run failed"


class TurnTimeout(
    AppError
):  # message says whether it was our watchdog or within provider
    code = 2002
    title = "AI timed out"


class AuthRejected(AppError):
    code = 2003
    title = "AI credentials rejected"


class QuotaExceeded(AppError):
    code = 2004
    title = "AI usage limit reached"


class BadOutput(AppError):
    code = 2005
    title = "Unusable AI response"


class NoChanges(AppError):
    code = 2006
    title = "AI made no changes"


class UnknownAIError(AppError):  # last in the band, the way 9000 is last overall
    code = 2999
    title = "Unexpected AI error"


def wrap(exc: Exception) -> AppError:
    """
    Turn any exception into an AppError so callers handle only one type.

    As a central point for all feature related exceptions  - prints to console here
    for observability.
    """
    error = (
        exc if isinstance(exc, AppError) else AppError(f"{type(exc).__name__}: {exc}")
    )

    # Assemble and include complete traceback for future investigation
    detail = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    print(f"[error] {error.status_line()}\n{detail}", flush=True)

    return error
