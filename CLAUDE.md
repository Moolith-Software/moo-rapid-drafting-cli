# CLAUDE.md

A rapid drafting tool for AI-generated apps: every feature is drafted on its own copy-on-write branch of the app, with a live preview. Read `dev-docs/proposal.md` (what it is) and `dev-docs/design.md` (how it works) before planning anything. The code is `backend/` (FastAPI), `frontend/` (Vue) and `base/` (the seed app).

## Working with OpenSpec

New features and real changes go through OpenSpec: `/opsx:explore` to think, `/opsx:propose` to write the change, `/opsx:apply` to build it, `/opsx:archive` once it's settled.

- **After editing a change's artifacts** (proposal, specs, design, tasks), **always** run both steps below. This is not optional: it applies to edits you made yourself, small ones, and ones you believe are already consistent. Never skip `/opsx:update` because `validate` passes. Run them **once per batch** of edits, not after each one: at the end of a round of developer feedback, at the end of a task group, and before reporting work ready or committing.
  1. Run `/opsx:update` to reconcile the artifacts with each other. It's an agent's judgment, so it can take a couple of rounds; repeat until it has nothing left to change.
  2. Then run `openspec validate <change> --strict`. This is the deterministic check, and the gate: the change isn't ready until it passes. If fixing a validation error changes meaning, go back to step 1.
- Every change's `design.md` ends with a `## Dev docs impact` section. Archiving syncs the delta specs into `openspec/specs/`, then edits `dev-docs/` in place (rules in `dev-docs/README.md`).
- Build a change one milestone (task group) at a time. When a milestone is done: run the AI review loop, then hand it to the developer to review. Commit the whole milestone as **one commit, only when the developer says so**, then start the next milestone. Never commit without that go-ahead.

## AI review

**Before reporting any milestone ready, run this loop.** The developer can also run it at any time with `/re`. Guidelines for the reviewer are in `dev-docs/reviewing.md`.

1. Run the project's checks (see Checks) and fix until they pass.
2. `make review-round ROUND=1`. It picks the mode itself: milestone mode when a change's `tasks.md` has uncommitted ticks, ad hoc otherwise. Add `CHANGE=<change>` if it asks, or when reviewing a named change; add `MODE=adhoc` for work that is not the milestone in progress, such as a hotfix. Pass the same arguments, including `ROUNDS`, to every round.
3. Answer **every** finding in `<run folder>/round-1/response.json`, one entry per finding id, exactly once: `{"responses": [{"id": "...", "outcome": "fixed", "files": ["..."], "reason": ""}, {"id": "...", "outcome": "declined", "files": [], "reason": "..."}]}`. A fix lists the files changed; a decline gives the reason. Fix in the working tree. **Never commit.**
4. Run the checks again.
5. While the previous round had findings and rounds remain (two by default; `ROUNDS=N` for 1 to 5): run the next round (`ROUND=2`, and so on), answer its findings in `round-N/response.json` the same way, and run the checks again.
6. Run `make review-round CHECK=1`; it must pass, confirming every finding of every round has exactly one response. Then write `<run folder>/report.md` from the findings and responses, and post the same report in chat:
   - first, flag any `high` finding that was not fixed;
   - then one table of every finding from every round, ordered high, medium, low: round, severity, file, title, outcome (fixed, declined with reason, or open);
   - then the counts per round and the run folder's path.

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
