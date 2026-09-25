"""
JARVIS - Hierarquia de Sub-Agentes Corporativos e Roteamento Adaptativo (Corporate Agent Hierarchy)

Responsável por:
- organizar o JARVIS como uma estrutura de departamentos especializados;
- aplicar o ciclo de vida sob demanda: o sub-agente desperta para a tarefa e hiberna após concluir;
- rotear a tarefa para uma camada de modelo (leve para rotina, pesado para tarefas críticas);
- executar a tarefa DE VERDADE quando um handler (executor) está registrado para o departamento;
  quando nenhum executor está conectado, o dispatch é honesto: apenas planeja o roteamento e
  declara que não houve execução.

Nota de honestidade: nenhum modelo de LLM está conectado a este orquestrador no momento. Os
nomes de camada ("leve"/"pesado") descrevem a POLÍTICA de roteamento; o campo `modelo_conectado`
indica se há de fato um executor ligado. A execução real acontece via handlers registrados com
`register_department_handler`.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

LOGGER = logging.getLogger("jarvis.runtime.corporate_hierarchy")

# Executor: recebe (task_title, task_payload) e devolve um dicionário de resultado real.
DepartmentHandler = Callable[[str, Dict[str, Any]], Dict[str, Any]]


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
        self.state = "active"
        self.last_active_at = datetime.now(timezone.utc).isoformat()
        LOGGER.info("[subagent_wake] %s (%s) despertado.", self.agent_id, self.department)

    def hibernate(self) -> None:
        self.state = "hibernating"
        LOGGER.info("[subagent_hibernate] %s (%s) hibernando.", self.agent_id, self.department)

    def select_model_tier(self, task_complexity: str) -> Dict[str, Any]:
        """Seleciona a camada de modelo (leve vs pesado) pela complexidade da tarefa."""
        if task_complexity in ("critica", "complexa", "high", "alta"):
            return {
                "modelo_selecionado": self.heavy_model,
                "tier": "pesado",
                "motivo_selecao": "Tarefa crítica/complexa: exige raciocínio profundo.",
            }
        return {
            "modelo_selecionado": self.light_model,
            "tier": "leve",
            "motivo_selecao": "Tarefa rotineira: otimiza tempo e custo.",
        }

    def to_dict(self) -> Dict[str, Any]:
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
    """Orquestrador dos departamentos e sub-agentes do JARVIS com execução por handlers reais."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "corporate_hierarchy"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Executores reais registrados por departamento (nenhum por padrão — honesto).
        self._handlers: Dict[str, DepartmentHandler] = {}

        # Camadas de modelo descrevem a POLÍTICA de roteamento, não um LLM conectado.
        self.agents: Dict[str, CorporateSubAgent] = {
            "ceo_executive": CorporateSubAgent(
                "ceo_executive", "Gabinete_Executivo",
                "Diretor Executivo de Estratégia e Decisões",
                light_model="roteador-leve", heavy_model="roteador-pesado",
            ),
            "security_director": CorporateSubAgent(
                "security_director", "Diretoria_de_Seguranca_e_Auditoria",
                "Especialista em Defesa e Análise Estática",
                light_model="checagem-rapida", heavy_model="analise-profunda",
            ),
            "engineering_lead": CorporateSubAgent(
                "engineering_lead", "Engenharia_de_Software_e_Arquitetura",
                "Líder de Desenvolvimento e Refatoração",
                light_model="codigo-leve", heavy_model="codigo-profundo",
            ),
            "web_research_agent": CorporateSubAgent(
                "web_research_agent", "Inteligencia_de_Mercado_e_Navegacao_Web",
                "Pesquisador Web e Coletor de Dados",
                light_model="scraper-leve", heavy_model="pesquisa-profunda",
            ),
            "finance_trader": CorporateSubAgent(
                "finance_trader", "Analise_Financeira_e_Day_Trade",
                "Analista de Fluxo de Ordens e Riscos",
                light_model="ticker-rapido", heavy_model="analise-financeira",
            ),
        }

    def register_department_handler(self, department: str, handler: DepartmentHandler) -> None:
        """Conecta um executor REAL a um departamento; sem isso, o dispatch apenas planeja."""
        self._handlers[department.lower()] = handler

    def _find_agent(self, department: str) -> CorporateSubAgent:
        dep = department.lower()
        for agent in self.agents.values():
            if agent.department.lower() in dep or dep in agent.department.lower():
                return agent
        return self.agents["ceo_executive"]  # fallback

    def _resolve_handler(self, agent: CorporateSubAgent, department: str) -> Optional[DepartmentHandler]:
        return self._handlers.get(department.lower()) or self._handlers.get(agent.department.lower())

    def dispatch_corporate_task(
        self,
        department: str,
        task_title: str,
        task_payload: Dict[str, Any],
        task_complexity: str = "intermediaria",
    ) -> Dict[str, Any]:
        """
        Localiza o sub-agente do departamento, desperta-o, seleciona a camada de modelo, executa
        via handler registrado (se houver) e o coloca de volta em hibernação.
        """
        now = datetime.now(timezone.utc).isoformat()
        agent = self._find_agent(department)
        agent.wake_up()
        model_selection = agent.select_model_tier(task_complexity)

        handler = self._resolve_handler(agent, department)
        if handler is not None:
            try:
                resultado_execucao = handler(task_title, task_payload)
                executado = True
                modelo_conectado = True
                resumo_execucao = (
                    f"Departamento '{agent.department}' executou '{task_title}' via executor conectado."
                )
                agent.tasks_completed += 1
            except Exception as exc:  # o executor falhou: reportar honestamente
                resultado_execucao = {"status": "erro", "motivo": str(exc)}
                executado = False
                modelo_conectado = True
                resumo_execucao = f"Executor do departamento '{agent.department}' falhou: {exc}"
        else:
            resultado_execucao = {
                "status": "nao_executado",
                "motivo": "Nenhum executor conectado a este departamento; roteamento apenas planejado.",
            }
            executado = False
            modelo_conectado = False
            resumo_execucao = (
                f"Roteamento planejado para '{agent.department}' (camada {model_selection['tier']}). "
                "Nenhum executor conectado — tarefa não foi executada."
            )

        agent.hibernate()

        report = {
            "tarefa": task_title,
            "departamento": agent.department,
            "subagente_responsavel": agent.to_dict(),
            "roteamento_modelo": model_selection,
            "modelo_conectado": modelo_conectado,
            "executado": executado,
            "resultado_execucao": resultado_execucao,
            "executado_em": now,
            "resumo_execucao": resumo_execucao,
            "estado_final_subagente": agent.state,
            "resumo_ptbr": resumo_execucao,
        }
        self._save_dispatch_record(task_title, report)
        return report

    def get_hierarchy_status(self) -> Dict[str, Any]:
        active_count = sum(1 for a in self.agents.values() if a.state == "active")
        hibernating_count = sum(1 for a in self.agents.values() if a.state == "hibernating")
        return {
            "total_departamentos": len(self.agents),
            "subagentes_ativos": active_count,
            "subagentes_em_hibernacao": hibernating_count,
            "departamentos_com_executor_conectado": sorted(self._handlers.keys()),
            "economia_recursos_status": "otimizado_sob_demanda",
            "departamentos": [agent.to_dict() for agent in self.agents.values()],
        }

    def _save_dispatch_record(self, task_title: str, report: Dict[str, Any]) -> None:
        clean = "".join(c if c.isalnum() or c in "-_" else "_" for c in task_title)[:40]
        path = self.data_dir / f"dispatch_{clean}_{int(datetime.now(timezone.utc).timestamp() * 1000)}.json"
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
