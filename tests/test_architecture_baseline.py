import unittest
from tools.architecture_baseline import measure, run


class ArchitectureBaselineTests(unittest.TestCase):
    def test_measure_reports_samples_and_checksum(self):
        result = measure(lambda: 42, 2)
        self.assertEqual(result["checksum"], 42)
        self.assertEqual(len(result["wall_ms_samples"]), 2)
        self.assertGreaterEqual(result["python_heap_peak_bytes"], 0)

    def test_non_deterministic_workload_is_rejected(self):
        values = iter([1, 2])
        with self.assertRaises(RuntimeError):
            measure(lambda: next(values), 1)

    def test_tiny_real_workload(self):
        result = run(3, 1)
        self.assertEqual(result["queue_memory"]["checksum"], 3)
        self.assertEqual(result["queue_json_persistence"]["checksum"], 3)
        self.assertEqual(result["priority"]["checksum"], 393)

    def test_invalid_bounds(self):
        with self.assertRaises(ValueError):
            run(0, 1)
