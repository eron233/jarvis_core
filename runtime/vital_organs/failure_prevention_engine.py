"""
JARVIS - Motor de Prevencao de Falhas

Responsavel por:
- detectar sinais precoces de degradacao operacional
- observar watchdogs recorrentes e fluxo potencialmente travado
- materializar stores essenciais ausentes quando isso for seguro

Integracoes principais:
- runtime.internal_agent_runtime
- executive_planner.audit
- executive_planner.queue
- memory_system
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class FailurePreventionEngine:
    """Monitora indicadores precoces de falha e aplica correcoes seguras."""

    critical_paths: Dict[str, Path]
    stalled_cycle_threshold_seconds: float = 120.0

    def run(self, runtime: Any) -> Dict[str, Any]:
        """Executa deteccao preventiva de falhas silenciosas do runtime."""

        findings: List[Dict[str, Any]] = []
        auto_actions: List[Dict[str, Any]] = []
        runtime_state = runtime.describe_state()

        watchdog_events = [
            entry
            for entry in getattr(runtime.audit_logger, "entries", [])
            if entry.get("event") == "runtime_watchdog"
        ]
        if len(watchdog_events) >= 3:
            findings.append(
                {
                    "finding_id": "recurrent_runtime_watchdog",
                    "severity": "high",
                    "message": "Excecoes recorrentes do watchdog foram observadas no runtime.",
                    "total_eventos": len(watchdog_events),
                }
            )

        queue_depth = int(runtime_state.get("queue_depth") or 0)
        if queue_depth > 0 and runtime.last_cycle_at:
            elapsed = self._seconds_since(runtime.last_cycle_at)
            if elapsed is not None and elapsed > self.stalled_cycle_threshold_seconds:
                findings.append(
                    {
                        "finding_id": "stalled_flow_with_pending_queue",
                        "severity": "high",
                        "message": "Ha tarefas pendentes sem progresso recente do loop principal.",
                        "queue_depth": queue_depth,
                        "segundos_sem_ciclo": elapsed,
                    }
                )

        missing_paths = [label for label, path in self.critical_paths.items() if not path.exists()]
        if missing_paths:
            auto_actions.extend(self._materialize_missing_paths(runtime, missing_paths))

        status = "saudavel"
        if any(item["severity"] == "high" for item in findings):
            status = "critico"
        elif findings or auto_actions:
            status = "atencao"

        return {
            "organ_id": "failure_prevention_engine",
            "status": status,
            "executado_em": runtime._utc_now(),
            "achados": findings,
            "acoes_aplicadas": auto_actions,
            "resumo": {
                "total_achados": len(findings),
                "total_acoes_aplicadas": len(auto_actions),
                "queue_depth_observado": queue_depth,
                "watchdog_events_observados": len(watchdog_events),
            },
        }

    def _materialize_missing_paths(self, runtime: Any, missing_labels: List[str]) -> List[Dict[str, Any]]:
        """Executa a rotina interna de materialize missing paths."""
        actions: List[Dict[str, Any]] = []

        queue_path = self.critical_paths.get("queue_storage_path")
        if "queue_storage_path" in missing_labels and runtime.task_queue is not None and queue_path is not None:
            runtime.task_queue.save_to_disk()
            actions.append(self._action("queue_storage_path", queue_path))

        semantic_path = self.critical_paths.get("semantic_storage_path")
        semantic_memory = runtime.memory.get("semantic") if runtime.memory else None
        if "semantic_storage_path" in missing_labels and semantic_memory is not None and semantic_path is not None:
            semantic_memory.snapshot()
            actions.append(self._action("semantic_storage_path", semantic_path))

        procedural_path = self.critical_paths.get("procedural_storage_path")
        procedural_memory = runtime.memory.get("procedural") if runtime.memory else None
        if "procedural_storage_path" in missing_labels and procedural_memory is not None and procedural_path is not None:
            procedural_memory.snapshot()
            actions.append(self._action("procedural_storage_path", procedural_path))

        goals_path = self.critical_paths.get("goals_storage_path")
        if "goals_storage_path" in missing_labels and runtime.goal_manager is not None and goals_path is not None:
            runtime.goal_manager.save()
            actions.append(self._action("goals_storage_path", goals_path))

        device_path = self.critical_paths.get("device_registry_path")
        if "device_registry_path" in missing_labels and runtime.device_registry is not None and device_path is not None:
            runtime.device_registry.save()
            actions.append(self._action("device_registry_path", device_path))

        cognitive_path = self.critical_paths.get("cognitive_evolution_storage_path")
        if (
            "cognitive_evolution_storage_path" in missing_labels
            and runtime.cognitive_evolution_tracker is not None
            and cognitive_path is not None
        ):
            runtime.cognitive_evolution_tracker.snapshot()
            actions.append(self._action("cognitive_evolution_storage_path", cognitive_path))

        audit_path = self.critical_paths.get("audit_storage_path")
        if "audit_storage_path" in missing_labels and runtime.audit_logger is not None and audit_path is not None:
            runtime.audit_logger.save_to_disk()
            actions.append(self._action("audit_storage_path", audit_path))

        self_defense_path = self.critical_paths.get("self_defense_report_path")
        if (
            "self_defense_report_path" in missing_labels
            and runtime.self_defense_monitor is not None
            and self_defense_path is not None
        ):
            runtime.self_defense_monitor.run_periodic_audit(
                runtime=runtime,
                environment_report={},
                health_report=runtime.build_health_report(
                    api_started_at=runtime.started_at,
                    token_configurado=True,
                    dispositivo_confiavel_configurado=True,
                ),
                auto_apply_safe=False,
            )
            actions.append(self._action("self_defense_report_path", self_defense_path))

        return actions

    @staticmethod
    def _action(label: str, path: Path) -> Dict[str, Any]:
        """Executa a rotina interna de action."""
        return {
            "action_id": f"materialize_{label}",
            "status": "applied",
            "message": f"Arquivo critico recriado com seguranca em {path}.",
            "path": str(path),
            "reversivel": True,
        }

    @staticmethod
    def _seconds_since(timestamp: str) -> float | None:
        """Executa a rotina interna de seconds since."""
        try:
            moment = datetime.fromisoformat(timestamp)
        except ValueError:
            return None

        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - moment.astimezone(timezone.utc)).total_seconds()
