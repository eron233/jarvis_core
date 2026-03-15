"""
JARVIS - Runtime Interno

Responsavel por:
- inicializar planner, memoria, workers e objetivos
- despachar tarefas com gate constitucional e de autonomia
- persistir estado operacional, relatorios e eventos de acesso
- servir como nucleo compartilhado entre loop, API e painel

Integracoes principais:
- executive_planner
- memory_system
- intent_layer.goal_manager
- interface.api.app
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
import logging
from threading import RLock
from typing import Any, Dict

#
# JARVIS_CORE_COMPONENT
# JARVIS_RUNTIME_ENTRYPOINT
# ==================================================
# BLOCO: Estado central e bootstrap do runtime
# ==================================================

from constitutional_core.policy import load_constitutional_policy
from executive_planner.audit import traduzir_estado, traduzir_motivo, traduzir_status
from runtime.cognitive_evolution import CognitiveEvolutionTracker
from runtime.runtime_identity import build_runtime_identity, load_build_metadata
from runtime.autonomy import AutonomyController

LOGGER = logging.getLogger("jarvis.server")


class InternalAgentRuntime:
    """Inicializa o runtime funcional do sistema e coordena a execucao basica."""

    def __init__(self, autonomy_controller: AutonomyController | None = None) -> None:
        """
        Inicializa o estado base do runtime antes do bootstrap completo.

        Parametros:
        - autonomy_controller: controlador opcional de autonomia supervisionada.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - cria o esqueleto do runtime, ainda sem componentes pesados carregados.
        """

        self.autonomy_controller = autonomy_controller or AutonomyController()
        self.status = "cold"
        self.started_at: str | None = None
        self.last_cycle_at: str | None = None
        self.last_cycle_result: Dict[str, Any] | None = None
        self.total_cycles_executed = 0
        self.goal_manager: Any = None
        self.task_queue: Any = None
        self.prioritizer: Any = None
        self.validator: Any = None
        self.audit_logger: Any = None
        self.planner: Any = None
        self.memory: Dict[str, Any] = {}
        self.workers: Dict[str, Any] = {}
        self.constitutional_policy: Any = None
        self.device_registry: Any = None
        self.access_control: Any = None
        self.self_defense_monitor: Any = None
        self.learning_advisor: Any = None
        self.last_self_defense_report: Dict[str, Any] | None = None
        self.cognitive_evolution_tracker: Any = None
        self.runtime_identity: Dict[str, Any] | None = None
        self._state_lock = RLock()
        self._request_nonces: Dict[str, str] = {}

    def attach_planner(
        self,
        planner: Any,
        task_queue: Any,
        prioritizer: Any,
        validator: Any,
        audit_logger: Any,
    ) -> None:
        """Compartilha com o runtime os componentes controlados pelo planner."""

        self.planner = planner
        self.task_queue = task_queue
        self.prioritizer = prioritizer
        self.validator = validator
        self.audit_logger = audit_logger

    def configure_runtime_identity(
        self,
        *,
        entrypoint: str,
        environment: Dict[str, Any] | None = None,
        loaded_config: Dict[str, Any] | None = None,
        build_metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Configura a identidade verificavel do runtime atual."""

        with self._state_lock:
            if self.runtime_identity is None:
                self.runtime_identity = build_runtime_identity(
                    entrypoint=entrypoint,
                    environment=deepcopy(environment or {}),
                    loaded_config=deepcopy(loaded_config or {}),
                )
                if build_metadata is not None:
                    self.runtime_identity.update(deepcopy(build_metadata))
            else:
                self.runtime_identity["entrypoint"] = entrypoint
                if environment is not None:
                    self.runtime_identity["environment"] = deepcopy(environment)
                if loaded_config is not None:
                    self.runtime_identity["configuracao_resumida"] = deepcopy(loaded_config)
                if build_metadata is not None:
                    self.runtime_identity.update(deepcopy(build_metadata))

            return deepcopy(self.runtime_identity)

    def build_runtime_identity_report(self) -> Dict[str, Any]:
        """Retorna a identidade completa do runtime em execucao."""

        with self._state_lock:
            if self.runtime_identity is None:
                self.runtime_identity = build_runtime_identity(
                    entrypoint="runtime.internal_agent_runtime.bootstrap",
                    environment={},
                    loaded_config={},
                )
                self.runtime_identity.update(load_build_metadata())
            return deepcopy(self.runtime_identity)

    def validate_request_replay(
        self,
        *,
        device_id: str,
        request_path: str,
        request_method: str,
        request_timestamp: str,
        request_nonce: str,
    ) -> tuple[bool, str | None]:
        """Registra e valida nonces de requests mutantes para reduzir replay simples."""

        with self._state_lock:
            nonce_key = f"{device_id}:{request_method}:{request_path}:{request_nonce}"
            if nonce_key in self._request_nonces:
                return False, "replay_detected"

            self._request_nonces[nonce_key] = request_timestamp
            if len(self._request_nonces) > 500:
                oldest_keys = list(self._request_nonces.keys())[:100]
                for key in oldest_keys:
                    self._request_nonces.pop(key, None)
            return True, None

    def bootstrap(self) -> Dict[str, Any]:
        """Inicializa o primeiro runtime funcional do sistema."""

        with self._state_lock:
            if self.status == "initialized":
                return self.describe_state()

            from executive_planner.audit import AuditLogger
            from executive_planner.planner import ExecutivePlanner
            from executive_planner.prioritizer import Prioritizer
            from executive_planner.queue import TaskQueue
            from executive_planner.validator import PlanValidator
            from intent_layer.goal_manager import GoalManager
            from memory_system.episodic_memory import EpisodicMemory
            from memory_system.procedural_memory import ProceduralMemory
            from memory_system.semantic_memory import SemanticMemory
            from device.device_registry import DeviceRegistry
            from learning.self_improvement import SelfImprovementAdvisor
            from security.access_control import AccessControl
            from security.self_defense import SelfDefenseMonitor
            from workers.worker_finance import FinanceWorker
            from workers.worker_runtime import RuntimeWorker
            from workers.worker_studio import StudioWorker
            from workers.worker_study import StudyWorker

            self.constitutional_policy = self.constitutional_policy or load_constitutional_policy()
            self.task_queue = self.task_queue if self.task_queue is not None else TaskQueue()
            if len(self.task_queue) == 0:
                self.task_queue.load_from_disk()
            self.task_queue.auto_persist_on_change(True)
            self.prioritizer = self.prioritizer if self.prioritizer is not None else Prioritizer()
            self.validator = self.validator if self.validator is not None else PlanValidator(policy=self.constitutional_policy)
            if hasattr(self.validator, "set_policy"):
                self.validator.set_policy(self.constitutional_policy)
            if hasattr(self.autonomy_controller, "set_policy"):
                self.autonomy_controller.set_policy(self.constitutional_policy)
            self.audit_logger = self.audit_logger if self.audit_logger is not None else AuditLogger()
            if not self.audit_logger.entries:
                self.audit_logger.load_snapshot()
            self.audit_logger.auto_persist_on_change(True)
            self.goal_manager = self.goal_manager if self.goal_manager is not None else GoalManager()
            self.device_registry = self.device_registry if self.device_registry is not None else DeviceRegistry()
            self.access_control = self.access_control if self.access_control is not None else AccessControl.from_env()
            self.self_defense_monitor = (
                self.self_defense_monitor if self.self_defense_monitor is not None else SelfDefenseMonitor()
            )
            self.learning_advisor = (
                self.learning_advisor if self.learning_advisor is not None else SelfImprovementAdvisor()
            )
            tracker_was_preconfigured = self.cognitive_evolution_tracker is not None
            self.cognitive_evolution_tracker = (
                self.cognitive_evolution_tracker
                if self.cognitive_evolution_tracker is not None
                else CognitiveEvolutionTracker(storage_path=None, auto_persist=False)
            )

            if not self.memory:
                self.memory = {}

            self.memory.setdefault("episodic", EpisodicMemory())
            self.memory.setdefault("semantic", SemanticMemory())
            self.memory.setdefault("procedural", ProceduralMemory())

            semantic_memory = self.memory["semantic"]
            procedural_memory = self.memory["procedural"]
            if not semantic_memory.entries and not semantic_memory.facts:
                semantic_memory.load_snapshot()
            semantic_memory.auto_persist = True
            if not procedural_memory.procedures:
                procedural_memory.load_snapshot()
            procedural_memory.auto_persist = True
            if not self.cognitive_evolution_tracker.events:
                self.cognitive_evolution_tracker.load_snapshot()
            self.cognitive_evolution_tracker.auto_persist = tracker_was_preconfigured

            if not self.workers:
                self.workers = {
                    "runtime": RuntimeWorker(),
                    "finance": FinanceWorker(),
                    "studio": StudioWorker(),
                    "study": StudyWorker(),
                }

            if self.planner is None:
                self.planner = ExecutivePlanner(
                    task_queue=self.task_queue,
                    prioritizer=self.prioritizer,
                    validator=self.validator,
                    audit_logger=self.audit_logger,
                    runtime=self,
                )

            self.memory["semantic"].upsert(
                "runtime_status",
                "inicializado",
                domain="system",
                tags=["runtime", "estado"],
                source="runtime.bootstrap",
                importance=5,
                metadata={"status": "initialized", "status_ptbr": "inicializado"},
            )
            self.memory["semantic"].upsert(
                "registered_workers",
                list(self.workers),
                domain="system",
                tags=["runtime", "workers"],
                source="runtime.bootstrap",
                importance=4,
                metadata={"worker_ids": list(self.workers)},
            )
            self.memory["semantic"].upsert(
                "active_goals",
                [goal["goal_id"] for goal in self.goal_manager.list_active_goals()],
                domain="intent",
                tags=["objetivos", "ativos"],
                source="runtime.bootstrap",
                importance=3,
                metadata={"goal_count": len(self.goal_manager.list_active_goals())},
            )
            self.memory["semantic"].upsert(
                "constitutional_operating_mode",
                self.constitutional_policy.identity.get("operating_mode"),
                domain="system",
                tags=["constitucional", "politica", "autonomia"],
                source="runtime.bootstrap",
                importance=5,
                metadata={"modo_autonomia": "supervisionada_por_politica_constitucional"},
            )
            self.memory["semantic"].upsert(
                "trusted_devices",
                [device["device_id"] for device in self.device_registry.list_devices(trusted_only=True)],
                domain="system",
                tags=["dispositivos", "trusted"],
                source="runtime.bootstrap",
                importance=4,
                metadata={
                    "device_count": self.device_registry.snapshot()["trusted_device_count"],
                    "registry_path": str(self.device_registry.storage_path),
                },
            )
            self.memory["procedural"].register(
                "planner_cycle",
                ["planejar", "priorizar", "validar", "agendar", "executar", "revisar"],
                domain="system",
                task_type="planner_cycle",
                heuristic="Seguir a ordem deterministica do planner e registrar todas as decisoes.",
                observed_result="ciclo_base_registrado",
                success=True,
                metadata={"source": "runtime.bootstrap"},
            )
            self.memory["episodic"].remember(
                {
                    "event": "bootstrap",
                    "event_ptbr": "inicializar",
                    "status": "initialized",
                    "status_ptbr": "inicializado",
                    "planner": self._planner_path(),
                    "worker_count": len(self.workers),
                    "politica_constitucional": self.constitutional_policy.identity.get("operating_mode"),
                }
            )
            self._record_cognitive_evolution_event(
                event_type="EVENT_NETWORK_RESTRUCTURE",
                region="runtime",
                connections_created=len(self.workers),
                connections_strengthened=len(self.memory),
                estimated_cognitive_impact=0.82,
                metadata={
                    "source": "runtime.bootstrap",
                    "workers": list(self.workers),
                    "memory_modules": list(self.memory),
                },
            )

            if self.started_at is None:
                self.started_at = self._utc_now()
            self.status = "initialized"
            if self.runtime_identity is None:
                self.configure_runtime_identity(
                    entrypoint="runtime.internal_agent_runtime.bootstrap",
                    environment={},
                    loaded_config={},
                    build_metadata=load_build_metadata(),
                )
            return self.describe_state()

    def can_execute(self, task: Dict[str, Any]) -> bool:
        """Retorna se a tarefa pode ser executada de forma deterministica agora."""

        return self.autonomy_controller.should_execute(task)

    def evaluate_task_execution(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Explica a decisao de autonomia para a tarefa atual."""

        self.bootstrap()
        return self.autonomy_controller.evaluate(task)

    def dispatch_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Executa uma tarefa por meio do gate de autonomia do runtime."""

        with self._state_lock:
            self.bootstrap()

            autonomy_decision = self.evaluate_task_execution(task)
            if not autonomy_decision["should_execute"]:
                self._apply_state(task, "blocked")
                blocking_reason = autonomy_decision.get("reason") or "autonomy_gate"
                result = {
                    "status": "blocked",
                    "status_ptbr": traduzir_status("blocked"),
                    "task": task,
                    "reason": blocking_reason,
                    "reason_ptbr": traduzir_motivo(blocking_reason),
                    "policy_evaluation": autonomy_decision.get("policy_evaluation"),
                }
                self.memory["episodic"].remember(
                    {
                        "event": "dispatch",
                        "event_ptbr": "despachar",
                        "status": result["status"],
                        "status_ptbr": result["status_ptbr"],
                        "task_id": task.get("task_id"),
                        "worker": task.get("worker", "runtime"),
                        "reason": result["reason"],
                        "reason_ptbr": result["reason_ptbr"],
                    }
                )
                return result

            worker_id = self._normalize_worker_id(task.get("worker") or task.get("worker_id") or "runtime")
            worker = self.workers.get(worker_id)
            procedural_guidance = self.get_procedural_guidance(task, worker_id=worker_id)

            if worker is None:
                self._apply_state(task, "rejected")
                result = {
                    "status": "rejected",
                    "status_ptbr": traduzir_status("rejected"),
                    "task": task,
                    "reason": "unknown_worker",
                    "reason_ptbr": traduzir_motivo("unknown_worker"),
                    "worker": worker_id,
                }
                self.memory["episodic"].remember(
                    {
                        "event": "dispatch",
                        "event_ptbr": "despachar",
                        "status": result["status"],
                        "status_ptbr": result["status_ptbr"],
                        "task_id": task.get("task_id"),
                        "worker": worker_id,
                    }
                )
                return result

            if procedural_guidance:
                task["procedural_guidance"] = deepcopy(procedural_guidance[0]["steps"])
                task["procedural_guidance_source"] = procedural_guidance[0]["name"]

            worker_task = deepcopy(task)
            worker_task["runtime_context"] = self.describe_state()
            worker_task["goal_summary"] = self.goal_manager.goal_report().get("resumo", {})
            if procedural_guidance:
                worker_task["procedural_guidance"] = deepcopy(procedural_guidance[0]["steps"])
                worker_task["procedural_guidance_source"] = procedural_guidance[0]["name"]
                task["procedural_guidance"] = deepcopy(procedural_guidance[0]["steps"])
                task["procedural_guidance_source"] = procedural_guidance[0]["name"]

            worker_response = worker.handle(worker_task)
            if worker_response.get("status") in {"rejected", "failed"}:
                result_status = "rejected" if worker_response.get("status") == "rejected" else "failed"
                result_reason = worker_response.get("reason") or "worker_rejected"
                self._apply_state(task, result_status)
                result = {
                    "status": result_status,
                    "status_ptbr": traduzir_status(result_status),
                    "task": task,
                    "worker": worker_id,
                    "worker_response": worker_response,
                    "reason": result_reason,
                    "reason_ptbr": worker_response.get("reason_ptbr") or traduzir_motivo(result_reason),
                }
                self.memory["episodic"].remember(
                    {
                        "event": "dispatch",
                        "event_ptbr": "despachar",
                        "status": result["status"],
                        "status_ptbr": result["status_ptbr"],
                        "task_id": task.get("task_id"),
                        "worker": worker_id,
                        "reason": result["reason"],
                        "reason_ptbr": result["reason_ptbr"],
                    }
                )
                return result

            self._apply_state(task, "completed")
            result = {
                "status": "executed",
                "status_ptbr": traduzir_status("executed"),
                "task": task,
                "worker": worker_id,
                "worker_response": worker_response,
                "procedural_context": {
                    "guidance_used": deepcopy(procedural_guidance[0]) if procedural_guidance else None,
                    "guidance_candidates": len(procedural_guidance),
                },
                "result": {
                    "runtime_status": "completed",
                    "runtime_status_ptbr": traduzir_status("completed"),
                },
            }
            self.memory["episodic"].remember(
                {
                    "event": "dispatch",
                    "event_ptbr": "despachar",
                    "status": result["status"],
                    "status_ptbr": result["status_ptbr"],
                    "task_id": task.get("task_id"),
                    "worker": worker_id,
                }
            )
            self.memory["semantic"].add_entry(
                content=self._build_completed_task_content(task, worker_id, result),
                domain=worker_id,
                tags=[worker_id, "resultado_tarefa", "concluida"],
                source="runtime.dispatch_task",
                importance=int(task.get("importance", 0)),
                metadata={
                    "task_id": task.get("task_id"),
                    "goal": task.get("goal"),
                    "worker": worker_id,
                    "dispatch_status": result["status"],
                    "dispatch_status_ptbr": result["status_ptbr"],
                    "runtime_status": result["result"]["runtime_status"],
                    "runtime_status_ptbr": result["result"]["runtime_status_ptbr"],
                    "worker_summary": worker_response.get("summary"),
                    "worker_result_type": worker_response.get("result_type"),
                    "worker_evidence_count": len(worker_response.get("evidence", [])),
                },
            )
            self._record_procedural_outcome(task, worker_id, result)
            self._record_cognitive_learning_from_task(
                task=task,
                worker_id=worker_id,
                result=result,
                procedural_guidance=procedural_guidance,
            )
            self.goal_manager.record_task_result(task, result)
            return result

    def enqueue_task(self, task: Dict[str, Any]) -> None:
        """Adiciona uma tarefa na fila controlada pelo runtime."""

        with self._state_lock:
            self.bootstrap()
            task_to_enqueue = deepcopy(task)
            parent_goal_id = task_to_enqueue.get("parent_goal_id")
            if parent_goal_id is not None:
                task_to_enqueue = self.goal_manager.link_task_to_goal(task_to_enqueue, str(parent_goal_id))
            return self.task_queue.enqueue(task_to_enqueue)

    def run_planner_cycle(self) -> Dict[str, Any]:
        """Executa um ciclo do planner a partir de um runtime inicializado."""

        with self._state_lock:
            self.bootstrap()
            cycle_result = self.planner.run_cycle()
            self.total_cycles_executed += 1
            self.last_cycle_at = self._utc_now()
            self.last_cycle_result = deepcopy(cycle_result)
            return cycle_result

    def handle_command(
        self,
        text: str,
        voice_id: str | None = None,
        password: str | None = None,
        source_device_id: str | None = None,
        response_mode: str = "conversacional",
        environment_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Processa um comando textual visivel ao usuario sem quebrar a arquitetura atual."""

        with self._state_lock:
            self.bootstrap()
            command_text = str(text or "").strip()
            normalized_command = command_text.lower()
            access_context = self.access_control.evaluate(
                phrase=command_text,
                voice_id=voice_id,
                password=password,
            )

            if source_device_id:
                self.device_registry.ensure_device(
                    device_id=source_device_id,
                    nome=source_device_id,
                    tipo="client",
                    trusted=True,
                    metadata={"source": "api_command"},
                )

            response_payload: Dict[str, Any] = {
                "comando": command_text,
                "nivel_acesso": access_context["access_level"],
                "metodos_autenticados": access_context["authenticated_by"],
                "respondido": True,
                "acao": "informativo",
                "dados_relacionados": {},
            }

            if access_context["should_ignore"]:
                response_payload.update(
                    {
                        "status": "ignored",
                        "status_ptbr": traduzir_status("ignored"),
                        "respondido": False,
                        "acao": "special_phrase",
                        "motivo": "special_phrase_ignored",
                        "motivo_ptbr": traduzir_motivo("special_phrase_ignored"),
                        "resposta": "Frase especial ignorada para este contexto.",
                    }
                )
            elif access_context["special_response"]:
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "special_phrase",
                        "resposta": access_context["special_response"],
                    }
                )
            elif "evolu" in normalized_command and "analis" in normalized_command:
                evolution_level = self._resolve_cognitive_level_from_text(normalized_command)
                cognitive_analysis = self.build_cognitive_evolution_analysis(level=evolution_level)
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "cognitive_evolution_analysis",
                        "dados_relacionados": cognitive_analysis,
                        "resposta": self._build_cognitive_analysis_message(cognitive_analysis, response_mode),
                    }
                )
            elif "evolu" in normalized_command:
                evolution_level = self._resolve_cognitive_level_from_text(normalized_command)
                evolution_report = self.build_cognitive_evolution_report(level=evolution_level)
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "cognitive_evolution_visualization",
                        "dados_relacionados": evolution_report,
                        "resposta": self._build_cognitive_evolution_message(evolution_report, response_mode),
                    }
                )
            elif any(keyword in normalized_command for keyword in ("status", "saude", "relatorio")):
                system_report = self.build_system_report(last_cycle_result=self.last_cycle_result)
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "system_report",
                        "dados_relacionados": system_report,
                        "resposta": self._build_system_report_message(system_report, response_mode),
                    }
                )
            elif "objetiv" in normalized_command or "meta" in normalized_command:
                goals_report = self.get_goal_report()
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "goal_report",
                        "dados_relacionados": goals_report,
                        "resposta": self._build_goal_report_message(goals_report, response_mode),
                    }
                )
            elif "taref" in normalized_command or "fila" in normalized_command:
                queue_report = self.build_queue_report()
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "queue_report",
                        "dados_relacionados": queue_report,
                        "resposta": self._build_queue_report_message(queue_report, response_mode),
                    }
                )
            elif "memoria" in normalized_command:
                memory_report = self.build_memory_report()
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "memory_report",
                        "dados_relacionados": memory_report,
                        "resposta": self._build_memory_report_message(memory_report, response_mode),
                    }
                )
            elif "seguranca" in normalized_command or "autodefesa" in normalized_command:
                if not self.access_control.can_execute_sensitive_action(access_context):
                    response_payload.update(self._build_guest_denial())
                else:
                    security_report = self.run_self_defense_audit(environment_report=environment_report)
                    response_payload.update(
                        {
                            "status": "authorized",
                            "status_ptbr": traduzir_status("authorized"),
                            "acao": "security_audit",
                            "dados_relacionados": security_report,
                            "resposta": self._build_security_report_message(security_report, response_mode),
                        }
                    )
            elif "ciclo" in normalized_command or "rodar" in normalized_command or "executar" in normalized_command:
                if not self.access_control.can_execute_sensitive_action(access_context):
                    response_payload.update(self._build_guest_denial())
                else:
                    cycle_result = self.run_planner_cycle()
                    response_payload.update(
                        {
                            "status": "authorized",
                            "status_ptbr": traduzir_status("authorized"),
                            "acao": "planner_cycle",
                            "dados_relacionados": cycle_result,
                            "resposta": self._build_cycle_message(cycle_result, response_mode),
                        }
                    )
            else:
                response_payload.update(
                    {
                        "status": "authorized",
                        "status_ptbr": traduzir_status("authorized"),
                        "acao": "help",
                        "resposta": (
                            "Comando nao reconhecido. Use: status, objetivos, tarefas, memoria, evolucao, seguranca ou ciclo."
                        ),
                    }
                )

            self._record_command_event(
                command_text=command_text,
                source_device_id=source_device_id,
                access_context=access_context,
                response_payload=response_payload,
            )
            return response_payload

    def run_self_defense_audit(
        self,
        environment_report: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Executa o autodiagnostico de seguranca usando os motores defensivos ja presentes no projeto."""

        with self._state_lock:
            self.bootstrap()
            effective_environment = deepcopy(environment_report or {})
            health_report = self.build_health_report(
                api_started_at=self.started_at,
                token_configurado=bool(
                    effective_environment.get("autenticacao_configurada", {}).get("token_configurado")
                ),
                dispositivo_confiavel_configurado=bool(
                    effective_environment.get("autenticacao_configurada", {}).get(
                        "dispositivo_confiavel_configurado"
                    )
                ),
            )
            self.last_self_defense_report = self.self_defense_monitor.run_periodic_audit(
                runtime=self,
                environment_report=effective_environment,
                health_report=health_report,
                auto_apply_safe=True,
            )
            if self.audit_logger is not None:
                self.audit_logger.record(
                    "self_defense",
                    {
                        "status": "completed",
                        "risk_level": self.last_self_defense_report["resumo"]["risco_geral"],
                        "automatic_actions": self.last_self_defense_report["resumo"]["acoes_automaticas_realizadas"],
                    },
                )
            self.memory["episodic"].remember(
                {
                    "event": "self_defense",
                    "event_ptbr": "autodefesa",
                    "status": "completed",
                    "status_ptbr": traduzir_status("completed"),
                    "risk_level": self.last_self_defense_report["resumo"]["risco_geral"],
                }
            )
            LOGGER.info(
                "[self_defense] risco_geral=%s fraquezas=%s acoes_automaticas=%s",
                self.last_self_defense_report["resumo"]["risco_geral"],
                self.last_self_defense_report["resumo"]["fraquezas_detectadas"],
                self.last_self_defense_report["resumo"]["acoes_automaticas_realizadas"],
            )
            return deepcopy(self.last_self_defense_report)

    def record_runtime_error(
        self,
        context: str,
        error: Exception,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Registra erros do runtime para watchdog, auditoria e memoria episodica."""

        with self._state_lock:
            self.bootstrap()
            payload = {
                "context": context,
                "status": "failed",
                "reason": "runtime_exception",
                "error_type": error.__class__.__name__,
                "error_message": str(error),
                "metadata": deepcopy(metadata or {}),
                "runtime_identity": self.build_runtime_identity_report(),
            }
            if self.audit_logger is not None:
                self.audit_logger.record("runtime_watchdog", payload)
            self.memory["episodic"].remember(
                {
                    "event": "runtime_watchdog",
                    "event_ptbr": "watchdog_do_runtime",
                    "status": "failed",
                    "status_ptbr": traduzir_status("failed"),
                    "reason": "runtime_exception",
                    "reason_ptbr": traduzir_motivo("runtime_exception"),
                    "context": context,
                    "error_type": error.__class__.__name__,
                    "error_message": str(error),
                    "metadata": deepcopy(metadata or {}),
                }
            )
            LOGGER.exception("[runtime_watchdog] context=%s error=%s", context, error)
            return payload

    def query_semantic_memory(
        self, query: str, domain: str | None = None, limit: int = 5
    ) -> list[Dict[str, Any]]:
        """Consulta a memoria semantica em busca de entradas relevantes."""

        with self._state_lock:
            self.bootstrap()
            return self.memory["semantic"].search(query=query, domain=domain, limit=limit)

    def query_procedural_memory(
        self,
        query: str = "",
        domain: str | None = None,
        task_type: str | None = None,
        success_only: bool = False,
        limit: int = 5,
    ) -> list[Dict[str, Any]]:
        """Consulta a memoria procedural em busca de heuristicas relevantes."""

        with self._state_lock:
            self.bootstrap()
            return self.memory["procedural"].search(
                query=query,
                domain=domain,
                task_type=task_type,
                success_only=success_only,
                limit=limit,
            )

    def get_goal_report(self, goal_id: str | None = None) -> Dict[str, Any]:
        """Retorna um relatorio de objetivos em pt-BR."""

        with self._state_lock:
            self.bootstrap()
            return self.goal_manager.goal_report(goal_id)

    def list_tasks(self) -> list[Dict[str, Any]]:
        """Retorna uma copia da fila atual de tarefas."""

        with self._state_lock:
            self.bootstrap()
            return self.task_queue.snapshot_items()

    def get_recent_events(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Retorna os eventos episodicos mais recentes."""

        with self._state_lock:
            self.bootstrap()
            return self.memory["episodic"].recent(limit)

    def get_recent_semantic_entries(
        self,
        limit: int = 10,
        domain: str | None = None,
    ) -> list[Dict[str, Any]]:
        """Retorna as entradas semanticas mais recentes."""

        with self._state_lock:
            self.bootstrap()
            return self.memory["semantic"].recent_entries(limit=limit, domain=domain)

    def get_recent_procedural_entries(
        self,
        limit: int = 10,
        domain: str | None = None,
    ) -> list[Dict[str, Any]]:
        """Retorna os procedimentos mais recentes, opcionalmente por dominio."""

        with self._state_lock:
            self.bootstrap()
            return self.memory["procedural"].recent_entries(limit=limit, domain=domain)

    def build_system_report(self, last_cycle_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Monta um relatorio operacional resumido do sistema."""

        with self._state_lock:
            self.bootstrap()
            queue_report = self.build_queue_report()
            memory_report = self.build_memory_report()
            goals_report = self.build_goal_operational_report()
            audit_report = self.build_audit_report()
            planner_report = self.build_planner_report()
            evolution_report = self.build_cognitive_evolution_report(level="semanal")
            current_cycle = deepcopy(last_cycle_result or self.last_cycle_result)

            return {
                "mensagem": "Relatorio operacional do JARVIS.",
                "status_runtime": self.describe_state(),
                "identidade_runtime": self.build_runtime_identity_report(),
                "uptime_segundos": self._uptime_seconds(),
                "ultimo_ciclo_executado": current_cycle,
                "total_ciclos_executados": self.total_cycles_executed,
                "estado_do_planner": planner_report,
                "estado_da_fila": queue_report["resumo"],
                "estado_da_memoria": memory_report["resumo"],
                "objetivos": goals_report["resumo"],
                "quantidade_objetivos_ativos": goals_report["resumo"]["total_objetivos_ativos"],
                "quantidade_tarefas_pendentes": queue_report["resumo"]["tarefas_pendentes"],
                "quantidade_tarefas_concluidas": queue_report["resumo"]["tarefas_concluidas_total"],
                "ultimas_falhas_registradas": audit_report["ultimas_falhas"],
                "ultimos_eventos": audit_report["ultimas_acoes_relevantes"],
                "ultimas_memorias": memory_report["memorias_recentes"],
                "politica_ativa": self.build_policy_report(),
                "dispositivos_autorizados": self.device_registry.build_report(),
                "seguranca_operacional": self.last_self_defense_report["resumo"]
                if self.last_self_defense_report is not None
                else {
                    "risco_geral": "nao_auditado",
                    "fraquezas_detectadas": 0,
                    "acoes_automaticas_realizadas": 0,
                    "acoes_pendentes_de_aprovacao": 0,
                    "portas_ativas_observadas": 0,
                },
                "aprendizado_futuro": self.learning_advisor.suggest_structural_improvements(
                    runtime_state=self.describe_state(),
                    analysis_report=self.last_self_defense_report or {},
                ),
                "evolucao_cognitiva": evolution_report["resumo"],
                "saude_runtime": {
                    "status": "ok" if self.status == "initialized" else "degradado",
                    "status_ptbr": "saudavel" if self.status == "initialized" else "degradado",
                },
            }

    def build_planner_report(self) -> Dict[str, Any]:
        """Retorna o estado operacional atual do planner."""

        with self._state_lock:
            self.bootstrap()
            planner_entries = [
                deepcopy(entry)
                for entry in self.audit_logger.entries
                if entry["event"] in {"plan", "prioritize", "validate", "schedule", "execute", "review"}
            ]
            return {
                "acoplado": self.planner is not None and self.planner.runtime is self,
                "classe": self._planner_path(),
                "total_entradas_auditoria": len(planner_entries),
                "ultima_decisao": planner_entries[-1] if planner_entries else None,
            }

    def build_queue_report(self) -> Dict[str, Any]:
        """Retorna um relatorio operacional da fila."""

        with self._state_lock:
            self.bootstrap()
            tasks = self.list_tasks()
            pending_states = {"queued", "scheduled", "deferred"}
            top_tasks = sorted(
                tasks,
                key=lambda task: (
                    -self.prioritizer.score(task),
                    task.get("created_at", ""),
                    task.get("task_id", ""),
                ),
            )[:5]

            return {
                "resumo": {
                    "total_tarefas": len(tasks),
                    "tarefas_pendentes": len([task for task in tasks if task.get("state") in pending_states]),
                    "tarefas_em_execucao": len([task for task in tasks if task.get("state") == "executing"]),
                    "tarefas_bloqueadas": len([task for task in tasks if task.get("state") == "blocked"]),
                    "tarefas_concluidas_total": self._count_completed_tasks(),
                    "tarefas_aguardando_aprovacao": len(
                        [
                            task
                            for task in tasks
                            if task.get("requires_supervision") and not task.get("approved", False)
                        ]
                    ),
                    "tarefas_vinculadas_a_objetivos": len([task for task in tasks if task.get("parent_goal_id")]),
                },
                "principais_tarefas": [
                    {
                        "task_id": task.get("task_id"),
                        "goal": task.get("goal"),
                        "estado": task.get("state"),
                        "estado_ptbr": task.get("state_ptbr"),
                        "prioridade_calculada": self.prioritizer.score(task),
                        "parent_goal_id": task.get("parent_goal_id"),
                        "parent_goal": task.get("parent_goal"),
                    }
                    for task in top_tasks
                ],
                "tarefas": tasks,
            }

    def build_goal_operational_report(self) -> Dict[str, Any]:
        """Retorna um relatorio enriquecido da camada de objetivos."""

        with self._state_lock:
            self.bootstrap()
            tasks = self.list_tasks()
            queued_tasks_by_goal: Dict[str, list[Dict[str, Any]]] = {}
            for task in tasks:
                goal_id = task.get("parent_goal_id")
                if not goal_id:
                    continue
                queued_tasks_by_goal.setdefault(str(goal_id), []).append(
                    {
                        "task_id": task.get("task_id"),
                        "goal": task.get("goal"),
                        "estado": task.get("state"),
                        "estado_ptbr": task.get("state_ptbr"),
                    }
                )

            base_report = self.goal_manager.goal_report()
            strategic_raw = {goal["goal_id"]: goal for goal in self.goal_manager.list_strategic_goals()}
            active_raw = {goal["goal_id"]: goal for goal in self.goal_manager.list_active_goals()}

            strategic_reports = []
            for item in base_report["metas_estrategicas"]:
                raw_goal = strategic_raw.get(item["goal_id"], {})
                strategic_reports.append(
                    {
                        **item,
                        "tarefas_ids": list(raw_goal.get("task_ids", [])),
                        "tarefas_concluidas_ids": list(raw_goal.get("completed_task_ids", [])),
                        "tarefas_na_fila": queued_tasks_by_goal.get(item["goal_id"], []),
                    }
                )

            active_reports = []
            for item in base_report["objetivos_ativos"]:
                raw_goal = active_raw.get(item["goal_id"], {})
                active_reports.append(
                    {
                        **item,
                        "tarefas_ids": list(raw_goal.get("task_ids", [])),
                        "tarefas_concluidas_ids": list(raw_goal.get("completed_task_ids", [])),
                        "tarefas_na_fila": queued_tasks_by_goal.get(item["goal_id"], []),
                    }
                )

            return {
                "metas_estrategicas": strategic_reports,
                "objetivos_ativos": active_reports,
                "resumo": base_report["resumo"],
            }

    def build_memory_report(self) -> Dict[str, Any]:
        """Retorna um relatorio operacional da memoria semantica."""

        with self._state_lock:
            self.bootstrap()
            semantic_memory = self.memory["semantic"]
            procedural_memory = self.memory["procedural"]
            domain_counts: Dict[str, int] = {}
            for entry in semantic_memory.entries:
                domain_counts[entry["domain"]] = domain_counts.get(entry["domain"], 0) + 1

            integrity = {
                "arquivo_configurado": str(semantic_memory.storage_path),
                "arquivo_existe": semantic_memory.storage_path.exists(),
                "json_valido": True,
                "contagem_consistente": True,
            }
            if semantic_memory.storage_path.exists():
                try:
                    persisted_snapshot = json.loads(semantic_memory.storage_path.read_text(encoding="utf-8"))
                    persisted_entry_count = int(persisted_snapshot.get("entry_count", 0))
                    integrity["contagem_consistente"] = persisted_entry_count == len(semantic_memory.entries)
                except json.JSONDecodeError:
                    integrity["json_valido"] = False
                    integrity["contagem_consistente"] = False

            latest_write = None
            if semantic_memory.entries:
                latest_write = max(entry["created_at"] for entry in semantic_memory.entries)

            return {
                "resumo": {
                    "total_entradas_semanticas": len(semantic_memory.entries),
                    "total_fatos_semanticos": len(semantic_memory.facts),
                    "total_procedimentos": len(procedural_memory.procedures),
                    "ultima_escrita": latest_write,
                    "ultima_atualizacao_procedural": procedural_memory.latest_updated_at(),
                    "integridade_basica": integrity,
                    "eventos_evolutivos_cognitivos": len(self.cognitive_evolution_tracker.events),
                },
                "memorias_recentes": self.get_recent_semantic_entries(limit=5),
                "procedimentos_recentes": self.get_recent_procedural_entries(limit=5),
                "memorias_por_dominio": [
                    {"dominio": domain, "total": total}
                    for domain, total in sorted(domain_counts.items(), key=lambda item: item[0])
                ],
                "historico_evolutivo_recente": self.cognitive_evolution_tracker.recent_events(level="semanal", limit=5),
            }

    def build_cognitive_evolution_report(self, level: str = "historica") -> Dict[str, Any]:
        """Retorna o payload consolidado do mapa evolutivo cognitivo."""

        with self._state_lock:
            self.bootstrap()
            visualization = self.cognitive_evolution_tracker.build_visualization_payload(level=level)
            visualization["estado_cognitivo"] = {
                "procedimentos_disponiveis": len(self.memory["procedural"].procedures),
                "entradas_semanticas": len(self.memory["semantic"].entries),
                "objetivos_ativos": len(self.goal_manager.list_active_goals()),
                "workers_ativos": list(self.workers),
            }
            return visualization

    def build_cognitive_evolution_analysis(self, level: str = "historica") -> Dict[str, Any]:
        """Retorna uma analise interna do crescimento cognitivo do Jarvis."""

        with self._state_lock:
            self.bootstrap()
            analysis = self.cognitive_evolution_tracker.build_analysis(level=level)
            analysis["estado_runtime"] = {
                "status": self.status,
                "status_ptbr": traduzir_status(self.status),
                "total_ciclos_executados": self.total_cycles_executed,
                "ultima_execucao": self.last_cycle_at,
            }
            return analysis

    def build_audit_report(self) -> Dict[str, Any]:
        """Retorna um relatorio consolidado de auditoria."""

        with self._state_lock:
            self.bootstrap()
            planner_entries = [
                deepcopy(entry)
                for entry in self.audit_logger.entries
                if entry["event"] in {"plan", "prioritize", "validate", "schedule", "execute", "review"}
            ][-10:]
            access_entries = self.get_access_events(limit=10)
            denied_entries = self.get_access_events(limit=10, denied_only=True)
            recent_actions = self.get_recent_events(limit=10)

            failures: list[Dict[str, Any]] = []
            for entry in reversed(self.audit_logger.entries):
                payload = entry.get("payload", {})
                if payload.get("status") in {"failed", "denied", "rejected"} or payload.get("reason") or payload.get("valid") is False:
                    failures.append(deepcopy(entry))
                if len(failures) >= 5:
                    break

            return {
                "ultimas_decisoes_planner": planner_entries,
                "ultimos_acessos": access_entries,
                "ultimas_tentativas_negadas": denied_entries,
                "ultimas_acoes_relevantes": recent_actions,
                "ultimas_falhas": failures,
                "persistencia": {
                    "caminho": str(self.audit_logger.storage_path),
                    "arquivo_existe": self.audit_logger.storage_path.exists(),
                    "total_eventos": len(self.audit_logger.entries),
                },
            }

    def build_health_report(
        self,
        api_started_at: str | None = None,
        token_configurado: bool = False,
        dispositivo_confiavel_configurado: bool = False,
    ) -> Dict[str, Any]:
        """Retorna um health report operacional do sistema."""

        with self._state_lock:
            self.bootstrap()
            queue_loaded = self.task_queue is not None and self.task_queue.storage_path is not None
            memory_loaded = all(key in self.memory for key in ("episodic", "semantic", "procedural"))
            goals_loaded = self.goal_manager is not None and self.goal_manager.storage_path is not None
            planner_attached = self.planner is not None and self.planner.runtime is self
            config_valid = token_configurado and dispositivo_confiavel_configurado
            status = "ok" if all([api_started_at, self.status == "initialized", planner_attached, queue_loaded, memory_loaded, goals_loaded, config_valid]) else "degradado"

            return {
                "status": status,
                "status_ptbr": "saudavel" if status == "ok" else "degradado",
                "api_ativa": api_started_at is not None,
                "runtime_ativo": self.status == "initialized",
                "planner_acoplado": planner_attached,
                "politica_constitucional_carregada": self.constitutional_policy is not None,
                "fila_carregada": queue_loaded,
                "memoria_carregada": memory_loaded,
                "objetivos_carregados": goals_loaded,
                "registro_de_dispositivos_carregado": self.device_registry is not None,
                "autodefesa_operacional_carregada": self.self_defense_monitor is not None,
                "configuracao_minima_valida": config_valid,
                "dispositivo_confiavel_configurado": dispositivo_confiavel_configurado,
                "token_configurado": token_configurado,
                "uptime_segundos": self._uptime_seconds(),
                "api_iniciada_em": api_started_at,
                "runtime_iniciado_em": self.started_at,
                "identidade_runtime": self.build_runtime_identity_report(),
                "ultima_persistencia_fila": self._last_persisted_at(
                    getattr(self.task_queue, "storage_path", None)
                ),
                "ultima_persistencia_memoria": self._last_persisted_at(
                    getattr(self.memory.get("semantic"), "storage_path", None)
                ),
                "ultima_persistencia_objetivos": self._last_persisted_at(
                    getattr(self.goal_manager, "storage_path", None)
                ),
                "ultima_persistencia_auditoria": self._last_persisted_at(
                    getattr(self.audit_logger, "storage_path", None)
                ),
            }

    def record_access_attempt(
        self,
        endpoint: str,
        method: str,
        device_id: str | None,
        allowed: bool,
        reason: str | None = None,
        client_host: str | None = None,
    ) -> Dict[str, Any]:
        """Registra uma tentativa de acesso na auditoria e na memoria episodica."""

        with self._state_lock:
            self.bootstrap()
            status = "authorized" if allowed else "denied"
            payload = {
                "endpoint": endpoint,
                "method": method,
                "device_id": device_id or "nao_informado",
                "status": status,
                "client_host": client_host,
                "runtime_identity": self.build_runtime_identity_report(),
            }
            if reason is not None:
                payload["reason"] = reason

            entry = self.audit_logger.record("access", payload)
            self.memory["episodic"].remember(
                {
                    "event": "access",
                    "event_ptbr": "acesso",
                    "endpoint": endpoint,
                    "method": method,
                    "device_id": device_id or "nao_informado",
                    "status": status,
                    "status_ptbr": traduzir_status(status),
                    "reason": reason,
                    "reason_ptbr": traduzir_motivo(reason) if reason is not None else None,
                    "client_host": client_host,
                }
            )
            return entry

    def get_access_events(self, limit: int = 10, denied_only: bool = False) -> list[Dict[str, Any]]:
        """Retorna os eventos de acesso mais recentes da auditoria."""

        with self._state_lock:
            self.bootstrap()
            access_entries = [entry for entry in self.audit_logger.entries if entry["event"] == "access"]
            if denied_only:
                access_entries = [
                    entry for entry in access_entries if entry["payload"].get("status") == "denied"
                ]
            return [deepcopy(entry) for entry in access_entries[-limit:]]

    def persist_runtime_state(self) -> Dict[str, Any]:
        """Persiste os artefatos de runtime necessarios para reinicio seguro."""

        with self._state_lock:
            self.bootstrap()

            queue_snapshot = None
            if self.task_queue is not None:
                queue_snapshot = self.task_queue.save_to_disk()

            semantic_snapshot = None
            semantic_memory = self.memory.get("semantic")
            if semantic_memory is not None:
                semantic_snapshot = semantic_memory.snapshot()

            procedural_snapshot = None
            procedural_memory = self.memory.get("procedural")
            if procedural_memory is not None:
                procedural_snapshot = procedural_memory.snapshot()

            goals_snapshot = None
            if self.goal_manager is not None:
                goals_snapshot = self.goal_manager.snapshot()

            device_snapshot = None
            if self.device_registry is not None:
                device_snapshot = self.device_registry.snapshot()

            cognitive_snapshot = None
            if self.cognitive_evolution_tracker is not None:
                cognitive_snapshot = self.cognitive_evolution_tracker.snapshot()

            audit_snapshot = None
            if self.audit_logger is not None:
                audit_snapshot = self.audit_logger.save_to_disk()

            return {
                "queue": deepcopy(queue_snapshot),
                "semantic_memory": deepcopy(semantic_snapshot),
                "procedural_memory": deepcopy(procedural_snapshot),
                "goals": deepcopy(goals_snapshot),
                "devices": deepcopy(device_snapshot),
                "cognitive_evolution": deepcopy(cognitive_snapshot),
                "audit": deepcopy(audit_snapshot),
            }

    def describe_state(self) -> Dict[str, Any]:
        """Retorna um snapshot leve do estado atual do runtime inicializado."""

        with self._state_lock:
            queue_depth = 0
            if self.task_queue is not None:
                queue_depth = len(self.task_queue.items)

            return {
                "status": self.status,
                "status_ptbr": traduzir_status(self.status),
                "default_locale": "pt-BR",
                "modo_autonomia": "supervisionada_por_politica_constitucional",
                "politica_constitucional_carregada": self.constitutional_policy is not None,
                "identidade_constitucional": self.constitutional_policy.identity.get("system_name")
                if self.constitutional_policy is not None
                else None,
                "started_at": self.started_at,
                "uptime_segundos": self._uptime_seconds(),
                "planner": self._planner_path(),
                "memory": "memory_system",
                "memory_modules": list(self.memory),
                "workers": [f"worker_{worker_id}" for worker_id in self.workers],
                "active_goal_count": len([goal for goal in self.goal_manager.list_active_goals() if goal["state"] != "completed"]),
                "strategic_goal_count": len(self.goal_manager.list_strategic_goals()),
                "queue_depth": queue_depth,
                "queue_store": str(self.task_queue.storage_path) if self.task_queue is not None else None,
                "goal_store": str(self.goal_manager.storage_path) if self.goal_manager is not None else None,
                "semantic_store": (
                    str(self.memory["semantic"].storage_path) if self.memory.get("semantic") is not None else None
                ),
                "procedural_store": (
                    str(self.memory["procedural"].storage_path)
                    if self.memory.get("procedural") is not None and self.memory["procedural"].storage_path is not None
                    else None
                ),
                "audit_store": str(self.audit_logger.storage_path) if self.audit_logger is not None else None,
                "device_registry_store": str(self.device_registry.storage_path) if self.device_registry is not None else None,
                "cognitive_evolution_store": (
                    str(self.cognitive_evolution_tracker.storage_path)
                    if self.cognitive_evolution_tracker is not None
                    else None
                ),
                "registered_device_count": len(self.device_registry.devices) if self.device_registry is not None else 0,
                "trusted_device_count": len(self.device_registry.list_devices(trusted_only=True)) if self.device_registry is not None else 0,
                "cognitive_evolution_event_count": (
                    len(self.cognitive_evolution_tracker.events)
                    if self.cognitive_evolution_tracker is not None
                    else 0
                ),
                "brain_avatar_ready": self.cognitive_evolution_tracker is not None,
                "learning_module_loaded": self.learning_advisor is not None,
                "security_module_loaded": self.self_defense_monitor is not None,
                "last_cycle_at": self.last_cycle_at,
                "total_cycles_executed": self.total_cycles_executed,
                "runtime_identity": self.build_runtime_identity_report(),
            }

    def build_policy_report(self) -> Dict[str, Any]:
        """Retorna um resumo seguro da politica constitucional ativa."""

        self.bootstrap()
        return self.constitutional_policy.describe()

    def get_procedural_guidance(self, task: Dict[str, Any], worker_id: str | None = None) -> list[Dict[str, Any]]:
        """Busca heuristicas relevantes para a tarefa atual."""

        self.bootstrap()
        normalized_worker = self._normalize_worker_id(worker_id or task.get("worker") or task.get("worker_id") or task.get("domain") or "general")
        query = " ".join(
            item
            for item in [
                str(task.get("goal", "")),
                str(task.get("description", "")),
            ]
            if item
        )
        return self.query_procedural_memory(
            query=query,
            domain=str(task.get("domain") or normalized_worker),
            task_type=normalized_worker,
            success_only=True,
            limit=3,
        )

    def _record_procedural_outcome(self, task: Dict[str, Any], worker_id: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """Registra um padrao util de execucao para reutilizacao futura."""

        procedure_name = f"{worker_id}_execution_pattern"
        guidance_source = task.get("procedural_guidance_source")
        base_steps = task.get("procedural_guidance") or [
            "validar contexto da tarefa",
            f"executar o worker {worker_id}",
            "registrar evidencias",
            "persistir resultado nas memorias",
        ]
        evidence = list(task.get("evidence", []))
        worker_response = result.get("worker_response", {})
        if isinstance(worker_response, dict):
            evidence.extend(str(item) for item in worker_response.get("evidence", []))

        heuristic = (
            f"Reaproveitar o padrao de {worker_id} no dominio {task.get('domain', worker_id)} "
            "mantendo evidencia explicita e registro de memoria."
        )
        if guidance_source:
            heuristic += f" Guia reaproveitado: {guidance_source}."

        return self.memory["procedural"].register(
            name=procedure_name,
            steps=[str(step) for step in base_steps],
            domain=str(task.get("domain") or worker_id),
            task_type=worker_id,
            heuristic=heuristic,
            context={
                "goal": task.get("goal"),
                "description": task.get("description"),
                "worker": worker_id,
            },
            preconditions=[
                "tarefa validada pelo planner",
                "politica constitucional carregada",
            ],
            observed_result=result["status"],
            success=result["status"] == "executed",
            evidence=evidence,
            metadata={
                "task_id": task.get("task_id"),
                "worker": worker_id,
                "guidance_source": guidance_source,
                "dispatch_status": result["status"],
                "dispatch_status_ptbr": result["status_ptbr"],
            },
        )

    def _record_cognitive_learning_from_task(
        self,
        task: Dict[str, Any],
        worker_id: str,
        result: Dict[str, Any],
        procedural_guidance: list[Dict[str, Any]],
    ) -> None:
        """Converte execucoes concluidas em eventos evolutivos do cerebro cognitivo."""

        worker_response = result.get("worker_response", {}) if isinstance(result, dict) else {}
        evidence_count = len(task.get("evidence", [])) + len(worker_response.get("evidence", []))
        created_connections = max(1, min(12, evidence_count or 1))
        strengthened_connections = max(
            1,
            len((procedural_guidance[0] if procedural_guidance else {}).get("steps", []))
            or len(worker_response.get("next_steps", []))
            or 1,
        )
        base_region = str(task.get("domain") or worker_id)
        impact = min(
            2.0,
            0.35
            + (0.08 * created_connections)
            + (0.04 * strengthened_connections)
            + (0.2 if worker_response.get("summary") else 0.0),
        )

        self._record_cognitive_evolution_event(
            event_type="EVENT_NEW_KNOWLEDGE",
            region=base_region,
            connections_created=created_connections,
            connections_strengthened=max(1, strengthened_connections // 2),
            estimated_cognitive_impact=impact,
            metadata={
                "source": "runtime.dispatch_task",
                "task_id": task.get("task_id"),
                "worker": worker_id,
                "result_type": worker_response.get("result_type"),
            },
        )

        if procedural_guidance:
            self._record_cognitive_evolution_event(
                event_type="EVENT_PATTERN_DISCOVERED",
                region="procedural",
                connections_created=1,
                connections_strengthened=strengthened_connections,
                estimated_cognitive_impact=min(1.7, impact + 0.18),
                metadata={
                    "source": "runtime.dispatch_task",
                    "guidance_source": procedural_guidance[0].get("name"),
                    "task_id": task.get("task_id"),
                },
            )

        self._record_cognitive_evolution_event(
            event_type="EVENT_SKILL_IMPROVED",
            region=worker_id,
            connections_created=0,
            connections_strengthened=max(1, strengthened_connections),
            estimated_cognitive_impact=min(1.9, impact + 0.12),
            metadata={
                "source": "runtime.procedural_memory",
                "task_id": task.get("task_id"),
                "worker": worker_id,
            },
        )
        self._record_cognitive_evolution_event(
            event_type="EVENT_MEMORY_CONSOLIDATED",
            region="memory",
            connections_created=max(1, created_connections // 2),
            connections_strengthened=max(1, strengthened_connections),
            estimated_cognitive_impact=min(1.6, impact + 0.08),
            metadata={
                "source": "runtime.memory_consolidation",
                "task_id": task.get("task_id"),
                "worker": worker_id,
            },
        )

    def _record_cognitive_evolution_event(
        self,
        event_type: str,
        region: str,
        connections_created: int,
        connections_strengthened: int,
        estimated_cognitive_impact: float,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any] | None:
        """Registra um evento evolutivo em auditoria e memoria episodica."""

        if self.cognitive_evolution_tracker is None:
            return None

        event = self.cognitive_evolution_tracker.record_event(
            event_type=event_type,
            region=region,
            connections_created=connections_created,
            connections_strengthened=connections_strengthened,
            estimated_cognitive_impact=estimated_cognitive_impact,
            metadata=metadata,
        )
        return event

    def _record_command_event(
        self,
        command_text: str,
        source_device_id: str | None,
        access_context: Dict[str, Any],
        response_payload: Dict[str, Any],
    ) -> None:
        """Registra comandos recebidos em auditoria, memoria episodica e log central."""

        payload = {
            "status": response_payload.get("status", "authorized"),
            "access_level": access_context["access_level"],
            "device_id": source_device_id or "nao_informado",
            "action": response_payload.get("acao"),
            "command_text": command_text,
            "reason": response_payload.get("motivo"),
        }
        if self.audit_logger is not None:
            self.audit_logger.record("command", payload)
        self.memory["episodic"].remember(
            {
                "event": "command",
                "event_ptbr": "comando",
                "status": payload["status"],
                "status_ptbr": traduzir_status(payload["status"]),
                "device_id": payload["device_id"],
                "access_level": payload["access_level"],
                "command_text": command_text,
                "action": payload["action"],
                "reason": payload.get("reason"),
                "reason_ptbr": traduzir_motivo(payload["reason"]) if payload.get("reason") else None,
            }
        )
        LOGGER.info(
            "[command] access=%s device=%s action=%s texto=%s",
            access_context["access_level"],
            payload["device_id"],
            payload["action"],
            command_text,
        )

    @staticmethod
    def _build_guest_denial() -> Dict[str, Any]:
        """Monta a resposta padrao para comandos restritos ao contexto administrativo."""

        return {
            "status": "denied",
            "status_ptbr": traduzir_status("denied"),
            "acao": "restricted_command",
            "respondido": True,
            "motivo": "guest_restricted_command",
            "motivo_ptbr": traduzir_motivo("guest_restricted_command"),
            "resposta": "Modo guest ativo. Esse comando requer autenticacao administrativa por voz ou senha.",
        }

    @staticmethod
    def _build_cycle_message(cycle_result: Dict[str, Any], response_mode: str) -> str:
        """Sintetiza o resultado do ciclo executado para a camada visivel."""

        if response_mode == "tecnico":
            return json.dumps(cycle_result, ensure_ascii=False, indent=2)
        return "Ciclo executado com status {status}.".format(
            status=cycle_result.get("status_ptbr", cycle_result.get("status", "desconhecido"))
        )

    @staticmethod
    def _build_system_report_message(system_report: Dict[str, Any], response_mode: str) -> str:
        """Resume o relatorio geral do sistema em formato conversacional ou tecnico."""

        if response_mode == "tecnico":
            return json.dumps(system_report, ensure_ascii=False, indent=2)
        return (
            "Runtime em {status} com fila {fila}, {objetivos} objetivo(s) ativo(s) e "
            "{ciclos} ciclo(s) executado(s)."
        ).format(
            status=system_report["status_runtime"]["status_ptbr"],
            fila=system_report["estado_da_fila"]["tarefas_pendentes"],
            objetivos=system_report["quantidade_objetivos_ativos"],
            ciclos=system_report["total_ciclos_executados"],
        )

    @staticmethod
    def _build_goal_report_message(goals_report: Dict[str, Any], response_mode: str) -> str:
        """Resume o estado dos objetivos para resposta por comando."""

        if response_mode == "tecnico":
            return json.dumps(goals_report, ensure_ascii=False, indent=2)
        resumo = goals_report.get("resumo", {})
        return (
            "Ha {ativos} objetivo(s) ativo(s), {estrategicos} meta(s) estrategica(s) "
            "e progresso medio de {progresso}%."
        ).format(
            ativos=resumo.get("total_objetivos_ativos", 0),
            estrategicos=resumo.get("total_metas_estrategicas", 0),
            progresso=resumo.get("progresso_medio", 0),
        )

    @staticmethod
    def _build_queue_report_message(queue_report: Dict[str, Any], response_mode: str) -> str:
        """Resume a fila atual para resposta por comando."""

        if response_mode == "tecnico":
            return json.dumps(queue_report, ensure_ascii=False, indent=2)
        resumo = queue_report.get("resumo", {})
        return (
            "Fila com {total} tarefa(s), {pendentes} pendente(s), {bloqueadas} bloqueada(s) "
            "e {concluidas} concluida(s)."
        ).format(
            total=resumo.get("total_tarefas", 0),
            pendentes=resumo.get("tarefas_pendentes", 0),
            bloqueadas=resumo.get("tarefas_bloqueadas", 0),
            concluidas=resumo.get("tarefas_concluidas_total", 0),
        )

    @staticmethod
    def _build_memory_report_message(memory_report: Dict[str, Any], response_mode: str) -> str:
        """Resume o estado das memorias do sistema para resposta por comando."""

        if response_mode == "tecnico":
            return json.dumps(memory_report, ensure_ascii=False, indent=2)
        resumo = memory_report.get("resumo", {})
        return (
            "Memoria com {entradas} entrada(s) semantica(s), {procedimentos} procedimento(s) "
            "e ultima escrita em {ultima_escrita}."
        ).format(
            entradas=resumo.get("total_entradas_semanticas", 0),
            procedimentos=resumo.get("total_procedimentos", 0),
            ultima_escrita=resumo.get("ultima_escrita") or "nao registrada",
        )

    @staticmethod
    def _build_security_report_message(security_report: Dict[str, Any], response_mode: str) -> str:
        """Resume o relatorio de autodefesa para resposta por comando."""

        if response_mode == "tecnico":
            return json.dumps(security_report, ensure_ascii=False, indent=2)
        resumo = security_report.get("resumo", {})
        return (
            "Autodiagnostico concluido com risco {risco}, {fraquezas} fraqueza(s) detectada(s) "
            "e {acoes} correcao(oes) automatica(s) segura(s)."
        ).format(
            risco=resumo.get("risco_geral", "desconhecido"),
            fraquezas=resumo.get("fraquezas_detectadas", 0),
            acoes=resumo.get("acoes_automaticas_realizadas", 0),
        )

    @staticmethod
    def _resolve_cognitive_level_from_text(command_text: str) -> str:
        """Infere o nivel temporal do mapa evolutivo a partir do comando textual."""

        normalized = str(command_text or "").lower()
        if "24h" in normalized or "recente" in normalized or "hoje" in normalized:
            return "recente"
        if "seman" in normalized:
            return "semanal"
        if "mens" in normalized:
            return "mensal"
        return "historica"

    @staticmethod
    def _build_cognitive_evolution_message(evolution_report: Dict[str, Any], response_mode: str) -> str:
        """Resume o mapa evolutivo para a camada textual do Jarvis."""

        if response_mode == "tecnico":
            return json.dumps(evolution_report, ensure_ascii=False, indent=2)
        resumo = evolution_report.get("resumo", {})
        regiao = (resumo.get("regiao_mais_ativa") or {}).get("label", "nenhuma")
        return (
            "Mapa evolutivo pronto em {nivel}. Foram observados {eventos} evento(s), "
            "{criadas} conexao(oes) nova(s) e {reforcadas} reforco(s) sinaptico(s). "
            "A regiao com maior crescimento foi {regiao}."
        ).format(
            nivel=evolution_report.get("nivel_ptbr", evolution_report.get("nivel", "historica")),
            eventos=resumo.get("total_eventos", 0),
            criadas=resumo.get("conexoes_criadas", 0),
            reforcadas=resumo.get("conexoes_reforcadas", 0),
            regiao=regiao,
        )

    @staticmethod
    def _build_cognitive_analysis_message(analysis_report: Dict[str, Any], response_mode: str) -> str:
        """Resume a analise interna de evolucao cognitiva."""

        if response_mode == "tecnico":
            return json.dumps(analysis_report, ensure_ascii=False, indent=2)
        mais_utilizadas = analysis_report.get("regioes_mais_utilizadas", [])
        subutilizadas = analysis_report.get("regioes_subutilizadas", [])
        regiao_forte = mais_utilizadas[0]["label"] if mais_utilizadas else "nenhuma"
        regiao_fraca = subutilizadas[0]["label"] if subutilizadas else "nenhuma"
        return (
            "Analise cognitiva concluida. A regiao mais utilizada foi {forte} e a mais subutilizada foi {fraca}. "
            "O sistema identificou {conexoes} trilha(s) forte(s) de aprendizado neste recorte."
        ).format(
            forte=regiao_forte,
            fraca=regiao_fraca,
            conexoes=len(analysis_report.get("conexoes_mais_fortes", [])),
        )

    # ==================================================
    # BLOCO: Utilitarios internos de estado e persistencia
    # ==================================================

    def _uptime_seconds(self) -> int:
        """
        Calcula o uptime do runtime em segundos.

        Parametros:
        - nenhum.

        Retorno:
        - inteiro com o tempo de atividade desde o bootstrap.

        Efeitos no sistema:
        - nenhum; usado em relatorios operacionais e healthcheck.
        """

        if self.started_at is None:
            return 0
        started_at = self._parse_isoformat(self.started_at)
        return int((datetime.now(timezone.utc) - started_at).total_seconds())

    def _count_completed_tasks(self) -> int:
        """
        Conta tarefas concluidas a partir da memoria semantica persistida.

        Parametros:
        - nenhum.

        Retorno:
        - total de tarefas com dispatch executado.

        Efeitos no sistema:
        - nenhum; alimenta relatorios da fila e do sistema.
        """

        completed_task_ids = {
            entry["metadata"]["task_id"]
            for entry in self.memory["semantic"].entries
            if entry.get("metadata", {}).get("dispatch_status") == "executed"
            and entry.get("metadata", {}).get("task_id") is not None
        }
        return len(completed_task_ids)

    def _planner_path(self) -> str:
        """
        Identifica o caminho fully-qualified da implementacao do planner.

        Parametros:
        - nenhum.

        Retorno:
        - string com modulo e nome da classe do planner.

        Efeitos no sistema:
        - nenhum; usado para introspeccao e relatorios.
        """

        if self.planner is None:
            return "executive_planner.planner.ExecutivePlanner"
        return f"{self.planner.__class__.__module__}.{self.planner.__class__.__name__}"

    @staticmethod
    def _normalize_worker_id(worker_id: str) -> str:
        """
        Remove o prefixo `worker_` quando presente.

        Parametros:
        - worker_id: identificador bruto do worker.

        Retorno:
        - nome normalizado do dominio de worker.

        Efeitos no sistema:
        - nenhum; padroniza lookup interno de workers.
        """

        if worker_id.startswith("worker_"):
            return worker_id[len("worker_") :]
        return worker_id

    @staticmethod
    def _apply_state(task: Dict[str, Any], state: str) -> None:
        """
        Atualiza o estado interno e localizado de uma tarefa.

        Parametros:
        - task: tarefa a ser mutada.
        - state: novo estado interno da tarefa.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - modifica a tarefa informada com `state` e `state_ptbr`.
        """

        task["state"] = state
        task["state_ptbr"] = traduzir_estado(state)

    @staticmethod
    def _build_completed_task_content(task: Dict[str, Any], worker_id: str, result: Dict[str, Any]) -> str:
        """
        Monta o texto semantico padrao para uma tarefa concluida.

        Parametros:
        - task: tarefa executada.
        - worker_id: worker responsavel pela execucao.
        - result: resultado final do dispatch.

        Retorno:
        - texto resumido pronto para armazenamento semantico.

        Efeitos no sistema:
        - nenhum; apenas sintetiza conteudo para memoria.
        """

        goal = task.get("goal", "Tarefa concluida")
        runtime_status = result["result"]["runtime_status_ptbr"]
        worker_summary = result.get("worker_response", {}).get("summary")
        if worker_summary:
            return f"{goal} concluida por {worker_id} com status de runtime {runtime_status}. {worker_summary}"
        return f"{goal} concluida por {worker_id} com status de runtime {runtime_status}"

    @staticmethod
    def _last_persisted_at(storage_path: Any) -> str | None:
        """
        Consulta o horario da ultima persistencia de um arquivo.

        Parametros:
        - storage_path: caminho do artefato persistente.

        Retorno:
        - timestamp ISO UTC ou `None` quando o arquivo nao existe.

        Efeitos no sistema:
        - nenhum; utilitario de healthcheck e relatorios.
        """

        if storage_path is None:
            return None
        if not storage_path.exists():
            return None
        return datetime.fromtimestamp(storage_path.stat().st_mtime, timezone.utc).isoformat()

    @staticmethod
    def _parse_isoformat(value: str) -> datetime:
        """
        Converte uma string ISO em objeto `datetime`.

        Parametros:
        - value: string temporal em formato ISO.

        Retorno:
        - objeto `datetime` correspondente.

        Efeitos no sistema:
        - nenhum; utilitario interno para calculos temporais.
        """

        return datetime.fromisoformat(value)

    @staticmethod
    def _utc_now() -> str:
        """
        Gera um timestamp UTC em formato ISO 8601.

        Parametros:
        - nenhum.

        Retorno:
        - string temporal padronizada.

        Efeitos no sistema:
        - nenhum; utilitario do runtime para registros e persistencia.
        """

        return datetime.now(timezone.utc).isoformat()
