# CLAUDE.md

A rapid drafting tool for AI-generated apps: every feature is drafted on its own copy-on-write branch of the app, with a live preview. Read `dev-docs/proposal.md` (what it is) and `dev-docs/design.md` (how it works) before planning anything. The code is `backend/` (FastAPI), `frontend/` (Vue) and `base/` (the seed app).

## Working with OpenSpec

New features and real changes go through OpenSpec: `/opsx:explore` to think, `/opsx:propose` to write the change, `/opsx:apply` to build it, `/opsx:archive` once it's settled.

- **After any edit to a change's artifacts** (proposal, specs, design, tasks):
  1. Run `/opsx:update` to reconcile the artifacts with each other. It's an agent's judgment, so it can take a couple of rounds; repeat until it has nothing left to change.
  2. Then run `openspec validate <change> --strict`. This is the deterministic check, and the gate: the change isn't ready until it passes. If fixing a validation error changes meaning, go back to step 1.
- Every change's `design.md` ends with a `## Dev docs impact` section. Archiving syncs the delta specs into `openspec/specs/`, then edits `dev-docs/` in place (rules in `dev-docs/README.md`).
- Build a change one task group at a time, and commit each group on its own.

## Commits

Format: `type(scope): summary`. Lowercase, imperative, no trailing period, about 72 characters at most. One logical change per commit; spec commits and code commits stay separate.

| Type | For | Example |
|---|---|---|
| `spec` | proposing a change: its proposal, specs, design, tasks | `spec: propose add-docs-studio (proposal, specs, design, tasks)` |
| `spec(refactor)` | reworking a change's artifacts without changing what it builds | `spec(refactor): reorganize tasks into six layer-by-layer milestones` |
| `feat` | new behavior | `feat(docs-studio): group 2 - authoring and publishing endpoints` |
| `fix` | a bug fix | `fix(cloning): retry hdiutil detach before forcing it` |
| `refactor` | same behavior, better code | `refactor(docs-studio): production run command, env-based API docs, router file` |
| `docs` | dev-docs, READMEs | `docs: document copy-on-write layout per OS` |
| `test` | tests only | `test(pipelines): cover warm and cold add paths` |
| `chore` | tooling, config, housekeeping | `chore: add CLAUDE.md requiring validate + /opsx:update after spec changes` |

- **Scope** is the OpenSpec change name for change work (`feat(docs-studio)`), or the area otherwise (`backend`, `frontend`, `cloning`). Leave it out when nothing fits.
- **Task group commits** name the group: `feat(<change>): group N - <what it adds>`.
- A body is optional: what changed and why, as short bullets.
- Plain hyphens only, never em or en dashes: the `CR001` custom rule rejects them in `.md`, `.py` and `.toml` files.

## Pull requests

Title: `[type] Summary`, with the type in square brackets: `[feat]`, `[bugfix]`, `[refactor]`, `[spec]`, `[docs]`, `[chore]`. For example, `[feat] Docs studio authoring and publishing`.

The body has a short summary, anything to do after merging, and a test plan with what was and wasn't verified.

**Keep it current.** Every time you push new commits to an open PR, update its description (and its title, if the scope changed) in the same step, so it always describes everything on the branch.

## Checks

Run `npm --prefix frontend run check:backend` before pushing (ruff format, ruff lint, mypy, vulture, custom rules). The pre-push hook runs the same checks.
