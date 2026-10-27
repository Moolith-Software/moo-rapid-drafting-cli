# Tasks

## 1. Reviewer guidelines

- [x] 1.1 Write `dev-docs/reviewing.md` (what to check, in order; findings only; empty list when clean; a follow-up rounds section) and list it in `dev-docs/README.md`; verify it covers every item in design Decision 9
- [x] 1.2 **Checkpoint:** the developer adds their own rules to `dev-docs/reviewing.md`; work resumes only after they confirm it is ready

## 2. One review round

- [x] 2.1 Confirm the installed Codex CLI's flags for a read-only sandbox, an output schema and writing the final message to a file, and that it uses `~/.codex` by default; verify by running `codex exec` once on a trivial prompt with a tiny schema
- [x] 2.2 Write `backend/scripts/review_round.py` with the `Finding`/`Findings` Pydantic models: detect the mode (ad hoc if requested, else a named change, else uncommitted ticks in a change's `tasks.md`, else ad hoc), build the prompt (round header with the mode and round N of `ROUNDS`, every earlier round's files for a follow-up, guidelines, `CLAUDE.md`, dev-docs, the change's artifacts in milestone mode, the work in scope including untracked files), run Codex read-only in a new process with the generated schema, validate the answer, save `findings.json` and `meta.json`; base `HEAD` in milestone mode, the merge base with `origin/main` in ad hoc mode, `BASE` overrides; verify milestone mode sees a new untracked file but not the previous commit, ad hoc mode sees the branch's commits and uncommitted work, findings validate, and `backend/.codex_home` is unchanged
- [x] 2.3 Add a root `Makefile` with `review-round` (`ROUND`, optional `ROUNDS` (default 2, 1 to 5), `MODE=adhoc`, `CHANGE`, `MILESTONE`, `BASE` and `MODEL`), and `.reviews/` to `.gitignore`; verify `make review-round` runs a round and `git status` stays clean of `.reviews/`

- [x] 2.4 Add the `Response`/`Responses` models and the matching check (every finding id answered exactly once, no unknown ids); follow-up rounds check the previous round, and `make review-round CHECK=1` checks every round of the current review; verify a missing, a duplicate and an unknown id are each refused with the id named, and a complete response passes

## 3. The loop

- [x] 3.1 Add the review rule to `CLAUDE.md`: after every milestone, Claude runs the loop with `make review-round` (checks, round 1, answer every finding in `response.json`, checks, further rounds while the previous had findings, up to `ROUNDS`), leaves fixes uncommitted, and posts the severity-ordered report before reporting the milestone ready; verify the wording matches the `ai-review` spec
- [x] 3.2 Write `.claude/commands/re.md` for the developer: `/re [change | adhoc] [rounds=N]` runs the same loop in whichever mode applies (`adhoc` forces ad hoc mode; `rounds=N` sets the rounds), ending with the same report; verify `/re` appears in Claude and an exact `/re` runs it rather than another command starting with `re`

## 4. End-to-end dry run

- [x] 4.1 On a scratch branch, add a throwaway HTML file with planted mistakes (a broken script reference, an undefined variable, a missing image alt text, a hard-coded fake API key) and run the loop in milestone mode (against this change) and again with `/re adhoc`; verify for each round 1 catches them, Claude fixes most and declines one with a reason, round 2 runs and judges the decline, the chat report is ordered by severity with an unfixed high finding flagged, the records are under `.reviews/`, and nothing was committed. The review also covers this change's own uncommitted files (and, in ad hoc mode, the branch's earlier commits): the planted mistakes must be among the findings, and any findings on this change's files are handled like a normal review, so the dry run doubles as M0's first review
- [x] 4.2 Delete the scratch branch and the throwaway file; verify `git branch` and `git status` are back to where they started, then `openspec validate add-ai-review-loop --strict` passes
