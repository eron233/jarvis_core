"""Worker de estudio."""

from typing import Any, Dict

from executive_planner.audit import traduzir_status


class StudioWorker:
    """Executa tarefas orientadas ao dominio de estudio e criacao."""

    worker_id = "studio"

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "worker": self.worker_id,
            "status": "accepted",
            "status_ptbr": traduzir_status("accepted"),
            "task": task,
        }
