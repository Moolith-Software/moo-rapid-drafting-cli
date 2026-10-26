# Spec Delta

## Purpose

Defines how a feature is drafted, refined, branched and taken deeper, how warm environments are used, and what survives a restart.

## ADDED Requirements

### Requirement: Cold build when nothing is preloaded
When no matching warm environment exists, an add SHALL create a new feature and build its environment before the AI runs, moving through `queued`, `initializing`, `building` and `completed`.

#### Scenario: First feature on a fresh install
- **WHEN** a feature is added with nothing preloaded
- **THEN** it is built cold and ends `completed` with file changes

### Requirement: Warm claim reuses a preloaded environment
An add SHALL claim the oldest warm environment with the same parent that was cloned from the parent's current version, without creating a new feature.

#### Scenario: Preloaded root
- **WHEN** two root environments are preloaded and a root feature is added
- **THEN** the oldest one becomes that feature, and no new feature id is created

### Requirement: A warm environment is claimed once
A warm environment SHALL go to at most one request, even when requests arrive at the same moment.

#### Scenario: Two adds race for one environment
- **WHEN** two adds arrive together and one environment is ready
- **THEN** exactly one of them gets it and the other is built cold

### Requirement: Stale warm children are skipped
A warm child cloned from an older version of its parent SHALL NOT be claimed.

#### Scenario: Parent refined after a child was preloaded
- **WHEN** a child is preloaded, the parent is refined, and a child of it is then added
- **THEN** the stale warm child is not used and the new child is built cold from the refined parent

### Requirement: One refinement at a time
Of two refine requests for the same feature, only one SHALL be accepted.

#### Scenario: Double refine
- **WHEN** two refines of one feature arrive together
- **THEN** one returns 202 and the other 409, and exactly one refinement is recorded

### Requirement: The AI session carries through
An add SHALL continue the session its environment was warmed with, and a refine SHALL resume the feature's own session. A child SHALL start a new session.

#### Scenario: Session ids across a feature's life
- **WHEN** a warm feature is added and then refined
- **THEN** both turns are run with the session id from the warm-up, and the stored session id does not change

#### Scenario: Child session
- **WHEN** a child of a feature is built
- **THEN** its session id differs from its parent's

### Requirement: Children start from the parent's code
A child SHALL start with every file in its parent's branch at the time it was cloned, and record that version in `cloned_from_version`.

#### Scenario: Going deep
- **WHEN** a child of a child is built
- **THEN** its branch contains its parent's and grandparent's changes and its `cloned_from_version` is its parent's version

### Requirement: Parents with children are locked
A feature with a real child SHALL NOT be refined; a new child can be branched and refined instead.

#### Scenario: Branch fresh to keep going
- **WHEN** a parent with children is refined
- **THEN** the response is 409, and refining a newly branched child of it succeeds without changing the parent

### Requirement: Only the target feature changes
Work on one feature SHALL NOT change any other feature's row. Each writing turn SHALL raise `workspace_version` by one, and refinements SHALL only be appended.

#### Scenario: Siblings untouched
- **WHEN** a child is refined
- **THEN** its parent and siblings are unchanged, and the child's `workspace_version` is one higher

### Requirement: Data survives a restart
Features and their history SHALL be unchanged after the backend stops and starts again, and no workspace SHALL be left open.

#### Scenario: Restart
- **WHEN** the backend is shut down and started again on the same database
- **THEN** every feature reads back the same, and the startup sweep has closed any open workspace
