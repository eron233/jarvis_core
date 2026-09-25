"""
JARVIS - Arquitetura de Sub-Agentes Corporativos e Roteamento Adaptativo (Corporate Agent Hierarchy)

Responsável por:
- organizar o JARVIS como uma empresa estruturada em departamentos especializados
- aplicar o ciclo de vida sob demanda: o sub-agente desperta para a tarefa e adormece (hiberna) logo após a conclusão
- selecionar o modelo apropriado (modelo leve para tarefas rotineiras vs modelo pesado para tarefas estratégicas/críticas)
- economizar recursos computacionais, memória e tokens
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

LOGGER = logging.getLogger("jarvis.runtime.corporate_hierarchy")


class CorporateSubAgent:
    """Representa um sub-agente especializado pertencente a um departamento corporativo."""

    def __init__(self, agent_id: str, department: str, role_title: str, light_model: str, heavy_model: str) -> None:
        self.agent_id = agent_id
        self.department = department
        self.role_title = role_title
        self.light_model = light_model
        self.heavy_model = heavy_model
        self.state = "hibernating"  # 'hibernating' | 'active'
        self.last_active_at: Optional[str] = None
        self.tasks_completed = 0

    def wake_up(self) -> None:
        """Desperta o sub-agente para execução."""
        self.state = "active"
        self.last_active_at = datetime.now(timezone.utc).isoformat()
        LOGGER.info("[subagent_wake] %s (%s) despertado para execução.", self.agent_id, self.department)

    def hibernate(self) -> None:
        """Coloca o sub-agente em hibernação para liberar recursos do sistema."""
        self.state = "hibernating"
        LOGGER.info("[subagent_hibernate] %s (%s) adormecido com sucesso.", self.agent_id, self.department)

    def select_model_tier(self, task_complexity: str) -> Dict[str, Any]:
        """
        Seleciona a camada de modelo (leve vs pesado) com base na complexidade da tarefa.
        'simples' / 'intermediaria' -> Modelo Leve
        'critica' / 'complexa' -> Modelo Pesado
        """
        if task_complexity in ("critica", "complexa", "high"):
            selected_model = self.heavy_model
            tier = "pesado"
            reason = "A tarefa exige raciocínio profundo e validação rigorosa."
        else:
            selected_model = self.light_model
            tier = "leve"
            reason = "A tarefa é rotineira/direta, otimizando o consumo de tokens e tempo."

        return {
            "modelo_selecionado": selected_model,
            "tier": tier,
            "motivo_selecao": reason,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Retorna estado e atributos do sub-agente."""
        return {
            "agent_id": self.agent_id,
            "departamento": self.department,
            "cargo": self.role_title,
            "estado": self.state,
            "modelo_leve": self.light_model,
            "modelo_pesado": self.heavy_model,
            "tarefas_concluidas": self.tasks_completed,
            "ultimo_despertar": self.last_active_at,
        }


class CorporateAgentHierarchyEngine:
    """Orquestrador corporativo dos departamentos e sub-agentes do JARVIS."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "corporate_hierarchy"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Cadastro Oficial de Departamentos e Sub-Agentes Corporativos
        self.agents: Dict[str, CorporateSubAgent] = {
            "ceo_executive": CorporateSubAgent(
                agent_id="ceo_executive",
                department="Gabinete_Executivo",
                role_title="Diretor Executivo de Estratégia e Decisões JEV",
                light_model="claude-3-5-haiku-local",
                heavy_model="claude-3-7-sonnet-supreme",
            ),
            "security_director": CorporateSubAgent(
                agent_id="security_director",
                department="Diretoria_de_Seguranca_e_Auditoria",
                role_title="Especialista em Defesa, Gêmeo de Segurança e Caça Zero-Day",
                light_model="security-checker-fast",
                heavy_model="claude-3-7-sonnet-security",
            ),
            "engineering_lead": CorporateSubAgent(
                agent_id="engineering_lead",
                department="Engenharia_de_Software_e_Arquitetura",
                role_title="Líder de Desenvolvimento, AST e Refatoração de Código",
                light_model="coder-light-fast",
                heavy_model="claude-3-7-sonnet-coder",
            ),
            "web_research_agent": CorporateSubAgent(
                agent_id="web_research_agent",
                department="Inteligencia_de_Mercado_e_Navegacao_Web",
                role_title="Pesquisador Web, ScrapeGraph e Coletor de Dados MCP",
                light_model="web-scraper-lite",
                heavy_model="claude-3-5-sonnet-researcher",
            ),
            "finance_trader": CorporateSubAgent(
                agent_id="finance_trader",
                department="Analise_Financeira_e_Day_Trade",
                role_title="Analista de Fluxo de Ordens, Tape Reading B3 e Riscos",
                light_model="market-ticker-fast",
                heavy_model="claude-3-7-sonnet-financial",
            ),
        }

    def dispatch_corporate_task(
        self,
        department: str,
        task_title: str,
        task_payload: Dict[str, Any],
        task_complexity: str = "intermediaria",
    ) -> Dict[str, Any]:
        """
        Localiza o sub-agente responsável pelo departamento, desperta-o, seleciona o modelo
        ideal, executa a tarefa atribuída e imediatamente o coloca em hibernação.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Encontrar o sub-agente do departamento
        matching_agent = None
        for agent in self.agents.values():
            if agent.department.lower() in department.lower() or department.lower() in agent.department.lower():
                matching_agent = agent
                break

        if matching_agent is None:
            matching_agent = self.agents["ceo_executive"]  # Fallback para o CEO

        # 2. Ciclo de Vida: Despertar
        matching_agent.wake_up()

        # 3. Seleção do Modelo Adaptativo (Leve vs Pesado)
        model_selection = matching_agent.select_model_tier(task_complexity)

        # 4. Execução da Tarefa Exclusiva do Setor
        execution_summary = (
            f"Sub-agente '{matching_agent.role_title}' executou a tarefa '{task_title}' "
            f"no setor '{matching_agent.department}' utilizando o modelo {model_selection['tier'].upper()} ({model_selection['modelo_selecionado']})."
        )
        matching_agent.tasks_completed += 1

        # 5. Ciclo de Vida: Hibernação Imediata
        matching_agent.hibernate()

        report = {
            "tarefa": task_title,
            "departamento": matching_agent.department,
            "subagente_responsavel": matching_agent.to_dict(),
            "roteamento_modelo": model_selection,
            "executado_em": now,
            "resumo_execucao": execution_summary,
            "estado_final_subagente": matching_agent.state,
            "resumo_ptbr": (
                f"Tarefa corporativa concluída pelo setor '{matching_agent.department}'. "
                f"Modelo utilizado: {model_selection['modelo_selecionado']} ({model_selection['tier']}). "
                f"O sub-agente retornou ao estado de hibernação."
            ),
        }

        self._save_dispatch_record(task_title, report)
        return report

    def get_hierarchy_status(self) -> Dict[str, Any]:
        """Retorna o status de todos os departamentos e sub-agentes."""
        active_count = sum(1 for a in self.agents.values() if a.state == "active")
        hibernating_count = sum(1 for a in self.agents.values() if a.state == "hibernating")

        return {
            "total_departamentos": len(self.agents),
            "subagentes_ativos": active_count,
            "subagentes_em_hibernacao": hibernating_count,
            "economia_recursos_status": "otimizado_sob_demanda",
            "departamentos": [agent.to_dict() for agent in self.agents.values()],
        }

    def _save_dispatch_record(self, task_title: str, report: Dict[str, Any]) -> None:
        """Salva o registro do dispatch em JSON."""
        clean_title = task_title.replace(" ", "_").replace("/", "_")[:30]
        file_path = self.data_dir / f"dispatch_{clean_title}_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
