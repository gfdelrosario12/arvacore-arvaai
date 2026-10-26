"""
Data models and Schema Definitions for Arva AI Workflow Steps and Dependencies.
Enforces foreign keys, unique dependency pairs, valid task ownership,
and dependency relationships (REQUIRED vs CONDITIONAL).
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    PENDING = "PENDING"
    ELIGIBLE = "ELIGIBLE"
    WAITING = "WAITING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    SKIPPED = "SKIPPED"
    INVALIDATED = "INVALIDATED"


class DependencyType(str, Enum):
    REQUIRED = "REQUIRED"
    CONDITIONAL = "CONDITIONAL"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_DECISION = "WAITING_FOR_DECISION"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    PARTIAL = "PARTIAL"


class EventType(str, Enum):
    TASK_CREATED = "TASK_CREATED"
    STEP_STATE_CHANGED = "STEP_STATE_CHANGED"
    DEPENDENCY_EVALUATED = "DEPENDENCY_EVALUATED"
    DOWNSTREAM_INVALIDATED = "DOWNSTREAM_INVALIDATED"
    DECISION_RECORDED = "DECISION_RECORDED"
    REMEDIATION_TRIGGERED = "REMEDIATION_TRIGGERED"
    TASK_STATUS_CHANGED = "TASK_STATUS_CHANGED"


class WorkflowStepDependency(BaseModel):
    id: str
    workflow_step_id: str
    depends_on_step_id: str
    dependency_type: DependencyType = DependencyType.REQUIRED
    condition: Optional[Dict[str, Any]] = None  # Structured condition for conditional dependencies
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class WorkflowStep(BaseModel):
    id: str
    task_id: str
    step_code: str  # S01..S13
    name: str
    status: StepStatus = StepStatus.PENDING
    skip_reason: Optional[str] = None
    blocking_reason: Optional[str] = None
    error_message: Optional[str] = None
    output_data: Optional[Dict[str, Any]] = None
    execution_evidence: Optional[Dict[str, Any]] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    dependencies: List[WorkflowStepDependency] = Field(default_factory=list)


class AITask(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    user_id: str = "anonymous"
    field_id: int = 1
    session_id: Optional[str] = None
    current_step_code: Optional[str] = None
    context_data: Dict[str, Any] = Field(default_factory=dict)
    final_outcome: Optional[Dict[str, Any]] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class AITaskEvent(BaseModel):
    id: str
    task_id: str
    step_id: Optional[str] = None
    event_type: EventType
    event_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

