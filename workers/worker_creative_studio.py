"""
JARVIS - Módulo 5: Desenvolvimento Criativo e Projetos Autossustentáveis

Responsável por:
- incubação de ideias e projetos criativos baseados em tecnologias open-source
- avaliação de viabilidade, lacunas de mercado e análise de falhas dos concorrentes
- planejamento de soluções refinadas e diferenciais não copiáveis para gerar recursos
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STUDIO_DIR = PROJECT_ROOT / "data" / "creative_studio"


class CreativeStudioWorker:
    """Worker de desenvolvimento de projetos criativos e autossustentabilidade."""

    def __init__(self, studio_dir: Optional[Path] = None) -> None:
        self.studio_dir = Path(studio_dir) if studio_dir else DEFAULT_STUDIO_DIR
        self.studio_dir.mkdir(parents=True, exist_ok=True)

    def incubate_project(
        self,
        project_name: str,
        concept: str,
        target_market: str,
        competitors: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analisa uma ideia, avalia falhas dos concorrentes e gera um plano de execução de alto padrão.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Análise de Falhas dos Concorrentes
        identified_weaknesses = []
        for comp in competitors:
            c_name = comp.get("nome", "Concorrente")
            c_flaws = comp.get("falhas", ["Falta de refino", "Preço elevado"])
            identified_weaknesses.append({
                "concorrente": c_name,
                "falhas_identificadas": c_flaws,
                "oportunidade_jarvis": f"Transformar as falhas de {c_name} em diferenciais do projeto.",
            })

        # 2. Roteiro de Execução e Refinamento
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
            "analise_concorrencia": identified_weaknesses,
            "diferenciais_unicos": [
                "Execução determinística e autônoma sem lock-in.",
                "Interface refinada com foco na melhor experiência do usuário.",
                "Resolução direta das falhas não atendidas pelos concorrentes.",
            ],
            "plano_execucao": execution_plan,
        }

        self._save_project(project_blueprint)
        return project_blueprint

    def _save_project(self, project: Dict[str, Any]) -> None:
        """Salva o plano de projeto em disco."""
        file_name = f"project_{project.get('projeto', 'novo').lower().replace(' ', '_')}.json"
        file_path = self.studio_dir / file_name
        file_path.write_text(json.dumps(project, indent=2, ensure_ascii=False), encoding="utf-8")
