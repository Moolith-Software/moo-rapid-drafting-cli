"""Deterministic checks - no model involved, same answer every time.

Each check takes (output, expected) and returns (name, passed, note).
Run these first: they're free, instant, and catch most regressions.
"""

from task import CATEGORIES, URGENCIES


def check_is_json(output, expected):
    ok = "_parse_error" not in output
    return ("is_json", ok, "" if ok else output.get("_parse_error", ""))


def check_has_fields(output, expected):
    missing = [f for f in ("category", "urgency", "reply") if f not in output]
    return ("has_fields", not missing, f"missing: {missing}" if missing else "")


def check_category_valid(output, expected):
    got = output.get("category")
    return ("category_valid", got in CATEGORIES, f"got {got!r}")


def check_category_correct(output, expected):
    got, want = output.get("category"), expected["category"]
    return ("category_correct", got == want, f"got {got!r}, want {want!r}")


def check_urgency_correct(output, expected):
    got, want = output.get("urgency"), expected["urgency"]
    return ("urgency_correct", got == want, f"got {got!r}, want {want!r}")


def check_mentions_identifier(output, expected):
    reply = output.get("reply") or ""
    missing = [m for m in expected["must_mention"] if m.lower() not in reply.lower()]
    return ("mentions_identifier", not missing, f"missing: {missing}" if missing else "")


def check_reply_length(output, expected):
    words = len((output.get("reply") or "").split())
    return ("reply_under_60_words", 0 < words <= 60, f"{words} words")


ALL_CHECKS = [
    check_is_json,
    check_has_fields,
    check_category_valid,
    check_category_correct,
    check_urgency_correct,
    check_mentions_identifier,
    check_reply_length,
]


def run_checks(output, expected):
    """Return a list of {name, passed, note} dicts."""
    results = []
    for check in ALL_CHECKS:
        name, passed, note = check(output, expected)
        results.append({"name": name, "passed": bool(passed), "note": note})
    return results
