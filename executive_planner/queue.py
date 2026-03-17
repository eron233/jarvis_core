"""
JARVIS - Fila Persistente de Tarefas

Responsavel por:
- armazenar tarefas em ordem de processamento
- normalizar estados, aprovacoes e timestamps
- persistir e recarregar a fila do planner em JSON

Integracoes principais:
- executive_planner.planner
- runtime.internal_agent_runtime
- intent_layer.goal_manager
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any, Deque, Dict, List, Optional

from executive_planner.audit import traduzir_estado

#
# JARVIS_PLANNER_LOGIC
# ==================================================
# BLOCO: Fila persistente e normalizacao de tarefas
# ==================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STORAGE_PATH = PROJECT_ROOT / "data" / "task_queue_store.json"
LEGACY_STORAGE_PATH = Path(__file__).with_name("task_queue_store.json")


@dataclass
class TaskQueue:
    """Fila FIFO de tarefas com persistencia deterministica em disco."""

    items: Deque[Dict[str, Any]] = field(default_factory=deque)
    storage_path: Path = field(default_factory=lambda: DEFAULT_STORAGE_PATH)
    auto_persist: bool = False
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        """
        Normaliza o path de persistencia recebido pelo construtor.

        Parametros:
        - nenhum.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - garante que `storage_path` sempre seja um `Path`.
        """

        self.storage_path = Path(self.storage_path)
        self._migrate_legacy_storage_if_needed()

    def enqueue(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Adiciona uma tarefa normalizada ao fim da fila.

        Parametros:
        - task: tarefa bruta ou parcialmente normalizada.

        Retorno:
        - copia profunda da tarefa enfileirada.

        Efeitos no sistema:
        - atualiza a fila e pode persisti-la imediatamente.
        """

        with self._lock:
            normalized_task = self._normalize_task(task, default_state="queued")
            self.items.append(normalized_task)

            if self.auto_persist:
                self.save_to_disk()

            return deepcopy(normalized_task)

    def dequeue(self) -> Optional[Dict[str, Any]]:
        """
        Remove e retorna a primeira tarefa da fila.

        Parametros:
        - nenhum.

        Retorno:
        - tarefa removida ou `None` quando a fila esta vazia.

        Efeitos no sistema:
        - reduz a profundidade da fila e pode persistir o novo estado.
        """

        with self._lock:
            if not self.items:
                return None

            task = self.items.popleft()
            task = self._normalize_task(task, default_state=task.get("state", "queued"))

            if self.auto_persist:
                self.save_to_disk()

            return deepcopy(task)

    def drain(self) -> List[Dict[str, Any]]:
        """
        Esvazia a fila retornando todas as tarefas atuais.

        Parametros:
        - nenhum.

        Retorno:
        - lista com copia das tarefas drenadas.

        Efeitos no sistema:
        - remove todas as tarefas da fila e pode persistir a mudanca.
        """

        with self._lock:
            tasks = [deepcopy(task) for task in self.items]
            self.items.clear()

            if self.auto_persist:
                self.save_to_disk()

            return tasks

    def snapshot_items(self) -> List[Dict[str, Any]]:
        """
        Retorna um snapshot das tarefas sem esvaziar a fila persistente.

        Parametros:
        - nenhum.

        Retorno:
        - copia profunda das tarefas atualmente enfileiradas.

        Efeitos no sistema:
        - nenhum; permite planejamento sem abrir janela silenciosa de perda.
        """

        with self._lock:
            return [deepcopy(task) for task in self.items]

    def replace(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Substitui o conteudo inteiro da fila por uma nova lista de tarefas.

        Parametros:
        - tasks: novo conjunto final de tarefas a persistir.

        Retorno:
        - snapshot gravado apos a substituicao.

        Efeitos no sistema:
        - atualiza a fila de forma atomica no processo e no armazenamento.
        """

        with self._lock:
            self.items = deque(self._normalize_task(task, default_state=task.get("state", "queued")) for task in tasks)
            return self.save_to_disk()

    def save_to_disk(self) -> Dict[str, Any]:
        """
        Persiste o snapshot atual da fila em disco.

        Parametros:
        - nenhum.

        Retorno:
        - snapshot serializado que foi gravado.

        Efeitos no sistema:
        - escreve o arquivo JSON da fila persistente.
        """

        with self._lock:
            snapshot = self._build_snapshot()
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_snapshot_atomic(snapshot)
            return snapshot

    def load_from_disk(self) -> Dict[str, Any]:
        """
        Recarrega a fila a partir do arquivo persistente.

        Parametros:
        - nenhum.

        Retorno:
        - snapshot normalizado apos a carga.

        Efeitos no sistema:
        - substitui o conteudo atual da fila pelo estado em disco.
        """

        with self._lock:
            if not self.storage_path.exists():
                self.items = deque()
                return self._build_snapshot(saved_at=None)

            snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))
            loaded_tasks = snapshot.get("tasks", [])
            self.items = deque(self._normalize_task(task) for task in loaded_tasks)
            return self._build_snapshot(saved_at=snapshot.get("saved_at"))

    def auto_persist_on_change(self, enabled: bool = True) -> None:
        """
        Ativa ou desativa persistencia automatica a cada mutacao.

        Parametros:
        - enabled: indicador de ativacao do auto-save.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - altera a estrategia de persistencia da fila.
        """

        with self._lock:
            self.auto_persist = enabled

    def __len__(self) -> int:
        """
        Retorna o tamanho atual da fila.

        Parametros:
        - nenhum.

        Retorno:
        - quantidade de tarefas atualmente armazenadas.

        Efeitos no sistema:
        - nenhum; apenas leitura da fila.
        """

        with self._lock:
            return len(self.items)

    def _build_snapshot(self, saved_at: Optional[str] = None) -> Dict[str, Any]:
        """
        Monta o snapshot serializavel da fila atual.

        Parametros:
        - saved_at: timestamp opcional reaproveitado de um snapshot existente.

        Retorno:
        - dicionario pronto para gravacao em JSON.

        Efeitos no sistema:
        - nenhum; usado por persistencia e relatorios.
        """

        return {
            "version": "0.1.0",
            "task_count": len(self.items),
            "saved_at": saved_at or self._utc_now(),
            "tasks": [deepcopy(task) for task in self.items],
        }

    def _normalize_task(
        self,
        task: Dict[str, Any],
        default_state: str = "queued",
    ) -> Dict[str, Any]:
        """
        Padroniza a estrutura de uma tarefa para armazenamento na fila.

        Parametros:
        - task: tarefa original recebida do planner, runtime ou API.
        - default_state: estado aplicado quando o payload nao o informa.

        Retorno:
        - tarefa normalizada com campos obrigatorios e labels em pt-BR.

        Efeitos no sistema:
        - nenhum; prepara dados consistentes para fila e persistencia.
        """

        normalized = deepcopy(task)
        now = self._utc_now()

        task_id = normalized.get("task_id", normalized.get("id"))
        if task_id is not None:
            normalized["task_id"] = str(task_id)

        description = str(normalized.get("description") or normalized.get("goal") or "")
        parent_goal = str(normalized.get("parent_goal") or normalized.get("goal") or description)
        parent_goal_id = normalized.get("parent_goal_id")
        domain = str(
            normalized.get("domain")
            or normalized.get("worker")
            or normalized.get("worker_id")
            or "general"
        )

        approval = normalized.get("approval", {})
        if not isinstance(approval, dict):
            approval = {}

        approved = bool(approval.get("approved", normalized.get("approved", True)))
        requires_supervision = bool(
            approval.get("requires_supervision", normalized.get("requires_supervision", False))
        )

        evidence = normalized.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [evidence]

        timestamps = normalized.get("timestamps", {})
        if not isinstance(timestamps, dict):
            timestamps = {}

        created_at = str(normalized.get("created_at") or timestamps.get("created_at") or now)
        updated_at = str(normalized.get("updated_at") or timestamps.get("updated_at") or created_at)
        queued_at = str(normalized.get("queued_at") or timestamps.get("queued_at") or created_at)
        state = str(normalized.get("state", default_state))

        normalized.update(
            {
                "description": description,
                "goal": str(normalized.get("goal") or description or parent_goal),
                "domain": domain,
                "urgency": int(normalized.get("urgency", 0)),
                "impact": int(normalized.get("impact", normalized.get("importance", 0))),
                "importance": int(normalized.get("importance", normalized.get("impact", 0))),
                "cost": int(normalized.get("cost", 0)),
                "reversibility": int(normalized.get("reversibility", 0)),
                "risk": int(normalized.get("risk", 0)),
                "goal_priority": int(normalized.get("goal_priority", 0)),
                "approval": {
                    "approved": approved,
                    "requires_supervision": requires_supervision,
                },
                "approved": approved,
                "requires_supervision": requires_supervision,
                "state": state,
                "state_ptbr": traduzir_estado(state),
                "evidence": deepcopy(evidence),
                "parent_goal": parent_goal,
                "parent_goal_id": None if parent_goal_id is None else str(parent_goal_id),
                "timestamps": {
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "queued_at": queued_at,
                },
                "created_at": created_at,
                "updated_at": updated_at,
                "queued_at": queued_at,
            }
        )
        return normalized

    def _write_snapshot_atomic(self, snapshot: Dict[str, Any]) -> None:
        """
        Grava um snapshot JSON via arquivo temporario seguido de replace atomico.

        Parametros:
        - snapshot: payload serializavel da fila.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - reduz risco de corrupcao parcial durante persistencia da fila.
        """

        temp_path = self.storage_path.with_name(f"{self.storage_path.name}.tmp")
        temp_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
        os.replace(temp_path, self.storage_path)

    def _migrate_legacy_storage_if_needed(self) -> None:
        """
        Migra automaticamente a fila legada para o store oficial em `data/`.

        Parametros:
        - nenhum.

        Retorno:
        - nenhum.

        Efeitos no sistema:
        - move o arquivo legado para o path oficial quando a fila ainda nao foi migrada.
        """

        if self.storage_path != DEFAULT_STORAGE_PATH:
            return
        if self.storage_path.exists():
            return
        if not LEGACY_STORAGE_PATH.exists() or LEGACY_STORAGE_PATH == self.storage_path:
            return

        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        os.replace(LEGACY_STORAGE_PATH, self.storage_path)

    @staticmethod
    def _utc_now() -> str:
        """
        Gera um timestamp UTC em formato ISO 8601.

        Parametros:
        - nenhum.

        Retorno:
        - string de data e hora em UTC.

        Efeitos no sistema:
        - nenhum; utilitario para normalizacao temporal.
        """

        return datetime.now(timezone.utc).isoformat()
