import os
import pytest
import tempfile
import threading
from app.db.workflow_db import WorkflowDatabase
from app.services.workflow_dependency_engine import (
    WorkflowDependencyEngine,
    DependencyViolationError,
    CircularDependencyError,
    StepConcurrencyError
)
from app.models.workflow_models import StepStatus, TaskStatus


@pytest.fixture
def test_engine():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    db = WorkflowDatabase(db_path=db_path)
    engine = WorkflowDependencyEngine(db=db)
    yield engine
    if os.path.exists(db_path):
        os.remove(db_path)


def test_normal_sequential_execution(test_engine):
    """Verifies that each step can only execute after its prerequisites complete."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_seq_1",
        title="Test Sequential Execution",
        user_id="farmer_01",
        field_id=1
    )

    # Initially S01 should be ELIGIBLE, all others WAITING
    step_s01 = test_engine.db.get_step_by_code("task_seq_1", "S01")
    assert step_s01.status == StepStatus.ELIGIBLE

    step_s02 = test_engine.db.get_step_by_code("task_seq_1", "S02")
    assert step_s02.status == StepStatus.WAITING

    # Attempting to start S02 before S01 must raise DependencyViolationError
    with pytest.raises(DependencyViolationError):
        test_engine.start_step("task_seq_1", "S02")

    # Start and complete S01
    test_engine.start_step("task_seq_1", "S01")
    test_engine.complete_step("task_seq_1", "S01", output_data={"prompt": "Prepare paddy"})

    # Now S02 must be ELIGIBLE
    step_s02 = test_engine.db.get_step_by_code("task_seq_1", "S02")
    assert step_s02.status == StepStatus.ELIGIBLE

    # S03 depends on S01 and S02; cannot start yet
    with pytest.raises(DependencyViolationError):
        test_engine.start_step("task_seq_1", "S03")

    # Complete S02
    test_engine.start_step("task_seq_1", "S02")
    test_engine.complete_step("task_seq_1", "S02", output_data={"history": []})

    # Now S03 is ELIGIBLE
    step_s03 = test_engine.db.get_step_by_code("task_seq_1", "S03")
    assert step_s03.status == StepStatus.ELIGIBLE


def test_independent_steps_parallel_execution(test_engine):
    """Verifies parallel execution is allowed for independent eligible steps with thread safety."""
    # Define a graph where S02A and S02B both depend on S01 independently
    custom_graph = [
        {"code": "S01", "name": "Start", "depends_on": []},
        {"code": "S02A", "name": "Step A", "depends_on": ["S01"]},
        {"code": "S02B", "name": "Step B", "depends_on": ["S01"]},
        {"code": "S03", "name": "End", "depends_on": ["S02A", "S02B"]}
    ]
    task, steps = test_engine.initialize_workflow(
        task_id="task_parallel",
        title="Parallel Branching",
        custom_graph=custom_graph
    )

    test_engine.start_step("task_parallel", "S01")
    test_engine.complete_step("task_parallel", "S01")

    # Both S02A and S02B are now ELIGIBLE
    s2a = test_engine.db.get_step_by_code("task_parallel", "S02A")
    s2b = test_engine.db.get_step_by_code("task_parallel", "S02B")
    assert s2a.status == StepStatus.ELIGIBLE
    assert s2b.status == StepStatus.ELIGIBLE

    # Execute in parallel threads
    results = {}
    def run_worker(code):
        test_engine.start_step("task_parallel", code)
        test_engine.complete_step("task_parallel", code, output_data={"worker": code})
        results[code] = "OK"

    t1 = threading.Thread(target=run_worker, args=("S02A",))
    t2 = threading.Thread(target=run_worker, args=("S02B",))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert results["S02A"] == "OK"
    assert results["S02B"] == "OK"

    # Now S03 should be ELIGIBLE
    s3 = test_engine.db.get_step_by_code("task_parallel", "S03")
    assert s3.status == StepStatus.ELIGIBLE


def test_blocked_and_failed_dependencies_propagation(test_engine):
    """Prerequisite failure/blockage propagates waiting/blocked to dependents without falsely marking them failed."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_fail",
        title="Test Failure Propagation"
    )

    # Complete S01, S02, S03, S04, S05, S06
    for code in ["S01", "S02", "S03", "S04", "S05", "S06"]:
        test_engine.start_step("task_fail", code)
        test_engine.complete_step("task_fail", code)

    # S07 verifies prerequisites and encounters missing access -> BLOCKED
    test_engine.start_step("task_fail", "S07")
    test_engine.db.update_step_status(
        test_engine.db.get_step_by_code("task_fail", "S07").id,
        status=StepStatus.BLOCKED,
        blocking_reason="Missing valve actuator permission on ArvaGate"
    )
    test_engine.recalculate_eligibility("task_fail")

    # S08 depends on S07: it must be BLOCKED, NOT FAILED
    s08 = test_engine.db.get_step_by_code("task_fail", "S08")
    assert s08.status == StepStatus.BLOCKED
    assert "Missing valve actuator permission" in s08.blocking_reason

    # S08 cannot start
    with pytest.raises(DependencyViolationError):
        test_engine.start_step("task_fail", "S08")

    # Task status reflects BLOCKED
    task = test_engine.db.get_task("task_fail")
    assert task.status == TaskStatus.BLOCKED


def test_approved_and_rejected_step_skipping(test_engine):
    """Skipping satisfies dependency only when permitted and justified."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_skip",
        title="Test Step Skipping"
    )

    # Complete S01..S06
    for code in ["S01", "S02", "S03", "S04", "S05", "S06"]:
        test_engine.start_step("task_skip", code)
        test_engine.complete_step("task_skip", code)

    # Attempting to skip S01 without reason or approval fails
    with pytest.raises(DependencyViolationError):
        test_engine.skip_step("task_skip", "S01", skip_reason="just because")

    # S07 and S08 are skippable when prompt requires advisory only (no code/state changes)
    test_engine.skip_step(
        "task_skip",
        "S07",
        skip_reason="No hardware access required for advisory query",
        approved_by_policy=True
    )
    test_engine.skip_step(
        "task_skip",
        "S08",
        skip_reason="Advisory response only; no physical pump state changes",
        approved_by_policy=True
    )
    test_engine.skip_step(
        "task_skip",
        "S09",
        skip_reason="No code changes executed; test suite run not applicable",
        approved_by_policy=True
    )

    # Downstream S11 should be ELIGIBLE (with S10 conditional skip)
    test_engine.recalculate_eligibility("task_skip")
    s11 = test_engine.db.get_step_by_code("task_skip", "S11")
    assert s11.status == StepStatus.ELIGIBLE


def test_conditional_remediation_and_revalidation(test_engine):
    """S10 is conditional. When failures exist in S09, S10 diagnoses, remediates, and re-triggers S09."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_remed",
        title="Conditional Remediation"
    )

    for code in ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08"]:
        test_engine.start_step("task_remed", code)
        test_engine.complete_step("task_remed", code)

    # S09 completes with failures_exist: True
    test_engine.start_step("task_remed", "S09")
    test_engine.complete_step(
        "task_remed",
        "S09",
        output_data={"failures_exist": True, "failed_checks": ["AWD_THRESHOLD_EXCEEDED"]}
    )

    # S10 must now be ELIGIBLE
    s10 = test_engine.db.get_step_by_code("task_remed", "S10")
    assert s10.status == StepStatus.ELIGIBLE

    # S11 cannot complete yet because remediation is active
    s11 = test_engine.db.get_step_by_code("task_remed", "S11")
    assert s11.status == StepStatus.WAITING

    # Trigger remediation
    test_engine.trigger_remediation(
        "task_remed",
        failure_diagnosis={"root_cause": "AWD threshold offset", "fix_action": "Recalibrated AWD baseline"}
    )

    # S10 is now COMPLETED, and S09 is reset to ELIGIBLE for rerun
    s10_after = test_engine.db.get_step_by_code("task_remed", "S10")
    assert s10_after.status == StepStatus.COMPLETED

    s09_reset = test_engine.db.get_step_by_code("task_remed", "S09")
    assert s09_reset.status == StepStatus.ELIGIBLE

    # Rerun S09, now successful
    test_engine.start_step("task_remed", "S09")
    test_engine.complete_step("task_remed", "S09", output_data={"failures_exist": False, "passed": True})

    # Now S11 is ELIGIBLE
    s11_ready = test_engine.db.get_step_by_code("task_remed", "S11")
    assert s11_ready.status == StepStatus.ELIGIBLE


def test_circular_dependency_rejection(test_engine):
    """Verifies that circular dependency graphs are caught and rejected immediately."""
    circular_graph = [
        {"code": "S01", "name": "One", "depends_on": ["S03"]},
        {"code": "S02", "name": "Two", "depends_on": ["S01"]},
        {"code": "S03", "name": "Three", "depends_on": ["S02"]}
    ]
    with pytest.raises(CircularDependencyError):
        test_engine.initialize_workflow(
            task_id="task_cycle",
            title="Cycle Test",
            custom_graph=circular_graph
        )


def test_upstream_change_invalidates_downstream_results(test_engine):
    """Modifying or invalidating an upstream step resets downstream dependent steps."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_inval",
        title="Downstream Invalidation Test"
    )

    # Run through S01..S05
    for code in ["S01", "S02", "S03", "S04", "S05"]:
        test_engine.start_step("task_inval", code)
        test_engine.complete_step("task_inval", code)

    assert test_engine.db.get_step_by_code("task_inval", "S05").status == StepStatus.COMPLETED

    # User re-evaluates intent at S03 (upstream change)
    invalidated = test_engine.invalidate_downstream(
        "task_inval",
        from_step_code="S03",
        invalidation_reason="User altered crop selection from Rc 222 to NSIC Rc 160"
    )

    assert "S04" in invalidated
    assert "S05" in invalidated

    # S05 must now be INVALIDATED
    s05 = test_engine.db.get_step_by_code("task_inval", "S05")
    assert s05.status == StepStatus.INVALIDATED


def test_concurrency_protection(test_engine):
    """Prevents two concurrent workers from starting the same step."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_concurr",
        title="Concurrency Test"
    )

    # Worker 1 starts S01
    test_engine.start_step("task_concurr", "S01")

    # Worker 2 attempts to start S01 simultaneously -> StepConcurrencyError
    with pytest.raises(StepConcurrencyError):
        test_engine.start_step("task_concurr", "S01")


def test_conditional_user_decision_and_task_continuation(test_engine):
    """S04 records decision whether to continue prior task or start new, unblocking S05."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_decision",
        title="User Decision Flow"
    )

    test_engine.start_step("task_decision", "S01")
    test_engine.complete_step("task_decision", "S01")

    test_engine.start_step("task_decision", "S02")
    test_engine.complete_step("task_decision", "S02", output_data={"prior_task_id": "task_old_99", "status": "UNFINISHED"})

    test_engine.start_step("task_decision", "S03")
    test_engine.complete_step("task_decision", "S03", output_data={"scope": "CONTINUE_OR_START_NEW"})

    # S04 requires user decision; S05 cannot start
    s05 = test_engine.db.get_step_by_code("task_decision", "S05")
    assert s05.status == StepStatus.WAITING

    # Record user decision at S04
    test_engine.record_decision(
        "task_decision",
        decision_data={"user_choice": "CONTINUE_PRIOR_TASK", "prior_task_id": "task_old_99"}
    )

    # S04 is completed and S05 becomes ELIGIBLE
    s04 = test_engine.db.get_step_by_code("task_decision", "S04")
    assert s04.status == StepStatus.COMPLETED

    s05_after = test_engine.db.get_step_by_code("task_decision", "S05")
    assert s05_after.status == StepStatus.ELIGIBLE


def test_final_persistence_and_task_lifecycle(test_engine):
    """End-to-end execution through S12 (Persist) and S13 (Report), verifying task completion and audit events."""
    task, steps = test_engine.initialize_workflow(
        task_id="task_full",
        title="Full Lifecycle Execution"
    )

    # S01..S09
    for code in ["S01", "S02", "S03", "S04", "S05", "S06", "S07", "S08"]:
        test_engine.start_step("task_full", code)
        test_engine.complete_step("task_full", code)

    # S09 validation passes (no failures)
    test_engine.start_step("task_full", "S09")
    test_engine.complete_step("task_full", "S09", output_data={"failures_exist": False})

    # S11 Review
    test_engine.start_step("task_full", "S11")
    test_engine.complete_step("task_full", "S11", output_data={"completeness": "100%", "all_criteria_met": True})

    # Finalize
    final_task = test_engine.finalize_task(
        "task_full",
        final_outcome={"success": True, "summary": "Paddy pre-irrigation fully configured and verified."}
    )

    assert final_task.status == TaskStatus.COMPLETED
    assert final_task.current_step_code == "S13"

    # Audit events verified
    events = test_engine.db.get_events_for_task("task_full")
    assert len(events) >= 10
    event_types = [e.event_type for e in events]
    assert "TASK_CREATED" in event_types
    assert "STEP_STATE_CHANGED" in event_types
    assert "TASK_STATUS_CHANGED" in event_types

