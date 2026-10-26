import pytest
from app.services.langchain_memory_engine import ArvaMemoryStore, MemorySourceType
from app.services.pre_irrigation_scheduler import (
    IntelligentPreIrrigationScheduler,
    TaskLifecycleState
)


def test_langchain_memory_store_layers():
    store = ArvaMemoryStore()
    user_id = "farmer_test"
    field_id = 1

    # Layer 1: Conversation memory via BaseChatMessageHistory
    chat_hist = store.get_chat_history("sess_01", user_id, field_id)
    assert len(chat_hist.messages) == 0

    # Layer 2: Farm and field memory
    rec_farm = store.record_farm_memory(
        user_id=user_id,
        field_id=field_id,
        category="crop_profile",
        content="Planted NSIC Rc 222 on 2026-10-15, direct seeded",
        source_type=MemorySourceType.USER_REPORTED,
        verified=True
    )
    assert rec_farm.verified is True

    # Layer 3: Operational memory
    rec_op = store.record_operational_memory(
        user_id=user_id,
        field_id=field_id,
        category="task_abandoned",
        content="Pump inspection task abandoned due to heavy storm",
        source_type=MemorySourceType.USER_REPORTED
    )
    assert rec_op.is_active is True

    # Layer 4: Retrieval partitioning
    memories = store.get_relevant_memories(user_id, field_id)
    assert len(memories["farm_and_field_memory"]) == 1
    assert len(memories["operational_memory"]) == 1
    assert "NSIC Rc 222" in memories["summary_context"]


def test_pre_irrigation_scheduler_with_rain_hazard():
    scheduler = IntelligentPreIrrigationScheduler()

    # Heavy rain forecast
    plan = scheduler.generate_preparation_plan(
        field_id=1,
        user_id="farmer_test",
        crop_variety="NSIC Rc 222",
        crop_stage="VEGETATIVE",
        weather_forecast={"pop": 85, "rain_24h_mm": 35.0}
    )

    assert plan.overall_status == TaskLifecycleState.BLOCKED
    assert plan.prerequisites_met is False
    assert any(t.category == "SAFETY_BLOCKED" for t in plan.tasks)


def test_pre_irrigation_scheduler_normal_conditions():
    scheduler = IntelligentPreIrrigationScheduler()

    # Clear weather, healthy nodes
    plan = scheduler.generate_preparation_plan(
        field_id=1,
        user_id="farmer_test",
        crop_variety="NSIC Rc 222",
        crop_stage="TILLERING",
        nodes_telemetry=[
            {"node_id": "ARVANODE-001", "is_online": True, "is_stale": False},
            {"node_id": "ARVANODE-002", "is_online": True, "is_stale": False}
        ],
        weather_forecast={"pop": 10, "rain_24h_mm": 0.0}
    )

    assert plan.overall_status == TaskLifecycleState.PROPOSED
    assert plan.prerequisites_met is True
    assert len(plan.tasks) >= 3


def test_post_irrigation_outcome_association():
    scheduler = IntelligentPreIrrigationScheduler()
    res = scheduler.record_post_irrigation_outcome(
        plan_id="PREP-F1-100",
        user_id="farmer_test",
        field_id=1,
        irrigation_command_id="CMD-IRR-20261027-01",
        controller_status="COMPLETED_NORMAL",
        water_level_delta_cm=4.8,
        soil_moisture_delta_pct=15.2,
        duration_minutes=45,
        success=True,
        notes="AWD reflood successfully reached target +5cm depth"
    )

    assert res["status"] == "RECORDED"
    assert res["outcome"]["success"] is True
    assert res["outcome"]["water_level_delta_cm"] == 4.8

