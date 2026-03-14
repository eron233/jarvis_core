"""Motor de remediacao hibrida para fraquezas detectadas no JARVIS."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from security.security_twin import SecurityTwin


@dataclass
class RemediationEngine:
    """Transforma fraquezas em planos de correcao seguros e auditaveis."""

    twin: SecurityTwin = field(default_factory=SecurityTwin)

    def build_remediation_plan(
        self,
        validation_report: Dict[str, Any],
        runtime: Any | None = None,
        config: Any | None = None,
        twin_snapshot: Dict[str, Any] | None = None,
        environment_report: Dict[str, Any] | None = None,
        health_report: Dict[str, Any] | None = None,
        auto_apply_safe: bool = True,
    ) -> Dict[str, Any]:
        """Gera um plano estruturado e aplica apenas correcoes automaticas seguras."""

        weakness_plans: List[Dict[str, Any]] = []
        automatic_actions: List[Dict[str, Any]] = []
        pending_actions: List[Dict[str, Any]] = []
        weaknesses = validation_report.get("fraquezas", [])

        for weakness in weaknesses:
            solutions = self._build_solution_set(weakness)
            safe_strategy = self._select_safe_strategy(
                weakness=weakness,
                config=config,
                runtime=runtime,
                twin_snapshot=twin_snapshot,
                environment_report=environment_report,
                health_report=health_report,
            )
            classification = (
                "correcao_automatica_segura" if safe_strategy is not None else "correcao_assistida"
            )

            plan = {
                "weakness_id": weakness["weakness_id"],
                "nome": weakness["nome"],
                "gravidade": weakness["gravidade"],
                "score_risco": weakness["score_risco"],
                "classificacao_correcao": classification,
                "solucoes": solutions,
                "correcao_automatica_elegivel": safe_strategy is not None,
                "aplicada_automaticamente": False,
            }

            if safe_strategy is not None and auto_apply_safe:
                action = self._apply_safe_strategy(
                    strategy=safe_strategy,
                    weakness=weakness,
                    runtime=runtime,
                    config=config,
                    twin_snapshot=twin_snapshot,
                    environment_report=environment_report,
                    health_report=health_report,
                )
                plan["aplicada_automaticamente"] = action["status"] == "applied"
                plan["acao_automatica"] = action

                if action["status"] == "applied":
                    automatic_actions.append(action)
                else:
                    pending_actions.append(
                        {
                            "weakness_id": weakness["weakness_id"],
                            "motivo": action.get("reason", "safe_correction_not_available"),
                            "motivo_ptbr": action.get("reason_ptbr"),
                        }
                    )
            else:
                pending_actions.append(
                    {
                        "weakness_id": weakness["weakness_id"],
                        "motivo": "requires_human_approval" if safe_strategy is None else "safe_correction_not_available",
                        "motivo_ptbr": "requer_aprovacao_humana" if safe_strategy is None else "correcao_segura_indisponivel",
                    }
                )

            weakness_plans.append(plan)

        return {
            "mensagem": "Plano de remediacao hibrida gerado com sucesso.",
            "gerado_em": self._utc_now(),
            "fraquezas_avaliadas": len(weaknesses),
            "planos_por_fraqueza": weakness_plans,
            "acoes_automaticas_realizadas": automatic_actions,
            "acoes_pendentes_de_aprovacao": pending_actions,
        }

    def _build_solution_set(self, weakness: Dict[str, Any]) -> List[Dict[str, Any]]:
        weak_id = weakness["weakness_id"]
        immediate = self._build_immediate_solution(weak_id)
        structural = self._build_structural_solution(weak_id)
        mitigation = self._build_operational_mitigation(weak_id)
        return [immediate, structural, mitigation]

    def _build_immediate_solution(self, weakness_id: str) -> Dict[str, Any]:
        solutions = {
            "auth_identity_guard_missing": {
                "descricao": "Revalidar token e dispositivo confiavel configurados antes de liberar qualquer acesso protegido.",
                "complexidade": "baixa",
                "risco_residual": "medio",
                "impacto_esperado": "Reduz imediatamente a exposicao indevida de acesso.",
                "requer_aprovacao": True,
                "prioridade_recomendada": "urgente",
            },
            "configuration_startup_degraded": {
                "descricao": "Garantir diretorios e paths persistentes minimos antes do proximo startup.",
                "complexidade": "baixa",
                "risco_residual": "baixo",
                "impacto_esperado": "Recupera previsibilidade do bootstrap e reduz erro operacional simples.",
                "requer_aprovacao": False,
                "prioridade_recomendada": "alta",
            },
            "persistence_inconsistency": {
                "descricao": "Repersistir fila, memoria e objetivos a partir do estado atual confiavel do runtime.",
                "complexidade": "baixa",
                "risco_residual": "baixo",
                "impacto_esperado": "Reduz divergencias de estado e melhora a retomada segura.",
                "requer_aprovacao": False,
                "prioridade_recomendada": "alta",
            },
            "observability_degraded": {
                "descricao": "Emitir novo snapshot de healthcheck e confirmar trilha de auditoria recente.",
                "complexidade": "baixa",
                "risco_residual": "baixo",
                "impacto_esperado": "Aumenta a rastreabilidade sem alterar comportamento funcional.",
                "requer_aprovacao": False,
                "prioridade_recomendada": "media",
            },
            "continuity_degraded": {
                "descricao": "Forcar persistencia segura do estado atual e validar timestamps de retomada.",
                "complexidade": "baixa",
                "risco_residual": "baixo",
                "impacto_esperado": "Reduz risco de perda parcial de estado apos reinicio.",
                "requer_aprovacao": False,
                "prioridade_recomendada": "alta",
            },
            "operational_integrity_gap": {
                "descricao": "Congelar a criacao de novas tarefas relacionadas ate revisar vinculos entre objetivos, fila e planner.",
                "complexidade": "media",
                "risco_residual": "medio",
                "impacto_esperado": "Evita ampliacao da inconsistência operacional.",
                "requer_aprovacao": True,
                "prioridade_recomendada": "alta",
            },
            "twin_integrity_invalid": {
                "descricao": "Regenerar o gemeo de seguranca a partir de um estado vivo e confiavel antes de qualquer nova validacao.",
                "complexidade": "baixa",
                "risco_residual": "baixo",
                "impacto_esperado": "Restaura um ambiente de analise valido sem tocar no ambiente produtivo.",
                "requer_aprovacao": False,
                "prioridade_recomendada": "alta",
            },
        }
        return {
            "tipo": "solucao_imediata",
            **solutions.get(
                weakness_id,
                {
                    "descricao": "Executar correcao pontual e reversivel para conter a fraqueza detectada.",
                    "complexidade": "baixa",
                    "risco_residual": "medio",
                    "impacto_esperado": "Contencao rapida do risco atual.",
                    "requer_aprovacao": True,
                    "prioridade_recomendada": "media",
                },
            ),
        }

    def _build_structural_solution(self, weakness_id: str) -> Dict[str, Any]:
        descriptions = {
            "auth_identity_guard_missing": "Consolidar a politica de acesso confiavel em um registro versionado de dispositivos e rotacao planejada de segredos.",
            "configuration_startup_degraded": "Fortalecer a validacao de configuracao com regras declarativas e checagens de startup mais granulares.",
            "persistence_inconsistency": "Adicionar verificacao transacional e checksums simples para snapshots de fila, memoria e objetivos.",
            "observability_degraded": "Consolidar trilhas de health, auditoria e eventos relevantes em um relatorio operacional unificado.",
            "continuity_degraded": "Introduzir checkpoints de runtime e rotina de restauracao validada para restart seguro.",
            "operational_integrity_gap": "Criar reconciliacao explicita entre objetivos, tarefas e planner antes da execucao.",
            "twin_integrity_invalid": "Padronizar a geracao do gemeo com versao, schema e trilha de integridade obrigatoria.",
        }
        return {
            "tipo": "solucao_estrutural",
            "descricao": descriptions.get(
                weakness_id,
                "Reforcar a arquitetura do componente afetado para reduzir recorrencia do problema."
            ),
            "complexidade": "media",
            "risco_residual": "baixo",
            "impacto_esperado": "Reduz recorrencia e aumenta robustez de longo prazo.",
            "requer_aprovacao": True,
            "prioridade_recomendada": "alta",
        }

    def _build_operational_mitigation(self, weakness_id: str) -> Dict[str, Any]:
        descriptions = {
            "auth_identity_guard_missing": "Manter a API restrita, revisar negacoes recentes e monitorar qualquer tentativa de acesso fora do dispositivo confiavel.",
            "configuration_startup_degraded": "Executar checklist de deploy e startup antes de cada reinicio planejado.",
            "persistence_inconsistency": "Aumentar a frequencia de verificacao de integridade e registrar divergencias no relatorio semanal.",
            "observability_degraded": "Monitorar healthcheck e volume de auditoria em cada ciclo relevante.",
            "continuity_degraded": "Executar teste de retomada supervisionado apos qualquer mudanca de persistencia.",
            "operational_integrity_gap": "Suspender tarefas relacionadas ao objetivo afetado ate a revisao humana dos vinculos.",
            "twin_integrity_invalid": "Descartar snapshots antigos e operar apenas com espelhos regenerados e validados.",
        }
        return {
            "tipo": "mitigacao_operacional",
            "descricao": descriptions.get(
                weakness_id,
                "Aplicar uma mitigacao operacional temporaria enquanto a correcao definitiva nao entra."
            ),
            "complexidade": "baixa",
            "risco_residual": "medio",
            "impacto_esperado": "Reduz risco enquanto a correcao principal e planejada.",
            "requer_aprovacao": False,
            "prioridade_recomendada": "media",
        }

    def _select_safe_strategy(
        self,
        weakness: Dict[str, Any],
        config: Any | None,
        runtime: Any | None,
        twin_snapshot: Dict[str, Any] | None,
        environment_report: Dict[str, Any] | None,
        health_report: Dict[str, Any] | None,
    ) -> Dict[str, Any] | None:
        weakness_id = weakness["weakness_id"]
        evidencias = weakness.get("evidencias", [])

        if weakness_id == "twin_integrity_invalid":
            if runtime is not None and twin_snapshot is not None:
                return {"strategy_id": "rebuild_security_twin"}
            return None

        if weakness_id == "configuration_startup_degraded":
            if config is not None and any("Paths persistentes ausentes" in evidence for evidence in evidencias):
                return {"strategy_id": "ensure_environment_directories"}
            return None

        if weakness_id in {"persistence_inconsistency", "continuity_degraded"} and runtime is not None:
            return {"strategy_id": "refresh_runtime_persistence"}

        if weakness_id == "observability_degraded" and runtime is not None:
            return {"strategy_id": "emit_runtime_observability_snapshot"}

        return None

    def _apply_safe_strategy(
        self,
        strategy: Dict[str, Any],
        weakness: Dict[str, Any],
        runtime: Any | None,
        config: Any | None,
        twin_snapshot: Dict[str, Any] | None,
        environment_report: Dict[str, Any] | None,
        health_report: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        strategy_id = strategy["strategy_id"]

        if strategy_id == "ensure_environment_directories":
            if config is None:
                return self._build_skipped_action(weakness, strategy_id, "missing_environment_context")
            before = {
                "data_dir": str(config.data_dir),
                "logs_dir": str(config.logs_dir),
                "reports_dir": str(config.reports_dir),
            }
            config.ensure_directories()
            action = self._build_applied_action(
                weakness=weakness,
                strategy_id=strategy_id,
                before=before,
                after=before,
                rollback_disponivel=True,
            )
            self._record_automatic_action(runtime, action)
            return action

        if strategy_id == "refresh_runtime_persistence":
            if runtime is None:
                return self._build_skipped_action(weakness, strategy_id, "missing_runtime_context")
            before = runtime.describe_state()
            persisted = runtime.persist_runtime_state()
            after = runtime.describe_state()
            action = self._build_applied_action(
                weakness=weakness,
                strategy_id=strategy_id,
                before=before,
                after={
                    "runtime_state": after,
                    "persistencia": persisted,
                },
                rollback_disponivel=True,
            )
            self._record_automatic_action(runtime, action)
            return action

        if strategy_id == "emit_runtime_observability_snapshot":
            if runtime is None:
                return self._build_skipped_action(weakness, strategy_id, "missing_runtime_context")
            before = {"audit_entries": len(runtime.audit_logger.entries)}
            after = {
                "planner_report": runtime.build_planner_report(),
                "audit_report": runtime.build_audit_report(),
            }
            action = self._build_applied_action(
                weakness=weakness,
                strategy_id=strategy_id,
                before=before,
                after=after,
                rollback_disponivel=True,
            )
            self._record_automatic_action(runtime, action)
            return action

        if strategy_id == "rebuild_security_twin":
            if runtime is None or twin_snapshot is None:
                return self._build_skipped_action(weakness, strategy_id, "missing_runtime_context")
            rebuilt_snapshot = self.twin.create_twin_snapshot(
                runtime=runtime,
                environment_report=environment_report,
                health_report=health_report,
                snapshot_name="security-twin-regenerado",
            )
            action = self._build_applied_action(
                weakness=weakness,
                strategy_id=strategy_id,
                before={"twin_id": twin_snapshot.get("twin_id")},
                after={"twin_id": rebuilt_snapshot.get("twin_id")},
                rollback_disponivel=True,
            )
            self._record_automatic_action(runtime, action)
            return action

        return self._build_skipped_action(weakness, strategy_id, "safe_correction_not_available")

    def _record_automatic_action(self, runtime: Any | None, action: Dict[str, Any]) -> None:
        if runtime is None:
            return
        runtime.bootstrap()
        if runtime.audit_logger is not None:
            runtime.audit_logger.record(
                "security_remediation",
                {
                    "status": action["status"],
                    "weakness_id": action["weakness_id"],
                    "strategy_id": action["strategy_id"],
                    "rollback_disponivel": action["rollback_disponivel"],
                },
            )
        if runtime.memory.get("episodic") is not None:
            runtime.memory["episodic"].remember(
                {
                    "event": "security_remediation",
                    "event_ptbr": "remediacao_de_seguranca",
                    "status": action["status"],
                    "status_ptbr": action["status_ptbr"],
                    "weakness_id": action["weakness_id"],
                    "strategy_id": action["strategy_id"],
                }
            )

    def _build_applied_action(
        self,
        weakness: Dict[str, Any],
        strategy_id: str,
        before: Dict[str, Any],
        after: Dict[str, Any],
        rollback_disponivel: bool,
    ) -> Dict[str, Any]:
        return {
            "action_id": f"remediation-{weakness['weakness_id']}-{strategy_id}",
            "weakness_id": weakness["weakness_id"],
            "strategy_id": strategy_id,
            "status": "applied",
            "status_ptbr": "aplicada",
            "before": deepcopy(before),
            "after": deepcopy(after),
            "rollback_disponivel": rollback_disponivel,
            "aplicada_em": self._utc_now(),
        }

    def _build_skipped_action(
        self,
        weakness: Dict[str, Any],
        strategy_id: str,
        reason: str,
    ) -> Dict[str, Any]:
        reason_ptbr = {
            "missing_runtime_context": "contexto_de_runtime_ausente",
            "missing_environment_context": "contexto_de_ambiente_ausente",
            "safe_correction_not_available": "correcao_segura_indisponivel",
        }.get(reason, reason)
        return {
            "action_id": f"remediation-{weakness['weakness_id']}-{strategy_id}",
            "weakness_id": weakness["weakness_id"],
            "strategy_id": strategy_id,
            "status": "skipped",
            "status_ptbr": "nao_aplicada",
            "reason": reason,
            "reason_ptbr": reason_ptbr,
            "rollback_disponivel": False,
            "aplicada_em": self._utc_now(),
        }

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()
