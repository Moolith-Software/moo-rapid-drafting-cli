# Design

## Context

See proposal.md for why. Today a milestone goes straight from Claude to the developer. This change adds a review step in between, run by the Codex CLI, without changing any application code. It is the first verification gate; later gates (more reviewers, narrower checks) should be able to slot into the same loop.

## Goals / Non-Goals

**Goals:**

- Claude reviews every milestone with Codex before reporting it ready, and the developer can trigger the same loop again on demand.
- Every finding answered: fixed or declined with a reason, visible to the next round and to the developer.
- A report in chat, ordered by severity, that the developer can trust before reviewing.
- Records of every review kept locally, so the process can be tuned from real history.

**Non-Goals:**

- Running reviews in CI. This loop is local; CI gates come with `harden-db-and-expand-tests` (M5).
- More than one reviewer, or scoring reviewers. Possible later on the same structure.
- Committing fixes or review records. The developer approves commits.

## Decisions

### 1. Two entry points, one loop

| Entry point | Who | When |
|---|---|---|
| `make review-round CHANGE=<change> MILESTONE=<m> ROUND=<n>` | **Claude** | the main path: Claude drives the loop with it after finishing every milestone, before reporting it ready |
| `/review-milestone [change] [milestone]` | **the developer** | an extra pass on demand, e.g. to let the AI patch quick fixes instead of reviewing them by hand |

Both run the same loop:

```
checks green? -- no --> fix, re-run checks
   |
   v
round 1: make review-round ... ROUND=1  -->  round-1/findings.json
   |
   v
Claude answers every finding (fix in the working tree, or decline + reason)  -->  round-1/response.md
   |
   v
checks green? -- no --> fix
   |
   v
round 2 (only if round 1 had findings): new process, told it is round 2, given round 1's files
   |
   v
Claude answers round 2 --> round-2/response.md; checks green
   |
   v
report in chat (and report.md); nothing committed
```

The make target does one mechanical thing: run one Codex round and save its output. The loop itself needs Claude's judgment (fixing, declining), so it lives in Claude's instructions: the `CLAUDE.md` rule for the main path, and the slash command for the developer's extra pass.

### 2. Files

```
Makefile                         review-round target (created here; M1 of
                                 harden-db-and-expand-tests extends it)
backend/scripts/review_round.py  runs one round: prompt, Codex, validate, save
dev-docs/reviewing.md            reviewer guidelines, read every round
.claude/commands/
  review-milestone.md            the developer's extra-pass command
.reviews/                        (gitignored)
  <change>/<milestone>/<YYYYMMDD-HHMMSS>/
    round-1/  findings.json  response.md
    round-2/  findings.json  response.md
    report.md                    the same report Claude posts in chat
    meta.json                    rounds, changes reviewed, reviewer model,
                                 timestamps, finding counts per round
```

The script lives in `backend/scripts/` (beside the linting rules) so it runs in the backend environment and can use Pydantic. A timestamped folder per run keeps earlier reviews next to new ones.

### 3. The prompt for each round

`review_round.py` builds the prompt from:

- a **round header**: "This is round N of 2.", and for round 2 the paths of round 1's `findings.json` and `response.md`, with the instruction to check the fixes, judge the declines, and look for problems the fixes introduced;
- `dev-docs/reviewing.md` (the same guidelines every round);
- the change name and its artifact paths (`openspec/changes/<change>/`);
- `dev-docs/proposal.md` and `dev-docs/design.md`;
- what to review: everything changed since the base commit, committed or not, **including new untracked files** (which `git diff` alone does not show). The reviewer inspects them with `git` itself.

The prompt is not saved: the guidelines are in git, and the round, base and paths are in `meta.json`.

**The base commit** defaults to `HEAD`. The workflow is: Claude builds a milestone, the loop reviews it, the developer reviews it, and only then is it committed as one commit. So during a review, the milestone is exactly the uncommitted work on top of `HEAD`, and earlier milestones (already reviewed and committed) are left out. `BASE=<ref>` overrides it, e.g. to review several commits.

### 4. Structured findings with Pydantic

```python
class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    severity: Literal["high", "medium", "low"]
    file: str
    line: int | None
    title: str
    details: str
    suggestion: str

class Findings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    findings: list[Finding]
```

The script generates the JSON schema Codex needs from `Findings.model_json_schema()`, passes it as the output schema, and validates the answer with `Findings.model_validate_json`. An answer that does not validate fails the round. This is the same pattern the app uses for AI output (`core/ai/operations/features/schemas.py`).

### 5. Running Codex

- `codex exec` in a **read-only sandbox**, with the generated output schema, writing its final message to a file the script then validates. The exact flags are confirmed against the installed CLI in task 1.1.
- **A new process per round**, so each round is a fresh session.
- **The developer's own login.** The `codex` on `PATH`, with the default Codex home (`~/.codex`), so a ChatGPT plan login works. The script never sets `CODEX_HOME` to `backend/.codex_home`.

### 6. Responses and the report

`response.md` is a table: finding id, `fixed` (with the files changed) or `declined` (with the reason). Fixes stay in the working tree; the developer approves any commit.

The report, posted in chat and saved as `report.md`:

1. **Flags first:** any `high` finding that was not fixed.
2. A table of every finding from every round, ordered high, medium, low: round, severity, file, title, outcome (fixed, declined with reason, or open).
3. Counts per round and the path to the records.

### 7. The checks gate

The loop runs "the project's checks", named in one place in `CLAUDE.md` and the slash command. Until `harden-db-and-expand-tests` M1 lands, that is `npm --prefix frontend run check:backend`; M1 changes it to `make check` and `make test`.

### 8. Reviewer guidelines

`dev-docs/reviewing.md` asks the reviewer to check, in order: correctness and regressions; the change's specs and design; invariants (`INV-*` in `dev-docs/design.md`) and the Dev docs impact; simplicity (the smallest thing that works); and the conventions in `CLAUDE.md`. Findings only, no praise, an empty list when clean. A short "follow-up rounds" section says how to treat earlier findings, fixes and declines.

*Alternatives:*
- Claude reviewing its own work: same model family, same blind spots.
- One long reviewer session across rounds: round 2 anchors on its own earlier opinions. A fresh session told its round and given the earlier files keeps the context without the anchoring.
- A hand-written JSON schema file: a second definition to keep in sync. Generated from Pydantic instead.
- Saving each round's prompt: redundant with git and `meta.json`.
- Committing each fix: commits need the developer's approval.

## Risks / Trade-offs

- [Codex plan limits] -> Two rounds per milestone on a ChatGPT plan should fit; an API key login works the same way if not.
- [Noisy findings] -> Findings only, with severity; declines with reasons keep noise from turning into churn.
- [Claude declining too much] -> Every decline is recorded, judged by round 2, and listed in the report; unfixed high-severity findings are flagged first.
- [Codex CLI flags change] -> All Codex invocation lives in `review_round.py`.
- [Reviewers disagreeing with the specs] -> The guidelines treat the change's specs and design as the reference; disagreement is reported to the developer, not silently fixed.
- [Reviewing uncommitted changes] -> The reviewer sees the working tree as it is; anything unrelated in progress should be stashed before a review.

## Open Questions

- Whether a high-severity finding left open after round 2 should block the "ready" report or only be flagged. Starting with flagged.

## Dev docs impact

- README.md - the file table: adds `reviewing.md`.
- design.md - a short development-workflow note (OpenSpec changes, reviewed by the AI review loop before reaching the developer), pointing at `dev-docs/reviewing.md`, `make review-round` and `/review-milestone`.
- design.md - Change log: one line for this change.
- proposal.md: None.
