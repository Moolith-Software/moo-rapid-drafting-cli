"""
Small general methods that can be reused elsewhere
"""

SECONDS_PER_MINUTE = 60


def readable_duration(seconds: float) -> str:
    """Time limits are set in seconds; say them the way a person reads them."""
    if seconds >= SECONDS_PER_MINUTE:
        return f"{seconds / SECONDS_PER_MINUTE:.0f} minutes"
    return f"{seconds:.0f}s"


def mentions(text: str, *patterns: str) -> bool:
    """
    Match any of patterns to text
    """
    lowered = text.lower()
    return any(pattern in lowered for pattern in patterns)
