"""
JARVIS - Hierarquia Corporativa e Roteamento por Capacidade

Organiza subagentes especializados e seleciona somente um tier/capacidade de
inferência. O modelo concreto é resolvido pelo LocalInferenceRouter e pode
permanecer indefinido até o benchmark do hardware real.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

LOGGER = logging.getLogger("jarvis.runtime.corporate_hierarchy")


class CorporateSubAgent:
    """Representa um papel especializado sem acoplamento a nome de modelo."""

    def __init__(
        self,
        agent_id: str,
        department: str,
        role_title: str,
        preferred_capability: str = "general",
    ) -> None:
        self.agent_id = agent_id
        self.department = department
        self.role_title = role_title
        self.preferred_capability = preferred_capability
        self.state = "hibernating"
        self.last_active_at: Optional[str] = None
        self.tasks_dispatched = 0

    def wake_up(self) -> None:
        self.state = "active"
        self.last_active_at = datetime.now(timezone.utc).isoformat()

    def hibernate(self) -> None:
        self.state = "hibernating"

    def select_model_tier(
        self,
        task_complexity: str,
        inference_router: Any = None,
    ) -> Dict[str, Any]:
        heavy = str(task_complexity).lower() in {"critica", "complexa", "high", "heavy"}
        tier_en = "heavy" if heavy else "light"
        tier_pt = "pesado" if heavy else "leve"

        resolution = {
            "status": "indisponivel",
            "modelo": None,
            "origem": None,
            "motivo": "Nenhum roteador de inferencia foi conectado.",
        }
        if inference_router is not None and hasattr(inference_router, "resolve_model"):
            resolution = inference_router.resolve_model(
                tier=tier_en,
                capability=self.preferred_capability,
            )

        return {
            "tier": tier_pt,
            "tier_id": tier_en,
            "capacidade": self.preferred_capability,
            "modelo_selecionado": resolution.get("modelo"),
            "modelo_resolvido": resolution.get("status") == "sucesso",
            "origem_modelo": resolution.get("origem"),
            "motivo_modelo": resolution.get("motivo"),
            "motivo_selecao": (
                "Tarefa crítica/complexa pede o tier pesado."
                if heavy
                else "Tarefa simples/intermediária pede o tier leve."
            ),
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "departamento": self.department,
            "cargo": self.role_title,
            "estado": self.state,
            "capacidade_preferida": self.preferred_capability,
            "tarefas_despachadas": self.tasks_dispatched,
            "ultimo_despertar": self.last_active_at,
        }


class CorporateAgentHierarchyEngine:
    """Roteia tarefas por departamento e tier, sem inventar nomes de modelos."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        inference_router: Any = None,
    ) -> None:
        self.data_dir = (
            Path(data_dir)
            if data_dir
            else Path(__file__).resolve().parents[1] / "data" / "corporate_hierarchy"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.inference_router = inference_router

        self.agents: Dict[str, CorporateSubAgent] = {
            "ceo_executive": CorporateSubAgent(
                "ceo_executive",
                "Gabinete_Executivo",
                "Diretor Executivo de Estratégia e Decisões JEV",
                "reasoning",
            ),
            "security_director": CorporateSubAgent(
                "security_director",
                "Diretoria_de_Seguranca_e_Auditoria",
                "Especialista em Defesa, Twin e Auditoria",
                "reasoning",
            ),
            "engineering_lead": CorporateSubAgent(
                "engineering_lead",
                "Engenharia_de_Software_e_Arquitetura",
                "Líder de Desenvolvimento e Arquitetura",
                "coding",
            ),
            "web_research_agent": CorporateSubAgent(
                "web_research_agent",
                "Inteligencia_de_Mercado_e_Navegacao_Web",
                "Pesquisador Web e Coletor de Evidências",
                "general",
            ),
            "finance_trader": CorporateSubAgent(
                "finance_trader",
                "Analise_Financeira_e_Day_Trade",
                "Analista Financeiro e de Riscos",
                "reasoning",
            ),
        }

    def dispatch_corporate_task(
        self,
        department: str,
        task_title: str,
        task_payload: Dict[str, Any],
        task_complexity: str = "intermediaria",
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc).isoformat()

        matching_agent = None
        for agent in self.agents.values():
            if (
                agent.department.lower() in department.lower()
                or department.lower() in agent.department.lower()
            ):
                matching_agent = agent
                break
        if matching_agent is None:
            matching_agent = self.agents["ceo_executive"]

        matching_agent.wake_up()
        model_selection = matching_agent.select_model_tier(
            task_complexity,
            inference_router=self.inference_router,
        )
        matching_agent.tasks_dispatched += 1
        matching_agent.hibernate()

        selected_model = model_selection.get("modelo_selecionado")
        model_text = selected_model or "ainda não definido pelo benchmark local"
        routing_decision = (
            f"Tarefa '{task_title}' roteada para '{matching_agent.role_title}' "
            f"no setor '{matching_agent.department}', tier {model_selection['tier'].upper()}, "
            f"capacidade '{model_selection['capacidade']}', modelo {model_text}."
        )

        payload = task_payload or {}
        report = {
            "tarefa": task_title,
            "departamento": matching_agent.department,
            "subagente_responsavel": matching_agent.to_dict(),
            "roteamento_modelo": model_selection,
            "roteado_em": now,
            "decisao_roteamento": routing_decision,
            "tarefa_executada": False,
            "motivo_nao_execucao": (
                "Este módulo roteia departamento/tier/capacidade. O executor de inferencia "
                "ainda nao esta ligado a esta etapa; a execução deve passar pelo motor de "
                "inferência e pelo planner constitucional."
            ),
            "carga_recebida": {
                "possui_conteudo": bool(payload),
                "campos": sorted(payload.keys()),
            },
            "estado_final_subagente": matching_agent.state,
            "resumo_ptbr": (
                f"Tarefa roteada para {matching_agent.department}; tier "
                f"{model_selection['tier']}; modelo {model_text}. Nenhuma execução "
                "foi simulada neste módulo."
            ),
        }

        self._save_dispatch_record(task_title, report)
        return report

    def get_hierarchy_status(self) -> Dict[str, Any]:
        active_count = sum(1 for agent in self.agents.values() if agent.state == "active")
        hibernating_count = sum(
            1 for agent in self.agents.values() if agent.state == "hibernating"
        )
        return {
            "total_departamentos": len(self.agents),
            "subagentes_ativos": active_count,
            "subagentes_em_hibernacao": hibernating_count,
            "economia_recursos_status": "roteamento_sob_demanda",
            "modelos_hardcoded": False,
            "departamentos": [agent.to_dict() for agent in self.agents.values()],
        }

    def _save_dispatch_record(self, task_title: str, report: Dict[str, Any]) -> None:
        clean_title = task_title.replace(" ", "_").replace("/", "_")[:30]
        file_path = self.data_dir / (
            f"dispatch_{clean_title}_{int(datetime.now(timezone.utc).timestamp())}.json"
        )
        file_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
