# Spec Delta

## Purpose

Defines the backend's HTTP contract: what each endpoint accepts, what it returns on success, and every error a client must handle.

## ADDED Requirements

### Requirement: Work endpoints answer before the work is done
`POST /core/preload_environment`, `POST /core/add` and `POST /core/refine` SHALL validate, reserve the affected rows, queue the work and return 202 without waiting for it.

#### Scenario: Add returns at once
- **WHEN** a client adds a feature
- **THEN** the response is 202 and the feature's status is readable straight away

### Requirement: Preload responses
`POST /core/preload_environment` SHALL accept `count` from 1 to 1000 (default 1) and an optional `parent_id`, and return 202 with `{"queued": count}`. It SHALL return 404 when the parent does not exist and 409 when the parent is not `completed`.

#### Scenario: Preload under a missing parent
- **WHEN** a client preloads under a `parent_id` that does not exist
- **THEN** the response is 404 `parent feature <id> not found` and nothing is queued

### Requirement: Add responses
`POST /core/add` SHALL accept one request or 1 to 1000 requests and an optional `parent_id`, and return 202 with one `{feature_id, feature_request}` per request, in order, each request echoed cut to 1000 characters. It SHALL return 404 for a missing parent, and 409 for a parent that is not `completed` or a conflicting write.

#### Scenario: Batch keeps order
- **WHEN** a client adds three requests
- **THEN** the response lists three features in the order sent

#### Scenario: Parent not completed
- **WHEN** a client adds a child of a `building` feature
- **THEN** the response is 409 and nothing is queued

### Requirement: Refine responses
`POST /core/refine` SHALL accept `feature_id` and `user_request` and return 202 with `{"feature_id"}`. It SHALL return 404 for a missing feature, and 409 when the feature has real children, is not refinable, or the write conflicts.

#### Scenario: Refining a missing feature
- **WHEN** a client refines a feature id that does not exist
- **THEN** the response is 404 `feature not found` and nothing is queued

#### Scenario: Refining a feature in flight
- **WHEN** a client refines a feature that is `building`
- **THEN** the response is 409 `feature is not in a refinable state`

### Requirement: Read responses
`GET /features` SHALL return every feature, newest first. `GET /features/{id}` SHALL return one feature with every column and 404 when it does not exist. `GET /features/{id}/status` SHALL return only `id`, `status` and `progress`, and 404 when it does not exist.

#### Scenario: Status shape
- **WHEN** a client reads an existing feature's status
- **THEN** the body has exactly `id`, `status` and `progress`

### Requirement: Invalid input is 422
Every endpoint SHALL return 422 for a body or path that fails validation, and queue nothing.

#### Scenario: Blank request
- **WHEN** a client adds a request that is only spaces
- **THEN** the response is 422

### Requirement: Database unavailable is 503
Every endpoint SHALL return 503 with a `[3001] Database unavailable` detail when the database cannot be opened, and recover on the next request once it can.

#### Scenario: Recovery without restart
- **WHEN** the database becomes openable again after a 503
- **THEN** the next request succeeds

### Requirement: Unexpected errors are 500
Every endpoint SHALL return 500 for an unexpected error, without leaking its details in the body.

#### Scenario: Unexpected failure
- **WHEN** an endpoint hits an error nothing maps
- **THEN** the response is 500 `Internal Server Error`

### Requirement: API docs only in development
The app SHALL serve `/docs`, `/redoc` and `/openapi.json` only when started in development (`ENV` of `dev` or `development`, any case), and return 404 for them otherwise.

#### Scenario: Unset or misspelled ENV
- **WHEN** the app starts with `ENV` unset or set to `developmnet`
- **THEN** `/docs` returns 404
