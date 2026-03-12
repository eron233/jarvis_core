"""Orquestracao de alto nivel do planejador executivo do JARVIS."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from executive_planner.audit import (
    AuditLogger,
    traduzir_estado,
    traduzir_motivo,
    traduzir_status,
)
from executive_planner.prioritizer import Prioritizer
from executive_planner.queue import TaskQueue
from executive_planner.validator import PlanValidator
from runtime.internal_agent_runtime import InternalAgentRuntime


class ExecutivePlanner:
    """Executa um ciclo deterministico e auditavel do planejador."""

    def __init__(
        self,
        task_queue: Optional[TaskQueue] = None,
        prioritizer: Optional[Prioritizer] = None,
        validator: Optional[PlanValidator] = None,
        audit_logger: Optional[AuditLogger] = None,
        runtime: Optional[InternalAgentRuntime] = None,
    ) -> None:
        self.task_queue = task_queue if task_queue is not None else TaskQueue()
        self.prioritizer = prioritizer if prioritizer is not None else Prioritizer()
        self.validator = validator if validator is not None else PlanValidator()
        self.audit_logger = audit_logger if audit_logger is not None else AuditLogger()
        self.runtime = runtime if runtime is not None else InternalAgentRuntime()
        self.runtime.attach_planner(
            planner=self,
            task_queue=self.task_queue,
            prioritizer=self.prioritizer,
            validator=self.validator,
            audit_logger=self.audit_logger,
        )

    def create_plan(self, goal: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        return {
            "goal": goal,
            "context": context or {},
            "steps": [],
            "status": "draft",
            "status_ptbr": traduzir_status("draft"),
        }

    def run_cycle(self) -> Dict[str, Any]:
        tasks = self._load_tasks()
        cycle_summary: Dict[str, Any] = {
            "status": "idle",
            "status_ptbr": traduzir_status("idle"),
            "selected_task": None,
            "dispatch_result": None,
            "rejected_tasks": [],
            "deferred_tasks": [],
            "reason": "no_tasks",
            "reason_ptbr": traduzir_motivo("no_tasks"),
        }

        if not tasks:
            self.audit_logger.record("review", {"status": "idle", "reason": "no_tasks"})
            return cycle_summary

        ranked_tasks = self._rank_tasks(tasks)
        valid_tasks, rejected_tasks = self._validate_tasks(ranked_tasks)
        selected_task, deferred_tasks = self._schedule_task(valid_tasks)
        dispatch_result = self._execute_task(selected_task)
        self._requeue_tasks(deferred_tasks)

        cycle_status = dispatch_result["status"] if dispatch_result else "idle"
        cycle_reason = dispatch_result.get("reason") if dispatch_result else "no_executable_task"

        cycle_summary = {
            "status": cycle_status,
            "status_ptbr": traduzir_status(cycle_status),
            "selected_task": selected_task["task"] if selected_task else None,
            "dispatch_result": dispatch_result,
            "rejected_tasks": rejected_tasks,
            "deferred_tasks": deferred_tasks,
            "reason": cycle_reason,
            "reason_ptbr": traduzir_motivo(cycle_reason) if cycle_reason else None,
        }

        self.audit_logger.record(
            "review",
            {
                "status": cycle_summary["status"],
                "selected_task_id": self._task_id(cycle_summary["selected_task"]),
                "rejected_count": len(rejected_tasks),
                "deferred_count": len(deferred_tasks),
            },
        )
        return cycle_summary

    def _load_tasks(self) -> List[Dict[str, Any]]:
        tasks = self.task_queue.drain()

        self.audit_logger.record(
            "plan",
            {
                "task_count": len(tasks),
                "task_ids": [self._task_id(task) for task in tasks],
            },
        )
        return tasks

    def _rank_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        ranked_tasks: List[Dict[str, Any]] = []

        for position, task in enumerate(tasks):
            score = self.prioritizer.score(task)
            ranked_tasks.append(
                {
                    "task": task,
                    "score": score,
                    "position": position,
                }
            )
            self.audit_logger.record(
                "prioritize",
                {
                    "task_id": self._task_id(task),
                    "score": score,
                    "position": position,
                },
            )

        ranked_tasks.sort(key=lambda item: (-item["score"], item["position"]))
        return ranked_tasks

    def _validate_tasks(
        self, ranked_tasks: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        valid_tasks: List[Dict[str, Any]] = []
        rejected_tasks: List[Dict[str, Any]] = []

        for candidate in ranked_tasks:
            is_valid, issues = self.validator.validate_task(candidate["task"])
            self.audit_logger.record(
                "validate",
                {
                    "task_id": self._task_id(candidate["task"]),
                    "valid": is_valid,
                    "issues": issues,
                    "score": candidate["score"],
                },
            )

            if is_valid:
                valid_tasks.append(candidate)
                continue

            candidate["task"]["state"] = "rejected"
            candidate["task"]["state_ptbr"] = traduzir_estado("rejected")
            rejected_tasks.append(
                {
                    "task": candidate["task"],
                    "score": candidate["score"],
                    "issues": issues,
                }
            )

        return valid_tasks, rejected_tasks

    def _schedule_task(
        self, valid_tasks: List[Dict[str, Any]]
    ) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
        selected_task: Optional[Dict[str, Any]] = None
        deferred_tasks: List[Dict[str, Any]] = []

        for candidate in valid_tasks:
            task = candidate["task"]

            if selected_task is None and self.runtime.can_execute(task):
                task["state"] = "scheduled"
                task["state_ptbr"] = traduzir_estado("scheduled")
                selected_task = candidate
                self.audit_logger.record(
                    "schedule",
                    {
                        "task_id": self._task_id(task),
                        "decision": "selected",
                        "score": candidate["score"],
                    },
                )
                continue

            decision = "deferred"
            if selected_task is None:
                decision = "blocked"

            task["state"] = decision
            task["state_ptbr"] = traduzir_estado(decision)
            deferred_tasks.append(task)
            self.audit_logger.record(
                "schedule",
                {
                    "task_id": self._task_id(task),
                    "decision": decision,
                    "score": candidate["score"],
                },
            )

        return selected_task, deferred_tasks

    def _execute_task(self, selected_task: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if selected_task is None:
            self.audit_logger.record(
                "execute",
                {
                    "status": "idle",
                    "reason": "no_executable_task",
                },
            )
            return None

        selected_task["task"]["state"] = "executing"
        selected_task["task"]["state_ptbr"] = traduzir_estado("executing")
        dispatch_result = self.runtime.dispatch_task(selected_task["task"])
        self.audit_logger.record(
            "execute",
            {
                "task_id": self._task_id(selected_task["task"]),
                "status": dispatch_result["status"],
            },
        )
        return dispatch_result

    def _requeue_tasks(self, deferred_tasks: List[Dict[str, Any]]) -> None:
        for task in deferred_tasks:
            self.task_queue.enqueue(task)

    @staticmethod
    def _task_id(task: Optional[Dict[str, Any]]) -> Optional[str]:
        if task is None:
            return None
        task_id = task.get("task_id")
        if task_id is None:
            return None
        return str(task_id)


def run_planner_cycle(
    task_queue: Optional[TaskQueue] = None,
    prioritizer: Optional[Prioritizer] = None,
    validator: Optional[PlanValidator] = None,
    audit_logger: Optional[AuditLogger] = None,
    runtime: Optional[InternalAgentRuntime] = None,
) -> Dict[str, Any]:
    """Executa um unico ciclo deterministico do planejador."""

    planner = ExecutivePlanner(
        task_queue=task_queue,
        prioritizer=prioritizer,
        validator=validator,
        audit_logger=audit_logger,
        runtime=runtime,
    )
    return planner.run_cycle()
