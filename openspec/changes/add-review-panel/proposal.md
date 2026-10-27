# Proposal

> **Parked.** Only the proposal is written. Specs, design and tasks come when this change is picked up, after the review loop (`add-ai-review-loop`) has been used on real milestones and shown which kinds of issues it keeps missing.

## Why

One reviewer has blind spots, and running the same reviewer several times shares them. The `add-ai-review-loop` dry runs showed it: a single reviewer caught most planted mistakes but missed a hard-coded API key twice, even with a security check in its guidelines. Several reviewers each looking for something different should catch more, without much extra wall-clock time, since they run in parallel.

Separately, when a review turns up many serious problems at once, the fault may be the design or the spec rather than the code. Fixing finding by finding then wastes effort; the developer should decide first.

## What Changes

- **A panel in round 1 only.** Several reviewers run in parallel, each with a different lens, for example:
  - correctness and security;
  - the developer's rules (`DR-*` in `dev-docs/reviewing.md`);
  - the change's specs, design and invariants.

  Lenses may also use different models (for example `gpt-6.1-sol` and `gpt-6-astra`), or a different provider later.
- **Claude flattens round 1.** It merges the panel's findings, removes duplicates (same file and line, or the same problem), resolves contradictions visibly, then fixes or declines each one as today.
- **Later rounds stay as now:** one fresh reviewer checks the fixes, judges the declines and looks for new problems.
- **An escalation control.** If round 1 surfaces too many `high` findings, or findings that point at the design or spec rather than the code, the loop stops before fixing anything and raises it to the developer as a possible design or spec problem. The threshold is set when this change is designed.
- **Flags:** `/re panel` (or `panel=N` / `lenses=...`) to use the panel; without it, the single-reviewer loop runs as today.
- **The report** gains a `source` column (which lens found each finding) and notes merged duplicates.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `ai-review`: adds the round-1 panel, merging and de-duplication, and escalation to the developer. (`ai-review` is created by `add-ai-review-loop`; this change follows it.)

## Impact

- Changed: `backend/scripts/review_round.py` (parallel reviewers, lenses, merged findings with a source), `dev-docs/reviewing.md` (per-lens guidelines), the AI review loop in `CLAUDE.md`, `/re`.
- Cost: round 1 uses N times the Codex plan usage; later rounds are unchanged.
- Depends on `add-ai-review-loop` being archived, so `ai-review` exists to modify.
