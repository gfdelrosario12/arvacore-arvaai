"""
Arva AI - FastAPI Microservice Entrypoint.
Provides backend-mediated endpoints for ArvaLink, the 5 agronomic data sources,
and MCP-based agricultural reasoning.
"""

import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from app.schemas.decision_models import UserQueryRequest
from app.tools.read_only_tools import ReadOnlyTelemetryTools
from app.services.gemini_advisor import ArvaGeminiAdvisor
from app.services.multi_source_evidence_aggregator import MultiSourceAgronomicEvidenceAggregator
from app.services.event_driven_intelligence import EventDrivenArvaEngine
from app.services.langchain_memory_engine import global_memory_store, MemorySourceType
from app.services.pre_irrigation_scheduler import (
    global_pre_irrigation_scheduler,
    PreIrrigationPlan,
    TaskLifecycleState
)
from app.services.soil_fallback_engine import (
    global_soil_fallback_engine,
    SoilFallbackEvaluation,
    FallbackDecisionType
)
from app.services.workflow_dependency_engine import (
    global_workflow_dependency_engine,
    DependencyViolationError,
    CircularDependencyError,
    StepConcurrencyError
)
from app.models.workflow_models import StepStatus, TaskStatus

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize configuration
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "https://api-aquaflow.gladwindr.me/api/v1")
ARVACORE_API_TOKEN = os.getenv("ARVACORE_API_TOKEN", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Initialize Service Components
try:
    tools = ReadOnlyTelemetryTools(BACKEND_BASE_URL, ARVACORE_API_TOKEN)
    advisor = ArvaGeminiAdvisor(tools, GEMINI_API_KEY, GEMINI_MODEL)
    aggregator = MultiSourceAgronomicEvidenceAggregator(BACKEND_BASE_URL, ARVACORE_API_TOKEN)
    event_engine = EventDrivenArvaEngine()
except Exception as e:
    tools = None
    advisor = None
    aggregator = None
    event_engine = EventDrivenArvaEngine()

app = FastAPI(title="Arva AI Advisory Service", version="1.2.0")

class QueryPayload(BaseModel):
    user_id: str = "anonymous"
    query_text: str
    field_id: int = 1
    role: str = "FARMER"

class AssessmentPayload(BaseModel):
    user_id: str = "farmer_01"
    field_id: int = 1
    role: str = "FARMER"
    target_crop: str = "Lowland Rice (NSIC Rc 222)"
    preparation_days_left: int = 21
    query_context: str = "planting preparation and AWD water management"

class FarmEventsPayload(BaseModel):
    field_id: int = 1
    nodes_telemetry: list = []
    zones: list = []
    weather_forecast: Optional[dict] = None
    is_pump_running: bool = False
    is_estop_active: bool = False
    crop_stage: str = "VEGETATIVE"

class MemoryRecordPayload(BaseModel):
    user_id: str
    field_id: int = 1
    category: str
    content: str
    source_type: str = "USER_REPORTED"
    metadata: dict = {}
    verified: bool = False

class PreIrrigationPlanPayload(BaseModel):
    user_id: str
    field_id: int = 1
    crop_variety: str = "NSIC Rc 222"
    crop_stage: str = "TILLERING"
    nodes_telemetry: list = []
    weather_forecast: Optional[dict] = None

class PostIrrigationOutcomePayload(BaseModel):
    plan_id: str
    user_id: str
    field_id: int = 1
    irrigation_command_id: str
    controller_status: str
    water_level_delta_cm: float
    soil_moisture_delta_pct: float
    duration_minutes: int
    success: bool
    notes: str = ""

class SoilFallbackPayload(BaseModel):
    field_id: int = 1
    crop_stage: str = "VEGETATIVE"
    nodes_telemetry: list = []
    weather_forecast: Optional[dict] = None
    historical_last_valid_moisture: Optional[float] = None

class WorkflowInitPayload(BaseModel):
    task_id: str
    title: str
    user_id: str = "anonymous"
    field_id: int = 1
    session_id: Optional[str] = None
    context_data: dict = {}

class StepActionPayload(BaseModel):
    task_id: str
    step_code: str
    output_data: Optional[dict] = None
    execution_evidence: Optional[dict] = None
    error_message: Optional[str] = None
    skip_reason: Optional[str] = None
    approved_by_policy: bool = False

class DecisionPayload(BaseModel):
    task_id: str
    step_code: str = "S04"
    decision_data: dict = {}

class RemediationPayload(BaseModel):
    task_id: str
    failure_diagnosis: dict = {}

class InvalidationPayload(BaseModel):
    task_id: str
    from_step_code: str
    invalidation_reason: str

@app.get("/health")
def health():
    return {
        "status": "UP",
        "service": "arva-ai",
        "model": GEMINI_MODEL,
        "data_sources": {
            "pagasa_mcp": "CONFIGURED",
            "lopez_historical_agri_mcp": "CONFIGURED",
            "arvanode_telemetry": "CONNECTED",
            "philrice_manual_pdf": "INDEXED",
            "farmer_database": "CONNECTED"
        },
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@app.post("/api/v1/ai/query")
def api_query(payload: QueryPayload):
    res = handle_query(payload.model_dump())
    if "error" in res:
        raise HTTPException(status_code=500, detail=res)
    return res

@app.post("/api/v1/ai/planting-assessment")
def api_planting_assessment(payload: AssessmentPayload):
    """
    Executes grounded 5-source multi-evidence assessment yielding one of:
    'Suitable', 'Conditionally suitable', 'Further assessment required', 'High risk'.
    """
    try:
        if not aggregator:
            raise RuntimeError("Agronomic aggregator service not initialized.")
        return aggregator.aggregate_evidence(
            field_id=payload.field_id,
            user_id=payload.user_id,
            role=payload.role,
            target_crop=payload.target_crop,
            preparation_days_left=payload.preparation_days_left,
            query_context=payload.query_context
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "ASSESSMENT_FAILED", "message": str(e)})

@app.post("/api/v1/ai/event-intelligence")
def api_event_intelligence(payload: FarmEventsPayload):
    """
    Analyzes live farm telemetry, weather, and operational state to return:
    - active_events: validated deduplicated farm events
    - primary_advisory: headline, summary, AWD proposal, and urgency for mobile app
    - dynamic_questions: context-aware questions reflecting current conditions
    """
    try:
        return event_engine.analyze_farm_state(
            nodes_telemetry=payload.nodes_telemetry,
            zones=payload.zones,
            weather_forecast=payload.weather_forecast,
            is_pump_running=payload.is_pump_running,
            is_estop_active=payload.is_estop_active,
            crop_stage=payload.crop_stage,
            field_id=payload.field_id
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "EVENT_INTELLIGENCE_FAILED", "message": str(e)})

@app.post("/api/v1/ai/memory/record")
def api_record_memory(payload: MemoryRecordPayload):
    """
    Stores persistent memory layer record (conversation, farm/field context, or operational action).
    """
    try:
        source_type = MemorySourceType(payload.source_type)
    except ValueError:
        source_type = MemorySourceType.USER_REPORTED

    rec = global_memory_store.record_farm_memory(
        user_id=payload.user_id,
        field_id=payload.field_id,
        category=payload.category,
        content=payload.content,
        source_type=source_type,
        metadata=payload.metadata,
        verified=payload.verified
    )
    return {"status": "SUCCESS", "record": rec.model_dump()}

@app.get("/api/v1/ai/memory")
def api_get_memory(user_id: str, field_id: int = 1):
    """
    Retrieves active persistent memory partitioned by memory layer.
    """
    return global_memory_store.get_relevant_memories(user_id=user_id, field_id=field_id)

@app.post("/api/v1/ai/pre-irrigation/plan")
def api_generate_pre_irrigation_plan(payload: PreIrrigationPlanPayload):
    """
    Generates intelligent pre-irrigation preparation plan evaluating telemetry, weather, and memory.
    """
    try:
        plan = global_pre_irrigation_scheduler.generate_preparation_plan(
            field_id=payload.field_id,
            user_id=payload.user_id,
            crop_variety=payload.crop_variety,
            crop_stage=payload.crop_stage,
            nodes_telemetry=payload.nodes_telemetry,
            weather_forecast=payload.weather_forecast
        )
        return plan.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "PREP_PLAN_FAILED", "message": str(e)})

@app.post("/api/v1/ai/pre-irrigation/outcome")
def api_record_post_irrigation_outcome(payload: PostIrrigationOutcomePayload):
    """
    Records post-irrigation outcome and associates with pre-irrigation plan in persistent memory.
    """
    try:
        return global_pre_irrigation_scheduler.record_post_irrigation_outcome(
            plan_id=payload.plan_id,
            user_id=payload.user_id,
            field_id=payload.field_id,
            irrigation_command_id=payload.irrigation_command_id,
            controller_status=payload.controller_status,
            water_level_delta_cm=payload.water_level_delta_cm,
            soil_moisture_delta_pct=payload.soil_moisture_delta_pct,
            duration_minutes=payload.duration_minutes,
            success=payload.success,
            notes=payload.notes
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "RECORD_OUTCOME_FAILED", "message": str(e)})

@app.post("/api/v1/ai/soil-fallback")
def api_soil_fallback(payload: SoilFallbackPayload):
    """
    Evaluates fallback reasoning when soil moisture telemetry is missing, stale, zero-padded, or conflicting.
    Returns evidence-based irrigation advisory with explicit confidence, alternative sources used, and safety interlocks.
    """
    try:
        res = global_soil_fallback_engine.evaluate_fallback(
            nodes_telemetry=payload.nodes_telemetry,
            weather_forecast=payload.weather_forecast,
            crop_stage=payload.crop_stage,
            historical_last_valid_moisture=payload.historical_last_valid_moisture,
            field_id=payload.field_id
        )
        return res.model_dump()
    except Exception as e:
        raise HTTPException(status_code=500, detail={"error": "SOIL_FALLBACK_FAILED", "message": str(e)})

@app.post("/api/v1/ai/workflow/init")
def api_init_workflow(payload: WorkflowInitPayload):
    try:
        task, steps = global_workflow_dependency_engine.initialize_workflow(
            task_id=payload.task_id,
            title=payload.title,
            user_id=payload.user_id,
            field_id=payload.field_id,
            session_id=payload.session_id,
            context_data=payload.context_data
        )
        return {
            "task": task.model_dump(),
            "steps": [s.model_dump() for s in steps]
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": "WORKFLOW_INIT_FAILED", "message": str(e)})

@app.get("/api/v1/ai/workflow/{task_id}")
def api_get_workflow(task_id: str):
    task = global_workflow_dependency_engine.db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    steps = global_workflow_dependency_engine.db.get_task_steps(task_id)
    events = global_workflow_dependency_engine.db.get_events_for_task(task_id)
    return {
        "task": task.model_dump(),
        "steps": [s.model_dump() for s in steps],
        "events": [e.model_dump() for e in events]
    }

@app.post("/api/v1/ai/workflow/step/start")
def api_start_step(payload: StepActionPayload):
    try:
        step = global_workflow_dependency_engine.start_step(payload.task_id, payload.step_code)
        return step.model_dump()
    except DependencyViolationError as dve:
        raise HTTPException(status_code=409, detail={"error": "DEPENDENCY_VIOLATION", "message": str(dve)})
    except StepConcurrencyError as sce:
        raise HTTPException(status_code=423, detail={"error": "CONCURRENCY_LOCKED", "message": str(sce)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": "STEP_START_FAILED", "message": str(e)})

@app.post("/api/v1/ai/workflow/step/complete")
def api_complete_step(payload: StepActionPayload):
    try:
        step = global_workflow_dependency_engine.complete_step(
            payload.task_id, payload.step_code, payload.output_data, payload.execution_evidence
        )
        return step.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": "STEP_COMPLETE_FAILED", "message": str(e)})

@app.post("/api/v1/ai/workflow/step/skip")
def api_skip_step(payload: StepActionPayload):
    try:
        step = global_workflow_dependency_engine.skip_step(
            payload.task_id, payload.step_code, payload.skip_reason or "", payload.approved_by_policy
        )
        return step.model_dump()
    except DependencyViolationError as dve:
        raise HTTPException(status_code=400, detail={"error": "SKIP_REJECTED", "message": str(dve)})
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": "STEP_SKIP_FAILED", "message": str(e)})

@app.post("/api/v1/ai/workflow/decision")
def api_record_decision(payload: DecisionPayload):
    try:
        step = global_workflow_dependency_engine.record_decision(
            payload.task_id, payload.decision_data, payload.step_code
        )
        return step.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": "DECISION_RECORD_FAILED", "message": str(e)})

@app.post("/api/v1/ai/workflow/remediation")
def api_trigger_remediation(payload: RemediationPayload):
    try:
        step = global_workflow_dependency_engine.trigger_remediation(
            payload.task_id, payload.failure_diagnosis
        )
        return step.model_dump()
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": "REMEDIATION_FAILED", "message": str(e)})

@app.post("/api/v1/ai/workflow/invalidate")
def api_invalidate_downstream(payload: InvalidationPayload):
    try:
        invalidated = global_workflow_dependency_engine.invalidate_downstream(
            payload.task_id, payload.from_step_code, payload.invalidation_reason
        )
        return {"invalidated_steps": invalidated}
    except Exception as e:
        raise HTTPException(status_code=400, detail={"error": "INVALIDATION_FAILED", "message": str(e)})

def handle_query(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Pure Python handler compatible with standard ASGI/WSGI or FastAPI."""
    try:
        user_req = UserQueryRequest(
            user_id=payload.get("user_id", "anonymous"),
            query_text=payload.get("query_text", ""),
            field_id=payload.get("field_id", 1),
            role=payload.get("role", "FARMER")
        )
        return advisor.evaluate_query(user_req)
    except ValueError as ve:
        return {
            "error": "BAD_REQUEST",
            "message": str(ve),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "error": "INTERNAL_SERVER_ERROR",
            "message": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

if __name__ == "__main__":
    print("Testing local standalone query...")
    sample_query = {"user_id": "farmer_01", "query_text": "What is the condition of my rice paddies?", "field_id": 1}
    res = handle_query(sample_query)
    import json
    print(json.dumps(res, indent=2))
