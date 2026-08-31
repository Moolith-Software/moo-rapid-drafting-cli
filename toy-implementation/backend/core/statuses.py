"""
The states a feature moves through.

    initializing -> ready -> running   -> completed
                                       \\-> failed
                          -> refining  -> completed

Defined once and imported everywhere (db, core, main) so the strings are never
retyped. Deliberately dependency-free.
"""

INITIALIZING = "initializing"  # row exists; its environment is being built
READY = "ready"  # environment built and warmed, waiting for a request
RUNNING = "running"  # the AI agent is building the feature
REFINING = "refining"  # the AI agent is changing one it already built
COMPLETED = "completed"
FAILED = "failed"

# Still in flight — the frontend polls while a feature is in one of these.
ACTIVE = (RUNNING, REFINING)
