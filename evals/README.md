# evals

A minimal eval harness: golden dataset + deterministic checks + an LLM judge.

The thing under test is a **support ticket triager** (`task.py`) — it takes a
customer message and returns `{category, urgency, reply}`.

## Run it

```bash
cd evals && python -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/python run_evals.py
```

The API key is read from `../toy-implementation/backend/.env`. Nothing is
copied into this folder.

## The pieces

| File | What it is |
|---|---|
| `dataset.json` | 6 hand-written cases: an input plus what a correct answer looks like. This is the golden dataset — it's small on purpose. |
| `task.py` | The system being evaluated. Iterate on the prompt here. |
| `checks.py` | Deterministic checks. No model, no cost, no flake. |
| `judge.py` | LLM judge for reply quality, scored 1-5 against a fixed rubric. |
| `run_evals.py` | Runs everything, prints a table, writes `results.json`. |

A case passes only if **every** deterministic check passes **and** the judge
scores >= 4. `run_evals.py` exits non-zero on any failure, so you can wire it
into a pre-commit hook or CI.

## Deterministic checks vs. judge

Deterministic checks are the ones where a correct answer is a fact:

- `is_json`, `has_fields` — did we get parseable output with the right shape
- `category_valid` — is the category in the allowed enum at all
- `category_correct`, `urgency_correct` — exact match against the golden label
- `mentions_identifier` — does the reply echo back the order number
- `reply_under_60_words` — length budget

Reach for the judge only for things you genuinely can't assert: here, whether
the reply is warm and actually offers a next step. Judges cost money, add
latency, and drift between model versions — so the rule of thumb is to push
as much as possible into `checks.py` and leave the judge a narrow question.

## Making it yours

- **Add a case**: append to `dataset.json`. Failures you hit in real usage
  should become cases here, that's how the set earns its value over time.
- **Add a check**: write a function in `checks.py`, add it to `ALL_CHECKS`.
- **Change the model**: `EVAL_MODEL` / `EVAL_JUDGE_MODEL` env vars. Defaults
  are `gpt-4o-mini` for the task and `gpt-4o` for the judge — a stronger judge
  than task model is the usual setup.
- **Tune the judge**: edit `RUBRIC` in `judge.py`. If scores look noisy, the
  rubric is too vague; make each band describe something observable.

## Cost

Each run is 6 task calls + 6 judge calls. Fractions of a cent.
