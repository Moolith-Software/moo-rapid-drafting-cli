# Proposal

## Why

Almost every rule in `dev-docs/design.md` (INV-01 to INV-25) is enforced only by Python, and nothing tests any of them: the backend has no tests. One known race (EC-04) can refine a parent while a child is being created from it. Before shipping more features, the foundations need to hold on their own: the database should refuse states that must never exist, and a focused test suite should prove the rules, the API contract and the main flow.

## What Changes

Built layer by layer, in five milestones:

- **M1 Tooling.** A `Makefile` as the single entry point (`setup`, `start`, `dev`, `check`, `fix`, `test`, `test-cow`, `test-live`, `reset-db`); the backend checks move out of `frontend/package.json`; `scripts/custom_rules.py` is renamed `custom_linting_rules.py`; the app is built by `create_app(...)` so tests can start it in any mode; pytest with a minimal temp-database fixture.
- **M2 Database hardening.** The initial schema (`0001`, edited in place, no migration) gains CHECK constraints, a unique index and triggers, so the database refuses invalid states, illegal status transitions, changes to fixed columns, and the two lifecycle races. A refused lifecycle write becomes a new `ConflictError` (3002), returned as **409**. A direct-SQL test proves each rule.
- **M3 Test foundation.** Fixtures grow to temp workspaces, the mock harness and a deferred executor; `database/` tests for the concurrency rules, rollback, migrations and restart persistence; `harness/` tests of the harness contract against the mock; `settings/` tests for the dev/prod switch and harness selection.
- **M4 Test apps and API.** Test apps stored as zips on a private R2 bucket and pulled by `make setup`; the mock harness can replay recorded multi-file changes; `api/` tests for every success and error code; one golden-path test of the whole flow.
- **M5 Test tiers in CI.** GitHub Actions: the fast tier on every PR (macOS and Linux), real copy-on-write tests when `backend/core/cloning/` changes, a live-AI end-to-end suite before merging to main, and a placeholder for desktop tests.

**BREAKING (dev only):** existing local databases must be deleted once (`make reset-db`), because `0001` is edited in place.

Out of scope, each its own later change: the copy-on-write speed benchmark (`add-cow-benchmark`), building the backend as a desktop sidecar (`package-backend`), and a feature-tree endpoint.

## Capabilities

### New Capabilities

- `database-integrity`: what the database itself refuses: invalid values, inconsistent columns, illegal status transitions, changes to fixed columns, and lifecycle conflicts, with conflicts surfaced as 409.
- `feature-api`: the HTTP contract: each endpoint's success and error responses, validation, database-unavailable and conflict handling, and the dev/prod docs switch.
- `feature-lifecycle`: how features move through cold and warm builds, refinement, branching and going deep, including session continuity, locks and persistence across restarts.
- `ai-harness`: the contract every AI harness keeps: one turn in, one normalized outcome out, read-only warm-ups, session reuse, and flattened, tagged error codes.

### Modified Capabilities

None.

## Impact

- Backend: `migrations/0001_create_features.sql`, `repositories/database.py`, `core/errors.py`, `main.py` (`create_app`), the mock harness (replay), `scripts/custom_linting_rules.py`, `pyproject.toml` (pytest, httpx, boto3 in the dev group).
- New: `Makefile`, `backend/tests/`, `testapps/manifest.json`, `.github/workflows/`.
- Tooling: `frontend/package.json` loses its backend scripts; the pre-push hook calls `make check`.
- Docs: `CLAUDE.md`, `README.md`, `dev-docs/` (via the Dev docs impact).
- Needs: R2 credentials for test apps (local `.env`, CI secrets), and an OpenAI key as a CI secret for the live-AI suite.
