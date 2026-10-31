# Proposal: AI Chat History, Context Retrieval, and Implementation Plan Lifecycle Management

## Problem Statement
The current AI agricultural chat interface within ArvaCore provides interactive consultations and planting readiness recommendations, but lacks comprehensive historical conversation continuity, multi-session plan state tracking, cross-plan dependency resolution, and rich frontend management controls. When users start new sessions, they lose access to prior discussions, unfinished implementation plans, and execution evidence. Furthermore, implementation plans do not have formal lifecycle states (`NOT_STARTED`, `IN_PROGRESS`, `CONTINUED`, `COMPLETED`, `CANCELLED`, `FAILED`) separate from conversational status, and task dependencies cannot be systematically tracked, updated, and validated against circular locks.

## Proposed Changes
1. **Persistent Conversation History & Context Retrieval**:
   - Enhance `ChatbotSession` with title, archived status, plan associations, and activity timestamps.
   - Implement backend search and retrieval APIs to look up historical conversations by user, field, keyword, and implementation plan status without loading entire conversation logs indiscriminately.
   - Extend ArvaAI microservice to integrate relevant conversation history and unfinished implementation plan state into context generation.

2. **Implementation Plan Lifecycle Management**:
   - Establish formal lifecycle statuses for implementation plans: `NOT_STARTED`, `IN_PROGRESS`, `CONTINUED`, `COMPLETED`, `CANCELLED`, `FAILED`.
   - Implement audit-trailed status transitions, capturing timestamps, explanations, cancellation/failure reasons, and completion evidence.
   - Support N:M mapping between conversations and implementation plans (a conversation can reference or create multiple plans; a plan can be resumed across multiple conversations).

3. **Task & Dependency Management**:
   - Introduce explicit task dependencies, cycle detection, blocking indicators, and progress recalculation.
   - Support task statuses: `PENDING`, `IN_PROGRESS`, `COMPLETED`, `BLOCKED`, `CANCELLED`.
   - Prevent dependent tasks from prematurely executing before prerequisites are satisfied.

4. **Frontend Interface Modernization**:
   - Provide a persistent conversation history drawer/panel showing titles, plan badges, timestamps, and active/archived state.
   - Provide an Implementation Plan Overview and Task Management drawer/view displaying progress, dependencies, blocked indicators, and lifecycle controls (`Resume`, `Pause/Continue`, `Complete`, `Cancel`, `Inspect`).

## Non-Goals
- Introducing external vector databases or heavyweight document stores. Existing PostgreSQL relational indexing and ArvaAI SQLite/in-memory memory stores are sufficient.
- Altering core edge firmware or physical pump actuation mechanics.
