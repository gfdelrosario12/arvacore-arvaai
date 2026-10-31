import pytest
from app.models.workflow_models import (
    PlanLifecycleStatus,
    ImplementationPlanSummary,
    TaskStatus
)
from app.services.langchain_memory_engine import (
    ArvaMemoryStore,
    MemorySourceType
)


def test_plan_lifecycle_and_memory_store():
    store = ArvaMemoryStore()

    # 1. Register a plan in NOT_STARTED
    plan1 = ImplementationPlanSummary(
        plan_id=1,
        plan_code="PLAN-001",
        title="NSIC Rc 222 Wet Bed Cultivation",
        crop_name="Lowland Rice (NSIC Rc 222)",
        lifecycle_status=PlanLifecycleStatus.NOT_STARTED,
        progress_percent=0,
        readiness_score=45,
        associated_session_ids=["sess-1"]
    )
    store.register_plan(plan1)

    active = store.find_active_or_continued_plans()
    assert len(active) == 1
    assert active[0].plan_code == "PLAN-001"
    assert active[0].lifecycle_status == PlanLifecycleStatus.NOT_STARTED

    # 2. Transition plan to IN_PROGRESS then CONTINUED
    plan1.lifecycle_status = PlanLifecycleStatus.IN_PROGRESS
    plan1.progress_percent = 50
    store.register_plan(plan1)
    assert store.get_plan(1).lifecycle_status == PlanLifecycleStatus.IN_PROGRESS

    plan1.lifecycle_status = PlanLifecycleStatus.CONTINUED
    plan1.status_reason = "Awaiting drainage"
    store.register_plan(plan1)
    assert store.get_plan(1).lifecycle_status == PlanLifecycleStatus.CONTINUED

    # 3. Complete plan
    plan1.lifecycle_status = PlanLifecycleStatus.COMPLETED
    plan1.progress_percent = 100
    plan1.completion_evidence = "All 4 preparation tasks confirmed by farmer and ArvaNode water tube sensors"
    store.register_plan(plan1)

    # Completed plans are no longer active/continued
    active_after = store.find_active_or_continued_plans()
    assert len(active_after) == 0

    # 4. Memory context includes historical operational record
    memories = store.get_relevant_memories("farmer", 1)
    assert len(memories["operational_memory"]) >= 1
    assert "PLAN-001" in memories["summary_context"]

