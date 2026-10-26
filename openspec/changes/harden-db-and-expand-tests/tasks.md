# Tasks

Each milestone ends with Claude running the review loop (`make review-round`, from `add-ai-review-loop`) before it is reported ready. Paths are relative to the repository root.

## 1. M1 - Tooling

- [ ] 1.1 Extend the root `Makefile` (created with `review-round` by `add-ai-review-loop`) with `setup`, `start`, `dev`, `check`, `fix`, `test`, `test-cow`, `test-live` and `reset-db` (design Decision 1); verify each target runs (`test-cow` and `test-live` may report "no tests yet")
- [ ] 1.2 Rename `backend/scripts/custom_rules.py` to `custom_linting_rules.py` and update every reference (`pyproject.toml`, `CLAUDE.md`, `README.md`, `dev-docs/`); verify `make check` runs it and `grep -rn custom_rules.py` finds nothing outside the archive
- [ ] 1.3 Remove the `check:backend` scripts from `frontend/package.json`, point `frontend/.husky/pre-push` at `make check`; verify a push runs `make check`
- [ ] 1.4 Add `pytest` and `httpx` to the backend `dev` group and a minimal `backend/tests/conftest.py` with a temp-database fixture; verify `make test` runs and passes with one smoke test
- [ ] 1.5 Introduce `create_app(env=None)` in `main.py`, keeping `app = create_app()` for uvicorn; verify `make start` and `make dev` boot and `/docs` is served only by `make dev`
- [ ] 1.6 Update `CLAUDE.md` (checks: `make check`, `make test`), `README.md` (setup and run via `make`) and the checks named in the review loop (`CLAUDE.md` and `.claude/commands/review-milestone.md`); verify the documented commands run as written
- [ ] 1.7 Run the review loop for M1 (`make review-round`, per `CLAUDE.md`) and address the findings; verify checks are green and the severity-ordered report is posted

## 2. M2 - Database hardening

- [ ] 2.1 Add the CHECK constraints, JSON checks and the `code_folder_name` unique index to `backend/migrations/0001_create_features.sql` (design Decision 3); verify `make reset-db` then `make dev` creates the schema
- [ ] 2.2 Add the status-transition and fixed-columns triggers, with `invalid:` messages; verify the app's normal flows still write successfully (start, preload, add with the mock harness)
- [ ] 2.3 Add the parent-lock and child-under-completed triggers, with `conflict:` messages, covering both child inserts and warm-child claims; verify by direct SQL that each refuses the race case
- [ ] 2.4 Add `ConflictError` (3002, "Conflicting write") to `core/errors.py`, map `conflict:` integrity errors to it in `database.session`, and return 409 with the status line from a handler in `main.py`; verify a forced conflict returns 409
- [ ] 2.5 Add `backend/tests/database/` tests: one direct-SQL refusal per rule in the `database-integrity` spec, plus the allowed transitions passing; verify `make test` passes
- [ ] 2.6 Run the review loop for M2 (`make review-round`, per `CLAUDE.md`) and address the findings; verify checks and tests are green and the severity-ordered report is posted

## 3. M3 - Test foundation

- [ ] 3.1 Grow `conftest.py` and add `helpers.py`: temp workspaces with stubbed clone/open/preview, the mock harness, a deferred executor with `drain()`, a spy harness, row snapshots, add/refine-and-wait helpers; verify existing database tests still pass on the refactored fixtures
- [ ] 3.2 Add `database/` concurrency tests (two claims of one warm environment, two refines, refine vs child creation) using threads and a barrier; verify each passes 20 runs in a row
- [ ] 3.3 Add `database/` tests for rollback, migrations (fresh database at the latest version, re-run applies nothing) and restart persistence (two `create_app` instances on one file, sweep called); verify they pass
- [ ] 3.4 Add `harness/` tests for the `ai-harness` contract through the mock (outcome shape, schema parsing and 2005, read-only, session reuse and foreign sessions, timeout as tagged 2002) and the Codex classification table; verify they pass
- [ ] 3.5 Add `settings/` tests: dev/prod docs switch via `create_app`, harness selection failures (2000), the storage cap (1002); verify they pass
- [ ] 3.6 Add `xfail(strict=True)` tests for INV-21 and EC-45; verify they report as xfailed
- [ ] 3.7 Run the review loop for M3 (`make review-round`, per `CLAUDE.md`) and address the findings; verify checks and tests are green and the severity-ordered report is posted

## 4. M4 - Test apps and API

- [ ] 4.1 Add `testapps/manifest.json`, gitignore `testapps/*/` and the root `.env`, and a `make testapps` script (boto3, R2 keys from `.env`, sha256 check, unzip, skip present), called by `make setup`; verify a first app downloads and unpacks, and a second run skips it
- [ ] 4.2 Document in `testapps/README.md` how to zip, upload and register an app and its recorded features; verify by registering the first app from the instructions
- [ ] 4.3 Add replay to the mock harness (apply a recorded diff instead of the note line); verify a replayed three-file change gives `file_changes` with exactly those files
- [ ] 4.4 Add `api/` tests: every success and error code per endpoint in the `feature-api` spec, plus one parametrized test of 422, 500 and 503 across all endpoints; verify they pass, that 404/409 cases queued nothing, and that a request after a 503 succeeds once the database opens again
- [ ] 4.5 Add the golden path (design Decision 9) with session spy and row snapshots; verify it passes
- [ ] 4.6 Run the review loop for M4 (`make review-round`, per `CLAUDE.md`) and address the findings; verify checks and tests are green and the severity-ordered report is posted

## 5. M5 - Test tiers in CI

- [ ] 5.1 Add `backend/tests/cloning/` (marker `cow`): real drivers in a temp folder for build base, clone, child clone, isolation, open/close, sweep and the storage cap; verify `make test-cow` passes on macOS
- [ ] 5.2 Add `backend/tests/live/` (marker `live`): real Codex on a small test app for add, refine and session resumption; verify `make test-live` passes with a key and skips without one
- [ ] 5.3 Add `.github/workflows/ci.yml`: `make check` and `make test` on macOS and Linux for every PR; verify a PR shows both jobs green
- [ ] 5.4 Add `.github/workflows/cow.yml`: `make test-cow` on macOS and Linux when `backend/core/cloning/**` changes; verify it runs on a PR touching that folder and is skipped otherwise, and that the Linux driver passes on a real runner
- [ ] 5.5 Add `.github/workflows/live.yml`: `make test-live` on `merge_group` (or a `ready-to-merge` label) and manual dispatch, with `OPENAI_API_KEY` and R2 secrets; verify a manual run passes
- [ ] 5.6 Add a placeholder for desktop end-to-end tests (marker and a note in `dev-docs/`); verify `make test` ignores it
- [ ] 5.7 Run the review loop for M5 (`make review-round`, per `CLAUDE.md`) and address the findings; verify checks and tests are green and the severity-ordered report is posted

## 6. Integration check

- [ ] 6.1 Run `make check`, `make test`, `make test-cow` and `make test-live` locally, and confirm every invariant in design Decision 10 Table A maps to a passing test (or a strict xfail); then `openspec validate harden-db-and-expand-tests --strict` passes

## Workflow follow-up

- Archive the change once all milestones are merged: sync the specs, apply the Dev docs impact.
