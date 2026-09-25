"""
JARVIS - Habilidade Padrão: Motor Graphify de Análise Topológica de Projetos

Responsável por:
- estruturar análises de projetos, ideias, códigos e arquiteturas em grafos topológicos
- extrair nós (componentes, dados, dependências, riscos) e arestas de relacionamento
- gerar saída estruturada pronta para visualização gráfica e tomada de decisão
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
import json
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GRAPHIFY_DIR = PROJECT_ROOT / "data" / "graphify_analyses"
MAX_NODES = 15
STOPWORDS = frozenset(
    """
    para como mais pelo pela pelos pelas entre sobre sendo sera esta este isso essa esse aqui
    onde quando porque cada muito muita tambem ainda apenas deve devem pode podem ser sao
    com sem uma umas uns dos das nos nas num numa que por the and with from that this into have
    projeto sistema
    """.split()
)


def _terms(sentence: str) -> List[str]:
    words = re.findall(r"[\wÀ-ÿ]{4,}", sentence.lower())
    return [w for w in words if w not in STOPWORDS and not w.isdigit()]


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

        text = f"{project_title}. {description or ''}"
        sentences = [chunk for chunk in re.split(r"[.!?;\n]+", text) if chunk.strip()]

        if raw_components:
            labels = [str(c).strip() for c in raw_components if str(c).strip()][:MAX_NODES]
            sentence_terms = [
                {label for label in labels if label.lower() in sentence.lower()} for sentence in sentences
            ]
            frequency = Counter({label: max(1, sum(label in terms for terms in sentence_terms)) for label in labels})
            origin = "componentes_informados"
        else:
            sentence_terms = [set(_terms(sentence)) for sentence in sentences]
            frequency = Counter(term for terms in sentence_terms for term in terms)
            labels = [term for term, _ in frequency.most_common(MAX_NODES)]
            origin = "termos_extraidos_do_texto"

        node_ids = {label: f"node_{index + 1}" for index, label in enumerate(labels)}
        top = max(frequency.values(), default=1)
        nodes = [
            {
                "id": node_ids[label],
                "label": label,
                "frequencia": frequency[label],
                "importancia_score": round(10.0 * frequency[label] / top, 2),
            }
            for label in labels
        ]

        cooccurrence: Counter = Counter()
        for terms in sentence_terms:
            present = sorted(t for t in terms if t in node_ids)
            for a, b in combinations(present, 2):
                cooccurrence[(a, b)] += 1
        if raw_components and not cooccurrence and len(labels) > 1:
            # Componentes informados sem mencao no texto: encadeia na ordem dada, marcado como tal.
            for a, b in zip(labels, labels[1:]):
                cooccurrence[(a, b)] = 0
        edges = [
            {
                "origem": node_ids[a],
                "destino": node_ids[b],
                "relacao": "coocorrem" if weight else "sequencia_informada",
                "peso": weight,
            }
            for (a, b), weight in cooccurrence.most_common()
        ]

        possible_edges = len(nodes) * (len(nodes) - 1) / 2
        graph_result = {
            "projeto": project_title,
            "analisado_em": now,
            "metodo": "coocorrencia_por_frase",
            "origem_dos_nos": origin,
            "estatisticas": {
                "total_nos": len(nodes),
                "total_arestas": len(edges),
                "densidade_topologica": round(len(edges) / possible_edges, 2) if possible_edges else 0.0,
            },
            "grafo": {
                "nos": nodes,
                "arestas": edges,
            },
            "resumo_topologico_ptbr": (
                f"'{project_title}': {len(nodes)} conceito(s) e {len(edges)} relacao(oes) de coocorrencia."
                + (f" Mais central: {labels[0]}." if labels else " Texto insuficiente para montar o grafo.")
            ),
        }

        self._save_graphify_record(graph_result)
        return graph_result

    def _save_graphify_record(self, record: Dict[str, Any]) -> None:
        """Salva a análise Graphify em disco."""
        file_id = f"graphify_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')}.json"
        file_path = self.data_dir / file_id
        file_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
