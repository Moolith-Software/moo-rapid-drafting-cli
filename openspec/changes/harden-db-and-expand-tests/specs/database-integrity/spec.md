# Spec Delta

## Purpose

Defines the states and changes the database itself refuses, so feature data stays valid even when application code has a bug, and how a refused lifecycle write is reported.

## ADDED Requirements

### Requirement: Status is one of seven values
The database SHALL refuse any feature whose `status` is not `initializing`, `ready`, `queued`, `building`, `refining`, `completed` or `failed`.

#### Scenario: Unknown status
- **WHEN** a write sets `status` to `bogus`
- **THEN** the database refuses it and the row is unchanged

### Requirement: Status changes follow the lifecycle
The database SHALL refuse a status change that is not one of the lifecycle's transitions: `initializing` to `ready`, `building` or `failed`; `ready` to `queued`; `queued` to `initializing`, `building`, `refining` or `failed`; `building` or `refining` to `completed` or `failed`; `completed` or `failed` to `queued`. Writing the same status again SHALL be allowed.

#### Scenario: Skipping the build
- **WHEN** a write changes a `ready` feature straight to `completed`
- **THEN** the database refuses it

#### Scenario: Same status again
- **WHEN** a write sets an `initializing` feature to `initializing`
- **THEN** the write succeeds

### Requirement: Fixed columns stay fixed
Once set, a feature's `id`, `parent_id` and `created_at` SHALL never change; `feature`, `code_folder_name` and `cloned_from_version` SHALL never change after they first become non-empty; and `workspace_version` SHALL never decrease.

#### Scenario: Rewriting the request
- **WHEN** a write changes the `feature` of a claimed feature
- **THEN** the database refuses it

#### Scenario: Version going backwards
- **WHEN** a write lowers `workspace_version`
- **THEN** the database refuses it

### Requirement: Columns agree with each other
The database SHALL refuse a feature where: a `ready` row has a request, a written branch, or no branch; a `building`, `refining` or `completed` row lacks a request or a branch; a `completed` row has no file changes; a `failed` row's `progress` is not a status line starting with `[`; `harness_session_id` and `harness` are not both set or both empty; or a root feature has a `cloned_from_version`.

#### Scenario: Completed without changes
- **WHEN** a write marks a feature `completed` with `file_changes` of `[]`
- **THEN** the database refuses it

#### Scenario: Session without a harness
- **WHEN** a write sets `harness_session_id` but leaves `harness` empty
- **THEN** the database refuses it

### Requirement: Stored values are well formed
The database SHALL refuse a `feature` longer than 10,000 characters, a `file_changes` or `refinements` value that is not a JSON array, and a `summary` that is not a JSON object.

#### Scenario: Malformed JSON
- **WHEN** a write stores `file_changes` as `not json`
- **THEN** the database refuses it

### Requirement: Branch names are unique
The database SHALL refuse two features with the same non-empty `code_folder_name`.

#### Scenario: Duplicate branch name
- **WHEN** a write gives a second feature an existing branch name
- **THEN** the database refuses it

### Requirement: Parents with children are not refined
The database SHALL refuse to claim a feature for refinement while it has a real child: one with a request that did not fail before getting a branch. Unclaimed warm children SHALL NOT count.

#### Scenario: Child created between the check and the claim
- **WHEN** a child of a feature is created after the refine request's check but before its claim
- **THEN** the claim is refused and the refine request returns 409

#### Scenario: Only warm children
- **WHEN** a feature's only children are unclaimed warm environments
- **THEN** it can be claimed for refinement

### Requirement: Children only under completed parents
The database SHALL refuse to create a child, or to claim a warm child, under a parent that is not `completed`.

#### Scenario: Parent claimed for refinement first
- **WHEN** a parent was just claimed for refinement and a child of it is then added
- **THEN** the child is refused and the add request returns 409

### Requirement: Lifecycle conflicts are reported as conflicts
A write refused by a lifecycle rule (the two rules above) SHALL surface as `ConflictError`, code 3002, title `Conflicting write`. In a request it SHALL return 409 with the status line as detail. Every other refusal SHALL surface as `DatabaseError` (3000).

#### Scenario: Conflict in a request
- **WHEN** a request's write is refused because the parent has children
- **THEN** the response is 409 and its detail starts with `[3002] Conflicting write`

#### Scenario: Any other refusal
- **WHEN** a bug writes an unknown status during a request
- **THEN** the error is `[3000] Database error` and the response is 500

### Requirement: A fresh schema for development
The schema SHALL be created from the single initial migration. A database created before this change SHALL be deleted and recreated, not migrated.

#### Scenario: Old local database
- **WHEN** a developer runs `make reset-db`
- **THEN** the dev database is deleted and the next start creates it with every rule above
