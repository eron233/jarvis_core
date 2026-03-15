"""
JARVIS - Auditoria do Planejador

Responsavel por:
- traduzir eventos, estados e motivos para a camada visivel em pt-BR
- registrar decisoes do planner, runtime e seguranca
- manter rastreabilidade leve em memoria para relatorios e validacoes

Integracoes principais:
- executive_planner.planner
- runtime.internal_agent_runtime
- interface.api.app
"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from threading import RLock
import threading
import time
from typing import Any, Dict, List, Optional

#
# JARVIS_PLANNER_LOGIC
# ==================================================
# BLOCO: Dicionarios de traducao para a camada visivel
# ==================================================

EVENTOS_PTBR = {
    "plan": "planejar",
    "prioritize": "priorizar",
    "validate": "validar",
    "schedule": "agendar",
    "execute": "executar",
    "review": "revisar",
    "bootstrap": "inicializar",
    "dispatch": "despachar",
    "access": "acesso",
    "command": "comando",
    "self_defense": "autodefesa",
    "runtime_watchdog": "watchdog_do_runtime",
    "security_remediation": "remediacao_de_seguranca",
    "cognitive_evolution": "evolucao_cognitiva",
}

STATUS_PTBR = {
    "pending": "pendente",
    "running": "em_execucao",
    "blocked": "bloqueada",
    "completed": "concluida",
    "failed": "falhou",
    "awaiting_approval": "aguardando_aprovacao",
    "initialized": "inicializado",
    "idle": "ociosa",
    "executed": "executada",
    "rejected": "rejeitada",
    "accepted": "aceita",
    "draft": "rascunho",
    "cold": "frio",
    "queued": "na_fila",
    "scheduled": "agendada",
    "executing": "em_execucao",
    "deferred": "adiada",
    "selected": "selecionada",
    "authorized": "autorizado",
    "denied": "negado",
    "applied": "aplicada",
    "skipped": "nao_aplicada",
    "ignored": "ignorada",
}

MOTIVOS_PTBR = {
    "no_tasks": "sem_tarefas",
    "no_executable_task": "sem_tarefa_executavel",
    "autonomy_gate": "bloqueada_pela_politica_de_autonomia",
    "policy_denied": "negada_pela_politica_constitucional",
    "outside_autonomy_scope": "fora_do_escopo_autonomo",
    "unknown_worker": "worker_desconhecido",
    "worker_rejected": "worker_rejeitou_a_tarefa",
    "invalid_domain": "dominio_invalido_para_worker",
    "missing_token": "token_ausente",
    "invalid_token": "token_invalido",
    "missing_device_id": "device_id_ausente",
    "untrusted_device": "dispositivo_nao_autorizado",
    "requires_human_approval": "requer_aprovacao_humana",
    "missing_runtime_context": "contexto_de_runtime_ausente",
    "missing_environment_context": "contexto_de_ambiente_ausente",
    "safe_correction_not_available": "correcao_segura_indisponivel",
    "guest_restricted_command": "comando_restrito_ao_admin",
    "special_phrase_ignored": "frase_especial_ignorada",
    "runtime_exception": "excecao_no_loop_principal",
    "missing_request_nonce": "nonce_ausente",
    "missing_request_timestamp": "timestamp_ausente",
    "invalid_request_timestamp": "timestamp_invalido",
    "stale_request_timestamp": "timestamp_expirado",
    "replay_detected": "replay_detectado",
}

DEFAULT_AUDIT_STORAGE_PATH = Path(__file__).resolve().parents[1] / "data" / "runtime_audit_store.json"


def traduzir_evento(evento: str) -> str:
    """
    Traduz um identificador interno de evento para pt-BR.

    Parametros:
    - evento: nome interno do evento registrado pelo sistema.

    Retorno:
    - label localizada para exibicao humana.

    Efeitos no sistema:
    - nenhum; apenas padroniza a representacao visivel.
    """

    return EVENTOS_PTBR.get(evento, evento)


def traduzir_status(status: str) -> str:
    """
    Traduz um status operacional interno para pt-BR.

    Parametros:
    - status: status bruto do planner, runtime ou worker.

    Retorno:
    - equivalente localizado do status.

    Efeitos no sistema:
    - nenhum; usado por respostas, logs e auditoria.
    """

    return STATUS_PTBR.get(status, status)


def traduzir_estado(estado: str) -> str:
    """
    Traduz um estado de tarefa para pt-BR.

    Parametros:
    - estado: identificador interno do estado da tarefa.

    Retorno:
    - equivalente localizado do estado.

    Efeitos no sistema:
    - nenhum; centraliza a nomenclatura visivel das filas e decisoes.
    """

    return STATUS_PTBR.get(estado, estado)


def traduzir_motivo(motivo: str) -> str:
    """
    Traduz um motivo tecnico de bloqueio ou falha para pt-BR.

    Parametros:
    - motivo: chave interna que explica uma decisao.

    Retorno:
    - label localizada do motivo informado.

    Efeitos no sistema:
    - nenhum; melhora rastreabilidade humana dos relatorios.
    """

    return MOTIVOS_PTBR.get(motivo, motivo)


@dataclass
class AuditLogger:
    """Armazena entradas leves de auditoria em memoria e em JSON persistente."""

    entries: List[Dict[str, Any]] = field(default_factory=list)
    storage_path: Path = field(default_factory=lambda: DEFAULT_AUDIT_STORAGE_PATH)
    auto_persist: bool = False
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def __post_init__(self) -> None:
        """Normaliza o caminho de persistencia do logger."""

        self.storage_path = Path(self.storage_path)

    def record(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Registra uma entrada de auditoria com traducao dos campos visiveis.

        Parametros:
        - event: nome interno do evento registrado.
        - payload: dados associados a decisao ou ocorrencia.

        Retorno:
        - entrada completa de auditoria pronta para armazenamento em memoria.

        Efeitos no sistema:
        - adiciona um novo evento rastreavel em `entries`.
        """

        with self._lock:
            payload_normalizado = dict(payload or {})

            if "status" in payload_normalizado:
                payload_normalizado["status_ptbr"] = traduzir_status(str(payload_normalizado["status"]))

            if "reason" in payload_normalizado:
                payload_normalizado["reason_ptbr"] = traduzir_motivo(str(payload_normalizado["reason"]))

            if "decision" in payload_normalizado:
                payload_normalizado["decision_ptbr"] = traduzir_estado(str(payload_normalizado["decision"]))

            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "event": event,
                "event_ptbr": traduzir_evento(event),
                "payload": payload_normalizado,
            }
            self.entries.append(entry)
            if self.auto_persist:
                self.save_to_disk()
            return deepcopy(entry)

    def snapshot(self) -> Dict[str, Any]:
        """
        Retorna o snapshot serializavel da auditoria atual.

        Parametros:
        - nenhum.

        Retorno:
        - dicionario com metadados e todas as entradas registradas.

        Efeitos no sistema:
        - nenhum; usado por persistencia e relatorios.
        """

        with self._lock:
            return {
                "version": "0.1.0",
                "entry_count": len(self.entries),
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "entries": [deepcopy(entry) for entry in self.entries],
            }

    def save_to_disk(self) -> Dict[str, Any]:
        """
        Persiste a auditoria completa em disco via replace atomico.

        Parametros:
        - nenhum.

        Retorno:
        - snapshot gravado em JSON.

        Efeitos no sistema:
        - grava a trilha de auditoria operacional e de seguranca.
        """

        with self._lock:
            snapshot = self.snapshot()
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.storage_path.with_name(
                f"{self.storage_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
            )
            temp_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False), encoding="utf-8")
            for attempt in range(5):
                try:
                    os.replace(temp_path, self.storage_path)
                    break
                except PermissionError:
                    if attempt == 4:
                        raise
                    time.sleep(0.05 * (attempt + 1))
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            return snapshot

    def load_snapshot(self) -> Dict[str, Any]:
        """
        Recarrega a auditoria persistida anteriormente.

        Parametros:
        - nenhum.

        Retorno:
        - snapshot carregado apos normalizacao.

        Efeitos no sistema:
        - substitui `entries` pelo conteudo persistido em disco.
        """

        with self._lock:
            if not self.storage_path.exists():
                self.entries = []
                return self.snapshot()

            snapshot = json.loads(self.storage_path.read_text(encoding="utf-8"))
            entries = snapshot.get("entries", [])
            self.entries = [deepcopy(entry) for entry in entries if isinstance(entry, dict)]
            return self.snapshot()

    def auto_persist_on_change(self, enabled: bool = True) -> None:
        """Ativa ou desativa a persistencia automatica da auditoria."""

        with self._lock:
            self.auto_persist = enabled
