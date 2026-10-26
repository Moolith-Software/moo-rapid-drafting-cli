# Tasks

## 1. Reviewer setup

- [ ] 1.1 Confirm the installed Codex CLI's flags for a read-only sandbox, an output schema and writing the final message to a file, and that it uses `~/.codex` by default; verify by running `codex exec` once on a trivial prompt with a tiny schema
- [ ] 1.2 Write `dev-docs/reviewing.md` (what to check, in order; findings only; empty list when clean; a follow-up rounds section) and list it in `dev-docs/README.md`; verify it covers every item in design Decision 8

## 2. One review round

- [ ] 2.1 Write `backend/scripts/review_round.py` with the `Finding`/`Findings` Pydantic models: build the prompt (round header, guidelines, change artifacts, dev-docs, everything changed since the base commit including untracked files), run Codex read-only in a new process with the generated schema, validate the answer, save `findings.json` and `meta.json`; verify a round on a small change produces validated findings and `backend/.codex_home` is unchanged
- [ ] 2.2 Base commit: `HEAD` by default (the milestone is the uncommitted work on top of it, new untracked files included), overridable with `BASE`; verify a round sees a new untracked file and does not see the previous commit's changes
- [ ] 2.3 Add a root `Makefile` with `review-round` (`CHANGE`, `MILESTONE`, `ROUND`, optional `BASE`), and `.reviews/` to `.gitignore`; verify `make review-round` runs a round and `git status` stays clean of `.reviews/`

## 3. The loop

- [ ] 3.1 Add the review rule to `CLAUDE.md`: after every milestone, Claude runs the loop with `make review-round` (checks, round 1, answer every finding in `response.md`, checks, round 2 if needed, answer, checks), leaves fixes uncommitted, and posts the severity-ordered report before reporting the milestone ready; verify the wording matches the `ai-review` spec
- [ ] 3.2 Write `.claude/commands/review-milestone.md` for the developer: the same loop as an extra pass, ending with the same report; verify the command appears in Claude

## 4. End-to-end dry run

- [ ] 4.1 On a scratch branch, add a throwaway HTML file with planted mistakes (a broken script reference, an undefined variable, a missing image alt text, a hard-coded fake API key) and run the loop; verify round 1 catches them, Claude fixes most and declines one with a reason, round 2 runs and judges the decline, the chat report is ordered by severity with the unfixed one flagged if high, the records are under `.reviews/`, and nothing was committed
- [ ] 4.2 Delete the scratch branch and the throwaway file; verify `git branch` and `git status` are back to where they started, then `openspec validate add-ai-review-loop --strict` passes
