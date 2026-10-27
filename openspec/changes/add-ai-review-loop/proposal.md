# Proposal

## Why

Milestones are built by Claude and reviewed only by the developer. A second reviewer from a different model family catches different mistakes, and catching them before the developer looks saves a round trip. This is the first of several verification gates, so it should be a defined, evolvable process rather than a habit.

## What Changes

- A review loop that Claude runs on every milestone before reporting it ready: checks green, a Codex review round, Claude fixes or declines each finding, checks green again, further fresh Codex rounds if needed (two rounds by default, set with `rounds=N`), then a report to the developer.
- **For Claude:** `make review-round`, which runs one Codex round on the work in scope (a milestone, or ad hoc work) and saves structured findings. Claude drives the loop with it. This is the main path.
- **For the developer:** a `/re` slash command, to run the loop at any time: an extra pass on a milestone, or a review of other work such as a hotfix. It detects which: milestone mode for OpenSpec work in progress, ad hoc mode otherwise; `/re <change>` names a change, and `/re adhoc` forces ad hoc mode (e.g. a hotfix during a milestone).
- Reviewer guidelines in `dev-docs/reviewing.md`, read by Codex every round; the script tells each round which round it is.
- Findings and Claude's responses both defined as Pydantic models: findings to ask Codex for structured output and validate it; responses so every finding is answered exactly once, checked by code.
- A report in chat at the end, ordered by severity, with unfixed high-severity findings flagged first. Fixes are left uncommitted for the developer to approve.
- Review records kept locally, per change and milestone (or per branch for ad hoc reviews), outside version control.
- A CLAUDE.md rule: no milestone is reported ready until the loop has run.

## Capabilities

### New Capabilities

- `ai-review`: how work (an OpenSpec milestone, or any other change) is reviewed by an AI reviewer before it reaches the developer: the two modes, the checks gate, rounds, reviewer inputs, findings and responses, the report, and the records kept.

### Modified Capabilities

None.

## Impact

- New: `backend/scripts/review_round.py`, `dev-docs/reviewing.md`, `.claude/commands/re.md`, a root `Makefile` with the `review-round` target (extended by `harden-db-and-expand-tests` M1).
- Changed: `CLAUDE.md` (the review rule), `.gitignore` (`.reviews/`), `dev-docs/README.md` (lists `reviewing.md`).
- Needs a current Codex CLI (`codex update`; 0.161 or later for `gpt-6.1-sol`) with the developer's own login (ChatGPT plan or API key), kept separate from the app's project-local `.codex_home`.
- No application code changes.
