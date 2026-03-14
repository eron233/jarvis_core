"""Worker de estudio."""

from typing import Any, Dict

from workers.worker_utils import (
    build_domain_rejection,
    build_success_response,
    domain_is_valid,
    extract_text,
    extract_topics,
    split_sentences,
)


class StudioWorker:
    """Executa tarefas orientadas ao dominio de estudio e criacao."""

    worker_id = "studio"
    allowed_domains = ["studio", "creative", "general"]

    def handle(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if not domain_is_valid(task, self.allowed_domains):
            return build_domain_rejection(self.worker_id, task, self.allowed_domains)

        metadata = task.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        text = extract_text(task)
        topics = extract_topics(text or task.get("goal", ""), limit=5)
        sentences = split_sentences(text, limit=2)
        briefing = {
            "objetivo": str(task.get("goal", "")),
            "publico": str(metadata.get("audience", "publico principal")),
            "formato": str(metadata.get("format", "conteudo curto")),
            "mensagem_central": sentences[0] if sentences else str(task.get("description", "")),
        }
        checklist = [
            "alinhar briefing com objetivo principal",
            "definir mensagem central e gancho",
            "organizar etapas de producao",
            "revisar checklist criativo antes da execucao",
        ]
        summary = (
            f"Briefing criativo organizado para {briefing['formato']} com foco em {briefing['publico']}."
        )
        return build_success_response(
            worker_id=self.worker_id,
            task=task,
            result_type="studio_briefing",
            summary=summary,
            details={
                "briefing": briefing,
                "topicos_criativos": topics,
                "checklist_producao": checklist,
            },
            evidence=topics[:3] or [briefing["mensagem_central"]],
            next_steps=checklist,
        )
