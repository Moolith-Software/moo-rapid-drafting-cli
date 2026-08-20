"""Tiny OpenAI wrapper.

Reads OPENAI_API_KEY from toy-implementation/backend/.env. No copy of the key
is made anywhere in this folder.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

_ENV = Path(__file__).parent.parent / "toy-implementation" / "backend" / ".env"
load_dotenv(_ENV)

if not os.getenv("OPENAI_API_KEY"):
    raise SystemExit(f"No OPENAI_API_KEY found in {_ENV}")

MODEL = os.getenv("EVAL_MODEL", "gpt-4o-mini")
JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "gpt-4o")

_client = OpenAI()


def chat(system: str, user: str, model: str | None = None, temperature: float = 0.0) -> str:
    resp = _client.chat.completions.create(
        model=model or MODEL,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return (resp.choices[0].message.content or "").strip()
