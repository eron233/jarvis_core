"""Primitivos de auditoria e rotulos pt-BR para o planejador."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

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
}

MOTIVOS_PTBR = {
    "no_tasks": "sem_tarefas",
    "no_executable_task": "sem_tarefa_executavel",
    "autonomy_gate": "bloqueada_pela_politica_de_autonomia",
    "unknown_worker": "worker_desconhecido",
    "missing_token": "token_ausente",
    "invalid_token": "token_invalido",
    "missing_device_id": "device_id_ausente",
    "untrusted_device": "dispositivo_nao_autorizado",
}


def traduzir_evento(evento: str) -> str:
    return EVENTOS_PTBR.get(evento, evento)


def traduzir_status(status: str) -> str:
    return STATUS_PTBR.get(status, status)


def traduzir_estado(estado: str) -> str:
    return STATUS_PTBR.get(estado, estado)


def traduzir_motivo(motivo: str) -> str:
    return MOTIVOS_PTBR.get(motivo, motivo)


@dataclass
class AuditLogger:
    """Armazena entradas leves de auditoria em memoria."""

    entries: List[Dict[str, Any]] = field(default_factory=list)

    def record(self, event: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        return entry
