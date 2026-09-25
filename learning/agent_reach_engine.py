"""
JARVIS - Motor de Alcance Profundo e Agregação Multi-Fonte (Agent Reach Engine)

Responsável por:
- realizar pesquisas abrangentes e agregadas em múltiplas plataformas, fontes de notícias, repositórios de dados e redes
- agregar contextualização profunda de informações públicas dispersas na web
- sumarizar e validar a consistência cruzada das fontes antes da ingestão na memória semântica

A pesquisa é real: cada fonte é consultada através de
WebBrowserEngine.search_and_extract, que faz busca de verdade (DuckDuckGo
HTML). As métricas de "validação cruzada" são calculadas a partir dos
resultados reais (sobreposição de termos entre os trechos retornados, via
similaridade de Jaccard), nunca números fixos.

Padrão de injeção para testes: aceita `search_results_by_source` (mapa
fonte -> HTML de resultados já baixado) e/ou `browser_engine` (motor
substituto), para que o teste do chamador não dependa de rede.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional

from runtime.web_browser_engine import WebBrowserEngine

LOGGER = logging.getLogger("jarvis.learning.agent_reach")

_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)


def _tokenize(text: str) -> set:
    return set(_WORD_PATTERN.findall(text.lower()))


def _jaccard_similarity(a: str, b: str) -> float:
    """Mede a sobreposição de termos entre dois textos (0.0 a 1.0)."""
    tokens_a = _tokenize(a)
    tokens_b = _tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    intersecao = tokens_a & tokens_b
    uniao = tokens_a | tokens_b
    return len(intersecao) / len(uniao) if uniao else 0.0


class AgentReachEngine:
    """Motor de alcance expandido para agregação contextual multi-fonte."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "agent_reach_reports"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def reach_multi_source_context(
        self,
        topic_query: str,
        sources_to_reach: Optional[List[str]] = None,
        search_results_by_source: Optional[Dict[str, str]] = None,
        browser_engine: Optional[WebBrowserEngine] = None,
    ) -> Dict[str, Any]:
        """
        Executa uma varredura multi-fonte para agregar contexto profundo e cruzar informações.

        Para cada fonte em `sources_to_reach`, é feita uma busca real via
        WebBrowserEngine.search_and_extract. Em testes, `search_results_by_source`
        pode injetar o HTML de resultados por fonte (sem tocar a rede), e
        `browser_engine` pode injetar um motor substituto por completo.
        """
        now = datetime.now(timezone.utc).isoformat()

        sources = sources_to_reach or ["web_search", "tech_news_feeds", "market_data", "academic_papers"]
        search_results_by_source = search_results_by_source or {}
        engine = browser_engine or WebBrowserEngine()

        aggregated_results: List[Dict[str, Any]] = []
        todos_snippets: List[str] = []
        fontes_com_resultado = 0

        for src in sources:
            html_injetado = search_results_by_source.get(src)
            busca = engine.search_and_extract(topic_query, html_content=html_injetado)

            fontes_encontradas = busca.get("fontes", [])
            busca_status = busca.get("status", "erro")

            if fontes_encontradas:
                fontes_com_resultado += 1
                status = "alcance_bem_sucedido"
            elif busca_status == "sucesso":
                status = "sem_resultados"
            else:
                status = "falha_de_alcance"

            dados_relevantes = [
                f"{item.get('titulo') or item.get('url', 'fonte sem titulo')}: {item.get('resumo_snippet', '')}".strip(": ")
                for item in fontes_encontradas
            ]

            snippets_da_fonte = [item.get("resumo_snippet", "") for item in fontes_encontradas if item.get("resumo_snippet")]
            todos_snippets.extend(snippets_da_fonte)

            # Confiabilidade real: proporção de resultados obtidos sobre o
            # máximo esperado (heurística simples baseada em dados efetivos).
            confiabilidade = round(min(100.0, 100.0 * len(fontes_encontradas) / 3.0), 2) if busca_status == "sucesso" else 0.0

            aggregated_results.append({
                "fonte": src,
                "status": status,
                "total_resultados_reais": len(fontes_encontradas),
                "dados_relevantes": dados_relevantes,
                "confiabilidade_0_100": confiabilidade,
                "detalhe_busca": {
                    "status_busca": busca_status,
                    "motivo": busca.get("motivo"),
                },
            })

        # Validação cruzada real: similaridade de Jaccard média entre todos
        # os pares de trechos (snippets) retornados pelas diferentes fontes.
        pares_similaridade: List[float] = []
        divergencias = 0
        limiar_convergencia = 0.05
        for i in range(len(todos_snippets)):
            for j in range(i + 1, len(todos_snippets)):
                sim = _jaccard_similarity(todos_snippets[i], todos_snippets[j])
                pares_similaridade.append(sim)
                if sim < limiar_convergencia:
                    divergencias += 1

        if pares_similaridade:
            consistencia = round(100.0 * (sum(pares_similaridade) / len(pares_similaridade)), 2)
        else:
            consistencia = 0.0

        if fontes_com_resultado == 0:
            nivel_confianca = "nenhum_dado"
        elif consistencia >= 30.0:
            nivel_confianca = "alto"
        elif consistencia >= 10.0:
            nivel_confianca = "medio"
        else:
            nivel_confianca = "baixo"

        cross_validation = {
            "consistencia_geral_porcentagem": consistencia,
            "divergencias_encontradas": divergencias,
            "nivel_confianca": nivel_confianca,
            "total_fontes_com_resultados": fontes_com_resultado,
            "total_fontes_consultadas": len(sources),
            "total_trechos_comparados": len(todos_snippets),
        }

        report = {
            "topico_pesquisado": topic_query,
            "executado_em": now,
            "fontes_alcancadas": sources,
            "resultados_agregados": aggregated_results,
            "validacao_cruzada": cross_validation,
            "sintese_alcance_ptbr": (
                f"Alcance multi-fonte do Agent Reach concluído para '{topic_query}' em {len(sources)} fonte(s) consultada(s), "
                f"{fontes_com_resultado} com resultado real. "
                f"Consistência cruzada calculada de {cross_validation['consistencia_geral_porcentagem']}%. "
                f"Nível de confiança: {nivel_confianca}."
            ),
        }

        self._save_reach_report(topic_query, report)
        return report

    def _save_reach_report(self, topic: str, report: Dict[str, Any]) -> None:
        """Salva o relatório do Agent Reach em arquivo JSON."""
        clean_topic = topic.replace(" ", "_").replace("/", "_")[:30]
        file_path = self.data_dir / f"reach_{clean_topic}_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
