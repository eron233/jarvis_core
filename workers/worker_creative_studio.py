"""
JARVIS - Módulo 5: Desenvolvimento Criativo e Projetos Autossustentáveis

Responsável por:
- incubação de ideias e projetos criativos baseados em tecnologias open-source
- avaliação de viabilidade, lacunas de mercado e análise de falhas dos concorrentes
- monitoramento de métricas financeiras (ROI) e disparo de kill-switch para descontinuação de projetos inviáveis
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.quantum_tree_search_engine import QuantumTreeSearchEngine

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDIO_DIR = PROJECT_ROOT / "data" / "creative_studio"


class CreativeStudioWorker:
    """Worker de desenvolvimento de projetos criativos com avaliação de viabilidade e Kill-Switch."""

    def __init__(self, studio_dir: Optional[Path] = None) -> None:
        self.studio_dir = Path(studio_dir) if studio_dir else DEFAULT_STUDIO_DIR
        self.studio_dir.mkdir(parents=True, exist_ok=True)
        self.quantum_search_engine = QuantumTreeSearchEngine()

    def incubate_project(
        self,
        project_name: str,
        concept: str,
        target_market: str,
        competitors: List[Dict[str, Any]],
        expected_monthly_roi_brl: float = 0.0,
        unsuccessful_cycles_count: int = 0,
    ) -> Dict[str, Any]:
        """
        Analisa uma ideia, avalia falhas dos concorrentes, calcula viabilidade e aciona Kill-Switch se necessário.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Avaliação do Kill-Switch (descontinuação por insucesso prolongado)
        kill_switch_triggered = False
        kill_switch_reason = None
        if unsuccessful_cycles_count >= 5 or (unsuccessful_cycles_count >= 3 and expected_monthly_roi_brl <= 0):
            kill_switch_triggered = True
            kill_switch_reason = (
                f"Projeto descontinuado pelo Kill-Switch após {unsuccessful_cycles_count} ciclos "
                "sem tração ou ROI negativo."
            )

        # 2. Análise de Falhas dos Concorrentes
        identified_weaknesses = []
        for comp in competitors:
            c_name = comp.get("nome", "Concorrente")
            c_flaws = comp.get("falhas", ["Falta de refino", "Preço elevado"])
            identified_weaknesses.append({
                "concorrente": c_name,
                "falhas_identificadas": c_flaws,
                "oportunidade_jarvis": f"Transformar as falhas de {c_name} em diferenciais do projeto.",
            })

        # 3. Exploração em Árvore Paralela e Validação Socrática dos 11 Pilares
        initial_hypotheses = [
            {"nome": f"{project_name} - Open Source Puro", "open_source": True, "custo_estimado_brl": 0.0, "diferencial_inovacao_0_10": 9.0},
            {"nome": f"{project_name} - Modelo Híbrido Cripto", "open_source": True, "custo_estimado_brl": 50.0, "diferencial_inovacao_0_10": 9.5},
            {"nome": f"{project_name} - Solução Proprietária", "open_source": False, "custo_estimado_brl": 500.0, "diferencial_inovacao_0_10": 6.0},
        ]
        quantum_tree_results = self.quantum_search_engine.explore_hypotheses_tree(
            domain_goal=concept,
            initial_hypotheses=initial_hypotheses,
            available_crypto_budget_brl=100.0,
        )

        # 4. Roteiro de Execução e Refinamento
        execution_plan = [
            "Fase 1: Mapeamento de componentes Open-Source essenciais.",
            "Fase 2: Arquitetura modular e design estético de alto padrão.",
            "Fase 3: Desenvolvimento MVP com validação de usabilidade.",
            "Fase 4: Lançamento com modelo de sustentabilidade transparente.",
        ]

        project_blueprint = {
            "projeto": project_name,
            "conceito": concept,
            "mercado_alvo": target_market,
            "criado_em": now,
            "investimento_inicial_requerido": "R$ 0,00 (baseado em Open-Source)",
            "estimativa_roi_mensal_brl": expected_monthly_roi_brl,
            "ciclos_sem_tracao": unsuccessful_cycles_count,
            "status_projeto": "descontinuado_kill_switch" if kill_switch_triggered else "ativo",
            "kill_switch": {
                "ativado": kill_switch_triggered,
                "motivo": kill_switch_reason,
            },
            "analise_arvore_quantica": quantum_tree_results,
            "analise_concorrencia": identified_weaknesses,
            "diferenciais_unicos": [
                "Execução determinística e autônoma sem lock-in.",
                "Interface refinada com foco na melhor experiência do usuário.",
                "Resolução direta das falhas não atendidas pelos concorrentes.",
            ],
            "plano_execucao": execution_plan if not kill_switch_triggered else [],
        }

        self._save_project(project_blueprint)
        return project_blueprint

    def _save_project(self, project: Dict[str, Any]) -> None:
        """Salva o plano de projeto em disco."""
        file_name = f"project_{project.get('projeto', 'novo').lower().replace(' ', '_')}.json"
        file_path = self.studio_dir / file_name
        file_path.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8")
