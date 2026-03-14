"""Bootstrap interno do runtime do Sistema Cognitivo JARVIS."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import json
from typing import Any, Dict

from constitutional_core.policy import load_constitutional_policy
from executive_planner.audit import traduzir_estado, traduzir_motivo, traduzir_status
from runtime.autonomy import AutonomyController


class InternalAgentRuntime:
    """Inicializa o runtime funcional do sistema e coordena a execucao basica."""

    def __init__(self, autonomy_controller: AutonomyController | None = None) -> None:
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

    def bootstrap(self) -> Dict[str, Any]:
        """Inicializa o primeiro runtime funcional do sistema."""

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
        self.goal_manager = self.goal_manager if self.goal_manager is not None else GoalManager()

        if not self.memory:
            self.memory = {}

        self.memory.setdefault("episodic", EpisodicMemory())
        self.memory.setdefault("semantic", SemanticMemory())
        self.memory.setdefault("procedural", ProceduralMemory())

        semantic_memory = self.memory["semantic"]
        if not semantic_memory.entries and not semantic_memory.facts:
            semantic_memory.load_snapshot()
        semantic_memory.auto_persist = True

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
        self.memory["procedural"].register(
            "planner_cycle",
            ["planejar", "priorizar", "validar", "agendar", "executar", "revisar"],
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

        if self.started_at is None:
            self.started_at = self._utc_now()
        self.status = "initialized"
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

        worker_response = worker.handle(task)
        self._apply_state(task, "completed")
        result = {
            "status": "executed",
            "status_ptbr": traduzir_status("executed"),
            "task": task,
            "worker": worker_id,
            "worker_response": worker_response,
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
            },
        )
        self.goal_manager.record_task_result(task, result)
        return result

    def enqueue_task(self, task: Dict[str, Any]) -> None:
        """Adiciona uma tarefa na fila controlada pelo runtime."""

        self.bootstrap()
        task_to_enqueue = deepcopy(task)
        parent_goal_id = task_to_enqueue.get("parent_goal_id")
        if parent_goal_id is not None:
            task_to_enqueue = self.goal_manager.link_task_to_goal(task_to_enqueue, str(parent_goal_id))
        return self.task_queue.enqueue(task_to_enqueue)

    def run_planner_cycle(self) -> Dict[str, Any]:
        """Executa um ciclo do planner a partir de um runtime inicializado."""

        self.bootstrap()
        cycle_result = self.planner.run_cycle()
        self.total_cycles_executed += 1
        self.last_cycle_at = self._utc_now()
        self.last_cycle_result = deepcopy(cycle_result)
        return cycle_result

    def query_semantic_memory(
        self, query: str, domain: str | None = None, limit: int = 5
    ) -> list[Dict[str, Any]]:
        """Consulta a memoria semantica em busca de entradas relevantes."""

        self.bootstrap()
        return self.memory["semantic"].search(query=query, domain=domain, limit=limit)

    def get_goal_report(self, goal_id: str | None = None) -> Dict[str, Any]:
        """Retorna um relatorio de objetivos em pt-BR."""

        self.bootstrap()
        return self.goal_manager.goal_report(goal_id)

    def list_tasks(self) -> list[Dict[str, Any]]:
        """Retorna uma copia da fila atual de tarefas."""

        self.bootstrap()
        return [deepcopy(task) for task in self.task_queue.items]

    def get_recent_events(self, limit: int = 10) -> list[Dict[str, Any]]:
        """Retorna os eventos episodicos mais recentes."""

        self.bootstrap()
        return self.memory["episodic"].recent(limit)

    def get_recent_semantic_entries(
        self,
        limit: int = 10,
        domain: str | None = None,
    ) -> list[Dict[str, Any]]:
        """Retorna as entradas semanticas mais recentes."""

        self.bootstrap()
        return self.memory["semantic"].recent_entries(limit=limit, domain=domain)

    def build_system_report(self, last_cycle_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Monta um relatorio operacional resumido do sistema."""

        self.bootstrap()
        queue_report = self.build_queue_report()
        memory_report = self.build_memory_report()
        goals_report = self.build_goal_operational_report()
        audit_report = self.build_audit_report()
        planner_report = self.build_planner_report()
        current_cycle = deepcopy(last_cycle_result or self.last_cycle_result)

        return {
            "mensagem": "Relatorio operacional do JARVIS.",
            "status_runtime": self.describe_state(),
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
            "saude_runtime": {
                "status": "ok" if self.status == "initialized" else "degradado",
                "status_ptbr": "saudavel" if self.status == "initialized" else "degradado",
            },
        }

    def build_planner_report(self) -> Dict[str, Any]:
        """Retorna o estado operacional atual do planner."""

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

        self.bootstrap()
        semantic_memory = self.memory["semantic"]
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
                "ultima_escrita": latest_write,
                "integridade_basica": integrity,
            },
            "memorias_recentes": self.get_recent_semantic_entries(limit=5),
            "memorias_por_dominio": [
                {"dominio": domain, "total": total}
                for domain, total in sorted(domain_counts.items(), key=lambda item: item[0])
            ],
        }

    def build_audit_report(self) -> Dict[str, Any]:
        """Retorna um relatorio consolidado de auditoria."""

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
        }

    def build_health_report(
        self,
        api_started_at: str | None = None,
        token_configurado: bool = False,
        dispositivo_confiavel_configurado: bool = False,
    ) -> Dict[str, Any]:
        """Retorna um health report operacional do sistema."""

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
            "configuracao_minima_valida": config_valid,
            "dispositivo_confiavel_configurado": dispositivo_confiavel_configurado,
            "token_configurado": token_configurado,
            "uptime_segundos": self._uptime_seconds(),
            "api_iniciada_em": api_started_at,
            "runtime_iniciado_em": self.started_at,
            "ultima_persistencia_fila": self._last_persisted_at(
                getattr(self.task_queue, "storage_path", None)
            ),
            "ultima_persistencia_memoria": self._last_persisted_at(
                getattr(self.memory.get("semantic"), "storage_path", None)
            ),
            "ultima_persistencia_objetivos": self._last_persisted_at(
                getattr(self.goal_manager, "storage_path", None)
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

        self.bootstrap()
        status = "authorized" if allowed else "denied"
        payload = {
            "endpoint": endpoint,
            "method": method,
            "device_id": device_id or "nao_informado",
            "status": status,
            "client_host": client_host,
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

        self.bootstrap()
        access_entries = [entry for entry in self.audit_logger.entries if entry["event"] == "access"]
        if denied_only:
            access_entries = [
                entry for entry in access_entries if entry["payload"].get("status") == "denied"
            ]
        return [deepcopy(entry) for entry in access_entries[-limit:]]

    def persist_runtime_state(self) -> Dict[str, Any]:
        """Persiste os artefatos de runtime necessarios para reinicio seguro."""

        self.bootstrap()

        queue_snapshot = None
        if self.task_queue is not None:
            queue_snapshot = self.task_queue.save_to_disk()

        semantic_snapshot = None
        semantic_memory = self.memory.get("semantic")
        if semantic_memory is not None:
            semantic_snapshot = semantic_memory.snapshot()

        goals_snapshot = None
        if self.goal_manager is not None:
            goals_snapshot = self.goal_manager.snapshot()

        return {
            "queue": deepcopy(queue_snapshot),
            "semantic_memory": deepcopy(semantic_snapshot),
            "goals": deepcopy(goals_snapshot),
        }

    def describe_state(self) -> Dict[str, Any]:
        """Retorna um snapshot leve do estado atual do runtime inicializado."""

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
            "last_cycle_at": self.last_cycle_at,
            "total_cycles_executed": self.total_cycles_executed,
        }

    def build_policy_report(self) -> Dict[str, Any]:
        """Retorna um resumo seguro da politica constitucional ativa."""

        self.bootstrap()
        return self.constitutional_policy.describe()

    def _uptime_seconds(self) -> int:
        if self.started_at is None:
            return 0
        started_at = self._parse_isoformat(self.started_at)
        return int((datetime.now(timezone.utc) - started_at).total_seconds())

    def _count_completed_tasks(self) -> int:
        completed_task_ids = {
            entry["metadata"]["task_id"]
            for entry in self.memory["semantic"].entries
            if entry.get("metadata", {}).get("dispatch_status") == "executed"
            and entry.get("metadata", {}).get("task_id") is not None
        }
        return len(completed_task_ids)

    def _planner_path(self) -> str:
        if self.planner is None:
            return "executive_planner.planner.ExecutivePlanner"
        return f"{self.planner.__class__.__module__}.{self.planner.__class__.__name__}"

    @staticmethod
    def _normalize_worker_id(worker_id: str) -> str:
        if worker_id.startswith("worker_"):
            return worker_id[len("worker_") :]
        return worker_id

    @staticmethod
    def _apply_state(task: Dict[str, Any], state: str) -> None:
        task["state"] = state
        task["state_ptbr"] = traduzir_estado(state)

    @staticmethod
    def _build_completed_task_content(task: Dict[str, Any], worker_id: str, result: Dict[str, Any]) -> str:
        goal = task.get("goal", "Tarefa concluida")
        runtime_status = result["result"]["runtime_status_ptbr"]
        return f"{goal} concluida por {worker_id} com status de runtime {runtime_status}"

    @staticmethod
    def _last_persisted_at(storage_path: Any) -> str | None:
        if storage_path is None:
            return None
        if not storage_path.exists():
            return None
        return datetime.fromtimestamp(storage_path.stat().st_mtime, timezone.utc).isoformat()

    @staticmethod
    def _parse_isoformat(value: str) -> datetime:
        return datetime.fromisoformat(value)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
