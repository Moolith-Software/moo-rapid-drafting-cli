# Design

## Context

See proposal.md for why. Today a milestone goes straight from Claude to the developer. This change adds a review step in between, run by the Codex CLI, without changing any application code. It is the first verification gate; later gates (more reviewers, narrower checks) should be able to slot into the same loop.

## Goals / Non-Goals

**Goals:**

- Claude reviews every milestone with Codex before reporting it ready, and the developer can trigger the same loop on demand, on a milestone or on any other work (ad hoc mode).
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
| `make review-round ROUND=<n> [ROUNDS=<n>] [MODE=adhoc] [CHANGE=<change>] [MILESTONE=<m>] [BASE=<ref>] [MODEL=<model>]` | **Claude** | the main path: Claude drives the loop with it after finishing every milestone, before reporting it ready |
| `make review-round CHECK=1` | **Claude** | before writing the report: confirms every finding of every round has exactly one response |
| `/re [change \| adhoc] [rounds=N]` | **the developer** | any time: an extra pass on a milestone, or a review of any other work (a hotfix, a refactor). `adhoc` forces ad hoc mode; `rounds=N` sets the number of rounds (default 2, 1 to 5) |

Both detect the mode the same way (Decision 3) and run the same loop:

```
checks green? -- no --> fix, re-run checks
   |
   v
round 1: make review-round ... ROUND=1  -->  round-1/findings.json
   |
   v
Claude answers every finding (fix in the working tree, or decline + reason)  -->  round-1/response.json
   |
   v
checks green? -- no --> fix
   |
   v
next round (only if the previous one had findings, up to ROUNDS): new process, told its round, given every earlier round's files
   |
   v
Claude answers it --> round-N/response.json; checks green; repeat while rounds remain
   |
   v
make review-round CHECK=1: every round's response matches its findings
   |
   v
report in chat (and report.md); nothing committed
```

The make target does one mechanical thing: run one Codex round and save its output. The loop itself needs Claude's judgment (fixing, declining), so it lives in Claude's instructions: the `CLAUDE.md` rule for the main path, and `/re` for the developer, on a milestone or any other work.

### 2. Files

```
Makefile                         review-round target, with CHECK=1 for the
                                 response check (created here; M1 of
                                 harden-db-and-expand-tests extends it)
backend/scripts/review_round.py  runs one round: prompt, Codex, validate, save
dev-docs/reviewing.md            reviewer guidelines, read every round
.claude/commands/
  re.md                          the developer's /re command
.reviews/                        (gitignored)
  <change>/<milestone>/<YYYYMMDD-HHMMSS>/   milestone mode
  adhoc/<branch>/<YYYYMMDD-HHMMSS>/         ad hoc mode
    (each run folder holds:)
    round-1/  findings.json  response.json
    round-2/  ...                (one folder per round run)
    report.md                    the same report Claude posts in chat
    meta.json                    mode, change, milestone, base, branch; per round:
                                 head, model, timestamps, finding count
                                 timestamps, finding counts per round
```

The script lives in `backend/scripts/` (beside the linting rules) so it runs in the backend environment and can use Pydantic. A timestamped folder per run keeps earlier reviews next to new ones. A round whose folder has no `findings.json` failed, and running it again replaces it.

Round 1 records its run folder in `.reviews/latest`. A follow-up round continues exactly that run, reading its mode, change, milestone and base from `meta.json` rather than detecting them again, so ticks changing between rounds cannot move the review to another folder. It is refused if that round already ran, if the previous round found nothing, or if the current branch differs from the run's.

### 3. Two modes

```
/re [change | adhoc]   or   make review-round ... [MODE=adhoc] [CHANGE=...]
   |
   +-- ad hoc requested? ----------------------------------> ad hoc mode
   +-- a change named? ------------------------------------> milestone mode
   +-- a change's tasks.md has uncommitted newly ticked tasks? --> milestone mode
   |     (apply ticks boxes as it builds; the milestone is the
   |      task group those ticks are in)
   +-- otherwise ------------------------------------------> ad hoc mode
```

| | Milestone mode | Ad hoc mode |
|---|---|---|
| Work in scope | everything changed since `HEAD` | the branch since it left `origin/main` (its merge base), plus uncommitted work; on `main` itself that is just the uncommitted work |
| Why that base | a milestone is reviewed, then the developer reviews it, and only then is it committed as one commit; so the milestone is exactly the uncommitted work, and earlier milestones are left out | a hotfix or refactor may already be several commits on its branch |
| Reviewer also reads | the change's proposal, specs, design and tasks | the `openspec/specs/` covering the changed code; the archive only if it needs history |
| Checked against | the change's specs and design | `dev-docs/` and the living specs |
| Records | `.reviews/<change>/<milestone>/<timestamp>/` | `.reviews/adhoc/<branch>/<timestamp>/` |

In ad hoc mode the base falls back to `main` when there is no `origin/main`, and to `HEAD` (with a warning) when neither exists. Requesting ad hoc mode matters when milestone work is in progress: a hotfix made meanwhile would otherwise be detected as part of the milestone. `BASE=<ref>` overrides the base in either mode. In both, the work in scope includes **new untracked files**, which `git diff` alone does not show.

### 4. The prompt for each round

`review_round.py` builds the prompt from:

- a **round header**: the mode, "This is round N of M." (M is `ROUNDS`, default 2), and for a follow-up round the paths of every earlier round's `findings.json` and `response.json`, with the instruction to check the fixes, judge the declines, and look for problems the fixes introduced;
- `dev-docs/reviewing.md` (the same guidelines every round), `CLAUDE.md`, `dev-docs/proposal.md` and `dev-docs/design.md`;
- in milestone mode, the change name and its artifact paths (`openspec/changes/<change>/`);
- the work in scope (Decision 3), which the reviewer inspects with `git` itself.

The prompt is not saved: the guidelines are in git, and the mode, round, base and paths are in `meta.json`.

### 5. Structured findings with Pydantic

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

### 6. Running Codex

- `codex exec` in a **read-only sandbox**, with the generated output schema, writing its final message to a file the script then validates. The exact flags are confirmed against the installed CLI in task 2.1.
- **A new process per round**, so each round is a fresh session.
- **The developer's own login.** The `codex` on `PATH`, with the default Codex home (`~/.codex`), so a ChatGPT plan login works. The script never sets `CODEX_HOME` to `backend/.codex_home`.
- **An explicit model.** `codex exec -m <model>`, defaulting to `gpt-6.1-sol` (OpenAI's recommended Codex model for paid ChatGPT plans) and overridable with `MODEL=`. The script names its model rather than relying on the developer's global default; newer models also need a current Codex CLI (`codex update`). The model used is recorded in `meta.json`.
- Confirmed flags: `-s read-only`, `--output-schema <file>`, `-o <file>`, `-C <dir>`, `--ephemeral`, and `-` to read the prompt from stdin.

### 7. Responses and the report

Claude writes `response.json`, validated by Pydantic like the findings, so every finding has a matching row:

```python
class Response(BaseModel):
    id: str                              # a finding id from the same round
    outcome: Literal["fixed", "declined"]
    files: list[str]                     # required when fixed
    reason: str                          # required when declined

class Responses(BaseModel):
    responses: list[Response]
```

The ids must match the round's findings **exactly once each**: no finding left out, none answered twice, no unknown ids. A follow-up round checks the previous round before it runs. `make review-round CHECK=1` checks every round of the current review; Claude runs it before writing the report, which is the only check the last round gets. Fixes stay in the working tree; the developer approves any commit.

The report, posted in chat and saved as `report.md`:

1. **Flags first:** any `high` finding that was not fixed.
2. A table of every finding from every round, ordered high, medium, low: round, severity, file, title, outcome (fixed, declined with reason, or open).
3. Counts per round and the path to the records.

### 8. The checks gate

The loop runs "the project's checks", named once, in `CLAUDE.md` (Checks and AI review); `/re` follows that section, so M1 changes one place. Until `harden-db-and-expand-tests` M1 lands, that is `npm --prefix frontend run check:backend`; M1 changes it to `make check` and `make test`.

### 9. Reviewer guidelines

`dev-docs/reviewing.md` asks the reviewer to check, in order: correctness and regressions; security (secrets, unsafe input handling); the change's specs and design (in ad hoc mode, `dev-docs/` and the living specs instead); invariants (`INV-*` in `dev-docs/design.md`) and the Dev docs impact; simplicity (the smallest thing that works); the conventions in `CLAUDE.md`; and anything else a senior engineer would block a merge for, reported only as `medium` or `high` so open-ended judgment does not turn into a stream of minor edge cases. The developer's rules (DR-1 to DR-12) apply on top, and findings that come from one cite its id. Findings only, no praise, an empty list when clean. A short "follow-up rounds" section says how to treat earlier findings, fixes and declines.

*Alternatives:*
- Claude reviewing its own work: same model family, same blind spots.
- One long reviewer session across rounds: round 2 anchors on its own earlier opinions. A fresh session told its round and given the earlier files keeps the context without the anchoring.
- A hand-written JSON schema file: a second definition to keep in sync. Generated from Pydantic instead.
- Saving each round's prompt: redundant with git and `meta.json`.
- Committing each fix: commits need the developer's approval.

## Risks / Trade-offs

- [Codex plan limits] -> Two rounds per milestone by default, capped at 5 so a mistake cannot run many; this should fit a ChatGPT plan, and an API key login works the same way if not.
- [Noisy findings] -> Findings only, with severity; declines with reasons keep noise from turning into churn.
- [Claude declining too much] -> Every decline is recorded, judged by the next round if there is one, and listed in the report; unfixed high-severity findings are flagged first.
- [Codex CLI flags change] -> All Codex invocation lives in `review_round.py`.
- [Reviewers disagreeing with the specs] -> The guidelines treat the change's specs and design as the reference; disagreement is reported to the developer, not silently fixed.
- [Reviewing uncommitted changes] -> The reviewer sees the working tree as it is; anything unrelated in progress should be stashed before a review.

## Open Questions

- Whether a high-severity finding left open after the last round should block the "ready" report or only be flagged. Starting with flagged.

## Dev docs impact

- README.md - the file table: adds `reviewing.md`.
- design.md - a short development-workflow note (OpenSpec changes, reviewed by the AI review loop before reaching the developer), pointing at `dev-docs/reviewing.md`, `make review-round` and `/re`.
- design.md - Change log: one line for this change.
- proposal.md: None.
