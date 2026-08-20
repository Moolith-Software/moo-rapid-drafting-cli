"""
What we ask the AI to do.

An operation owns one job end to end: the prompt that asks for it, the schema of
the reply, and what that reply means. It delegates the call itself to a provider,
so the same operation works on Codex, Claude, or the mock.

Each operation is its own package, laid out the same way — `operation.py` for
the functions, `prompts.py` for the instructions, `schemas.py` for the reply:

    features/       build or refine a feature by editing a workspace

Later operations — suggesting feature ideas as the user types, say — are new
packages here. They need not look like `features`: returning a suggestion and
editing a repository are genuinely different jobs, so let each operation take
the shape its job calls for.
"""
