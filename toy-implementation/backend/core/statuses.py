"""
The states a feature moves through.

    initialized -> preparing -> running -> completed
                                        \\-> failed

Defined once and imported everywhere (db, core, main) so the strings are never
retyped. Deliberately dependency-free.
"""

INITIALIZED = "initialized"  # row created, nothing done yet
PREPARING = "preparing"  # cloning the code, readying a provider session
RUNNING = "running"  # the AI agent is working
COMPLETED = "completed"  # finished successfully
FAILED = "failed"  # gave up; the reason is in `progress`

# Still in flight — the frontend polls while a feature is in one of these.
ACTIVE = (INITIALIZED, PREPARING, RUNNING)
