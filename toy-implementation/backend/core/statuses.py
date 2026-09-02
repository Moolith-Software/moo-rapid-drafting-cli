"""
The high level states a feature moves through for core functionality

    preload      initializing -> ready
    add (warm)   ready -> queued -> building -> completed
    add (cold)   queued -> initializing -> building -> completed
    refinement   completed|failed -> queued -> refining -> completed

a feature is 'claimed' the moment someone is waiting on it rather than
when a worker picks it up; every state after it is written by the worker
doing that step.
"""

INITIALIZING = "initializing"  # row exists; its environment is being built
READY = "ready"  # environment built and warmed, waiting for a request
QUEUED = "queued"  # a request has taken this row; waiting for a free worker
BUILDING = "building"  # the AI agent is building the feature
REFINING = "refining"  # the AI agent is changing one it already built
COMPLETED = "completed"
FAILED = "failed"

# Still in flight — the frontend polls while a feature is in one of these.
ACTIVE = (QUEUED, INITIALIZING, BUILDING, REFINING)
