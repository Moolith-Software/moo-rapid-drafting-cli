"""
Hard ceiling limits  on what a single request may ask for.
"""

# Environments one /core/preload_environment call may warm.
MAX_ENVIRONMENTS = 1000

# Features one /core/add call may queue
MAX_ADD_FEATURES = 1000

# Valid # of characters one feature or refinement request may have
# estimated to around twelve minutes of dictation, ~ 2,500 tokens, 7 paperback pages
# supported limit by both Codex Provider and Sqlite
# too many back-to-back refine may grow larger past a certain point and hit a natural AI limit
MAX_REQUEST_CHARS = 10_000
