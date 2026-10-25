# Rapid Prototyping Toy

A minimal working prototype of the flow diagram: describe a feature, and the
**OpenAI Codex** agent implements it in the background on a **copy-on-write clone**
of a seed Vue 3 app. Status is tracked in **SQLite** and polled by a single-page
**Vue 3 + TypeScript** frontend. Backend is **FastAPI**.

```
./
  base/        seed Vue 3 + TS app every feature branches from (node_modules and all)
  backend/     FastAPI + SQLite + the Feature Engine that drives Codex
  frontend/    single-page Vue 3 + TS UI
  dev-docs/    how the system works today (start here)
  openspec/    proposed and archived changes
```

## How it works

1. **initialize** - create a `features` row and a CoW clone of `base/` at
   `backend/workspaces/feature-<id>/` (macOS `cp -c`, instant, zero extra disk).
2. **add** - in the background, run `codex exec` inside that clone. Codex reads the
   code, edits files in place, and writes a plain-English summary.
3. **status** - the engine writes status at each step
   (`copying → warming → running → completed`); the page polls it.
4. **refine** - re-run Codex on the same clone; the new summary is appended to the
   feature's `refinements`.

## Prerequisites

- macOS on APFS (for copy-on-write clones)
- Node 18+ and Python 3.11+
- The Codex CLI: `npm install -g @openai/codex`

## Setup

**1. Backend key.** Create `backend/.env` from the example and add your key:

```bash
cd backend
cp .env.example .env
# edit .env: OPENAI_API_KEY=sk-...
```

**2. Backend.**

```bash
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000
```

The backend runs as production unless `ENV=development` is set or set in
your local `.env` to get `/docs`. In production, leave out the env var, it will run as prod by default. Keep it to one worker: the job pools, preview servers and the startup workspace 
sweep all live in the process.  A second worker would create conflicts.

```bash
uv run uvicorn main:app --host 0.0.0.0 --port 8000
```

**3. Frontend** (in another terminal).

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, type a feature, and click **Run feature**.

**Checks.** Formatting, lint, types, dead code and custom rules, the
same five a push runs:

```bash
cd frontend
npm run check:backend   # all five, read-only
npm run fix:backend     # apply the fixable lint and formatting changes
```

A `pre-push` hook runs `check:backend` automatically. The `npm install` in step
3 installs it; `git push --no-verify` skips it.

Custom rules are project conventions ruff cannot express, such as banning
emdashes. They live in `backend/scripts/custom_rules.py`; add one by adding a
line to its `RULES` table. Silence a single line with `noqa: <code>`, in
whatever comment syntax that file uses, the same way you would silence ruff or
vulture. Their `CR` prefix is listed in ruff's `lint.external` so ruff leaves
those comments alone.

## Previewing a generated app

Each workspace is a full CoW clone (it already has `node_modules`), so you can run
any generated result directly:

```bash
cd backend/workspaces/feature-1
npm run dev
```

## The `features` table

| column             | meaning                                                        |
| ------------------ | -------------------------------------------------------------- |
| `id`               | primary key                                                    |
| `parent_id`        | lineage for nested features (clone from a parent instead of base) |
| `code_folder_name` | the CoW workspace folder                                       |
| `feature`          | the original request                                           |
| `file_changes`     | JSON list of `{path, kind}` Codex changed                      |
| `summary`          | AI-written human-readable summary                              |
| `refinements`      | JSON list of `{refinement_id, user_request, file_changes, summary}` |
| `status`           | `initialized → copying → warming → running → completed / failed` |
| `progress`         | latest live status line (for polling)                          |
| `created_at`       | unix timestamp                                                 |
```



