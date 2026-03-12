"""Worker de estudo."""

from typing import Any, Dict

from executive_planner.audit import traduzir_status


class StudyWorker:
    """Executa tarefas orientadas ao dominio de estudo e aprendizado."""

    worker_id = "study"

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "worker": self.worker_id,
            "status": "accepted",
            "status_ptbr": traduzir_status("accepted"),
            "task": task,
        }
