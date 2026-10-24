"""
Pydantic / Dataclass schemas for Arva AI Decision Support Service.
Enforces strict typing, input sanitization, and structured outputs.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class UserQueryRequest:
    user_id: str
    query_text: str
    field_id: int = 1
    role: str = "FARMER"  # "OWNER", "FARMER", "AUDITOR"

    def validate_inputs(self) -> None:
        if not self.query_text or len(self.query_text.strip()) == 0:
            raise ValueError("Query text cannot be empty.")
        if len(self.query_text) > 500:
            raise ValueError("Query text exceeds maximum allowed length of 500 characters.")
        if self.field_id <= 0:
            raise ValueError("Invalid field_id.")

@dataclass
class NodeObservation:
    node_id: str
    zone_code: str
    water_level_cm: Optional[float]
    soil_moisture_percent: Optional[float]
    status: str
    is_stale: bool = False
    observation_note: str = ""

@dataclass
class ActionProposal:
    has_proposal: bool = False
    proposal_type: str = "NONE"  # "REFLOOD_PROPOSAL", "EXTEND_DRYING", "INSPECT_SENSOR", "NONE"
    target_zone: Optional[str] = None
    rationale: str = ""
    requires_confirmation: bool = True
    deterministic_state: str = "HOLD"

@dataclass
class AIAdvisorResponse:
    query_id: str
    timestamp: str
    summary_text: str
    node_observations: List[Dict[str, Any]]
    action_proposal: Dict[str, Any]
    agronomic_references: List[str]
    disclaimer: str = (
        "Advisory recommendation only. Physical irrigation actuation is subject to "
        "deterministic safety interlocks and authorized farmer confirmation."
    )
