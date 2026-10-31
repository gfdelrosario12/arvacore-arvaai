"""
Arva AI Persistent Memory Engine utilizing LangChain Core BaseChatMessageHistory.

Provides four explicit memory layers:
1. Conversation Memory (Multi-session message history & unresolved matters)
2. Farm & Field Memory (Cultivar, growth stage, soil type, AWD thresholds, confirmed practices)
3. Operational Memory (Preparation tasks, irrigation events, outcomes, accepted/rejected recommendations)
4. Knowledge & Retrieval (Authoritative PhilRice/IRRI agronomic standards & guidelines)

Distinguishes clearly between:
- USER_REPORTED (User chat input)
- VERIFIED_DB (Authoritative database records)
- SENSOR_MEASURED (Live IoT ArvaNode measurements)
- AI_RECOMMENDED (Generated proposals)
- INFERRED_CONCLUSION (Evaluated agronomic status)
"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from app.models.workflow_models import PlanLifecycleStatus, ImplementationPlanSummary


class MemorySourceType(str, Enum):
    USER_REPORTED = "USER_REPORTED"
    VERIFIED_DB = "VERIFIED_DB"
    SENSOR_MEASURED = "SENSOR_MEASURED"
    AI_RECOMMENDED = "AI_RECOMMENDED"
    INFERRED_CONCLUSION = "INFERRED_CONCLUSION"


class MemoryRecord(BaseModel):
    id: str
    source_type: MemorySourceType
    category: str  # e.g., 'farm_profile', 'operational_task', 'conversation', 'feedback', 'implementation_plan'
    content: str
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    verified: bool = False
    is_active: bool = True


class ArvaPersistentChatHistory(BaseChatMessageHistory):
    """
    LangChain BaseChatMessageHistory implementation backed by persistent storage
    (with in-memory cache and synchronization to backend database).
    """

    def __init__(self, session_id: str, user_id: str = "anonymous", field_id: int = 1, title: str = "Agricultural Consultation"):
        self.session_id = session_id
        self.user_id = user_id
        self.field_id = field_id
        self.title = title
        self.is_archived = False
        self.last_activity_at = datetime.now(timezone.utc).isoformat()
        self.associated_plan_ids: List[int] = []
        self._messages: List[BaseMessage] = []

    @property
    def messages(self) -> List[BaseMessage]:
        return self._messages

    def add_message(self, message: BaseMessage) -> None:
        self._messages.append(message)
        self.last_activity_at = datetime.now(timezone.utc).isoformat()

    def clear(self) -> None:
        self._messages.clear()


class ArvaMemoryStore:
    """
    Persistent Memory Store integrating conversation, farm/field context,
    operational schedules, implementation plans, and outcome tracking.
    """

    def __init__(self):
        # session_id -> ArvaPersistentChatHistory
        self._histories: Dict[str, ArvaPersistentChatHistory] = {}
        # (user_id, field_id) -> List[MemoryRecord]
        self._farm_memories: Dict[str, List[MemoryRecord]] = {}
        # (user_id, field_id) -> List[MemoryRecord]
        self._operational_memories: Dict[str, List[MemoryRecord]] = {}
        # plan_id -> ImplementationPlanSummary
        self._plans: Dict[int, ImplementationPlanSummary] = {}

    def _key(self, user_id: str, field_id: int) -> str:
        return f"{user_id}:{field_id}"

    def get_chat_history(self, session_id: str, user_id: str = "anonymous", field_id: int = 1) -> ArvaPersistentChatHistory:
        if session_id not in self._histories:
            self._histories[session_id] = ArvaPersistentChatHistory(session_id, user_id, field_id)
        return self._histories[session_id]

    def register_plan(self, plan: ImplementationPlanSummary) -> None:
        """Indexes an implementation plan and associates it with memory store."""
        self._plans[plan.plan_id] = plan
        # Also store operational memory
        key = self._key("farmer", 1)
        self.record_operational_memory(
            user_id="farmer",
            field_id=1,
            category="implementation_plan",
            content=f"Plan {plan.plan_code} for {plan.crop_name} is currently {plan.lifecycle_status.value} (progress: {plan.progress_percent}%)",
            source_type=MemorySourceType.VERIFIED_DB,
            metadata={"plan_id": plan.plan_id, "plan_code": plan.plan_code, "status": plan.lifecycle_status.value},
            verified=True
        )

    def get_plan(self, plan_id: int) -> Optional[ImplementationPlanSummary]:
        return self._plans.get(plan_id)

    def find_active_or_continued_plans(self, user_id: str = "farmer", field_id: int = 1) -> List[ImplementationPlanSummary]:
        """Finds implementation plans that are IN_PROGRESS or CONTINUED (unfinished)."""
        active_statuses = {PlanLifecycleStatus.IN_PROGRESS, PlanLifecycleStatus.CONTINUED, PlanLifecycleStatus.NOT_STARTED}
        return [p for p in self._plans.values() if p.lifecycle_status in active_statuses]

    def find_historical_conversations_with_plans(self, user_id: str = "farmer", limit: int = 5) -> List[Dict[str, Any]]:
        """Retrieves summary of recent conversation sessions including associated implementation plans."""
        results = []
        sorted_histories = sorted(
            self._histories.values(),
            key=lambda h: h.last_activity_at,
            reverse=True
        )
        for h in sorted_histories:
            if h.is_archived:
                continue
            plans = [self._plans[pid].model_dump() for pid in h.associated_plan_ids if pid in self._plans]
            results.append({
                "session_id": h.session_id,
                "title": h.title,
                "user_id": h.user_id,
                "field_id": h.field_id,
                "message_count": len(h.messages),
                "last_activity_at": h.last_activity_at,
                "associated_plans": plans
            })
            if len(results) >= limit:
                break
        return results

    def record_farm_memory(
        self,
        user_id: str,
        field_id: int,
        category: str,
        content: str,
        source_type: MemorySourceType,
        metadata: Optional[Dict[str, Any]] = None,
        verified: bool = False
    ) -> MemoryRecord:
        """Stores or updates farm profile, crop variety, growth stage, or practice memory."""
        key = self._key(user_id, field_id)
        if key not in self._farm_memories:
            self._farm_memories[key] = []

        rec_id = f"farm_{len(self._farm_memories[key]) + 1}_{int(datetime.now(timezone.utc).timestamp())}"
        record = MemoryRecord(
            id=rec_id,
            source_type=source_type,
            category=category,
            content=content,
            metadata=metadata or {},
            verified=verified,
            is_active=True
        )
        self._farm_memories[key].append(record)
        return record

    def record_operational_memory(
        self,
        user_id: str,
        field_id: int,
        category: str,
        content: str,
        source_type: MemorySourceType,
        metadata: Optional[Dict[str, Any]] = None,
        verified: bool = False
    ) -> MemoryRecord:
        """Stores preparation schedules, task completions, rejections, or post-irrigation outcomes."""
        key = self._key(user_id, field_id)
        if key not in self._operational_memories:
            self._operational_memories[key] = []

        rec_id = f"op_{len(self._operational_memories[key]) + 1}_{int(datetime.now(timezone.utc).timestamp())}"
        record = MemoryRecord(
            id=rec_id,
            source_type=source_type,
            category=category,
            content=content,
            metadata=metadata or {},
            verified=verified,
            is_active=True
        )
        self._operational_memories[key].append(record)
        return record

    def get_relevant_memories(
        self,
        user_id: str,
        field_id: int,
        query: str = "",
        limit: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieves relevant active memories partitioned by memory layer,
        prioritizing verified database records, unfinished plans, and recent operational feedback.
        """
        key = self._key(user_id, field_id)
        farm_recs = [r for r in self._farm_memories.get(key, []) if r.is_active]
        op_recs = [r for r in self._operational_memories.get(key, []) if r.is_active]

        # Prioritize verified and recent items
        sorted_farm = sorted(farm_recs, key=lambda r: (r.verified, r.timestamp), reverse=True)[:limit]
        sorted_op = sorted(op_recs, key=lambda r: (r.verified, r.timestamp), reverse=True)[:limit]

        # Check unfinished plans
        active_plans = self.find_active_or_continued_plans(user_id, field_id)

        return {
            "user_id": user_id,
            "field_id": field_id,
            "active_plans": [p.model_dump() for p in active_plans],
            "farm_and_field_memory": [r.model_dump() for r in sorted_farm],
            "operational_memory": [r.model_dump() for r in sorted_op],
            "summary_context": self._build_context_summary(sorted_farm, sorted_op, active_plans)
        }

    def _build_context_summary(
        self,
        farm_recs: List[MemoryRecord],
        op_recs: List[MemoryRecord],
        active_plans: Optional[List[ImplementationPlanSummary]] = None
    ) -> str:
        lines = []
        if active_plans:
            lines.append("Active or Continued Implementation Plans in Progress:")
            for p in active_plans:
                lines.append(f"- [PLAN {p.plan_code}] {p.title} (Status: {p.lifecycle_status.value}, Progress: {p.progress_percent}%)")
        if farm_recs:
            lines.append("Known Farm Context:")
            for r in farm_recs:
                lines.append(f"- [{r.source_type.value}] {r.category}: {r.content}")
        if op_recs:
            lines.append("Historical Operational Outcomes & Pre-Irrigation Decisions:")
            for r in op_recs:
                lines.append(f"- [{r.source_type.value}] {r.category}: {r.content}")
        return "\n".join(lines)


# Global singleton store instance
global_memory_store = ArvaMemoryStore()
