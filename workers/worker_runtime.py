"""Worker de runtime."""

from typing import Any, Dict

from executive_planner.audit import traduzir_status


class RuntimeWorker:
    """Executa tarefas orientadas ao dominio de runtime."""

    worker_id = "runtime"

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "worker": self.worker_id,
            "status": "accepted",
            "status_ptbr": traduzir_status("accepted"),
            "task": task,
        }
