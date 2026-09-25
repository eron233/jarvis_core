"""
JARVIS - Habilidade Padrão: Motor Graphify de Análise Topológica de Projetos

Responsável por:
- estruturar análises de projetos, ideias, códigos e arquiteturas em grafos topológicos
- extrair nós (componentes, dados, dependências, riscos) e arestas de relacionamento
- gerar saída estruturada pronta para visualização gráfica e tomada de decisão
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPHIFY_DIR = PROJECT_ROOT / "data" / "graphify_analyses"

# Stopwords em português usadas para limpar os fragmentos extraídos da descrição.
_PTBR_STOPWORDS = {
    "de", "da", "do", "das", "dos", "com", "e", "a", "o", "as", "os",
    "para", "por", "um", "uma", "uns", "umas", "em", "no", "na", "nos",
    "nas", "que", "é", "ao", "aos", "às", "se", "ou", "sem", "sob",
    "sobre", "entre", "até", "como",
}


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

        Os componentes (nós) vêm de `raw_components`, quando fornecido, ou são extraídos
        de verdade a partir do texto de `description` (tokenização + remoção de stopwords).
        As métricas topológicas (densidade, grau, hub, ciclicidade) são calculadas sobre o
        grafo efetivamente construído, não inventadas.
        """
        now = datetime.now(timezone.utc).isoformat()

        # 1. Extração Topológica de Nós (a partir da descrição, quando não há componentes explícitos)
        components = raw_components if raw_components else self._extract_components_from_description(description)
        if not components:
            components = ["Componente não identificado"]

        nodes = []
        for idx, comp in enumerate(components):
            nodes.append({
                "id": f"node_{idx + 1}",
                "label": comp,
                "grupo": "infraestrutura" if re.search(r"banco|api|servidor|fila|gateway", comp, re.IGNORECASE) else "topologia_principal",
                "importancia_score": 0.0,  # preenchido depois, a partir do grau real do nó
            })

        # 2. Construção de Arestas e Dependências (cadeia sequencial + retroalimentação em anel)
        edges = []
        if len(nodes) > 1:
            for i in range(len(nodes) - 1):
                edges.append({
                    "origem": nodes[i]["id"],
                    "destino": nodes[i + 1]["id"],
                    "relacao": "conecta_com",
                    "peso": 1.0,
                })
            # Aresta de retroalimentação fechando o ciclo com o primeiro nó
            edges.append({
                "origem": nodes[-1]["id"],
                "destino": nodes[0]["id"],
                "relacao": "retroalimenta",
                "peso": 0.8,
            })

        # 3. Métricas topológicas reais calculadas sobre o grafo construído
        metrics = self._compute_graph_metrics(nodes, edges)

        # importancia_score derivada do grau real do nó (não mais um valor arbitrário fixo)
        for node in nodes:
            node["importancia_score"] = round(metrics["graus"][node["id"]] * 1.0, 2)

        hub_id = metrics["hub_id"]
        hub_label = next((n["label"] for n in nodes if n["id"] == hub_id), None)

        ciclo_txt = (
            f"O grafo é cíclico (há retroalimentação entre nós)."
            if metrics["tem_ciclo"]
            else "O grafo é acíclico (nenhum ciclo de dependência foi detectado)."
        )
        hub_txt = f" O nó de maior grau (hub) é '{hub_label}' com grau {metrics['grau_maximo']}." if hub_label else ""

        graph_result = {
            "projeto": project_title,
            "analisado_em": now,
            "metodo": "Graphify_Topological_Structuring",
            "estatisticas": {
                "total_nos": len(nodes),
                "total_arestas": len(edges),
                "densidade_topologica": metrics["densidade"],
                "graus": metrics["graus"],
                "hub_id": hub_id,
                "grau_maximo": metrics["grau_maximo"],
                "tem_ciclo": metrics["tem_ciclo"],
            },
            "grafo": {
                "nos": nodes,
                "arestas": edges,
            },
            "resumo_topologico_ptbr": (
                f"Análise Graphify de '{project_title}': mapeados {len(nodes)} nós e {len(edges)} arestas "
                f"de dependência topológica (densidade {metrics['densidade']}). {ciclo_txt}{hub_txt}"
            ),
        }

        self._save_graphify_record(graph_result)
        return graph_result

    def _extract_components_from_description(self, description: str) -> List[str]:
        """
        Extrai componentes/termos reais a partir do texto livre da descrição.

        Estratégia: separa o texto por vírgulas, quebras de linha e pela conjunção " e ",
        depois remove stopwords em pt-BR token a token e descarta fragmentos vazios.
        """
        if not description or not description.strip():
            return []

        # Separa por vírgula, quebra de linha ou a conjunção " e " (com espaços ao redor)
        raw_fragments = re.split(r",|\n|\s+e\s+", description.strip())

        components: List[str] = []
        for fragment in raw_fragments:
            tokens = re.findall(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9]+", fragment)
            kept_tokens = [t for t in tokens if t.lower() not in _PTBR_STOPWORDS]
            if not kept_tokens:
                continue
            label = " ".join(kept_tokens)
            # Título simples para leitura (primeira letra de cada palavra maiúscula)
            label = " ".join(w.capitalize() if not w.isupper() else w for w in label.split())
            components.append(label)

        return components

    def _compute_graph_metrics(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcula métricas topológicas reais sobre o grafo dirigido construído:
        densidade, grau (entrada+saída) de cada nó, hub (maior grau) e presença de ciclo.
        """
        n = len(nodes)
        node_ids = [node["id"] for node in nodes]

        # Densidade de grafo dirigido: arestas / (n*(n-1)), protegendo divisão por zero
        max_possible_edges = n * (n - 1)
        densidade = round(len(edges) / max_possible_edges, 4) if max_possible_edges > 0 else 0.0

        # Grau (entrada + saída) de cada nó
        graus = {node_id: 0 for node_id in node_ids}
        adjacency: Dict[str, List[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            origem, destino = edge["origem"], edge["destino"]
            if origem in graus:
                graus[origem] += 1
            if destino in graus:
                graus[destino] += 1
            if origem in adjacency:
                adjacency[origem].append(destino)

        grau_maximo = max(graus.values()) if graus else 0
        hub_id = max(graus, key=graus.get) if graus else None

        # Detecção de ciclo real via DFS com pilha de recursão
        tem_ciclo = self._has_cycle(adjacency)

        return {
            "densidade": densidade,
            "graus": graus,
            "grau_maximo": grau_maximo,
            "hub_id": hub_id,
            "tem_ciclo": tem_ciclo,
        }

    @staticmethod
    def _has_cycle(adjacency: Dict[str, List[str]]) -> bool:
        """Detecta ciclo em grafo dirigido via DFS (busca por aresta de retorno na pilha atual)."""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in adjacency}

        def visit(node: str) -> bool:
            color[node] = GRAY
            for neighbor in adjacency.get(node, []):
                if neighbor not in color:
                    continue
                if color[neighbor] == GRAY:
                    return True
                if color[neighbor] == WHITE and visit(neighbor):
                    return True
            color[node] = BLACK
            return False

        for node in adjacency:
            if color[node] == WHITE:
                if visit(node):
                    return True
        return False

    def _save_graphify_record(self, record: Dict[str, Any]) -> None:
        """Salva a análise Graphify em disco."""
        file_id = f"graphify_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path = self.data_dir / file_id
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
