"""Unit tests for the first JARVIS runtime bootstrap."""

from pathlib import Path
import sys
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from runtime.internal_agent_runtime import InternalAgentRuntime


class RuntimeBootstrapTests(unittest.TestCase):
    def test_bootstrap_initializes_core_runtime_components(self) -> None:
        runtime = InternalAgentRuntime()

        state = runtime.bootstrap()

        self.assertEqual(state["status"], "initialized")
        self.assertEqual(state["planner"], "executive_planner.planner.ExecutivePlanner")
        self.assertEqual(state["memory"], "memory_system")
        self.assertEqual(state["memory_modules"], ["episodic", "semantic", "procedural"])
        self.assertEqual(
            state["workers"],
            ["worker_runtime", "worker_finance", "worker_studio", "worker_study"],
        )
        self.assertEqual(state["queue_depth"], 0)
        self.assertIsNotNone(runtime.planner)
        self.assertIs(runtime.planner.runtime, runtime)
        self.assertEqual(runtime.memory["semantic"].get("runtime_status"), "initialized")
        self.assertEqual(
            runtime.memory["procedural"].get("planner_cycle"),
            ["plan", "prioritize", "validate", "schedule", "execute", "review"],
        )
        self.assertEqual(runtime.memory["episodic"].recent(1)[0]["event"], "bootstrap")

    def test_bootstrapped_runtime_runs_one_planner_cycle(self) -> None:
        runtime = InternalAgentRuntime()
        runtime.bootstrap()
        runtime.enqueue_task(
            {
                "task_id": "finance-1",
                "goal": "Review cash flow",
                "worker": "worker_finance",
                "importance": 3,
                "urgency": 2,
            }
        )

        result = runtime.run_planner_cycle()

        self.assertEqual(result["status"], "executed")
        self.assertEqual(result["selected_task"]["task_id"], "finance-1")
        self.assertEqual(result["dispatch_result"]["worker"], "finance")
        self.assertEqual(result["dispatch_result"]["worker_response"]["worker"], "finance")
        self.assertEqual(runtime.describe_state()["queue_depth"], 0)
        self.assertEqual(runtime.memory["episodic"].recent(1)[0]["event"], "dispatch")

        semantic_results = runtime.query_semantic_memory("cash flow completed", domain="finance")
        self.assertEqual(len(semantic_results), 1)
        self.assertEqual(semantic_results[0]["metadata"]["task_id"], "finance-1")
        self.assertEqual(semantic_results[0]["domain"], "finance")


if __name__ == "__main__":
    unittest.main()
