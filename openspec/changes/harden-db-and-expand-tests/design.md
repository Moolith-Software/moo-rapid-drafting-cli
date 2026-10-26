# Design

## Context

See proposal.md for why. The current state is in `dev-docs/design.md`: one `features` table whose rules (INV-01 to INV-25) are almost all enforced in Python, a known race (EC-04), and no tests. There are no rows worth keeping, so the schema can be changed in place.

This change is built **layer by layer** in five milestones, each reviewed by Claude with the review loop (`make review-round`, from `add-ai-review-loop`) before it is reported ready, and archived together at the end.

```
M1 tooling --> M2 database hardening --> M3 test foundation --> M4 test apps + API --> M5 CI tiers
```

## Goals / Non-Goals

**Goals:**

- The database refuses every state that must never be stored, so a bug cannot persist bad data.
- Each invariant is enforced in the lowest layer that can hold it, and proven by a test.
- A small, focused suite: database tests, API tests and one golden path, plus a contract test for harnesses. No other unit tests.
- Tests that never touch the developer's database or workspaces.
- Test tiers that run where they belong: fast locally and on every PR, expensive ones only when relevant.

**Non-Goals:**

- Fixing process-level gaps: restart recovery (INV-21), a reaper, the RAM cap, the soft storage cap, preview ports. They stay known gaps, pinned by `xfail` tests.
- The copy-on-write benchmark (`add-cow-benchmark`), the desktop sidecar build (`package-backend`), a feature-tree endpoint, and desktop end-to-end tests (only a placeholder here).
- A migration for existing data: there is none.

## Decisions

### 1. Make is the single entry point (M1)

| Command | Does |
|---|---|
| `make review-round` | one AI review round (added by `add-ai-review-loop`) |
| `make setup` | `uv sync`; `npm install` in `frontend/` and `base/`; point git at the hooks; `make testapps` (M4) |
| `make start` | backend production-style: no reload, no API docs |
| `make dev` | backend with reload and docs (`ENV=development`), plus the frontend |
| `make check` | ruff format check, ruff lint, mypy, vulture, custom linting rules |
| `make fix` | the fixable parts of `check` |
| `make test` | the fast tier |
| `make test-cow` | real copy-on-write tests (M5) |
| `make test-live` | real AI end to end, needs `OPENAI_API_KEY` (M5) |
| `make reset-db` | delete `backend/data/app.db` |

The `check:backend` scripts leave `frontend/package.json`, and the pre-push hook calls `make check`. `make test-cow-bench` arrives with `add-cow-benchmark`.

`backend/scripts/custom_rules.py` becomes `custom_linting_rules.py`; its `CR` codes stay.

*Trade-off:* `make` rather than `just`. `make` ships with macOS and Linux; `just` would need installing everywhere but works natively on Windows. Revisit when Windows development is real. Keeping both in sync is rejected: they would drift.

### 2. `create_app(...)` (M1)

`main.py` reads `ENV` and builds the app, pools and handlers at import, which makes "start a second app" or "start in production mode" impossible in one test process. `create_app(env=None)` builds them on call; `main.py` keeps `app = create_app()` for uvicorn. Module-level state that tests need to redirect (`DB_PATH`, the copy-on-write driver, `SETTINGS`) is patched by fixtures; full settings injection is out of scope.

### 3. Database hardening strategies (M2)

All in `migrations/0001_create_features.sql`, edited in place. Developers run `make reset-db` once.

| Strategy | Rules |
|---|---|
| CHECK: allowed values | `status` in the seven; `harness` in the harness names; `length(feature) <= 10000` |
| CHECK: columns agree | `ready` => no request, version 0, has a branch; `building`/`refining`/`completed` => request and branch; `completed` => `file_changes != '[]'`; `failed` => `progress LIKE '[%'`; session id and harness set together; root => no `cloned_from_version` |
| CHECK: JSON shape | `file_changes`, `refinements` are JSON arrays; `summary` is a JSON object |
| UNIQUE index | `code_folder_name` where it is not `''` |
| FK | `parent_id` (as today, `foreign_keys = ON` per connection) |
| Trigger: transitions | `BEFORE UPDATE OF status`: only the lifecycle's (old, new) pairs, or the same status |
| Trigger: fixed columns | `BEFORE UPDATE`: `id`, `parent_id`, `created_at` never change; `feature`, `code_folder_name`, `cloned_from_version` only from empty to set; `workspace_version` never decreases |
| Trigger: parent lock | refuse `completed`/`failed` -> `queued` while the feature has a real child |
| Trigger: child under completed | refuse inserting a child, or claiming a warm child (`feature` from `''` to set), when the parent is not `completed` |
| Transaction | `BEGIN IMMEDIATE` for the batch claim (as today) |

Allowed status transitions:

| From | To |
|---|---|
| `initializing` | `ready`, `building`, `failed` |
| `ready` | `queued` |
| `queued` | `initializing`, `building`, `refining`, `failed` |
| `building`, `refining` | `completed`, `failed` |
| `completed`, `failed` | `queued` |

The app-level guards stay: they give the friendly 404/409 messages in the normal case, and the database is the backstop for races and bugs.

### 4. Conflicts become 409 (M2)

Lifecycle triggers raise with a message starting `conflict:`; all other triggers start `invalid:`.

```
trigger RAISE(ABORT, 'conflict: feature has children')
  -> sqlite3.IntegrityError
  -> database.session: message starts with 'conflict:'
  -> ConflictError (3002, "Conflicting write")
  -> request: handler returns 409, detail = status line
     worker:  recorded on the row like any failure
```

`invalid:` refusals and constraint failures stay `DatabaseError` (3000), a 500 in a request: reaching one means a bug, and a 409 would hide it.

### 5. Test layout and isolation (M1 to M3)

M1 adds pytest and a temp-database fixture, M2 the first `database/` tests, and M3 the rest of the fixtures and folders below.

```
backend/tests/
  conftest.py     temp DB per test, temp workspaces, stub clone/open/preview,
                  mock harness, a deferred executor for the pools
  helpers.py      factories (add and wait, refine and wait), row snapshots,
                  a spy harness that records each run_turn call
  database/       direct-SQL refusals, triggers, threads, rollback,
                  migrations, restart persistence
  harness/        the harness contract through the mock; Codex classification
  settings/       dev/prod switch, harness selection, storage cap
  api/            every success and error code; the golden path
  cloning/        real copy-on-write (marker: cow)          M5
  live/           real AI end to end (marker: live)          M5
```

- **Clean state:** every test gets its own SQLite file in pytest's `tmp_path` and its own workspaces folder. `backend/data/app.db` is never touched.
- **The pools:** a deferred executor queues submitted jobs until the test calls `drain()`. That makes "two requests before either runs" deterministic, and lets a test check that a 404/409 queued nothing.
- **No unit tests** beyond the harness contract and the Codex classification table, which no endpoint can reach.

### 6. Test tiers (M5)

| Tier | Runs | Where | Contents |
|---|---|---|---|
| fast | `make test`, every PR | macOS + Linux | database/, harness/, settings/, api/, golden path |
| copy-on-write | PRs touching `backend/core/cloning/**` | macOS + Linux runners | real drivers in a temp folder: build base, clone, child clone, isolation, open/close, sweep, storage cap |
| live AI | before merging to main | macOS | real Codex on a small test app: add, refine, provider resumes the session |
| desktop | later | per OS | placeholder: mock AI on every PR, real AI before merge, once the desktop app exists |

The live tier runs on GitHub's merge queue (`merge_group`) where the repository supports it, otherwise on a `ready-to-merge` label, plus a manual trigger. Secrets: `OPENAI_API_KEY`, R2 keys.

### 7. Test apps on R2 (M4)

- Every test app is a **zip in a private R2 bucket**: `app/` plus `features/<name>/` (a diff and `meta.json`: files touched, change size, and the harness and model that produced it). Nothing from them is committed.
- `testapps/manifest.json` is committed: name, size tier, object key and sha256 per zip.
- `make testapps` (called by `make setup`) downloads with `boto3` from the dev dependencies, using R2 keys from a gitignored root `.env`; checks the sha256, unzips into `testapps/<name>/` (gitignored), and skips apps already present. Large tiers download only when asked.
- **The fast tier never needs them**: it builds a tiny app in `tmp_path`. Tests that need a test app are marked and skipped when it is not present.

### 8. Mock replay (M4)

The mock harness takes an optional recorded change and applies it instead of its one-line note. Patches are plain diffs, so they do not depend on which agent produced them. No new harness name, so the `harness` CHECK is unchanged. The live tier can save its real changes as new recordings.

### 9. The golden path (M4)

One test through the HTTP API, with the default mock (whose note file makes "child has the parent's lines" easy to check) and a spy recording each turn's session id and `read_only` flag. After every step it compares row snapshots: the expected fields changed, and every other row is identical.

| Step | Action | Expect |
|---|---|---|
| 1 | add A, nothing preloaded | cold: `queued -> initializing -> building -> completed`; version 1; file changes from disk |
| 2 | preload 2 roots | 2 rows `ready`, no request, version 0; warm-up turns were read-only |
| 3 | add B | claims the oldest warm row, no new id; the add ran with the warm-up's session |
| 4 | refine B | refinement 1; version 2; same session id; `feature` and `file_changes` unchanged |
| 5 | two refines of B before draining | one 202, one 409; exactly one new refinement |
| 6 | preload 1 child of B; refine B; add 2 children of B | stale warm child skipped, children built cold; `cloned_from_version` = B's version; fresh sessions; B's note lines on their branches; B untouched |
| 7 | refine B | 409 "branched from it" |
| 8 | add a 3rd child of B and refine it | completed; B and siblings untouched |
| 9 | add a child of that child | `parent_id` and `cloned_from_version` from the child; B untouched |
| 10 | refine a missing id | 404, nothing queued |
| 11 | list | every feature, newest first |

### 10. Coverage by layer, after this change

**Table A: each invariant, by layer.** Bold marks what this change adds.

| # | Invariant | DB layer | App layer | Tests |
|---|---|---|---|---|
| INV-01 | status is one of seven | **CHECK** | constants | database |
| INV-02 | status follows the lifecycle | **transition trigger** | pipeline order | database; golden |
| INV-03 | `queued` as soon as accepted | | reserve, claim | golden; api |
| INV-04 | warm claim matching, stale skipped | | `_claim_ready` | database; golden 6 |
| INV-05 | one claim per warm environment | `BEGIN IMMEDIATE` | | database (threads) |
| INV-06 | child = parent's code, fresh session | | `build_environment` | golden 6, 9 |
| INV-07 | children only under `completed` | **trigger** | guard | database; api 409 |
| INV-08 | parent with children never refined | **trigger** | guard | database (threads); api 409; golden 7 |
| INV-09 | one refine at a time | single UPDATE | | database (threads); golden 5 |
| INV-10 | failed with a branch is retryable | WHERE clause | | database |
| INV-11 | completed means files changed | **CHECK** | `NoChangesError` | database; api 2006 |
| INV-12 | refinements only grow | | append | golden |
| INV-13 | version bumped before a write | **never decreases** | step order | database; golden |
| INV-14 | warm-up never writes | | read-only sandbox | harness; golden 2 |
| INV-15 | session paired with its harness | **CHECK** | harness compare | database; harness |
| INV-16 | failed rows carry a status line | **CHECK** | `errors.wrap` | database |
| INV-17 | parent exists | FK | | database |
| INV-18 | failed write leaves no change | transaction | | database |
| INV-19 | migrations run once, roll back on failure | `user_version` | | database |
| INV-20 | no workspace open across restart | | sweep | database (restart); copy-on-write tier |
| INV-21 | every claim reaches an end state | | none: **GAP** | `xfail(strict)` |
| INV-22 | no new branch over the size cap | | `_ensure_room` | settings; copy-on-write tier |
| INV-23 | branch names unique | **UNIQUE index** | uuid suffix | database |
| INV-24 | stored request never cut | | response model | api |
| INV-25 | request size bounds | **CHECK length** | Pydantic | database; api 422 |
| **INV-26** | `ready` rows have no request and no writes; working rows have a request and a branch | **CHECK** | sentinels | database |
| **INV-27** | a root feature has no `cloned_from_version` | **CHECK** | | database |
| **INV-28** | a lifecycle conflict returns 409 (3002) | trigger message | **ConflictError** | database; api |
| **INV-29** | fixed columns never change once set | **trigger** | | database; golden snapshots |

**Table B: risks, and where each is caught.**

| Risk | Caught by |
|---|---|
| bad state stored by a bug | CHECKs and triggers; database refusal tests |
| two requests racing on one parent or environment | triggers, `BEGIN IMMEDIATE`; database thread tests |
| cold and warm paths diverging | golden 1, 3 |
| session not handed back (ours) | golden spy |
| session not resumed (provider's) | live tier |
| the AI "succeeds" without changing anything | CHECK; api 2006 |
| rows changing that should not | immutability trigger; golden snapshots |
| API contract drift | api tests |
| settings or the dev/prod switch broken | settings tests |
| data lost across a restart | database restart test |
| copy-on-write broken on an OS | copy-on-write tier |
| the real provider broken | live tier |

**Known gaps left open:** INV-21 / EC-01 (restart strands in-flight features), EC-02 (failure not recorded when the database is down), EC-13 (no reaper), EC-14 (no RAM cap), EC-17 (storage cap overshoot), EC-18 (preview ports), EC-45 (nothing builds the base in the app). INV-21 and EC-45 are pinned with `xfail(strict)`.

## Risks / Trade-offs

- [Lifecycle rules now live in SQL triggers and Python guards] -> Change both together; the database tests fail if they disagree.
- [Editing `0001` in place] -> Existing dev databases must be deleted once (`make reset-db`); acceptable with no real data. The first schema change after this one is a real migration.
- [Triggers make SQLite do more per write] -> A handful of indexed lookups per status change; negligible at this scale.
- [Patching module globals in tests] -> All patching lives in `conftest.py`; a full settings injection is a later refactor.
- [Merge queue availability] -> Not every repository plan has it; the label trigger is the fallback.
- [R2 credentials] -> Needed locally and in CI for test apps; the fast tier does not need them, so a new developer can run `make test` without keys.
- [`make` on Windows] -> See Decision 1.

## Migration Plan

Development only: after merging M2, run `make reset-db`. No production data exists.

## Open Questions

- Which apps go into the first R2 upload, and at what size tiers. Doesn't change the tooling.

## Dev docs impact

- design.md - Decision 1 Repository layout: `Makefile`, `backend/tests/`, `testapps/`, `.github/workflows/`, `custom_linting_rules.py`.
- design.md - Decision 4 Data model: the CHECKs, unique index and triggers; the schema mapping table becomes "enforced today".
- design.md - Decision 5 Connections: `create_app`; conflict mapping in `database.session`.
- design.md - Decision 7 API shape: 409 for conflicting writes on add and refine.
- design.md - Decision 8 Validation and errors: adds `ConflictError` 3002.
- design.md - Decision 9 Settings: `make` commands; the `create_app` entry point.
- design.md - Decision 10 Testing approach: replaced by the real suite, tiers and test apps.
- design.md - Decision 12 Invariants and edge cases: strengths per Table A; adds INV-26 to INV-29; EC-04 no longer a gap; fills the Spec requirement and Tests columns.
- design.md - Risks / Trade-offs: removes "status has no CHECK", "checks can be slipped past", "No tests"; adds the trigger/guard duplication and `make` trade-offs.
- proposal.md - What it doesn't do yet: removes "Tests".
