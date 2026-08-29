"""
Small general methods that can be reused elsewhere
"""


def readable_duration(seconds: float) -> str:
    """Time limits are set in seconds; say them the way a person reads them."""
    return f"{seconds / 60:.0f} minutes" if seconds >= 60 else f"{seconds:.0f}s"


def mentions(text: str, *patterns: str) -> bool:
    """
    Match any of patterns to text
    """
    lowered = text.lower()
    return any(pattern in lowered for pattern in patterns)
