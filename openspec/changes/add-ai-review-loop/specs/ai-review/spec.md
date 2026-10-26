# Spec Delta

## Purpose

Defines how a finished milestone is reviewed by an AI reviewer from a different model family, and fixed, before it is handed to the developer for review.

## ADDED Requirements

### Requirement: Claude reviews before reporting ready
Claude SHALL run the review loop on every milestone before reporting it ready to the developer.

#### Scenario: Milestone finished
- **WHEN** Claude finishes a milestone's tasks
- **THEN** it runs the review loop and only then reports the milestone ready, with the review report

### Requirement: The developer can trigger an extra pass
The developer SHALL be able to run the same loop on demand with `/review-milestone`, for example to let the AI patch quick fixes instead of reviewing them by hand. Each run SHALL start a new review.

#### Scenario: Extra pass
- **WHEN** the developer runs `/review-milestone` after looking at a milestone
- **THEN** a new review runs with fresh rounds, recorded alongside the earlier ones

### Requirement: Checks gate every handoff
The project's checks SHALL pass before work is handed to the reviewer and before it is reported to the developer. Work with failing checks SHALL NOT be reviewed or reported ready.

#### Scenario: Checks fail before a round
- **WHEN** a review is started and the project's checks fail
- **THEN** no review round runs, and the failures are fixed first

#### Scenario: Checks fail after fixes
- **WHEN** fixes made for a round leave the checks failing
- **THEN** the next round does not start and nothing is reported until they pass

### Requirement: At most two review rounds
A review SHALL run one round, and a second round only when the first produced findings. It SHALL NOT run more than two rounds.

#### Scenario: Clean first round
- **WHEN** round 1 returns no findings
- **THEN** no round 2 runs and the milestone is reported ready

#### Scenario: Findings in round 1
- **WHEN** round 1 returns findings
- **THEN** after they are addressed, round 2 runs, and the loop then ends whatever round 2 finds

### Requirement: Each round is a fresh reviewer session
Every round SHALL start a new reviewer session with no memory of earlier sessions.

#### Scenario: New session
- **WHEN** round 2 starts
- **THEN** it runs in a new reviewer process

### Requirement: The reviewer knows its round
Every round SHALL use the same reviewer guidelines and SHALL be told which round it is. A later round SHALL also be given the earlier rounds' findings and responses, and asked to check the fixes, judge the declines, and look for problems the fixes introduced.

#### Scenario: Round 2 prompt
- **WHEN** round 2 starts
- **THEN** its prompt says it is round 2 of 2 and points to round 1's findings and responses

### Requirement: Reviewer inputs
Each round SHALL give the reviewer the reviewer guidelines, the OpenSpec change's artifacts, `dev-docs/`, and the milestone's changes: everything changed since the base commit (by default `HEAD`), including new untracked files. The reviewer SHALL NOT be able to modify the repository.

#### Scenario: Milestone not yet committed
- **WHEN** a milestone's work is uncommitted on top of the previous milestone's commit, and adds a new file
- **THEN** the round reviews that work, including the new file, and not the earlier milestones

#### Scenario: Read-only reviewer
- **WHEN** a review round runs
- **THEN** the reviewer reads the repository but cannot write to it

### Requirement: Structured findings
A round SHALL produce findings matching a defined model, each with an id, a severity (`high`, `medium`, `low`), a file, a line where one applies, a title, details and a suggestion. Output that does not match SHALL fail the round.

#### Scenario: Findings saved
- **WHEN** a round finishes
- **THEN** its findings are validated against the model and saved, and a round with no issues saves an empty list

### Requirement: Every finding gets a response
Each finding SHALL be answered as fixed, with the files changed, or declined, with a reason. Declining is allowed. Fixes SHALL be left uncommitted for the developer to approve.

#### Scenario: Declined finding
- **WHEN** a finding is declined
- **THEN** its reason is recorded, passed to the next round, and shown in the report

#### Scenario: Fixes left uncommitted
- **WHEN** the loop ends
- **THEN** every fix is in the working tree and nothing was committed by the loop

### Requirement: Report to the developer
The loop SHALL end with a report in chat: every finding in a table ordered by severity, with what was fixed and what was declined and why. Any high-severity finding not fixed SHALL be flagged at the top.

#### Scenario: Unfixed high-severity finding
- **WHEN** a high-severity finding was declined
- **THEN** the report starts by flagging it, before the table

### Requirement: Local review records
Each review SHALL be recorded under `.reviews/<change>/<milestone>/<timestamp>/`: per-round findings and responses, the report, and metadata (rounds, the changes reviewed, reviewer model, timestamps, finding counts). The records SHALL NOT be committed.

#### Scenario: Records stay local
- **WHEN** a review finishes
- **THEN** its records exist under `.reviews/` and `git status` does not show them

### Requirement: Developer's own reviewer login
The reviewer SHALL run with the developer's own Codex login, never the application's project-local Codex home.

#### Scenario: App credentials untouched
- **WHEN** a review round runs
- **THEN** the application's `.codex_home` is neither read nor changed
