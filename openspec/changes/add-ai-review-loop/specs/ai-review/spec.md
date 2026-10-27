# Spec Delta

## Purpose

Defines how work, an OpenSpec milestone or any other change, is reviewed by an AI reviewer from a different model family, and fixed, before the developer reviews it.

## ADDED Requirements

### Requirement: Claude reviews before reporting ready
Claude SHALL run the review loop on every milestone before reporting it ready to the developer.

#### Scenario: Milestone finished
- **WHEN** Claude finishes a milestone's tasks
- **THEN** it runs the review loop and only then reports the milestone ready, with the review report

### Requirement: One review command for the developer
The developer SHALL be able to run the same loop at any time with `/re`, on OpenSpec milestone work or on any other work such as a hotfix: `/re` detects the mode, `/re <change>` reviews that change's milestone, `/re adhoc` forces ad hoc mode, and `rounds=N` sets the number of rounds. Each run SHALL start a new review.

#### Scenario: Extra pass on a milestone
- **WHEN** the developer runs `/re` after looking at a milestone
- **THEN** a new review runs with fresh rounds, recorded alongside the earlier ones

#### Scenario: Hotfix outside OpenSpec
- **WHEN** the developer runs `/re` on a branch with a hotfix and no OpenSpec work in progress
- **THEN** the loop runs in ad hoc mode and ends with the same report

### Requirement: The review mode follows the work
A review SHALL run in ad hoc mode when ad hoc mode is requested, whatever is ticked. Otherwise it SHALL run in milestone mode when a change is named, or when a change's `tasks.md` has uncommitted newly ticked tasks; the milestone is the task group those ticks belong to. Otherwise it SHALL run in ad hoc mode.

#### Scenario: Milestone detected
- **WHEN** `/re` runs with no argument and a change's `tasks.md` has uncommitted ticks in group 2
- **THEN** the review runs in milestone mode for that change and milestone

#### Scenario: Change named
- **WHEN** the developer runs `/re harden-db-and-expand-tests`
- **THEN** the review runs in milestone mode for that change

#### Scenario: Nothing ticked
- **WHEN** `/re` runs with no argument and no change's tasks are newly ticked
- **THEN** the review runs in ad hoc mode

#### Scenario: Hotfix while a milestone is in progress
- **WHEN** the developer runs `/re adhoc` while a change's tasks are newly ticked
- **THEN** the review runs in ad hoc mode, not milestone mode

### Requirement: Checks gate every handoff
The project's checks SHALL pass before work is handed to the reviewer and before it is reported to the developer. Work with failing checks SHALL NOT be reviewed or reported ready.

#### Scenario: Checks fail before a round
- **WHEN** a review is started and the project's checks fail
- **THEN** no review round runs, and the failures are fixed first

#### Scenario: Checks fail after fixes
- **WHEN** fixes made for a round leave the checks failing
- **THEN** the next round does not start and nothing is reported until they pass

### Requirement: A set number of review rounds
A review SHALL run up to a set number of rounds: two by default, or the number the developer gives, from 1 to 5. Each round after the first SHALL run only when the previous round produced findings.

#### Scenario: Clean first round
- **WHEN** round 1 returns no findings
- **THEN** no round 2 runs and the milestone is reported ready

#### Scenario: Findings in round 1
- **WHEN** round 1 returns findings
- **THEN** after they are addressed, round 2 runs, and with the default of two rounds the loop then ends whatever round 2 finds

#### Scenario: More rounds requested
- **WHEN** the developer runs `/re rounds=3` and rounds 1 and 2 both return findings
- **THEN** round 3 runs, and the loop ends after it

### Requirement: Each round is a fresh reviewer session
Every round SHALL start a new reviewer session with no memory of earlier sessions.

#### Scenario: New session
- **WHEN** round 2 starts
- **THEN** it runs in a new reviewer process

### Requirement: The reviewer knows its round
Every round SHALL use the same reviewer guidelines and SHALL be told which round it is. A later round SHALL also be given the earlier rounds' findings and responses, and asked to check the fixes, judge the declines, and look for problems the fixes introduced.

#### Scenario: Round 2 prompt
- **WHEN** round 2 starts
- **THEN** its prompt says which round it is out of how many, and points to every earlier round's findings and responses

### Requirement: Reviewer inputs
Each round SHALL give the reviewer the reviewer guidelines, `dev-docs/`, `CLAUDE.md`, the mode and the work in scope. In milestone mode it SHALL also get the change's artifacts; in ad hoc mode it SHALL check the work against `dev-docs/` and the living specs. The reviewer SHALL NOT be able to modify the repository.

#### Scenario: Milestone inputs
- **WHEN** a milestone-mode round starts
- **THEN** the reviewer is given the change's proposal, specs, design and tasks

#### Scenario: Read-only reviewer
- **WHEN** a review round runs
- **THEN** the reviewer reads the repository but cannot write to it

### Requirement: Work in scope
The work in scope SHALL include new untracked files. In milestone mode it SHALL be everything changed since `HEAD`; in ad hoc mode, the branch since it left `origin/main` plus uncommitted work. An explicitly given base commit SHALL override either default.

#### Scenario: Milestone not yet committed
- **WHEN** a milestone's work is uncommitted on top of the previous milestone's commit, and adds a new file
- **THEN** the round reviews that work, including the new file, and not the earlier milestones

#### Scenario: Ad hoc branch
- **WHEN** an ad hoc review runs on a branch with two hotfix commits and an uncommitted edit
- **THEN** the round reviews both commits and the edit

### Requirement: Structured findings
A round SHALL produce findings matching a defined model, each with an id, a severity (`high`, `medium`, `low`), a file, a line where one applies, a title, details and a suggestion. Output that does not match SHALL fail the round.

#### Scenario: Findings saved
- **WHEN** a round finishes
- **THEN** its findings are validated against the model and saved, and a round with no issues saves an empty list

### Requirement: Every finding gets a response
Each finding SHALL be answered as fixed, with the files changed, or declined, with a reason, as structured data matching a defined model. Every finding SHALL be answered exactly once, with no answers to findings that do not exist; this SHALL be checked before a follow-up round runs and before the report is written. Declining is allowed. Fixes SHALL be left uncommitted for the developer to approve.

#### Scenario: Declined finding
- **WHEN** a finding is declined
- **THEN** its reason is recorded, passed to the next round, and shown in the report

#### Scenario: Unanswered finding
- **WHEN** a round's response leaves one finding unanswered
- **THEN** the next round refuses to start, and the check before the report fails, naming the missing finding

#### Scenario: Answer to a finding that does not exist
- **WHEN** a response answers an id the round did not report, or answers one finding twice
- **THEN** the check fails, naming the unknown or duplicated id

#### Scenario: Fixes left uncommitted
- **WHEN** the loop ends
- **THEN** every fix is in the working tree and nothing was committed by the loop

### Requirement: Report to the developer
The loop SHALL end with a report in chat: every finding in a table ordered by severity, with what was fixed and what was declined and why. Any high-severity finding not fixed SHALL be flagged at the top.

#### Scenario: Unfixed high-severity finding
- **WHEN** a high-severity finding was declined
- **THEN** the report starts by flagging it, before the table

### Requirement: Local review records
Each review SHALL be recorded under `.reviews/<change>/<milestone>/<timestamp>/` in milestone mode, or `.reviews/adhoc/<branch>/<timestamp>/` in ad hoc mode: per-round findings and responses, the report, and metadata (rounds, the changes reviewed, reviewer model, timestamps, finding counts). The records SHALL NOT be committed.

#### Scenario: Records stay local
- **WHEN** a review finishes
- **THEN** its records exist under `.reviews/` and `git status` does not show them

### Requirement: Developer's own reviewer login
The reviewer SHALL run with the developer's own Codex login, never the application's project-local Codex home.

#### Scenario: App credentials untouched
- **WHEN** a review round runs
- **THEN** the application's `.codex_home` is neither read nor changed
