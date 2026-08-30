"""
The states a feature moves through.

    initialized -> preparing -> running -> completed
                                        \\-> failed

Defined once and imported everywhere (db, core, main) so the strings are never
retyped. Deliberately dependency-free.
"""

INITIALIZED = "initialized"  # row created, nothing done yet
PREPARING = "preparing"
READY = "ready"  # workspace is ready
RUNNING = "running"  # the AI agent is working
REFINING = "refining"
COMPLETED = "completed"
FAILED = "failed"

# Still in flight — the frontend polls while a feature is in one of these.
ACTIVE = (RUNNING, REFINING)
