"""Finance worker scaffold."""

from typing import Any, Dict


class FinanceWorker:
    """Executes finance-oriented tasks."""

    worker_id = "finance"

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        return {"worker": self.worker_id, "status": "accepted", "task": task}
