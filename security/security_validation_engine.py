"""Validacao interna controlada do JARVIS sobre o gemeo de seguranca."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from security.security_twin import SecurityTwin

SEVERITY_POINTS = {
    "baixo": 1,
    "medio": 2,
    "alto": 3,
    "critico": 4,
}

DETECTABILITY_POINTS = {
    "alta": 1,
    "media": 2,
    "baixa": 3,
}

REVERSIBILITY_POINTS = {
    "alta": 1,
    "media": 2,
    "baixa": 3,
}


@dataclass
class SecurityValidationEngine:
    """Executa cenarios defensivos controlados apenas sobre o gemeo isolado."""

    twin: SecurityTwin = field(default_factory=SecurityTwin)

    def run_validation_suite(
        self,
        twin_snapshot: Dict[str, Any] | None = None,
        snapshot_path: str | None = None,
    ) -> Dict[str, Any]:
        """Executa a suite de validacao interna controlada."""

        snapshot = deepcopy(twin_snapshot) if twin_snapshot is not None else self.twin.load_twin_snapshot(snapshot_path)
        integrity_report = self.twin.validate_twin_integrity(snapshot)
        executed_at = self._utc_now()

        if not integrity_report["valido"]:
            weakness = self._build_weakness(
                weakness_id="twin_integrity_invalid",
                nome="Gemeo de seguranca inconsistente",
                descricao="O espelho defensivo nao passou na validacao estrutural e deve ser regenerado antes de qualquer simulacao.",
                categoria="integridade_do_ambiente",
                local="security_twin",
                gravidade="critico",
                impacto_estimado=5,
                detectabilidade="alta",
                reversibilidade="alta",
                efeitos={
                    "confidencialidade": "baixo",
                    "integridade": "critico",
                    "disponibilidade": "medio",
                },
                custo_mitigacao_estimado="baixo",
                evidencias=integrity_report["problemas"],
                cenarios_afetados=["twin_integrity_gate"],
            )
            scenario_result = self._build_scenario_result(
                scenario_id="twin_integrity_gate",
                categoria="integridade_do_ambiente",
                descricao="Valida se o gemeo esta consistente antes das simulacoes internas.",
                weakness=weakness,
            )
            return {
                "mensagem": "Validacao interna interrompida: o gemeo de seguranca nao esta consistente.",
                "executado_em": executed_at,
                "somente_ambiente_isolado": True,
                "twin_id": snapshot.get("twin_id"),
                "integridade_do_gemeo": integrity_report,
                "resultados_de_cenario": [scenario_result],
                "fraquezas": [weakness],
                "resumo": self._build_summary([weakness], [scenario_result]),
            }

        validators = [
            self._validate_authentication_and_identity,
            self._validate_configuration_and_startup,
            self._validate_persistence,
            self._validate_observability,
            self._validate_continuity,
            self._validate_operational_integrity,
        ]

        scenario_results: List[Dict[str, Any]] = []
        weaknesses: List[Dict[str, Any]] = []

        for validator in validators:
            scenario_result, weakness = validator(snapshot)
            scenario_results.append(scenario_result)
            if weakness is not None:
                weaknesses.append(weakness)

        return {
            "mensagem": "Validacao interna controlada concluida apenas sobre o gemeo autorizado.",
            "executado_em": executed_at,
            "somente_ambiente_isolado": True,
            "twin_id": snapshot.get("twin_id"),
            "integridade_do_gemeo": integrity_report,
            "resultados_de_cenario": scenario_results,
            "fraquezas": weaknesses,
            "resumo": self._build_summary(weaknesses, scenario_results),
        }

    def _validate_authentication_and_identity(
        self,
        snapshot: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        auth_config = snapshot.get("api_security_metadata", {}).get("autenticacao_configurada", {})
        evidencias: List[str] = []

        if not auth_config.get("token_configurado"):
            evidencias.append("Token de acesso nao aparece como configurado no espelho.")
        if not auth_config.get("dispositivo_confiavel_configurado"):
            evidencias.append("Dispositivo confiavel nao aparece como configurado no espelho.")

        weakness = None
        if evidencias:
            weakness = self._build_weakness(
                weakness_id="auth_identity_guard_missing",
                nome="Controles de identidade incompletos",
                descricao="A superficie de autenticacao do JARVIS nao confirma token e dispositivo confiavel ao mesmo tempo.",
                categoria="autenticacao_e_identidade",
                local="api_security_metadata.autenticacao_configurada",
                gravidade="critico",
                impacto_estimado=5,
                detectabilidade="alta",
                reversibilidade="alta",
                efeitos={
                    "confidencialidade": "critico",
                    "integridade": "alto",
                    "disponibilidade": "medio",
                },
                custo_mitigacao_estimado="baixo",
                evidencias=evidencias,
                cenarios_afetados=["authentication_and_identity"],
            )

        return self._build_scenario_result(
            scenario_id="authentication_and_identity",
            categoria="autenticacao_e_identidade",
            descricao="Simula ausencia de token, device id invalido e rotas protegidas sem credencial no gemeo isolado.",
            weakness=weakness,
        ), weakness

    def _validate_configuration_and_startup(
        self,
        snapshot: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        configuration = snapshot.get("configuration_snapshot", {})
        health = snapshot.get("operational_state_snapshot", {}).get("health_report", {})
        paths = configuration.get("paths_persistentes", {})
        evidencias: List[str] = []

        missing_paths = [path_name for path_name, value in paths.items() if not value]
        if missing_paths:
            evidencias.append(
                "Paths persistentes ausentes: " + ", ".join(sorted(missing_paths))
            )
        if not health.get("configuracao_minima_valida", False):
            evidencias.append("Configuracao minima valida nao foi confirmada no health report.")
        if not health.get("runtime_ativo", False):
            evidencias.append("Runtime nao aparece como ativo no startup espelhado.")
        if not health.get("api_ativa", False):
            evidencias.append("API nao aparece como ativa no startup espelhado.")

        weakness = None
        if evidencias:
            weakness = self._build_weakness(
                weakness_id="configuration_startup_degraded",
                nome="Configuracao ou startup degradado",
                descricao="O espelho indica ausencia de configuracao essencial ou degradacao no startup seguro.",
                categoria="configuracao_e_startup",
                local="configuration_snapshot + health_report",
                gravidade="alto",
                impacto_estimado=4,
                detectabilidade="alta",
                reversibilidade="alta",
                efeitos={
                    "confidencialidade": "medio",
                    "integridade": "alto",
                    "disponibilidade": "alto",
                },
                custo_mitigacao_estimado="baixo",
                evidencias=evidencias,
                cenarios_afetados=["configuration_and_startup"],
            )

        return self._build_scenario_result(
            scenario_id="configuration_and_startup",
            categoria="configuracao_e_startup",
            descricao="Valida variaveis criticas, paths persistentes e bootstrap seguro apenas no gemeo.",
            weakness=weakness,
        ), weakness

    def _validate_persistence(
        self,
        snapshot: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        queue_snapshot = snapshot.get("task_queue_snapshot", {})
        memory_snapshot = snapshot.get("semantic_memory_snapshot", {})
        goal_snapshot = snapshot.get("goal_snapshot", {})
        memory_summary = snapshot.get("operational_state_snapshot", {}).get("memory_summary", {})
        integrity = memory_summary.get("integridade_basica", {})
        evidencias: List[str] = []

        if int(queue_snapshot.get("task_count", 0)) != len(queue_snapshot.get("tasks", [])):
            evidencias.append("Contagem da fila diverge do total de tarefas espelhadas.")
        if int(memory_snapshot.get("entry_count", 0)) != len(memory_snapshot.get("entries", [])):
            evidencias.append("Contagem da memoria diverge do total de entradas espelhadas.")
        if int(goal_snapshot.get("active_goal_count", 0)) != len(goal_snapshot.get("active_goals", [])):
            evidencias.append("Contagem de objetivos ativos diverge do snapshot espelhado.")
        if integrity and not integrity.get("json_valido", True):
            evidencias.append("Armazenamento semantico aparece como JSON invalido no espelho.")
        if integrity and not integrity.get("contagem_consistente", True):
            evidencias.append("Armazenamento semantico aparece com contagem inconsistente.")

        weakness = None
        if evidencias:
            weakness = self._build_weakness(
                weakness_id="persistence_inconsistency",
                nome="Persistencia inconsistente",
                descricao="Fila, memoria ou objetivos espelhados exibem sinais de estado incompleto ou inconsistente.",
                categoria="persistencia",
                local="task_queue_snapshot + semantic_memory_snapshot + goal_snapshot",
                gravidade="alto",
                impacto_estimado=4,
                detectabilidade="media",
                reversibilidade="media",
                efeitos={
                    "confidencialidade": "baixo",
                    "integridade": "alto",
                    "disponibilidade": "alto",
                },
                custo_mitigacao_estimado="medio",
                evidencias=evidencias,
                cenarios_afetados=["persistence"],
            )

        return self._build_scenario_result(
            scenario_id="persistence",
            categoria="persistencia",
            descricao="Verifica perda parcial de fila, memoria ausente ou arquivo inconsistente apenas no espelho.",
            weakness=weakness,
        ), weakness

    def _validate_observability(
        self,
        snapshot: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        operational = snapshot.get("operational_state_snapshot", {})
        audit_summary = operational.get("audit_summary", {})
        planner_summary = operational.get("planner_summary", {})
        runtime_state = operational.get("runtime_state", {})
        evidencias: List[str] = []

        if runtime_state.get("total_cycles_executed", 0) > 0 and audit_summary.get("total_decisoes_planner", 0) == 0:
            evidencias.append("Ciclos executados sem decisoes do planner refletidas na auditoria.")
        if planner_summary.get("acoplado") and planner_summary.get("total_entradas_auditoria", 0) == 0 and runtime_state.get("total_cycles_executed", 0) > 0:
            evidencias.append("Planner acoplado sem entradas recentes de auditoria apesar de ciclos executados.")
        if "health_report" not in operational:
            evidencias.append("Health report ausente no estado operacional espelhado.")

        weakness = None
        if evidencias:
            weakness = self._build_weakness(
                weakness_id="observability_degraded",
                nome="Observabilidade degradada",
                descricao="O espelho indica lacunas de healthcheck, logs ou auditoria para explicar o estado atual.",
                categoria="observabilidade",
                local="operational_state_snapshot.audit_summary",
                gravidade="medio",
                impacto_estimado=3,
                detectabilidade="media",
                reversibilidade="alta",
                efeitos={
                    "confidencialidade": "baixo",
                    "integridade": "medio",
                    "disponibilidade": "medio",
                },
                custo_mitigacao_estimado="baixo",
                evidencias=evidencias,
                cenarios_afetados=["observability"],
            )

        return self._build_scenario_result(
            scenario_id="observability",
            categoria="observabilidade",
            descricao="Avalia healthcheck, rastreabilidade, auditoria e logs no espelho isolado.",
            weakness=weakness,
        ), weakness

    def _validate_continuity(
        self,
        snapshot: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        health = snapshot.get("operational_state_snapshot", {}).get("health_report", {})
        evidencias: List[str] = []

        if not health.get("fila_carregada", False):
            evidencias.append("Fila nao aparece como carregada para retomada segura.")
        if not health.get("memoria_carregada", False):
            evidencias.append("Memoria nao aparece como carregada para retomada segura.")
        if not health.get("objetivos_carregados", False):
            evidencias.append("Objetivos nao aparecem como carregados para retomada segura.")
        if not health.get("ultima_persistencia_fila"):
            evidencias.append("Ultima persistencia da fila nao foi registrada.")
        if not health.get("ultima_persistencia_memoria"):
            evidencias.append("Ultima persistencia da memoria nao foi registrada.")
        if not health.get("ultima_persistencia_objetivos"):
            evidencias.append("Ultima persistencia dos objetivos nao foi registrada.")

        weakness = None
        if evidencias:
            weakness = self._build_weakness(
                weakness_id="continuity_degraded",
                nome="Continuidade degradada",
                descricao="O espelho indica risco de retomada incompleta ou perda parcial de estado apos reinicio.",
                categoria="continuidade",
                local="operational_state_snapshot.health_report",
                gravidade="alto",
                impacto_estimado=4,
                detectabilidade="media",
                reversibilidade="media",
                efeitos={
                    "confidencialidade": "baixo",
                    "integridade": "alto",
                    "disponibilidade": "alto",
                },
                custo_mitigacao_estimado="medio",
                evidencias=evidencias,
                cenarios_afetados=["continuity"],
            )

        return self._build_scenario_result(
            scenario_id="continuity",
            categoria="continuidade",
            descricao="Simula reinicio inesperado e perda parcial de estado apenas sobre o gemeo autorizado.",
            weakness=weakness,
        ), weakness

    def _validate_operational_integrity(
        self,
        snapshot: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
        queue_snapshot = snapshot.get("task_queue_snapshot", {})
        goal_snapshot = snapshot.get("goal_snapshot", {})
        planner_summary = snapshot.get("operational_state_snapshot", {}).get("planner_summary", {})
        evidencias: List[str] = []

        known_goal_ids = {
            goal.get("goal_id")
            for goal in goal_snapshot.get("strategic_goals", []) + goal_snapshot.get("active_goals", [])
        }
        orphan_tasks = [
            task.get("task_id")
            for task in queue_snapshot.get("tasks", [])
            if task.get("parent_goal_id") and task.get("parent_goal_id") not in known_goal_ids
        ]
        if orphan_tasks:
            evidencias.append("Tarefas orfas detectadas: " + ", ".join(sorted(str(task_id) for task_id in orphan_tasks)))

        for goal in goal_snapshot.get("active_goals", []) + goal_snapshot.get("strategic_goals", []):
            task_total = len(goal.get("task_ids", []))
            completed_total = len(goal.get("completed_task_ids", []))
            expected_progress = int((completed_total / task_total) * 100) if task_total else 0
            if task_total and int(goal.get("progress", 0)) != expected_progress:
                evidencias.append(
                    f"Objetivo {goal.get('goal_id')} com progresso inconsistente: {goal.get('progress')} != {expected_progress}."
                )
            if completed_total > task_total:
                evidencias.append(
                    f"Objetivo {goal.get('goal_id')} possui mais tarefas concluidas do que vinculadas."
                )

        if not planner_summary.get("acoplado", False):
            evidencias.append("Planner nao aparece acoplado ao runtime no estado espelhado.")

        weakness = None
        if evidencias:
            weakness = self._build_weakness(
                weakness_id="operational_integrity_gap",
                nome="Integridade operacional fragilizada",
                descricao="O espelho aponta orfandade de tarefa, progresso inconsistente ou planner desacoplado.",
                categoria="integridade_operacional",
                local="task_queue_snapshot + goal_snapshot + planner_summary",
                gravidade="alto",
                impacto_estimado=4,
                detectabilidade="alta",
                reversibilidade="media",
                efeitos={
                    "confidencialidade": "baixo",
                    "integridade": "alto",
                    "disponibilidade": "medio",
                },
                custo_mitigacao_estimado="medio",
                evidencias=evidencias,
                cenarios_afetados=["operational_integrity"],
            )

        return self._build_scenario_result(
            scenario_id="operational_integrity",
            categoria="integridade_operacional",
            descricao="Procura tarefa orfa, objetivo inconsistente e runtime sem planner no gemeo isolado.",
            weakness=weakness,
        ), weakness

    def _build_scenario_result(
        self,
        scenario_id: str,
        categoria: str,
        descricao: str,
        weakness: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        if weakness is None:
            return {
                "scenario_id": scenario_id,
                "categoria": categoria,
                "descricao": descricao,
                "status": "aprovado",
                "status_ptbr": "sem_fraqueza_detectada",
                "fraqueza_id": None,
                "evidencias": [],
            }

        return {
            "scenario_id": scenario_id,
            "categoria": categoria,
            "descricao": descricao,
            "status": "fraqueza_detectada",
            "status_ptbr": "fraqueza_detectada",
            "fraqueza_id": weakness["weakness_id"],
            "evidencias": deepcopy(weakness["evidencias"]),
        }

    def _build_summary(
        self,
        weaknesses: List[Dict[str, Any]],
        scenario_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        severity_counts = {nivel: 0 for nivel in SEVERITY_POINTS}
        for weakness in weaknesses:
            severity_counts[weakness["gravidade"]] += 1

        highest_risk = "baixo"
        for nivel in ("critico", "alto", "medio", "baixo"):
            if severity_counts[nivel] > 0:
                highest_risk = nivel
                break

        return {
            "total_cenarios": len(scenario_results),
            "cenarios_com_fraqueza": len([result for result in scenario_results if result["fraqueza_id"]]),
            "total_fraquezas": len(weaknesses),
            "maior_gravidade": highest_risk,
            "fraquezas_por_gravidade": severity_counts,
        }

    def _build_weakness(
        self,
        weakness_id: str,
        nome: str,
        descricao: str,
        categoria: str,
        local: str,
        gravidade: str,
        impacto_estimado: int,
        detectabilidade: str,
        reversibilidade: str,
        efeitos: Dict[str, str],
        custo_mitigacao_estimado: str,
        evidencias: Iterable[str],
        cenarios_afetados: Iterable[str],
    ) -> Dict[str, Any]:
        score_risco = (
            SEVERITY_POINTS[gravidade] * 10
            + impacto_estimado * 3
            + DETECTABILITY_POINTS[detectabilidade]
            + REVERSIBILITY_POINTS[reversibilidade]
        )
        return {
            "weakness_id": weakness_id,
            "nome": nome,
            "descricao": descricao,
            "categoria": categoria,
            "local": local,
            "gravidade": gravidade,
            "impacto_estimado": impacto_estimado,
            "detectabilidade": detectabilidade,
            "reversibilidade": reversibilidade,
            "efeitos_cia": deepcopy(efeitos),
            "custo_mitigacao_estimado": custo_mitigacao_estimado,
            "score_risco": score_risco,
            "evidencias": list(evidencias),
            "cenarios_afetados": list(cenarios_afetados),
            "ocorrencia": "nova",
        }

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
