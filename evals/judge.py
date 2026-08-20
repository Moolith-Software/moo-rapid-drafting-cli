"""LLM-as-judge - for the part you can't check with an `if` statement.

Scores the reply's tone and helpfulness 1-5 against a fixed rubric.
Keep the rubric concrete: vague rubrics produce noisy scores.
"""

import json

from client import JUDGE_MODEL, chat

RUBRIC = """You grade customer support replies. Score 1-5:

5 - Acknowledges the specific problem, states a clear next step, warm tone.
4 - Addresses the problem and a next step, but generic or slightly stiff.
3 - Relevant but vague; no concrete next step.
2 - Mostly boilerplate, barely engages with what the customer said.
1 - Wrong topic, rude, or unusable.

Respond with JSON only: {"score": <1-5>, "reason": "<one sentence>"}
"""

PASS_THRESHOLD = 4


def judge(customer_message: str, reply: str) -> dict:
    if not reply:
        return {"score": 0, "reason": "no reply to grade", "passed": False}

    raw = chat(
        system=RUBRIC,
        user=f"CUSTOMER MESSAGE:\n{customer_message}\n\nSUPPORT REPLY:\n{reply}",
        model=JUDGE_MODEL,
        temperature=0.0,
    )
    try:
        result = json.loads(raw)
        score = int(result["score"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return {"score": 0, "reason": f"judge output unparseable: {raw[:100]}", "passed": False}

    return {"score": score, "reason": result.get("reason", ""), "passed": score >= PASS_THRESHOLD}
