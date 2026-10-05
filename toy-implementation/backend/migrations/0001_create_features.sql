CREATE TABLE IF NOT EXISTS features (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    parent_id      INTEGER REFERENCES features(id),  -- nested / refinement lineage
    code_folder_name TEXT NOT NULL,               -- the CoW workspace folder name
    feature        TEXT NOT NULL,                 -- the original (possibly rough) feature request
    file_changes   TEXT NOT NULL DEFAULT '[]',    -- JSON: list of {path, kind}, deterministic
    summary        TEXT NOT NULL DEFAULT '{}',     -- JSON: FeatureSummary (AI human-readable layer)
    refinements    TEXT NOT NULL DEFAULT '[]',    -- JSON: [{refinement_id, user_request, file_changes, summary}]
    status         TEXT NOT NULL DEFAULT 'initializing',
    progress       TEXT NOT NULL DEFAULT '',       -- latest live status line (for polling)
    harness_session_id TEXT,                      -- the harness's session id (for resume/fork)
    harness        TEXT CHECK (harness IN ('codex_sdk', 'mock')),  -- which harness owns that session; must match a harness's `name`
    workspace_version INTEGER NOT NULL DEFAULT 0, -- turns that have written to this workspace
    cloned_from_version INTEGER,                  -- the parent's workspace_version this was cloned from
    created_at     REAL NOT NULL
);
