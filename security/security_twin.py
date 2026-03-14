"""Gemeo de seguranca isolado para validacao interna do JARVIS."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Iterable

from security.threat_model_engine import ThreatModelEngine

DEFAULT_TWIN_STATE_DIR = Path(__file__).with_name("twin_state")


@dataclass
class SecurityTwin:
    """Gera e valida snapshots isolados do estado atual do JARVIS."""

    storage_dir: Path = field(default_factory=lambda: DEFAULT_TWIN_STATE_DIR)
    threat_model_engine: ThreatModelEngine = field(default_factory=ThreatModelEngine)

    def __post_init__(self) -> None:
        self.storage_dir = Path(self.storage_dir)

    @property
    def latest_snapshot_path(self) -> Path:
        return self.storage_dir / "latest_twin_snapshot.json"

    def create_twin_snapshot(
        self,
        runtime: Any,
        environment_report: Dict[str, Any] | None = None,
        health_report: Dict[str, Any] | None = None,
        snapshot_name: str | None = None,
    ) -> Dict[str, Any]:
        """Cria um snapshot sanitizado e isolado do estado atual do sistema."""

        runtime.bootstrap()
        runtime_state = deepcopy(runtime.describe_state())
        environment_snapshot = self._build_environment_snapshot(runtime_state, environment_report)
        auth_config = environment_snapshot.get("autenticacao_configurada", {})
        health_snapshot = deepcopy(
            health_report
            or runtime.build_health_report(
                api_started_at=runtime.started_at,
                token_configurado=bool(auth_config.get("token_configurado")),
                dispositivo_confiavel_configurado=bool(
                    auth_config.get("dispositivo_confiavel_configurado")
                ),
            )
        )
        threat_model = self.threat_model_engine.build_threat_model(
            runtime_state=runtime_state,
            health_report=health_snapshot,
            environment_report=environment_snapshot,
        )

        twin_id = self._build_twin_id()
        snapshot_filename = f"{snapshot_name or twin_id}.json"
        snapshot_path = self.storage_dir / snapshot_filename

        queue_snapshot = self._sanitize_queue_snapshot(runtime.list_tasks())
        semantic_snapshot = self._sanitize_semantic_memory_snapshot(runtime.memory["semantic"])
        goals_snapshot = self._sanitize_goal_snapshot(runtime.goal_manager.snapshot())
        operational_snapshot = self._build_operational_snapshot(runtime, runtime_state, health_snapshot)

        snapshot = {
            "version": "0.1.0",
            "twin_id": twin_id,
            "created_at": self._utc_now(),
            "isolated": True,
            "origem": "estado_autorizado_interno",
            "sanitizacao": {
                "conteudo_livre_mascarado": True,
                "segredos_omitidos": True,
                "metadados_sensiveis_reduzidos": True,
            },
            "configuration_snapshot": environment_snapshot,
            "task_queue_snapshot": queue_snapshot,
            "semantic_memory_snapshot": semantic_snapshot,
            "goal_snapshot": goals_snapshot,
            "operational_state_snapshot": operational_snapshot,
            "api_security_metadata": {
                "default_locale": runtime_state.get("default_locale", "pt-BR"),
                "host_api": environment_snapshot.get("host_api"),
                "porta_api": environment_snapshot.get("porta_api"),
                "painel_ativo": environment_snapshot.get("painel_ativo"),
                "autenticacao_configurada": deepcopy(
                    environment_snapshot.get("autenticacao_configurada", {})
                ),
            },
            "security_metadata": {
                "threat_model_summary": deepcopy(threat_model["resumo_ptbr"]),
                "threat_model": threat_model,
            },
            "persistencia": {
                "storage_dir": str(self.storage_dir),
                "snapshot_path": str(snapshot_path),
                "latest_snapshot_path": str(self.latest_snapshot_path),
            },
        }

        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._write_snapshot(snapshot_path, snapshot)
        self._write_snapshot(self.latest_snapshot_path, snapshot)
        return deepcopy(snapshot)

    def load_twin_snapshot(self, snapshot_path: Path | str | None = None) -> Dict[str, Any]:
        """Carrega um snapshot do gemeo de seguranca a partir do disco."""

        path = Path(snapshot_path) if snapshot_path is not None else self.latest_snapshot_path
        if not path.exists():
            raise FileNotFoundError(f"Snapshot do gemeo de seguranca nao encontrado: {path}")
        return json.loads(path.read_text(encoding="utf-8"))

    def describe_twin_state(self, snapshot: Dict[str, Any] | None = None) -> Dict[str, Any]:
        """Resume o estado atual do gemeo de seguranca em pt-BR."""

        twin_snapshot = deepcopy(snapshot) if snapshot is not None else self.load_twin_snapshot()
        queue_snapshot = twin_snapshot.get("task_queue_snapshot", {})
        semantic_snapshot = twin_snapshot.get("semantic_memory_snapshot", {})
        goal_snapshot = twin_snapshot.get("goal_snapshot", {})
        threat_summary = twin_snapshot.get("security_metadata", {}).get("threat_model_summary", {})

        return {
            "mensagem": "Gemeo de seguranca pronto para validacao interna controlada.",
            "twin_id": twin_snapshot.get("twin_id"),
            "criado_em": twin_snapshot.get("created_at"),
            "isolado": bool(twin_snapshot.get("isolated")),
            "tarefas_espelhadas": int(queue_snapshot.get("task_count", 0)),
            "memorias_espelhadas": int(semantic_snapshot.get("entry_count", 0)),
            "objetivos_ativos_espelhados": int(goal_snapshot.get("active_goal_count", 0)),
            "metas_estrategicas_espelhadas": int(goal_snapshot.get("strategic_goal_count", 0)),
            "risco_geral": threat_summary.get("risco_geral"),
            "snapshot_path": twin_snapshot.get("persistencia", {}).get("snapshot_path"),
        }

    def validate_twin_integrity(
        self,
        snapshot: Dict[str, Any] | None = None,
        forbidden_values: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """Valida a integridade estrutural e o isolamento do gemeo."""

        twin_snapshot = deepcopy(snapshot) if snapshot is not None else self.load_twin_snapshot()
        queue_snapshot = twin_snapshot.get("task_queue_snapshot", {})
        semantic_snapshot = twin_snapshot.get("semantic_memory_snapshot", {})
        goal_snapshot = twin_snapshot.get("goal_snapshot", {})
        serialized_snapshot = json.dumps(twin_snapshot, sort_keys=True, ensure_ascii=False)

        checks = {
            "versao_presente": bool(twin_snapshot.get("version")),
            "identificador_presente": bool(twin_snapshot.get("twin_id")),
            "isolamento_ativo": bool(twin_snapshot.get("isolated")),
            "sanitizacao_configurada": bool(
                twin_snapshot.get("sanitizacao", {}).get("segredos_omitidos")
                and twin_snapshot.get("sanitizacao", {}).get("conteudo_livre_mascarado")
            ),
            "configuracao_presente": "configuration_snapshot" in twin_snapshot,
            "fila_consistente": int(queue_snapshot.get("task_count", 0)) == len(
                queue_snapshot.get("tasks", [])
            ),
            "memoria_consistente": int(semantic_snapshot.get("entry_count", 0)) == len(
                semantic_snapshot.get("entries", [])
            ),
            "objetivos_consistentes": (
                int(goal_snapshot.get("strategic_goal_count", 0))
                == len(goal_snapshot.get("strategic_goals", []))
                and int(goal_snapshot.get("active_goal_count", 0))
                == len(goal_snapshot.get("active_goals", []))
            ),
            "metadados_de_seguranca_presentes": "security_metadata" in twin_snapshot,
        }

        forbidden_exposed = [
            value
            for value in (forbidden_values or [])
            if value and str(value) in serialized_snapshot
        ]
        checks["valores_proibidos_ausentes"] = not forbidden_exposed

        issues = [nome for nome, valido in checks.items() if not valido]
        mensagem = (
            "Gemeo de seguranca valido e isolado."
            if not issues
            else "Gemeo de seguranca com inconsistencias detectadas."
        )

        return {
            "valido": not issues,
            "mensagem": mensagem,
            "checks": checks,
            "problemas": issues,
            "valores_proibidos_expostos": forbidden_exposed,
        }

    def _build_environment_snapshot(
        self,
        runtime_state: Dict[str, Any],
        environment_report: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if environment_report is not None:
            snapshot = deepcopy(environment_report)
            snapshot.setdefault("ambiente", "desconhecido")
            snapshot.setdefault("host_api", None)
            snapshot.setdefault("porta_api", None)
            snapshot.setdefault("loop_runtime_ativo", True)
            snapshot.setdefault("painel_ativo", True)
            snapshot.setdefault("nivel_log", "INFO")
            snapshot.setdefault(
                "paths_persistentes",
                {
                    "queue_storage_path": runtime_state.get("queue_store"),
                    "semantic_storage_path": runtime_state.get("semantic_store"),
                    "goals_storage_path": runtime_state.get("goal_store"),
                },
            )
            snapshot.setdefault(
                "autenticacao_configurada",
                {
                    "token_configurado": False,
                    "dispositivo_confiavel_configurado": False,
                },
            )
            return snapshot

        return {
            "ambiente": "desconhecido",
            "host_api": None,
            "porta_api": None,
            "loop_runtime_ativo": True,
            "painel_ativo": True,
            "nivel_log": "INFO",
            "paths_persistentes": {
                "queue_storage_path": runtime_state.get("queue_store"),
                "semantic_storage_path": runtime_state.get("semantic_store"),
                "goals_storage_path": runtime_state.get("goal_store"),
            },
            "autenticacao_configurada": {
                "token_configurado": False,
                "dispositivo_confiavel_configurado": False,
            },
        }

    def _build_operational_snapshot(
        self,
        runtime: Any,
        runtime_state: Dict[str, Any],
        health_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        planner_report = runtime.build_planner_report()
        queue_report = runtime.build_queue_report()
        memory_report = runtime.build_memory_report()
        goal_report = runtime.build_goal_operational_report()
        audit_report = runtime.build_audit_report()

        return {
            "runtime_state": deepcopy(runtime_state),
            "health_report": deepcopy(health_report),
            "planner_summary": {
                "acoplado": planner_report.get("acoplado"),
                "classe": planner_report.get("classe"),
                "total_entradas_auditoria": planner_report.get("total_entradas_auditoria"),
                "ultimo_evento": (
                    planner_report.get("ultima_decisao", {}) or {}
                ).get("event"),
            },
            "queue_summary": deepcopy(queue_report.get("resumo", {})),
            "memory_summary": deepcopy(memory_report.get("resumo", {})),
            "goal_summary": deepcopy(goal_report.get("resumo", {})),
            "audit_summary": {
                "total_decisoes_planner": len(audit_report.get("ultimas_decisoes_planner", [])),
                "total_acessos_recentes": len(audit_report.get("ultimos_acessos", [])),
                "total_negacoes_recentes": len(audit_report.get("ultimas_tentativas_negadas", [])),
                "total_falhas_recentes": len(audit_report.get("ultimas_falhas", [])),
            },
        }

    def _sanitize_queue_snapshot(self, tasks: list[Dict[str, Any]]) -> Dict[str, Any]:
        sanitized_tasks = [
            {
                "task_id": task.get("task_id"),
                "domain": task.get("domain"),
                "worker": task.get("worker") or task.get("worker_id"),
                "urgency": int(task.get("urgency", 0)),
                "impact": int(task.get("impact", 0)),
                "cost": int(task.get("cost", 0)),
                "reversibility": int(task.get("reversibility", 0)),
                "risk": int(task.get("risk", 0)),
                "goal_priority": int(task.get("goal_priority", 0)),
                "approval": deepcopy(task.get("approval", {})),
                "state": task.get("state"),
                "state_ptbr": task.get("state_ptbr"),
                "parent_goal_id": task.get("parent_goal_id"),
                "timestamps": deepcopy(task.get("timestamps", {})),
                "has_description": bool(task.get("description")),
                "has_goal": bool(task.get("goal")),
                "has_parent_goal_label": bool(task.get("parent_goal")),
                "evidence_count": len(task.get("evidence", [])),
            }
            for task in tasks
        ]
        return {
            "task_count": len(sanitized_tasks),
            "tasks": sanitized_tasks,
        }

    def _sanitize_semantic_memory_snapshot(self, semantic_memory: Any) -> Dict[str, Any]:
        entries = [
            {
                "id": entry.get("id"),
                "domain": entry.get("domain"),
                "tags": list(entry.get("tags", [])),
                "source": entry.get("source"),
                "created_at": entry.get("created_at"),
                "importance": int(entry.get("importance", 0)),
                "content_masked": bool(entry.get("content")),
                "metadata": self._sanitize_free_text(entry.get("metadata", {})),
            }
            for entry in semantic_memory.entries
        ]

        return {
            "entry_count": len(entries),
            "fact_count": len(semantic_memory.facts),
            "fact_keys": sorted(str(key) for key in semantic_memory.facts),
            "entries": entries,
            "storage_path": str(semantic_memory.storage_path),
        }

    def _sanitize_goal_snapshot(self, goal_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        strategic_goals = [
            self._sanitize_goal(goal)
            for goal in goal_snapshot.get("strategic_goals", [])
        ]
        active_goals = [
            self._sanitize_goal(goal)
            for goal in goal_snapshot.get("active_goals", [])
        ]

        return {
            "updated_at": goal_snapshot.get("updated_at"),
            "constraints": list(goal_snapshot.get("constraints", [])),
            "preferences": self._sanitize_free_text(goal_snapshot.get("preferences", {})),
            "strategic_goal_count": len(strategic_goals),
            "active_goal_count": len(active_goals),
            "strategic_goals": strategic_goals,
            "active_goals": active_goals,
        }

    def _sanitize_goal(self, goal: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "goal_id": goal.get("goal_id"),
            "kind": goal.get("kind"),
            "state": goal.get("state"),
            "priority": int(goal.get("priority", 0)),
            "deadline": goal.get("deadline"),
            "progress": int(goal.get("progress", 0)),
            "task_ids": list(goal.get("task_ids", [])),
            "completed_task_ids": list(goal.get("completed_task_ids", [])),
            "created_at": goal.get("created_at"),
            "updated_at": goal.get("updated_at"),
            "last_result": goal.get("last_result"),
            "has_title": bool(goal.get("title")),
            "has_description": bool(goal.get("description")),
            "metadata": self._sanitize_free_text(goal.get("metadata", {})),
        }

    def _sanitize_free_text(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {str(key): self._sanitize_free_text(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._sanitize_free_text(item) for item in value]
        if isinstance(value, str):
            if not value:
                return value
            return "[sanitizado]"
        return deepcopy(value)

    @staticmethod
    def _write_snapshot(path: Path, snapshot: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    @staticmethod
    def _build_twin_id() -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        return f"security-twin-{timestamp}"

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
