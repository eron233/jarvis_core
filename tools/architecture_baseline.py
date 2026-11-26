"""Baseline local de componentes Python; dados sinteticos, sem rede ou telemetria externa."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import platform
import statistics
import sys
import tempfile
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]


def measure(fn, repeats: int) -> dict:
    if repeats < 1:
        raise ValueError("repeticoes invalidas")
    expected = fn()  # aquecimento, fora das amostras
    elapsed, cpu = [], []
    for _ in range(repeats):
        start, cpu_start = time.perf_counter_ns(), time.process_time_ns()
        value = fn()
        cpu.append((time.process_time_ns() - cpu_start) / 1e6)
        elapsed.append((time.perf_counter_ns() - start) / 1e6)
        if value != expected:
            raise RuntimeError("resultado nao deterministico")
    # Memoria em passada separada: tracemalloc altera tempos de execucao.
    tracemalloc.start()
    try:
        if fn() != expected:
            raise RuntimeError("resultado nao deterministico")
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {"wall_ms_samples": elapsed, "wall_ms_median": statistics.median(elapsed),
            "cpu_ms_median": statistics.median(cpu), "python_heap_peak_bytes": peak,
            "checksum": expected}


def run(count: int, repeats: int) -> dict:
    if not 1 <= count <= 10000 or not 1 <= repeats <= 20:
        raise ValueError("limites: 1..10000 tarefas, 1..20 repeticoes")
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from executive_planner.prioritizer import Prioritizer
    from executive_planner.queue import TaskQueue

    tasks = [{"task_id": str(i + 1), "goal": "synthetic", "urgency": i % 10,
              "impact": (i * 3) % 10, "goal_priority": i % 5} for i in range(count)]
    ranker = Prioritizer()

    def rank():
        return sum(ranker.score(task) for task in tasks)

    # A fila persiste o snapshot completo a cada mutacao; limitar IO do piloto.
    disk_count = min(count, 100)
    def queue(persist: bool):
        n = disk_count if persist else count
        with tempfile.TemporaryDirectory(prefix="iris-baseline-") as d:
            fifo = TaskQueue(storage_path=Path(d) / "queue.json", auto_persist=persist)
            for task in tasks[:n]:
                fifo.enqueue(task)
            for task in tasks[:n]:
                popped = fifo.dequeue()
                if popped is None or popped["task_id"] != task["task_id"]:
                    raise RuntimeError("ordem FIFO incorreta")
            return n

    return {
        "scope": "synthetic_microbenchmark_not_full_runtime",
        "python": platform.python_version(), "os": platform.system(),
        "architecture": platform.machine(), "repeats": repeats,
        "tasks": count, "disk_tasks": disk_count,
        "priority": measure(rank, repeats),
        "queue_memory": measure(lambda: queue(False), repeats),
        "queue_json_persistence": measure(lambda: queue(True), repeats),
        "limitations": "Python heap only, not RSS; disk workload capped at 100; no native comparison",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks", type=int, default=100)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(run(args.tasks, args.repeats), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
