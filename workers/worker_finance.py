"""
JARVIS - Worker de Financas

Responsavel por:
- organizar observacoes financeiras autorizadas
- produzir resumo analitico estruturado
- apoiar leitura de dados internos sem automacao financeira real

Integracoes principais:
- runtime.internal_agent_runtime
- workers.worker_utils
- memory_system.semantic_memory
"""

from typing import Any, Dict

from workers.worker_utils import (
    build_domain_rejection,
    build_success_response,
    domain_is_valid,
    extract_text,
    extract_topics,
    split_sentences,
)


#
# JARVIS_WORKER_DOMAIN
# ==================================================
# BLOCO: Worker focado no dominio financeiro analitico
# ==================================================

class FinanceWorker:
    """Executa tarefas orientadas ao dominio de financas."""

    worker_id = "finance"
    allowed_domains = ["finance", "general"]

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa de analise financeira segura.

        Parametros:
        - task: tarefa com observacoes e indicadores autorizados.

        Retorno:
        - resposta estruturada com resumo, observacoes e evidencias.

        Efeitos no sistema:
        - nenhum direto; nao executa operacoes financeiras reais.
        """

        if not domain_is_valid(task, self.allowed_domains):
            return build_domain_rejection(self.worker_id, task, self.allowed_domains)

        metadata = task.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        observations = metadata.get("observations", [])
        if not isinstance(observations, list):
            observations = []

        text = extract_text(task)
        topics = extract_topics(text or task.get("goal", ""), limit=5)
        sentences = split_sentences(text, limit=3)
        indicators = [
            {"nome": key, "valor": value}
            for key, value in metadata.get("values", {}).items()
        ] if isinstance(metadata.get("values"), dict) else []

        structured_observations = [str(item) for item in observations[:5]]
        if not structured_observations:
            structured_observations = topics

        summary = (
            "Analise financeira organizada em observacoes estruturadas, "
            f"com {len(structured_observations)} ponto(s) principal(is)."
        )
        next_steps = [
            "priorizar variacoes relevantes",
            "validar dados com evidencia interna autorizada",
            "registrar conclusoes sem executar operacoes reais",
        ]
        return build_success_response(
            worker_id=self.worker_id,
            task=task,
            result_type="finance_analysis",
            summary=summary,
            details={
                "resumo_analitico": sentences[0] if sentences else str(task.get("goal", "")),
                "observacoes_estruturadas": structured_observations,
                "indicadores": indicators,
                "topicos": topics,
            },
            evidence=structured_observations[:3] or topics[:3],
            next_steps=next_steps,
        )
