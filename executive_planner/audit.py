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

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
}


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
    """Armazena entradas leves de auditoria em memoria."""

    entries: List[Dict[str, Any]] = field(default_factory=list)

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
