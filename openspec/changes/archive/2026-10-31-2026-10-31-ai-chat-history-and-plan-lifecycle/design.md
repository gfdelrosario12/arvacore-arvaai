# Design: AI Chat History, Context Retrieval, and Implementation Plan Lifecycle Management

## Architecture Overview

The system spans three subprojects within the ArvaCore ecosystem:
1. **ArvaNet_Backend (Spring Boot + PostgreSQL)**:
   - Authoritative relational persistence for conversations (`chatbot_sessions`, `chatbot_messages`), implementation plans (`planting_plans`, `plan_conversation_links`, `plan_status_history`), tasks (`planting_tasks`), task dependencies (`planting_task_dependencies`), and execution evidence.
   - REST API endpoints for session history lookup, plan lifecycle transitions, task dependency manipulation, and contextual search.
2. **ArvaAI (FastAPI + LangChain Memory Store)**:
   - Historical context retrieval integrating previous plans and conversation memory.
   - Recognition of continued vs new plans, circular dependency validation, and contextual prompt injection.
3. **ArvaNet_Frontend (Flutter Web/Mobile)**:
   - UI with conversation history sidebar, implementation plan lifecycle overview, task dependency tree viewer, and state transition actions.

## Database Schema Extensions (Migration V26)

- `chatbot_sessions`:
  - `title VARCHAR(255)` - Human-readable or AI-generated conversation title
  - `is_archived BOOLEAN DEFAULT FALSE` - Soft archive flag
  - `last_activity_at TIMESTAMP WITH TIME ZONE` - Timestamp of latest message or plan action

- `planting_plans`:
  - `lifecycle_status VARCHAR(50) DEFAULT 'NOT_STARTED'` - `NOT_STARTED`, `IN_PROGRESS`, `CONTINUED`, `COMPLETED`, `CANCELLED`, `FAILED`
  - `title VARCHAR(255)` - Descriptive title of the plan
  - `description TEXT` - Detailed implementation plan scope
  - `objectives_json TEXT` - Plan objectives
  - `progress_percent INTEGER DEFAULT 0` - 0-100% computed progress
  - `status_reason TEXT` - Explanation for current status (e.g., failure or cancellation reason)
  - `completion_evidence TEXT` - Formal evidence verifying completion

- `plan_conversation_links`:
  - `id BIGSERIAL PRIMARY KEY`
  - `plan_id BIGINT REFERENCES planting_plans(id) ON DELETE CASCADE`
  - `session_id VARCHAR(64) REFERENCES chatbot_sessions(session_id) ON DELETE CASCADE`
  - `linked_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`
  - `link_type VARCHAR(50) DEFAULT 'ASSOCIATED'` (CREATED, REFERENCED, RESUMED)
  - `UNIQUE(plan_id, session_id)`

- `plan_status_history`:
  - `id BIGSERIAL PRIMARY KEY`
  - `plan_id BIGINT REFERENCES planting_plans(id) ON DELETE CASCADE`
  - `from_status VARCHAR(50)`
  - `to_status VARCHAR(50) NOT NULL`
  - `changed_by VARCHAR(100) NOT NULL`
  - `reason TEXT`
  - `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`

- `planting_task_dependencies`:
  - `id BIGSERIAL PRIMARY KEY`
  - `task_id BIGINT REFERENCES planting_tasks(id) ON DELETE CASCADE`
  - `depends_on_task_id BIGINT REFERENCES planting_tasks(id) ON DELETE CASCADE`
  - `dependency_type VARCHAR(50) DEFAULT 'REQUIRED'`
  - `created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP`
  - `UNIQUE(task_id, depends_on_task_id)`

## Dependency Management & Progress Computation
- A task can only transition to `IN_PROGRESS` or `COMPLETED` if all `REQUIRED` dependencies have status `COMPLETED`.
- Circular dependency checks prevent `A -> B -> A` loops.
- `progress_percent` is dynamically calculated: `(completed_tasks / total_tasks) * 100`.
- Changing task statuses recalculates plan progress and flags blocked tasks.
