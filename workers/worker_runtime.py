"""Worker de runtime."""

from typing import Any, Dict

from workers.worker_utils import build_domain_rejection, build_success_response, domain_is_valid


class RuntimeWorker:
    """Executa tarefas orientadas ao dominio de runtime."""

    worker_id = "runtime"
    allowed_domains = ["runtime", "system", "general"]

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not domain_is_valid(task, self.allowed_domains):
            return build_domain_rejection(self.worker_id, task, self.allowed_domains)

        runtime_context = task.get("runtime_context", {})
        technical_report = {
            "status_runtime": runtime_context.get("status_ptbr", "desconhecido"),
            "fila_atual": runtime_context.get("queue_depth", 0),
            "objetivos_ativos": runtime_context.get("active_goal_count", 0),
            "ciclos_executados": runtime_context.get("total_cycles_executed", 0),
            "politica_constitucional_carregada": runtime_context.get("politica_constitucional_carregada", False),
        }
        evidence = [
            f"fila={technical_report['fila_atual']}",
            f"objetivos_ativos={technical_report['objetivos_ativos']}",
            f"ciclos_executados={technical_report['ciclos_executados']}",
        ]
        summary = (
            f"Runtime em {technical_report['status_runtime']} com fila {technical_report['fila_atual']} "
            f"e {technical_report['objetivos_ativos']} objetivo(s) ativo(s)."
        )
        next_steps = [
            "revisar relatorio operacional atual",
            "confirmar gargalos da fila",
            "persistir diagnostico se houver anomalia",
        ]
        return build_success_response(
            worker_id=self.worker_id,
            task=task,
            result_type="runtime_report",
            summary=summary,
            details={"technical_report": technical_report},
            evidence=evidence,
            next_steps=next_steps,
        )
