"""The thing being evaluated.

A support-ticket triager: takes a customer message, returns JSON with a
category, an urgency, and a short reply. This is the code you'd iterate on;
the evals tell you whether your iterations helped.
"""

import json

from client import chat

CATEGORIES = ["refund", "shipping", "billing", "account", "defect", "other"]
URGENCIES = ["low", "medium", "high"]

SYSTEM_PROMPT = f"""You triage customer support messages.

Respond with JSON only, no markdown fences, in this exact shape:
{{"category": "...", "urgency": "...", "reply": "..."}}

category must be one of: {", ".join(CATEGORIES)}
urgency must be one of: {", ".join(URGENCIES)}
reply is a direct response to the customer, under 60 words. Always repeat the
order number or account identifier back to them so they know we found it.
"""


def run(message: str) -> dict:
    """Return the parsed output, or {"_parse_error": ...} if it isn't JSON."""
    raw = chat(system=SYSTEM_PROMPT, user=message, temperature=0.2)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw": raw}
