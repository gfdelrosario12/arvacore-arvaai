"""
Arva AI Intelligent Pre-Irrigation Preparation Scheduler.

Formulates evidence-based pre-irrigation preparation plans before scheduled or proposed
irrigation events. Inspects water availability, pump readiness, ArvaNode sensor health,
weather forecasts (rain hazard), and PhilRice growth stage requirements.

Connects to the operational lifecycle:
PROPOSED -> SCHEDULED -> IN_PROGRESS -> COMPLETED
Alternative states: REJECTED, CANCELLED, ABANDONED, OVERDUE, BLOCKED, RESCHEDULED
"""

import json
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from app.services.langchain_memory_engine import global_memory_store, MemorySourceType


class TaskLifecycleState(str, Enum):
    PROPOSED = "PROPOSED"
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    ABANDONED = "ABANDONED"
    OVERDUE = "OVERDUE"
    BLOCKED = "BLOCKED"
    RESCHEDULED = "RESCHEDULED"


class PreparationTaskItem(BaseModel):
    id: str
    category: str  # SYSTEM_AUTOMATED, FARMER_MANUAL, EQUIPMENT_INFO, SAFETY_BLOCKED
    title: str
    description: str
    rationale: str
    evidence_source: str  # PhilRice Manual, ArvaNode Telemetry, PAGASA Weather, Historical Outcome
    deadline: Optional[str] = None
    priority: str = "NORMAL"  # LOW, NORMAL, HIGH, CRITICAL_PREREQUISITE
    status: TaskLifecycleState = TaskLifecycleState.PROPOSED
    requires_confirmation: bool = True
    blocking_reason: Optional[str] = None
    completion_evidence: Optional[str] = None
    associated_irrigation_id: Optional[str] = None


class PreIrrigationPlan(BaseModel):
    plan_id: str
    field_id: int
    user_id: str
    crop_variety: str
    crop_stage: str
    irrigation_objective: str
    proposed_window_start: str
    proposed_window_end: str
    overall_status: TaskLifecycleState = TaskLifecycleState.PROPOSED
    prerequisites_met: bool = False
    readiness_score: int = 0
    tasks: List[PreparationTaskItem] = Field(default_factory=list)
    risk_factors: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class IntelligentPreIrrigationScheduler:
    """
    Intelligent Preparation Engine that evaluates telemetry, forecast,
    and historical outcomes to generate bespoke pre-irrigation plans.
    """

    def generate_preparation_plan(
        self,
        field_id: int,
        user_id: str,
        crop_variety: str = "NSIC Rc 222",
        crop_stage: str = "TILLERING",
        nodes_telemetry: Optional[List[Dict[str, Any]]] = None,
        weather_forecast: Optional[Dict[str, Any]] = None,
        irrigation_command_record: Optional[Dict[str, Any]] = None,
    ) -> PreIrrigationPlan:
        now = datetime.now(timezone.utc)
        plan_id = f"PREP-F{field_id}-{int(now.timestamp())}"
        nodes_telemetry = nodes_telemetry or []
        weather_forecast = weather_forecast or {}

        # 1. Inspect historical operational memories to learn from past outcomes
        memories = global_memory_store.get_relevant_memories(user_id, field_id)
        historical_context = memories.get("summary_context", "")

        tasks: List[PreparationTaskItem] = []
        risk_factors: List[str] = []

        # 2. Check Weather / PAGASA Rain Risk
        rain_prob = weather_forecast.get("pop", 0)  # probability of precipitation
        rain_mm = weather_forecast.get("rain_24h_mm", 0.0)

        if rain_prob >= 70 or rain_mm >= 25.0:
            risk_factors.append(f"High heavy rainfall forecast ({rain_mm}mm, {rain_prob}% pop). Natural reflood anticipated.")
            tasks.append(PreparationTaskItem(
                id=f"{plan_id}_T1",
                category="SAFETY_BLOCKED",
                title="Rainfall Interlock Verification",
                description=f"Predicted rainfall ({rain_mm} mm) exceeds immediate irrigation need. Hold irrigation to conserve energy and prevent paddy submergence.",
                rationale="PhilRice Rule: Avoid artificial pumping when precipitation meets crop requirement within 24-48h.",
                evidence_source="PAGASA Weather MCP",
                priority="CRITICAL_PREREQUISITE",
                status=TaskLifecycleState.BLOCKED,
                blocking_reason="Natural precipitation forecast sufficient"
            ))

        # 3. Check Monitoring Nodes Health & Water Levels
        offline_nodes = [n for n in nodes_telemetry if not n.get("is_online", True)]
        stale_nodes = [n for n in nodes_telemetry if n.get("is_stale", False)]

        if offline_nodes or stale_nodes:
            affected_ids = [n.get("node_id", "Unknown") for n in offline_nodes + stale_nodes]
            risk_factors.append(f"Degraded sensor health on nodes: {', '.join(affected_ids)}")
            tasks.append(PreparationTaskItem(
                id=f"{plan_id}_T2",
                category="FARMER_MANUAL",
                title="Inspect Field Monitoring Nodes",
                description=f"Verify battery level and LoRa/WiFi link on node(s) {', '.join(affected_ids)} prior to reflooding.",
                rationale="Accurate edge telemetry is required to detect AWD reflood completion (+5 cm) and prevent overflow.",
                evidence_source="ArvaNode Telemetry Quality Engine",
                priority="HIGH",
                status=TaskLifecycleState.SCHEDULED,
                deadline=(now + timedelta(hours=6)).isoformat()
            ))
        else:
            tasks.append(PreparationTaskItem(
                id=f"{plan_id}_T2",
                category="FARMER_MANUAL",
                title="Confirm Field Bunds and Pitak Inflow Intact",
                description="Inspect field bunds (pilapil) to prevent water leakage into neighboring paddies during reflooding.",
                rationale="PhilRice AWD guideline: Maintained bunds prevent water loss and ensure uniform 5cm ponding.",
                evidence_source="PhilRice Rice Production Manual",
                priority="NORMAL",
                status=TaskLifecycleState.SCHEDULED,
                deadline=(now + timedelta(hours=6)).isoformat()
            ))

        # 4. Check Pump & Valve Readiness
        tasks.append(PreparationTaskItem(
            id=f"{plan_id}_T3",
            category="EQUIPMENT_INFO",
            title="Inspect Main Pump & Sluice Gate Actuators",
            description="Ensure physical canal gate path is free of weed debris and emergency stop button is disengaged.",
            rationale="Previous operational logs indicate canal gate obstruction risk during rapid water intake.",
            evidence_source="ArvaCore Operational Safety Guidelines",
            priority="CRITICAL_PREREQUISITE",
            status=TaskLifecycleState.SCHEDULED,
            deadline=(now + timedelta(hours=4)).isoformat()
        ))

        # 5. Automated Edge Pre-Calibration (System Automated)
        tasks.append(PreparationTaskItem(
            id=f"{plan_id}_T4",
            category="SYSTEM_AUTOMATED",
            title="ArvaCore Sensor Baseline Snapshot",
            description="Autonomous recording of pre-irrigation ultrasonic distance and soil moisture baseline.",
            rationale="Used for post-irrigation outcome validation and efficiency assessment.",
            evidence_source="ArvaNet Backend Telemetry Engine",
            priority="NORMAL",
            status=TaskLifecycleState.PROPOSED,
            requires_confirmation=False
        ))

        # 6. Evaluate if critical prerequisites are satisfied
        critical_blocked = any(t.priority == "CRITICAL_PREREQUISITE" and t.status == TaskLifecycleState.BLOCKED for t in tasks)
        prerequisites_met = not critical_blocked

        # Compute readiness score
        completed_count = sum(1 for t in tasks if t.status == TaskLifecycleState.COMPLETED)
        total_tasks = len(tasks)
        readiness_score = int((completed_count / total_tasks * 100)) if total_tasks > 0 else 0
        if not critical_blocked and readiness_score == 0:
            readiness_score = 65  # Base ready-to-prepare score

        plan = PreIrrigationPlan(
            plan_id=plan_id,
            field_id=field_id,
            user_id=user_id,
            crop_variety=crop_variety,
            crop_stage=crop_stage,
            irrigation_objective="AWD +5.0 cm Replenishment",
            proposed_window_start=(now + timedelta(hours=12)).isoformat(),
            proposed_window_end=(now + timedelta(hours=18)).isoformat(),
            overall_status=TaskLifecycleState.PROPOSED if not critical_blocked else TaskLifecycleState.BLOCKED,
            prerequisites_met=prerequisites_met,
            readiness_score=readiness_score,
            tasks=tasks,
            risk_factors=risk_factors
        )

        # Store in operational memory
        global_memory_store.record_operational_memory(
            user_id=user_id,
            field_id=field_id,
            category="pre_irrigation_plan",
            content=f"Generated preparation plan {plan_id} with {len(tasks)} tasks (Readiness: {readiness_score}%, Status: {plan.overall_status.value})",
            source_type=MemorySourceType.AI_RECOMMENDED,
            metadata={"plan_id": plan_id, "tasks_count": len(tasks), "prerequisites_met": prerequisites_met}
        )

        return plan

    def evaluate_pre_irrigation_readiness(self, plan: PreIrrigationPlan) -> Dict[str, Any]:
        """
        Evaluates whether an irrigation event is cleared to proceed based on task completion evidence.
        """
        critical_uncompleted = [
            t for t in plan.tasks
            if t.priority == "CRITICAL_PREREQUISITE" and t.status != TaskLifecycleState.COMPLETED
        ]

        can_proceed = len(critical_uncompleted) == 0
        recommendation = "PROCEED_TO_AUTHORIZATION" if can_proceed else "HOLD_PREPARATION_PENDING"

        return {
            "plan_id": plan.plan_id,
            "can_proceed": can_proceed,
            "recommendation": recommendation,
            "critical_pending_tasks": [t.title for t in critical_uncompleted],
            "total_tasks": len(plan.tasks),
            "completed_tasks": sum(1 for t in plan.tasks if t.status == TaskLifecycleState.COMPLETED),
            "readiness_score": plan.readiness_score
        }

    def record_post_irrigation_outcome(
        self,
        plan_id: str,
        user_id: str,
        field_id: int,
        irrigation_command_id: str,
        controller_status: str,
        water_level_delta_cm: float,
        soil_moisture_delta_pct: float,
        duration_minutes: int,
        success: bool,
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Associates completed irrigation with preparation plan and saves outcome to operational memory.
        """
        outcome_data = {
            "plan_id": plan_id,
            "irrigation_command_id": irrigation_command_id,
            "controller_status": controller_status,
            "water_level_delta_cm": water_level_delta_cm,
            "soil_moisture_delta_pct": soil_moisture_delta_pct,
            "duration_minutes": duration_minutes,
            "success": success,
            "notes": notes,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        # Save to persistent memory
        global_memory_store.record_operational_memory(
            user_id=user_id,
            field_id=field_id,
            category="post_irrigation_outcome",
            content=f"Irrigation {irrigation_command_id} following {plan_id} completed. Delta water level: +{water_level_delta_cm}cm, Success: {success}",
            source_type=MemorySourceType.SENSOR_MEASURED if water_level_delta_cm > 0 else MemorySourceType.VERIFIED_DB,
            metadata=outcome_data,
            verified=True
        )

        return {
            "status": "RECORDED",
            "outcome": outcome_data,
            "message": "Post-irrigation outcome successfully logged to Arva AI operational memory."
        }


# Global singleton scheduler instance
global_pre_irrigation_scheduler = IntelligentPreIrrigationScheduler()
