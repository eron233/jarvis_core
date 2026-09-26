"""
JARVIS - Habilidade Padrão: Motor Graphify de Análise Topológica de Projetos

Responsável por:
- estruturar análises de projetos, ideias, códigos e arquiteturas em grafos topológicos
- extrair nós (componentes, dados, dependências, riscos) e arestas de relacionamento
- gerar saída estruturada pronta para visualização gráfica e tomada de decisão
"""

from __future__ import annotations

from datetime import datetime, timezone
import re
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPHIFY_DIR = PROJECT_ROOT / "data" / "graphify_analyses"


class GraphifyEngine:
    """Motor Graphify para estruturação topológica de projetos e conceitos em grafos."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else DEFAULT_GRAPHIFY_DIR
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def analyze_and_graphify(
        self,
        project_title: str,
        description: str,
        raw_components: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Transforma a descrição de um projeto em uma estrutura de grafo topológico com nós e arestas.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Extração Topológica de Nós
        nodes = []
        if raw_components:
            components = list(raw_components)
            origem_dos_nos = "componentes_informados"
        else:
            components = self._extract_components(description)
            origem_dos_nos = "extraidos_da_descricao" if components else "modelo_generico"
            if not components:
                # A versao anterior caia direto neste modelo para qualquer projeto
                # e ignorava a descricao, devolvendo sempre os mesmos cinco nos.
                components = ["Core Executivo", "Banco de Dados", "API Gateway", "Interface UI", "Módulo de Segurança"]
        for idx, comp in enumerate(components):
            nodes.append({
                "id": f"node_{idx + 1}",
                "label": comp,
                "grupo": "infraestrutura" if "Banco" in comp or "API" in comp else "topologia_principal",
                "importancia_score": 9.0 - (idx * 0.5),
            })

        # 2. Construção de Arestas e Dependências
        edges = []
        if len(nodes) > 1:
            for i in range(len(nodes) - 1):
                edges.append({
                    "origem": nodes[i]["id"],
                    "destino": nodes[i + 1]["id"],
                    "relacao": "conecta_com",
                    "peso": 1.0,
                })
            # Aresta de ciclo com o primeiro nó
            edges.append({
                "origem": nodes[-1]["id"],
                "destino": nodes[0]["id"],
                "relacao": "retroalimenta",
                "peso": 0.8,
            })

        graph_result = {
            "projeto": project_title,
            "analisado_em": now,
            "metodo": "Graphify_Topological_Structuring",
            "origem_dos_nos": origem_dos_nos,
            "descricao_utilizada": origem_dos_nos == "extraidos_da_descricao",
            "estatisticas": {
                "total_nos": len(nodes),
                "total_arestas": len(edges),
                "densidade_topologica": round(len(edges) / max(len(nodes), 1), 2),
            },
            "grafo": {
                "nos": nodes,
                "arestas": edges,
            },
            "resumo_topologico_ptbr": (
                f"Análise Graphify de '{project_title}': {len(nodes)} nós e {len(edges)} arestas. "
                + (
                    "Nós informados pelo chamador."
                    if origem_dos_nos == "componentes_informados"
                    else "Nós extraídos da descrição."
                    if origem_dos_nos == "extraidos_da_descricao"
                    else "A descrição não permitiu extrair componentes; foi usado um modelo genérico."
                )
            ),
        }

        self._save_graphify_record(graph_result)
        return graph_result

    @staticmethod
    def _extract_components(description: str) -> List[str]:
        """
        Extrai componentes candidatos a partir da descricao do projeto.

        Parametros:
        - description: texto livre descrevendo o projeto.

        Retorno:
        - lista de componentes encontrados, possivelmente vazia.

        Efeitos no sistema:
        - nenhum.

        A separacao e deliberadamente simples e previsivel: o texto e quebrado
        por virgula, ponto e virgula, barra, quebra de linha e pela conjuncao
        " e ". Nao ha inferencia semantica aqui, e o relatorio diz de onde os
        nos vieram para que ninguem leia isto como analise profunda.
        """

        if not description or not description.strip():
            return []

        partes = re.split(r"[,;/\n]| \be\b ", description)
        componentes = []
        for parte in partes:
            limpo = parte.strip(" .\t")
            if len(limpo) < 3 or len(limpo) > 60:
                continue
            if limpo.lower() in {termo.lower() for termo in componentes}:
                continue
            componentes.append(limpo)
        return componentes[:12]

    def _save_graphify_record(self, record: Dict[str, Any]) -> None:
        """Salva a análise Graphify em disco."""
        file_id = f"graphify_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path = self.data_dir / file_id
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
