"""
JARVIS - Nucleo de Auto-Otimizacao

Responsavel por:
- detectar desperdicio computacional repetitivo e leve
- aplicar apenas ajustes seguros, reversiveis e locais ao runtime
- sugerir reducao de polling excessivo e gargalos recorrentes

Integracoes principais:
- runtime.internal_agent_runtime
- runtime.server
- main
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class SelfOptimizationCore:
    """Executa otimizacoes internas pequenas e reversiveis."""

    cycle_sleep_seconds: float
    idle_sleep_seconds: float
    nonce_soft_limit: int = 200

    def run(self, runtime: Any) -> Dict[str, Any]:
        """Avalia gargalos simples e aplica ajustes locais de baixo risco."""

        findings: List[Dict[str, Any]] = []
        applied_actions: List[Dict[str, Any]] = []

        with runtime._state_lock:
            nonce_count = len(runtime._request_nonces)
            if nonce_count > self.nonce_soft_limit:
                preserved_keys = list(runtime._request_nonces.keys())[-self.nonce_soft_limit :]
                runtime._request_nonces = {
                    key: runtime._request_nonces[key]
                    for key in preserved_keys
                }
                applied_actions.append(
                    {
                        "action_id": "nonce_cache_trim",
                        "status": "applied",
                        "message": (
                            "Cache interno de nonces reduzido para evitar crescimento desnecessario em memoria."
                        ),
                        "before": nonce_count,
                        "after": len(runtime._request_nonces),
                        "reversivel": True,
                    }
                )

        if self.cycle_sleep_seconds < 0.5:
            findings.append(
                {
                    "finding_id": "aggressive_active_polling",
                    "severity": "medium",
                    "message": "O loop ativo esta configurado com intervalo muito baixo e pode consumir CPU em excesso.",
                    "valor_observado": self.cycle_sleep_seconds,
                    "limiar_recomendado": 0.5,
                    "acao_sugerida": "Aumentar cycle_sleep_seconds para pelo menos 0.5 segundo.",
                }
            )

        if self.idle_sleep_seconds < 1.0:
            findings.append(
                {
                    "finding_id": "aggressive_idle_polling",
                    "severity": "medium",
                    "message": "O loop ocioso esta agressivo demais para um orgao de baixa prioridade.",
                    "valor_observado": self.idle_sleep_seconds,
                    "limiar_recomendado": 1.0,
                    "acao_sugerida": "Aumentar idle_sleep_seconds para pelo menos 1 segundo.",
                }
            )

        audit_size = len(getattr(runtime.audit_logger, "entries", []) or [])
        if audit_size > 5000:
            findings.append(
                {
                    "finding_id": "large_in_memory_audit_buffer",
                    "severity": "medium",
                    "message": "A trilha de auditoria em memoria esta grande e pode aumentar o custo de leitura.",
                    "valor_observado": audit_size,
                    "limiar_recomendado": 5000,
                    "acao_sugerida": "Migrar a auditoria quente para armazenamento transacional ou rotacionado.",
                }
            )

        status = "saudavel"
        if any(item["severity"] == "high" for item in findings):
            status = "critico"
        elif findings or applied_actions:
            status = "atencao"

        return {
            "organ_id": "self_optimization_core",
            "status": status,
            "executado_em": runtime._utc_now(),
            "achados": findings,
            "acoes_aplicadas": applied_actions,
            "resumo": {
                "total_achados": len(findings),
                "total_acoes_aplicadas": len(applied_actions),
                "nonce_cache_atual": len(runtime._request_nonces),
                "audit_entries_em_memoria": audit_size,
            },
        }
