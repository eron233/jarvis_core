"""
JARVIS - Worker de Estudo

Responsavel por:
- resumir conteudo textual autorizado
- extrair topicos de estudo e proximos passos
- estruturar material para aprendizagem supervisionada

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
# BLOCO: Worker focado no dominio de estudo
# ==================================================

class StudyWorker:
    """Executa tarefas orientadas ao dominio de estudo e aprendizado."""

    worker_id = "study"
    allowed_domains = ["study", "education", "general"]

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa uma tarefa de estudo e gera um digest estruturado.

        Parametros:
        - task: tarefa com meta, descricao e conteudo opcional.

        Retorno:
        - resposta estruturada com resumo, topicos e proximos passos.

        Efeitos no sistema:
        - nenhum direto; o runtime decide como persistir o resultado.
        """

        if not domain_is_valid(task, self.allowed_domains):
            return build_domain_rejection(self.worker_id, task, self.allowed_domains)

        text = extract_text(task)
        topics = extract_topics(text or task.get("goal", ""), limit=6)
        sentences = split_sentences(text, limit=3)
        summary = sentences[0] if sentences else str(task.get("goal", "Resumo de estudo"))
        next_steps = [
            "revisar os topicos priorizados",
            "transformar os topicos em perguntas de estudo",
            "registrar duvidas e proximos passos na memoria",
        ]
        return build_success_response(
            worker_id=self.worker_id,
            task=task,
            result_type="study_digest",
            summary=summary,
            details={
                "topicos": topics,
                "resumo": summary,
                "proximos_passos_de_estudo": next_steps,
            },
            evidence=topics[:3] or sentences[:2],
            next_steps=next_steps,
        )
