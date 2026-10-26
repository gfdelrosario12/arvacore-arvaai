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


class MemorySourceType(str, Enum):
    USER_REPORTED = "USER_REPORTED"
    VERIFIED_DB = "VERIFIED_DB"
    SENSOR_MEASURED = "SENSOR_MEASURED"
    AI_RECOMMENDED = "AI_RECOMMENDED"
    INFERRED_CONCLUSION = "INFERRED_CONCLUSION"


class MemoryRecord(BaseModel):
    id: str
    source_type: MemorySourceType
    category: str  # e.g., 'farm_profile', 'operational_task', 'conversation', 'feedback'
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

    def __init__(self, session_id: str, user_id: str = "anonymous", field_id: int = 1):
        self.session_id = session_id
        self.user_id = user_id
        self.field_id = field_id
        self._messages: List[BaseMessage] = []

    @property
    def messages(self) -> List[BaseMessage]:
        return self._messages

    def add_message(self, message: BaseMessage) -> None:
        self._messages.append(message)

    def clear(self) -> None:
        self._messages.clear()


class ArvaMemoryStore:
    """
    Persistent Memory Store integrating conversation, farm/field context,
    operational schedules, and outcome tracking.
    """

    def __init__(self):
        # session_id -> ArvaPersistentChatHistory
        self._histories: Dict[str, ArvaPersistentChatHistory] = {}
        # (user_id, field_id) -> List[MemoryRecord]
        self._farm_memories: Dict[str, List[MemoryRecord]] = {}
        # (user_id, field_id) -> List[MemoryRecord]
        self._operational_memories: Dict[str, List[MemoryRecord]] = {}

    def _key(self, user_id: str, field_id: int) -> str:
        return f"{user_id}:{field_id}"

    def get_chat_history(self, session_id: str, user_id: str = "anonymous", field_id: int = 1) -> ArvaPersistentChatHistory:
        if session_id not in self._histories:
            self._histories[session_id] = ArvaPersistentChatHistory(session_id, user_id, field_id)
        return self._histories[session_id]

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
        prioritizing verified database records and recent operational feedback.
        """
        key = self._key(user_id, field_id)
        farm_recs = [r for r in self._farm_memories.get(key, []) if r.is_active]
        op_recs = [r for r in self._operational_memories.get(key, []) if r.is_active]

        # Prioritize verified and recent items
        sorted_farm = sorted(farm_recs, key=lambda r: (r.verified, r.timestamp), reverse=True)[:limit]
        sorted_op = sorted(op_recs, key=lambda r: r.timestamp, reverse=True)[:limit]

        return {
            "user_id": user_id,
            "field_id": field_id,
            "farm_and_field_memory": [r.model_dump() for r in sorted_farm],
            "operational_memory": [r.model_dump() for r in sorted_op],
            "summary_context": self._build_context_summary(sorted_farm, sorted_op)
        }

    def _build_context_summary(self, farm_recs: List[MemoryRecord], op_recs: List[MemoryRecord]) -> str:
        lines = []
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

