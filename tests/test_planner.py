"""Unit tests for the minimal executive planner."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from executive_planner.audit import AuditLogger
from executive_planner.planner import run_planner_cycle
from executive_planner.queue import TaskQueue


def queue_snapshot(task_queue: TaskQueue) -> list[str]:
    return [str(task.get("task_id")) for task in task_queue.items]


class ExecutivePlannerCycleTests(unittest.TestCase):
    def test_run_planner_cycle_executes_highest_priority_task(self) -> None:
        task_queue = TaskQueue()
        audit_logger = AuditLogger()

        task_queue.enqueue({"task_id": "task-low", "goal": "Low priority task", "importance": 1, "urgency": 1})
        task_queue.enqueue({"task_id": "task-high", "goal": "High priority task", "importance": 3, "urgency": 5})

        result = run_planner_cycle(task_queue=task_queue, audit_logger=audit_logger)

        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["selected_task"]["task_id"], "task-high")
        self.assertEqual(queue_snapshot(task_queue), ["task-low"])

        phases = [entry["event"] for entry in audit_logger.entries]
        self.assertEqual(phases, ["plan", "prioritize", "prioritize", "validate", "validate", "schedule", "schedule", "execute", "review"])

    def test_run_planner_cycle_skips_invalid_and_blocked_tasks(self) -> None:
        task_queue = TaskQueue()
        audit_logger = AuditLogger()

        task_queue.enqueue({"task_id": "task-invalid", "importance": 5, "urgency": 5})
        task_queue.enqueue(
            {
                "task_id": "task-blocked",
                "goal": "Needs supervision",
                "importance": 4,
                "urgency": 0,
                "requires_supervision": True,
                "approved": False,
            }
        )
        task_queue.enqueue({"task_id": "task-ready", "goal": "Ready task", "importance": 1, "urgency": 1})

        result = run_planner_cycle(task_queue=task_queue, audit_logger=audit_logger)

        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["selected_task"]["task_id"], "task-ready")
        self.assertEqual(len(result["rejected_tasks"]), 1)
        self.assertEqual(result["rejected_tasks"][0]["task"]["task_id"], "task-invalid")
        self.assertEqual(queue_snapshot(task_queue), ["task-blocked"])

        schedule_entries = [entry for entry in audit_logger.entries if entry["event"] == "schedule"]
        self.assertEqual(schedule_entries[0]["payload"]["decision"], "blocked")
        self.assertEqual(schedule_entries[0]["payload"]["task_id"], "task-blocked")

    def test_run_planner_cycle_is_idle_when_queue_is_empty(self) -> None:
        task_queue = TaskQueue()
        audit_logger = AuditLogger()

        result = run_planner_cycle(task_queue=task_queue, audit_logger=audit_logger)

        self.assertEqual(result["status"], "idle")
        self.assertIsNone(result["selected_task"])
        self.assertEqual(queue_snapshot(task_queue), [])
        self.assertEqual([entry["event"] for entry in audit_logger.entries], ["plan", "review"])


if __name__ == "__main__":
    unittest.main()
