"""
The core of the tool - everything that actually builds a feature.

    pipelines.py          the pipelines: add a feature, refine a feature
    environments.py       readying a runnable environment (clone + provider session)
    workspace_manager.py  per-feature copy-on-write clones of the app
    cloning/              how that clone is made, one driver per OS
    changes.py            what changed on disk, computed deterministically
    statuses.py           the states a feature moves through
    errors.py             every failure we report, and its code
    utils.py              small pure helpers shared across the above
    ai/                   what we ask the AI for, and who answers

Deliberately free of HTTP concerns; main.py wires these to endpoints, and repositories/
stores the results.
"""
