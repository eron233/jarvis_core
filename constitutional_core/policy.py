"""
JARVIS - Politica Constitucional Viva

Responsavel por:
- carregar identidade e principios do constitutional_core
- transformar regras constitucionais em politica executavel
- classificar tarefas como permitidas, sensiveis ou negadas
- fornecer um resumo seguro da politica ativa para runtime e relatorios

Integracoes principais:
- executive_planner.validator
- runtime.autonomy
- runtime.internal_agent_runtime
"""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List

#
# JARVIS_CORE_COMPONENT
# ==================================================
# BLOCO: Constantes e defaults da politica viva
# ==================================================

PRINCIPLES_PATH = Path(__file__).with_name("principles.json")
IDENTITY_PATH = Path(__file__).with_name("identity.json")

DEFAULT_ALLOWED_AUTONOMY_DOMAINS = (
    "runtime",
    "study",
    "studio",
    "finance",
    "system",
    "intent",
    "general",
)
DEFAULT_SENSITIVE_EFFECT_SCOPES = (
    "external",
    "financial_transaction",
    "credential_change",
    "destructive",
)
DEFAULT_PROHIBITED_KEYWORDS = (
    "invadir",
    "invasao",
    "acesso nao autorizado",
    "malware",
    "sabotagem",
    "fraude",
    "exploit",
    "phishing",
    "exfiltrar",
    "exfiltracao",
    "roubar credenciais",
    "operacao financeira automatica",
    "transferencia financeira automatica",
)


@dataclass
class ConstitutionalPolicy:
    """Representa a politica ativa derivada do constitutional core."""

    identity: Dict[str, Any]
    principles: List[Dict[str, Any]]
    allowed_autonomy_domains: List[str] = field(default_factory=lambda: list(DEFAULT_ALLOWED_AUTONOMY_DOMAINS))
    sensitive_effect_scopes: List[str] = field(default_factory=lambda: list(DEFAULT_SENSITIVE_EFFECT_SCOPES))
    prohibited_keywords: List[str] = field(default_factory=lambda: list(DEFAULT_PROHIBITED_KEYWORDS))

    def describe(self) -> Dict[str, Any]:
        """Retorna um resumo seguro da politica ativa."""

        principle_summaries = [
            {
                "id": principle.get("id"),
                "nome": principle.get("name"),
                "descricao": principle.get("description"),
            }
            for principle in self.principles
        ]
        return {
            "identidade": {
                "nome_sistema": self.identity.get("system_name"),
                "missao": self.identity.get("mission"),
                "modo_operacao": self.identity.get("operating_mode"),
                "locale_padrao": self.identity.get("default_locale", "pt-BR"),
            },
            "modo_autonomia": "supervisionada_por_politica_constitucional",
            "principios_ativos": principle_summaries,
            "dominios_autonomos": list(self.allowed_autonomy_domains),
            "efeitos_sensiveis": list(self.sensitive_effect_scopes),
            "proibicoes_absolutas": [
                "operacoes_ilegais_ou_nao_autorizadas",
                "malware_sabotagem_ou_fraude",
                "automacao_financeira_real",
                "destruicao_de_rastreabilidade_ou_auditoria",
            ],
            "aprovacao_humana_necessaria_quando": [
                "escopo_externo_ou_sensivel",
                "risco_alto",
                "mudanca_credencial_ou_privilegio",
                "supervisao_exigida_pela_tarefa",
            ],
        }

    def evaluate_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Classifica a tarefa segundo a politica constitucional ativa."""

        task_text = self._normalize_task_text(task)
        domain = str(task.get("domain") or task.get("worker") or task.get("worker_id") or "general").lower()
        effect_scope = str(task.get("effect_scope", "internal")).lower()
        approval = task.get("approval", {})
        if not isinstance(approval, dict):
            approval = {}

        approved = bool(approval.get("approved", task.get("approved", True)))
        requires_supervision = bool(
            approval.get("requires_supervision", task.get("requires_supervision", False))
        )
        risk = int(task.get("risk", 0))
        sensitive_action = bool(task.get("sensitive_action", False))
        prohibited_flags = {
            "illegal": bool(task.get("illegal", False)),
            "unauthorized_access": bool(task.get("unauthorized_access", False)),
            "malware": bool(task.get("malware", False)),
            "fraud": bool(task.get("fraud", False)),
            "financial_automation": bool(task.get("financial_automation", False)),
            "destructive_action": bool(task.get("destructive_action", False)),
        }
        matched_keywords = [
            keyword for keyword in self.prohibited_keywords if keyword in task_text
        ]

        hard_violations: list[str] = []
        if any(prohibited_flags.values()):
            hard_violations.append("A tarefa conflita com proibicoes absolutas da politica constitucional.")
        if matched_keywords:
            hard_violations.append(
                "A tarefa contem termos proibidos pela politica constitucional: "
                + ", ".join(sorted(matched_keywords))
                + "."
            )

        outside_autonomy_scope = domain not in self.allowed_autonomy_domains
        effect_requires_approval = effect_scope in self.sensitive_effect_scopes
        requires_human_approval = any(
            [
                requires_supervision,
                sensitive_action,
                outside_autonomy_scope,
                effect_requires_approval,
                risk >= 7,
            ]
        )
        denied = len(hard_violations) > 0 or bool(task.get("denied", False))

        if denied:
            blocking_reason = "policy_denied"
            blocking_reason_ptbr = "negada_pela_politica_constitucional"
        elif requires_human_approval and not approved:
            blocking_reason = "requires_human_approval"
            blocking_reason_ptbr = "requer_aprovacao_humana"
        elif outside_autonomy_scope and approved:
            blocking_reason = None
            blocking_reason_ptbr = None
        else:
            blocking_reason = None
            blocking_reason_ptbr = None

        return {
            "policy_loaded": True,
            "allowed_domain": not outside_autonomy_scope,
            "domain": domain,
            "effect_scope": effect_scope,
            "denied": denied,
            "approved": approved,
            "requires_human_approval": requires_human_approval,
            "outside_autonomy_scope": outside_autonomy_scope,
            "matched_keywords": matched_keywords,
            "hard_violations": hard_violations,
            "blocking_reason": blocking_reason,
            "blocking_reason_ptbr": blocking_reason_ptbr,
            "identity_mode": self.identity.get("operating_mode"),
            "principle_ids": [principle.get("id") for principle in self.principles],
        }

    @staticmethod
    def _normalize_task_text(task: Dict[str, Any]) -> str:
        """
        Consolida os campos textuais mais relevantes de uma tarefa.

        Parametros:
        - task: dicionario bruto da tarefa em avaliacao.

        Retorno:
        - string normalizada usada para buscar palavras proibidas.

        Efeitos no sistema:
        - nenhum; apenas gera texto auxiliar para avaliacao da politica.
        """

        goal = str(task.get("goal", ""))
        description = str(task.get("description", ""))
        evidence = " ".join(str(item) for item in task.get("evidence", []))
        return f"{goal} {description} {evidence}".strip().lower()


def load_constitutional_policy(
    identity_path: Path = IDENTITY_PATH,
    principles_path: Path = PRINCIPLES_PATH,
) -> ConstitutionalPolicy:
    """Carrega a politica ativa a partir dos arquivos constitucionais."""

    identity = json.loads(Path(identity_path).read_text(encoding="utf-8"))
    principles_snapshot = json.loads(Path(principles_path).read_text(encoding="utf-8"))
    principles = list(principles_snapshot.get("principles", []))
    return ConstitutionalPolicy(identity=identity, principles=principles)
