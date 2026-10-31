# ai-chat-history-plan-lifecycle Specification

## Purpose
TBD - created by archiving change 2026-10-31-ai-chat-history-and-plan-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: System SHALL persist and query multi-session conversation history
The backend SHALL persist conversation sessions with user-friendly titles, creation timestamps, last activity timestamps, and archive flags (`is_archived`). The system SHALL provide endpoints to list active and archived sessions and retrieve conversation message threads with associated plan indicators.

#### Scenario: List conversation history with plan status
- **WHEN** an authenticated user requests `GET /api/v1/farming-chat/sessions`
- **THEN** the system returns a list of sessions ordered by `last_activity_at` descending, including plan counts, plan statuses, and title summaries.

#### Scenario: Soft archive a conversation
- **WHEN** a user requests `POST /api/v1/farming-chat/sessions/{sessionId}/archive`
- **THEN** the session `is_archived` is set to TRUE without deleting messages or linked implementation plans.

### Requirement: System SHALL enforce implementation plan lifecycle states and audit trails
Implementation plans SHALL maintain an independent lifecycle status from the conversation: `NOT_STARTED`, `IN_PROGRESS`, `CONTINUED`, `COMPLETED`, `CANCELLED`, `FAILED`. Any transition SHALL be recorded in `plan_status_history` with actor username, timestamp, and explanation.

#### Scenario: Transition plan from IN_PROGRESS to CONTINUED
- **WHEN** an authorized user pauses an active plan with reason "Paused awaiting field drainage"
- **THEN** the plan lifecycle status updates to `CONTINUED`, an entry is recorded in `plan_status_history`, and the plan remains available for future resumption.

#### Scenario: Complete plan with verification evidence
- **WHEN** an authorized user marks a plan `COMPLETED` providing completion evidence
- **THEN** the system verifies that all prerequisite tasks are completed, saves the evidence, updates plan status to `COMPLETED`, and sets progress to 100%.

### Requirement: System SHALL manage task dependencies and prevent circular locks
Tasks within an implementation plan SHALL support dependencies on other tasks (`planting_task_dependencies`). Tasks with unfinished required dependencies SHALL be blocked from execution. The system SHALL reject circular dependencies.

#### Scenario: Prevent execution of blocked dependent task
- **WHEN** Task B depends on Task A (which is `PENDING`), and a user attempts to mark Task B as `COMPLETED`
- **THEN** the system rejects the transition with HTTP 400 and error message indicating Task A is a blocking prerequisite.

#### Scenario: Detect and reject circular task dependency
- **WHEN** a user or client attempts to add a dependency where Task A depends on Task B and Task B depends on Task A
- **THEN** the system detects the cycle and rejects the operation.

