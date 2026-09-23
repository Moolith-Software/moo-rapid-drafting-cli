"""
The AI layer, split by the two questions it answers.

    operations/     WHAT we ask for - the prompt, the reply contract, and what
                    the reply means (e.g. features: build or refine a feature)
    harnesses/      WHO does it - Codex today, Claude next, mock for offline work

An operation calls `harnesses.run_turn(...)` and never names a harness; a
harness takes a prompt and a schema and never knows what they are for. That
split is what lets either side grow on its own.
"""
