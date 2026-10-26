"""
Centralized Dependency Resolver and Workflow Execution Engine for Arva AI.

Enforces:
1. S01 -> S13 concrete dependency graph.
2. Mandatory dependency completion checks (only COMPLETED or approved SKIPPED).
3. Dependency failure/blocking propagation.
4. Downstream invalidation when upstream changes.
5. S10 conditional remediation routing.
6. Centralized graph cycle validation.
7. Concurrency and transactional idempotency.
8. LangChain persistent memory integration.
"""

from typing import Dict, Any, List, Set, Tuple, Optional
from datetime import datetime, timezone
import uuid
import threading

from app.models.workflow_models import (
    AITask, WorkflowStep, WorkflowStepDependency, AITaskEvent,
    StepStatus, TaskStatus, DependencyType, EventType
)
from app.db.workflow_db import WorkflowDatabase
from app.services.langchain_memory_engine import global_memory_store, MemorySourceType


# Canonical Step Specifications
CANONICAL_STEPS = [
    {"code": "S01", "name": "Capture Prompt", "depends_on": []},
    {"code": "S02", "name": "Retrieve Task History", "depends_on": ["S01"]},
    {"code": "S03", "name": "Classify Intent and Scope", "depends_on": ["S01", "S02"]},
    {"code": "S04", "name": "Resolve Prior Task or User Decision", "depends_on": ["S03"]},
    {"code": "S05", "name": "Define Requirements and Acceptance Criteria", "depends_on": ["S03", "S04"]},
    {"code": "S06", "name": "Plan Implementation", "depends_on": ["S05"]},
    {"code": "S07", "name": "Verify Prerequisites and Access", "depends_on": ["S06"]},
    {"code": "S08", "name": "Implement Changes", "depends_on": ["S07"]},
    {"code": "S09", "name": "Run Tests and Validation", "depends_on": ["S08"]},
    {"code": "S10", "name": "Diagnose and Resolve Failures", "depends_on": ["S09"], "conditional": True},
    {"code": "S11", "name": "Review Requirement Completeness", "depends_on": ["S09", "S10"]},
    {"code": "S12", "name": "Persist Final Outcome", "depends_on": ["S11"]},
    {"code": "S13", "name": "Report Results", "depends_on": ["S12"]},
]

# Steps that are allowed to be skipped if valid agronomic justification or flow condition applies
SKIPPABLE_POLICY = {
    "S07": "Allowed if no code/infrastructure changes or hardware prerequisites needed",
    "S08": "Allowed if prompt requires advisory only (no code/state modification)",
    "S09": "Allowed if no code changes executed",
    "S10": "Conditional step: skipped if validation succeeded without failure"
}


class DependencyViolationError(Exception):
    pass


class CircularDependencyError(Exception):
    pass


class StepConcurrencyError(Exception):
    pass


class WorkflowDependencyEngine:
    def __init__(self, db: Optional[WorkflowDatabase] = None):
        self.db = db or WorkflowDatabase()
        self._lock = threading.Lock()

    def initialize_workflow(
        self,
        task_id: str,
        title: str,
        user_id: str = "anonymous",
        field_id: int = 1,
        session_id: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        custom_graph: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[AITask, List[WorkflowStep]]:
        """
        Creates an AITask and populates all canonical steps and explicit dependencies.
        Validates graph for circular dependencies.
        """
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            task = AITask(
                id=task_id,
                title=title,
                status=TaskStatus.PENDING,
                user_id=user_id,
                field_id=field_id,
                session_id=session_id,
                context_data=context_data or {},
                created_at=now,
                updated_at=now
            )
            self.db.create_task(task)

            graph_specs = custom_graph or CANONICAL_STEPS
            step_code_to_id = {}
            created_steps = []

            for spec in graph_specs:
                step_id = f"step_{task_id}_{spec['code']}"
                step = WorkflowStep(
                    id=step_id,
                    task_id=task_id,
                    step_code=spec["code"],
                    name=spec["name"],
                    status=StepStatus.PENDING,
                    created_at=now,
                    updated_at=now
                )
                self.db.create_step(step)
                step_code_to_id[spec["code"]] = step_id
                created_steps.append(step)

            # Insert dependencies
            for spec in graph_specs:
                current_step_id = step_code_to_id[spec["code"]]
                is_conditional_step = spec.get("conditional", False)

                for dep_code in spec.get("depends_on", []):
                    dep_step_id = step_code_to_id[dep_code]
                    dep_type = DependencyType.CONDITIONAL if is_conditional_step or spec["code"] == "S11" and dep_code == "S10" else DependencyType.REQUIRED
                    condition = {"condition_type": "on_failure_only"} if is_conditional_step else None

                    dep = WorkflowStepDependency(
                        id=f"dep_{uuid.uuid4().hex[:12]}",
                        workflow_step_id=current_step_id,
                        depends_on_step_id=dep_step_id,
                        dependency_type=dep_type,
                        condition=condition,
                        created_at=now
                    )
                    self.db.create_dependency(dep)

            # Validate graph for cycles
            self.validate_graph(task_id)

            # Evaluate initial eligibility
            self.recalculate_eligibility(task_id)
            return self.db.get_task(task_id), self.db.get_task_steps(task_id)

    def validate_graph(self, task_id: str) -> bool:
        """
        Validates graph for circular dependencies via topological sort / cycle detection (Tarjan/DFS).
        Raises CircularDependencyError if a cycle exists.
        """
        steps = self.db.get_task_steps(task_id)
        step_id_map = {s.id: s for s in steps}

        # Build adjacency list: node -> outgoing edges (who depends on node)
        adj: Dict[str, List[str]] = {s.id: [] for s in steps}

        for s in steps:
            for dep in s.dependencies:
                # s depends on dep.depends_on_step_id, so edge dep.depends_on_step_id -> s
                if dep.depends_on_step_id in adj:
                    adj[dep.depends_on_step_id].append(s.id)

        # 0: unvisited, 1: visiting (recursion stack), 2: visited
        state: Dict[str, int] = {s.id: 0 for s in steps}

        def dfs(node: str, path: List[str]):
            state[node] = 1
            path.append(node)
            for neighbor in adj.get(node, []):
                if state[neighbor] == 1:
                    cycle = " -> ".join([step_id_map[n].step_code for n in path] + [step_id_map[neighbor].step_code])
                    raise CircularDependencyError(f"Circular dependency detected: {cycle}")
                if state[neighbor] == 0:
                    dfs(neighbor, path)
            path.pop()
            state[node] = 2

        for s in steps:
            if state[s.id] == 0:
                dfs(s.id, [])

        return True

    def evaluate_step_eligibility(self, step: WorkflowStep, all_steps: Dict[str, WorkflowStep]) -> Tuple[StepStatus, Optional[str]]:
        """
        Evaluates whether a step is ELIGIBLE, WAITING, BLOCKED, or SKIPPABLE.
        Rules:
        - All mandatory REQUIRED dependencies must be COMPLETED (or legitimately SKIPPED).
        - If any dependency is FAILED, step cannot start -> WAITING/BLOCKED.
        - If any dependency is BLOCKED, propagates BLOCKED condition.
        - If dependency is PENDING or IN_PROGRESS -> WAITING.
        - For CONDITIONAL dependencies (e.g. S10 or S11's dependency on S10):
          - S10 is conditionally eligible ONLY if S09 reported failure.
          - If S09 succeeded, S10 is auto-eligible for SKIP or considered satisfied.
        """
        if step.status in (StepStatus.COMPLETED, StepStatus.SKIPPED, StepStatus.IN_PROGRESS):
            return step.status, None

        if not step.dependencies:
            return StepStatus.ELIGIBLE, None

        has_blocked_dep = False
        has_failed_dep = False
        has_waiting_dep = False
        blocking_reasons = []

        for dep in step.dependencies:
            parent = all_steps.get(dep.depends_on_step_id)
            if not parent:
                raise DependencyViolationError(f"Missing dependency step reference: {dep.depends_on_step_id}")

            # Special case for S11 depending on S10:
            if step.step_code == "S11" and parent.step_code == "S10":
                # S10 is conditional. If S10 was SKIPPED or COMPLETED, or if S09 passed/skipped and S10 was not needed
                if parent.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                    continue
                s09_step = next((s for s in all_steps.values() if s.step_code == "S09"), None)
                if s09_step and s09_step.status in (StepStatus.COMPLETED, StepStatus.SKIPPED):
                    s09_output = s09_step.output_data or {}
                    if not s09_output.get("failures_exist", False):
                        # S10 was unnecessary because S09 had no failures or was skipped
                        continue
                if parent.status in (StepStatus.FAILED, StepStatus.BLOCKED):
                    has_blocked_dep = True
                    blocking_reasons.append(f"Conditional remediation {parent.step_code} unresolved: {parent.status.value}")
                    continue
                if parent.status in (StepStatus.PENDING, StepStatus.IN_PROGRESS, StepStatus.WAITING, StepStatus.ELIGIBLE):
                    has_waiting_dep = True
                    continue

            # Special case for S10 (conditional remediation step):
            if step.step_code == "S10" and parent.step_code == "S09":
                if parent.status == StepStatus.COMPLETED:
                    s09_output = parent.output_data or {}
                    if s09_output.get("failures_exist", False):
                        return StepStatus.ELIGIBLE, "Failures detected in S09 requiring diagnosis and remediation."
                    else:
                        return StepStatus.SKIPPED, "Validation passed in S09 with no failures; S10 not required."
                elif parent.status == StepStatus.SKIPPED:
                    return StepStatus.SKIPPED, "S09 skipped; S10 not required."
                elif parent.status in (StepStatus.FAILED, StepStatus.BLOCKED):
                    return StepStatus.BLOCKED, f"S09 ended in {parent.status.value}"
                else:
                    return StepStatus.WAITING, f"Awaiting S09 completion."

            # General Dependency Evaluation
            if parent.status == StepStatus.BLOCKED:
                has_blocked_dep = True
                blocking_reasons.append(f"Prerequisite {parent.step_code} is BLOCKED: {parent.blocking_reason or 'unknown reason'}")
            elif parent.status == StepStatus.FAILED:
                has_failed_dep = True
                blocking_reasons.append(f"Prerequisite {parent.step_code} FAILED: {parent.error_message or 'unspecified error'}")
            elif parent.status == StepStatus.SKIPPED:
                # SKIPPED satisfies a dependency only if skip_reason is recorded and policy allows
                if not parent.skip_reason:
                    has_blocked_dep = True
                    blocking_reasons.append(f"Prerequisite {parent.step_code} was skipped without a recorded reason.")
            elif parent.status != StepStatus.COMPLETED:
                has_waiting_dep = True

        if has_blocked_dep:
            return StepStatus.BLOCKED, "; ".join(blocking_reasons)
        if has_failed_dep:
            return StepStatus.BLOCKED, "; ".join(blocking_reasons)  # Propagates waiting/blocked without marking step itself failed
        if has_waiting_dep:
            return StepStatus.WAITING, "Awaiting prerequisite completion."

        return StepStatus.ELIGIBLE, None

    def recalculate_eligibility(self, task_id: str) -> Dict[str, StepStatus]:
        """
        Recalculates eligibility for all steps in the task, updating statuses in DB.
        Returns mapping of step_code -> current status.
        """
        steps = self.db.get_task_steps(task_id)
        step_map = {s.id: s for s in steps}
        step_code_map = {s.step_code: s for s in steps}
        results = {}

        for step in steps:
            # If already terminal or active, retain status
            if step.status in (StepStatus.COMPLETED, StepStatus.IN_PROGRESS, StepStatus.SKIPPED, StepStatus.FAILED, StepStatus.INVALIDATED):
                results[step.step_code] = step.status
                continue

            new_status, reason = self.evaluate_step_eligibility(step, step_map)
            if new_status != step.status:
                blocking_reason = reason if new_status == StepStatus.BLOCKED else None
                skip_reason = reason if new_status == StepStatus.SKIPPED else None
                self.db.update_step_status(
                    step_id=step.id,
                    status=new_status,
                    blocking_reason=blocking_reason,
                    skip_reason=skip_reason
                )
            results[step.step_code] = new_status

        # Synchronize task status
        self._sync_task_overall_status(task_id)
        return results

    def start_step(self, task_id: str, step_code: str) -> WorkflowStep:
        """
        Enters a step into IN_PROGRESS only if all dependencies are satisfied.
        Prevents concurrent execution on already running step.
        """
        with self._lock:
            step = self.db.get_step_by_code(task_id, step_code)
            if not step:
                raise ValueError(f"Step {step_code} not found for task {task_id}")

            if step.status == StepStatus.IN_PROGRESS:
                raise StepConcurrencyError(f"Step {step_code} is already IN_PROGRESS by another worker.")

            steps = self.db.get_task_steps(task_id)
            step_map = {s.id: s for s in steps}

            eligibility, reason = self.evaluate_step_eligibility(step, step_map)
            if eligibility not in (StepStatus.ELIGIBLE, StepStatus.IN_PROGRESS):
                raise DependencyViolationError(
                    f"Cannot start step {step_code}. Status is {eligibility.value}. Reason: {reason}"
                )

            updated_step = self.db.update_step_status(
                step_id=step.id,
                status=StepStatus.IN_PROGRESS
            )
            self.db.update_task_status(task_id, TaskStatus.IN_PROGRESS, current_step_code=step_code)
            return updated_step

    def complete_step(
        self,
        task_id: str,
        step_code: str,
        output_data: Optional[Dict[str, Any]] = None,
        execution_evidence: Optional[Dict[str, Any]] = None
    ) -> WorkflowStep:
        """
        Marks a step as COMPLETED with output data and execution evidence.
        Recalculates downstream eligibility.
        Syncs state to LangChain operational memory.
        """
        with self._lock:
            step = self.db.get_step_by_code(task_id, step_code)
            if not step:
                raise ValueError(f"Step {step_code} not found for task {task_id}")

            updated_step = self.db.update_step_status(
                step_id=step.id,
                status=StepStatus.COMPLETED,
                output_data=output_data,
                execution_evidence=execution_evidence
            )

            # Record in LangChain operational memory
            task = self.db.get_task(task_id)
            if task:
                global_memory_store.record_operational_memory(
                    user_id=task.user_id,
                    field_id=task.field_id,
                    category="workflow_step_completion",
                    content=f"Workflow step {step_code} ({step.name}) completed successfully.",
                    source_type=MemorySourceType.INFERRED_CONCLUSION,
                    metadata={"task_id": task_id, "step_code": step_code, "output_data": output_data or {}},
                    verified=True
                )

            self.recalculate_eligibility(task_id)
            return updated_step

    def fail_step(
        self,
        task_id: str,
        step_code: str,
        error_message: str,
        execution_evidence: Optional[Dict[str, Any]] = None
    ) -> WorkflowStep:
        """
        Marks a step as FAILED with error details.
        Propagates blocked condition to downstream steps without falsely failing them.
        """
        with self._lock:
            step = self.db.get_step_by_code(task_id, step_code)
            if not step:
                raise ValueError(f"Step {step_code} not found for task {task_id}")

            updated_step = self.db.update_step_status(
                step_id=step.id,
                status=StepStatus.FAILED,
                error_message=error_message,
                execution_evidence=execution_evidence
            )

            # Record in LangChain memory
            task = self.db.get_task(task_id)
            if task:
                global_memory_store.record_operational_memory(
                    user_id=task.user_id,
                    field_id=task.field_id,
                    category="workflow_step_failure",
                    content=f"Workflow step {step_code} ({step.name}) failed: {error_message}",
                    source_type=MemorySourceType.INFERRED_CONCLUSION,
                    metadata={"task_id": task_id, "step_code": step_code, "error": error_message},
                    verified=False
                )

            self.recalculate_eligibility(task_id)
            return updated_step

    def skip_step(
        self,
        task_id: str,
        step_code: str,
        skip_reason: str,
        approved_by_policy: bool = False
    ) -> WorkflowStep:
        """
        Skips a step only if genuine justification is recorded and permitted by policy.
        """
        with self._lock:
            if not approved_by_policy and step_code not in SKIPPABLE_POLICY:
                raise DependencyViolationError(
                    f"Step {step_code} cannot be skipped under policy. Policy requires explicit execution."
                )

            if not skip_reason or len(skip_reason.strip()) < 5:
                raise DependencyViolationError(
                    f"Skip reason required for step {step_code}. Must be documented and justified."
                )

            step = self.db.get_step_by_code(task_id, step_code)
            if not step:
                raise ValueError(f"Step {step_code} not found for task {task_id}")

            updated_step = self.db.update_step_status(
                step_id=step.id,
                status=StepStatus.SKIPPED,
                skip_reason=skip_reason
            )

            self.recalculate_eligibility(task_id)
            return updated_step

    def invalidate_downstream(self, task_id: str, from_step_code: str, invalidation_reason: str) -> List[str]:
        """
        If an upstream step changes or is re-executed, invalidates all downstream results
        that are no longer trustworthy. Resets them to PENDING/WAITING.
        """
        with self._lock:
            steps = self.db.get_task_steps(task_id)
            step_map = {s.id: s for s in steps}
            code_to_step = {s.step_code: s for s in steps}

            if from_step_code not in code_to_step:
                raise ValueError(f"Step {from_step_code} not found")

            # Find all downstream dependents via BFS/DFS
            adj: Dict[str, List[str]] = {s.id: [] for s in steps}
            for s in steps:
                for dep in s.dependencies:
                    adj[dep.depends_on_step_id].append(s.id)

            start_id = code_to_step[from_step_code].id
            visited: Set[str] = set()
            queue = [start_id]
            invalidated_codes = []

            while queue:
                curr = queue.pop(0)
                for downstream_id in adj.get(curr, []):
                    if downstream_id not in visited:
                        visited.add(downstream_id)
                        queue.append(downstream_id)

            for step_id in visited:
                step = step_map[step_id]
                # Invalidate if it had completed, in_progress, failed, or skipped
                if step.status != StepStatus.PENDING:
                    self.db.update_step_status(
                        step_id=step.id,
                        status=StepStatus.INVALIDATED,
                        error_message=f"Invalidated due to change in upstream {from_step_code}: {invalidation_reason}"
                    )
                    invalidated_codes.append(step.step_code)

            self.db.record_event(
                task_id=task_id,
                event_type=EventType.DOWNSTREAM_INVALIDATED,
                payload={
                    "from_step": from_step_code,
                    "reason": invalidation_reason,
                    "invalidated_steps": invalidated_codes
                }
            )

            self.recalculate_eligibility(task_id)
            return invalidated_codes

    def record_decision(self, task_id: str, decision_data: Dict[str, Any], step_code: str = "S04") -> WorkflowStep:
        """
        Records user decision or clarification at S04 (e.g., continue prior task, review, or start new).
        Unblocks S05 and downstream steps.
        """
        step = self.db.get_step_by_code(task_id, step_code)
        if not step:
            raise ValueError(f"Step {step_code} not found")

        self.db.record_event(
            task_id=task_id,
            step_id=step.id,
            event_type=EventType.DECISION_RECORDED,
            payload=decision_data
        )

        # Complete S04 with decision
        return self.complete_step(task_id, step_code, output_data=decision_data)

    def trigger_remediation(self, task_id: str, failure_diagnosis: Dict[str, Any]) -> WorkflowStep:
        """
        Conditional Remediation (S10):
        Triggered when S09 has failures. Diagnoses and resolves failures,
        then resets S09 for revalidation before S11 can be entered.
        """
        with self._lock:
            s09 = self.db.get_step_by_code(task_id, "S09")
            s10 = self.db.get_step_by_code(task_id, "S10")

            if not s09 or not s10:
                raise ValueError("S09 or S10 step missing in workflow")

            # Start S10
            self.db.update_step_status(s10.id, StepStatus.IN_PROGRESS)

            # Complete S10 with remediation record
            completed_s10 = self.db.update_step_status(
                step_id=s10.id,
                status=StepStatus.COMPLETED,
                output_data=failure_diagnosis,
                execution_evidence={"remediation_applied": True, "diagnosed_at": datetime.now(timezone.utc).isoformat()}
            )

            self.db.record_event(
                task_id=task_id,
                step_id=s10.id,
                event_type=EventType.REMEDIATION_TRIGGERED,
                payload=failure_diagnosis
            )

            # Reset S09 for rerun of validation checks
            self.db.update_step_status(
                step_id=s09.id,
                status=StepStatus.ELIGIBLE,
                skip_reason=None,
                error_message=None
            )

            self.recalculate_eligibility(task_id)
            return completed_s10

    def finalize_task(self, task_id: str, final_outcome: Dict[str, Any]) -> AITask:
        """
        Persists final outcome (S12/S13) and updates task overall status.
        """
        steps = self.db.get_task_steps(task_id)
        step_code_map = {s.step_code: s for s in steps}

        # Check S11 completeness
        s11 = step_code_map.get("S11")
        if not s11 or s11.status != StepStatus.COMPLETED:
            raise DependencyViolationError("Cannot finalize task: S11 (Review Requirement Completeness) must be COMPLETED.")

        # Complete S12
        self.complete_step(task_id, "S12", output_data=final_outcome)
        # Complete S13
        self.complete_step(task_id, "S13", output_data={"reported": True, "summary": final_outcome.get("summary")})

        task = self.db.get_task(task_id)
        task_status = TaskStatus.COMPLETED if final_outcome.get("success", True) else TaskStatus.FAILED
        self.db.update_task_status(task_id, task_status, current_step_code="S13", final_outcome=final_outcome)
        return self.db.get_task(task_id)

    def _sync_task_overall_status(self, task_id: str) -> None:
        task = self.db.get_task(task_id)
        if not task or task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
            return

        steps = self.db.get_task_steps(task_id)
        if any(s.status == StepStatus.IN_PROGRESS for s in steps):
            new_task_status = TaskStatus.IN_PROGRESS
        elif any(s.status == StepStatus.BLOCKED for s in steps):
            new_task_status = TaskStatus.BLOCKED
        elif any(s.step_code == "S04" and s.status in (StepStatus.WAITING, StepStatus.ELIGIBLE) for s in steps):
            new_task_status = TaskStatus.WAITING_FOR_DECISION
        else:
            new_task_status = TaskStatus.IN_PROGRESS if any(s.status == StepStatus.COMPLETED for s in steps) else TaskStatus.PENDING

        if new_task_status != task.status:
            self.db.update_task_status(task_id, new_task_status)


# Global singleton engine instance
global_workflow_dependency_engine = WorkflowDependencyEngine()
