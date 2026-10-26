# Spec Delta

## Purpose

Defines the contract every AI harness keeps, so the rest of the application behaves the same whichever harness or provider runs a turn.

## ADDED Requirements

### Requirement: One turn in, one normalized outcome out
Every harness SHALL run one turn on a workspace and return the final text, the session id and its own harness name, whatever its provider returns.

#### Scenario: Mock turn
- **WHEN** the mock harness runs a turn
- **THEN** it returns text, a session id and the name `mock`

### Requirement: Answers match the requested schema
The text a harness returns SHALL be parsed against the schema the turn asked for. An empty, non-JSON or wrongly shaped answer SHALL fail with 2005.

#### Scenario: Wrong shape
- **WHEN** a turn's answer is JSON with a missing field
- **THEN** it fails with `[2005] Unusable AI response`

### Requirement: Read-only turns do not write
A turn run as read-only SHALL NOT change any file in the workspace.

#### Scenario: Warm-up
- **WHEN** a read-only turn runs
- **THEN** every file in the workspace is unchanged

### Requirement: Sessions are reused when given
A harness given a session id SHALL continue that session; one given none SHALL start a new one. A session made by a different harness SHALL NOT be resumed.

#### Scenario: Foreign session
- **WHEN** a stored session belongs to another harness
- **THEN** the turn starts a new session

### Requirement: Failures are flattened and tagged
Every harness failure SHALL surface as one of the 2xxx codes, with the harness and model in front of the title.

#### Scenario: Timeout
- **WHEN** the mock harness is told to time out
- **THEN** the turn fails with a 2002 whose title starts with `[mock]`

#### Scenario: Provider messages classified
- **WHEN** the Codex harness reports an invalid API key, a rate limit or an unrecognized failure
- **THEN** they become 2003, 2004 and 2001 respectively

### Requirement: Replay of recorded changes
The mock harness SHALL be able to apply a recorded multi-file change to the workspace instead of its default one-line edit.

#### Scenario: Replayed change
- **WHEN** the mock replays a recorded change that edits three files
- **THEN** the feature's `file_changes` lists exactly those three files

### Requirement: The harness is chosen by settings
The harness SHALL be built from settings. An unknown harness name, a provider the harness does not support, or a missing API key SHALL fail with 2000.

#### Scenario: Missing key
- **WHEN** the Codex harness is selected and no API key is set
- **THEN** the turn fails with `[2000] AI not configured`
