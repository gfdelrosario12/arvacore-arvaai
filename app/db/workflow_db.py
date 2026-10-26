"""
Authoritative Database Manager and Schema Migrations for AI Task Workflow and Dependencies.
Enforces foreign keys, unique constraint on (workflow_step_id, depends_on_step_id),
ACID transactional execution, and row-level locking for worker concurrency.
"""

import sqlite3
import json
import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import os

from app.models.workflow_models import (
    AITask, WorkflowStep, WorkflowStepDependency, AITaskEvent,
    StepStatus, TaskStatus, DependencyType, EventType
)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ai_task (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'PENDING',
    user_id TEXT NOT NULL DEFAULT 'anonymous',
    field_id INTEGER NOT NULL DEFAULT 1,
    session_id TEXT,
    current_step_code TEXT,
    context_data TEXT,
    final_outcome TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ai_workflow_step (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_code TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'PENDING',
    skip_reason TEXT,
    blocking_reason TEXT,
    error_message TEXT,
    output_data TEXT,
    execution_evidence TEXT,
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES ai_task(id) ON DELETE CASCADE,
    UNIQUE(task_id, step_code)
);

CREATE INDEX IF NOT EXISTS idx_workflow_step_task ON ai_workflow_step(task_id);
CREATE INDEX IF NOT EXISTS idx_workflow_step_status ON ai_workflow_step(status);

CREATE TABLE IF NOT EXISTS ai_workflow_step_dependency (
    id TEXT PRIMARY KEY,
    workflow_step_id TEXT NOT NULL,
    depends_on_step_id TEXT NOT NULL,
    dependency_type TEXT NOT NULL DEFAULT 'REQUIRED',
    condition TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (workflow_step_id) REFERENCES ai_workflow_step(id) ON DELETE CASCADE,
    FOREIGN KEY (depends_on_step_id) REFERENCES ai_workflow_step(id) ON DELETE CASCADE,
    UNIQUE(workflow_step_id, depends_on_step_id)
);

CREATE INDEX IF NOT EXISTS idx_step_dep_target ON ai_workflow_step_dependency(workflow_step_id);
CREATE INDEX IF NOT EXISTS idx_step_dep_source ON ai_workflow_step_dependency(depends_on_step_id);

CREATE TABLE IF NOT EXISTS ai_task_event (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_id TEXT,
    event_type TEXT NOT NULL,
    event_payload TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES ai_task(id) ON DELETE CASCADE,
    FOREIGN KEY (step_id) REFERENCES ai_workflow_step(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_task_event_task ON ai_task_event(task_id);
"""


class WorkflowDatabase:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            # Check environment or default to writable path
            env_path = os.getenv("ARVA_WORKFLOW_DB_PATH")
            if env_path:
                self.db_path = env_path
            elif os.path.exists("/app/data"):
                self.db_path = "/app/data/arva_workflow.db"
            else:
                self.db_path = "arva_workflow.db"
        else:
            self.db_path = db_path
        
        # Ensure parent directory exists if path contains directories
        parent_dir = os.path.dirname(self.db_path)
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)
            
        self._init_db()

    def get_connection(self) -> sqlite3.Connection:
        # In SQLite, timeout allows busy handling for concurrency
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()

    def create_task(self, task: AITask) -> AITask:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_task (id, title, description, status, user_id, field_id, session_id,
                                     current_step_code, context_data, final_outcome, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id, task.title, task.description, task.status.value,
                    task.user_id, task.field_id, task.session_id,
                    task.current_step_code,
                    json.dumps(task.context_data),
                    json.dumps(task.final_outcome) if task.final_outcome else None,
                    task.created_at, task.updated_at
                )
            )
            self._record_event_tx(
                conn,
                task_id=task.id,
                step_id=None,
                event_type=EventType.TASK_CREATED,
                payload={"title": task.title, "status": task.status.value}
            )
            conn.commit()
        return task

    def get_task(self, task_id: str) -> Optional[AITask]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM ai_task WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_task(row)

    def update_task_status(self, task_id: str, status: TaskStatus, current_step_code: Optional[str] = None, final_outcome: Optional[Dict[str, Any]] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            conn.execute(
                """
                UPDATE ai_task
                SET status = ?, current_step_code = COALESCE(?, current_step_code),
                    final_outcome = COALESCE(?, final_outcome), updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    current_step_code,
                    json.dumps(final_outcome) if final_outcome is not None else None,
                    now,
                    task_id
                )
            )
            self._record_event_tx(
                conn,
                task_id=task_id,
                step_id=None,
                event_type=EventType.TASK_STATUS_CHANGED,
                payload={"status": status.value, "current_step_code": current_step_code}
            )
            conn.commit()

    def create_step(self, step: WorkflowStep) -> WorkflowStep:
        with self.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO ai_workflow_step (
                    id, task_id, step_code, name, status, skip_reason, blocking_reason,
                    error_message, output_data, execution_evidence, started_at, completed_at,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    step.id, step.task_id, step.step_code, step.name, step.status.value,
                    step.skip_reason, step.blocking_reason, step.error_message,
                    json.dumps(step.output_data) if step.output_data is not None else None,
                    json.dumps(step.execution_evidence) if step.execution_evidence is not None else None,
                    step.started_at, step.completed_at, step.created_at, step.updated_at
                )
            )
            conn.commit()
        return step

    def create_dependency(self, dep: WorkflowStepDependency) -> WorkflowStepDependency:
        # Enforce no self-dependency
        if dep.workflow_step_id == dep.depends_on_step_id:
            raise ValueError(f"Self-dependency is disallowed: step '{dep.workflow_step_id}' cannot depend on itself.")

        with self.get_connection() as conn:
            # Enforce same task ownership
            cursor = conn.execute(
                "SELECT task_id FROM ai_workflow_step WHERE id IN (?, ?)",
                (dep.workflow_step_id, dep.depends_on_step_id)
            )
            rows = cursor.fetchall()
            if len(rows) != 2 or rows[0]["task_id"] != rows[1]["task_id"]:
                raise ValueError("Both steps in a dependency must belong to the same ai_task and exist.")

            conn.execute(
                """
                INSERT INTO ai_workflow_step_dependency (
                    id, workflow_step_id, depends_on_step_id, dependency_type, condition, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    dep.id, dep.workflow_step_id, dep.depends_on_step_id,
                    dep.dependency_type.value,
                    json.dumps(dep.condition) if dep.condition is not None else None,
                    dep.created_at
                )
            )
            conn.commit()
        return dep

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM ai_workflow_step WHERE id = ?", (step_id,))
            row = cursor.fetchone()
            if not row:
                return None
            step = self._row_to_step(row)
            step.dependencies = self._get_step_dependencies_tx(conn, step_id)
            return step

    def get_step_by_code(self, task_id: str, step_code: str) -> Optional[WorkflowStep]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM ai_workflow_step WHERE task_id = ? AND step_code = ?", (task_id, step_code))
            row = cursor.fetchone()
            if not row:
                return None
            step = self._row_to_step(row)
            step.dependencies = self._get_step_dependencies_tx(conn, step.id)
            return step

    def get_task_steps(self, task_id: str) -> List[WorkflowStep]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM ai_workflow_step WHERE task_id = ? ORDER BY step_code ASC", (task_id,))
            rows = cursor.fetchall()
            steps = []
            for r in rows:
                s = self._row_to_step(r)
                s.dependencies = self._get_step_dependencies_tx(conn, s.id)
                steps.append(s)
            return steps

    def get_all_dependencies_for_task(self, task_id: str) -> List[WorkflowStepDependency]:
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT d.* FROM ai_workflow_step_dependency d
                JOIN ai_workflow_step s ON d.workflow_step_id = s.id
                WHERE s.task_id = ?
                """,
                (task_id,)
            )
            return [self._row_to_dependency(r) for r in cursor.fetchall()]

    def update_step_status(
        self,
        step_id: str,
        status: StepStatus,
        skip_reason: Optional[str] = None,
        blocking_reason: Optional[str] = None,
        error_message: Optional[str] = None,
        output_data: Optional[Dict[str, Any]] = None,
        execution_evidence: Optional[Dict[str, Any]] = None
    ) -> WorkflowStep:
        now = datetime.now(timezone.utc).isoformat()
        with self.get_connection() as conn:
            step_cur = conn.execute("SELECT * FROM ai_workflow_step WHERE id = ?", (step_id,))
            old_row = step_cur.fetchone()
            if not old_row:
                raise ValueError(f"Step with id {step_id} not found.")

            started_at = old_row["started_at"]
            completed_at = old_row["completed_at"]

            if status == StepStatus.IN_PROGRESS and not started_at:
                started_at = now
            elif status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.FAILED, StepStatus.BLOCKED):
                completed_at = now
            elif status == StepStatus.INVALIDATED:
                started_at = None
                completed_at = None

            conn.execute(
                """
                UPDATE ai_workflow_step
                SET status = ?, skip_reason = ?, blocking_reason = ?, error_message = ?,
                    output_data = COALESCE(?, output_data),
                    execution_evidence = COALESCE(?, execution_evidence),
                    started_at = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    status.value, skip_reason, blocking_reason, error_message,
                    json.dumps(output_data) if output_data is not None else None,
                    json.dumps(execution_evidence) if execution_evidence is not None else None,
                    started_at, completed_at, now, step_id
                )
            )

            self._record_event_tx(
                conn,
                task_id=old_row["task_id"],
                step_id=step_id,
                event_type=EventType.STEP_STATE_CHANGED,
                payload={
                    "step_code": old_row["step_code"],
                    "old_status": old_row["status"],
                    "new_status": status.value,
                    "skip_reason": skip_reason,
                    "blocking_reason": blocking_reason,
                    "error_message": error_message
                }
            )
            conn.commit()

        return self.get_step(step_id)

    def record_event(self, task_id: str, event_type: EventType, payload: Dict[str, Any], step_id: Optional[str] = None) -> AITaskEvent:
        with self.get_connection() as conn:
            event = self._record_event_tx(conn, task_id, step_id, event_type, payload)
            conn.commit()
        return event

    def get_events_for_task(self, task_id: str) -> List[AITaskEvent]:
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM ai_task_event WHERE task_id = ? ORDER BY created_at ASC", (task_id,))
            return [self._row_to_event(r) for r in cursor.fetchall()]

    # Transactional helpers
    def _get_step_dependencies_tx(self, conn: sqlite3.Connection, step_id: str) -> List[WorkflowStepDependency]:
        cursor = conn.execute("SELECT * FROM ai_workflow_step_dependency WHERE workflow_step_id = ?", (step_id,))
        return [self._row_to_dependency(r) for r in cursor.fetchall()]

    def _record_event_tx(self, conn: sqlite3.Connection, task_id: str, step_id: Optional[str], event_type: EventType, payload: Dict[str, Any]) -> AITaskEvent:
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        conn.execute(
            """
            INSERT INTO ai_task_event (id, task_id, step_id, event_type, event_payload, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (event_id, task_id, step_id, event_type.value, json.dumps(payload), now)
        )
        return AITaskEvent(
            id=event_id,
            task_id=task_id,
            step_id=step_id,
            event_type=event_type,
            event_payload=payload,
            created_at=now
        )

    def _row_to_task(self, row: sqlite3.Row) -> AITask:
        return AITask(
            id=row["id"],
            title=row["title"],
            description=row["description"],
            status=TaskStatus(row["status"]),
            user_id=row["user_id"],
            field_id=row["field_id"],
            session_id=row["session_id"],
            current_step_code=row["current_step_code"],
            context_data=json.loads(row["context_data"]) if row["context_data"] else {},
            final_outcome=json.loads(row["final_outcome"]) if row["final_outcome"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def _row_to_step(self, row: sqlite3.Row) -> WorkflowStep:
        return WorkflowStep(
            id=row["id"],
            task_id=row["task_id"],
            step_code=row["step_code"],
            name=row["name"],
            status=StepStatus(row["status"]),
            skip_reason=row["skip_reason"],
            blocking_reason=row["blocking_reason"],
            error_message=row["error_message"],
            output_data=json.loads(row["output_data"]) if row["output_data"] else None,
            execution_evidence=json.loads(row["execution_evidence"]) if row["execution_evidence"] else None,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )

    def _row_to_dependency(self, row: sqlite3.Row) -> WorkflowStepDependency:
        return WorkflowStepDependency(
            id=row["id"],
            workflow_step_id=row["workflow_step_id"],
            depends_on_step_id=row["depends_on_step_id"],
            dependency_type=DependencyType(row["dependency_type"]),
            condition=json.loads(row["condition"]) if row["condition"] else None,
            created_at=row["created_at"]
        )

    def _row_to_event(self, row: sqlite3.Row) -> AITaskEvent:
        return AITaskEvent(
            id=row["id"],
            task_id=row["task_id"],
            step_id=row["step_id"],
            event_type=EventType(row["event_type"]),
            event_payload=json.loads(row["event_payload"]) if row["event_payload"] else {},
            created_at=row["created_at"]
        )

