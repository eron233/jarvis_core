"""
JARVIS - Agregacao Web Multi-Fonte

Substitui o antigo Agent Reach simulado por agregacao real sobre o
WebBrowserEngine/SearXNG. O modulo mede cobertura (URLs, dominios, engines)
mas nao converte cobertura em "verdade" nem inventa percentuais de confianca.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from runtime.web_browser_engine import WebBrowserEngine


_DEFAULT_REACHES = [
    {"fonte": "web_general", "category": "general", "query_suffix": ""},
    {"fonte": "news", "category": "news", "query_suffix": ""},
    {"fonte": "science", "category": "science", "query_suffix": " pesquisa estudo"},
]


class AgentReachEngine:
    """Agrega evidencias web reais sem fabricar consistencia ou confianca."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        web_browser_engine: Optional[WebBrowserEngine] = None,
    ) -> None:
        self.data_dir = (
            Path(data_dir)
            if data_dir
            else Path(__file__).resolve().parents[1] / "data" / "agent_reach_reports"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.web_browser_engine = web_browser_engine or WebBrowserEngine()

    def reach_multi_source_context(
        self,
        topic_query: str,
        sources_to_reach: Optional[List[str]] = None,
        max_results_per_source: int = 3,
    ) -> Dict[str, Any]:
        """Executa buscas reais por categoria e deduplica evidencias por URL."""

        now = datetime.now(timezone.utc).isoformat()
        topic = str(topic_query).strip()
        if not topic:
            return {
                "status": "erro",
                "topico_pesquisado": topic_query,
                "executado_em": now,
                "resultados_agregados": [],
                "motivo": "Topico vazio.",
            }

        requested = set(sources_to_reach or [])
        reaches = (
            [reach for reach in _DEFAULT_REACHES if reach["fonte"] in requested]
            if requested
            else list(_DEFAULT_REACHES)
        )
        unknown = sorted(requested - {reach["fonte"] for reach in _DEFAULT_REACHES})

        aggregated = []
        unique_urls: Dict[str, Dict[str, Any]] = {}
        domains = set()
        engines = set()

        for reach in reaches:
            query = f"{topic}{reach['query_suffix']}".strip()
            result = self.web_browser_engine.search_and_extract(
                query,
                max_results=max_results_per_source,
                category=reach["category"],
                extract_pages=False,
            )
            source_payload = {
                "fonte": reach["fonte"],
                "categoria": reach["category"],
                "query": query,
                "status": result.get("status"),
                "motivo": result.get("motivo"),
                "resultados": result.get("fontes", []),
            }
            aggregated.append(source_payload)

            for item in result.get("fontes", []):
                url = str(item.get("url") or "").strip()
                if not url:
                    continue
                unique_urls[url] = item
                host = urlparse(url).hostname
                if host:
                    domains.add(host.lower())
                for engine in item.get("engines") or []:
                    engines.add(str(engine))

        successful_sources = sum(1 for item in aggregated if item["status"] == "sucesso")
        status = "sucesso" if successful_sources else "indisponivel"

        cross_validation = {
            "status": "cobertura_medida_sem_inferencia_de_verdade",
            "fontes_consultadas": len(aggregated),
            "fontes_com_resultados": successful_sources,
            "urls_unicas": len(unique_urls),
            "dominios_unicos": len(domains),
            "engines_observadas": sorted(engines),
            "consistencia_geral_porcentagem": None,
            "nivel_confianca": None,
            "divergencias_encontradas": None,
            "observacao": (
                "Cobertura de fontes nao equivale a verificacao factual. "
                "Concordancia/contradicao entre alegacoes exige uma etapa de analise baseada em evidencias."
            ),
        }

        report = {
            "status": status,
            "topico_pesquisado": topic,
            "executado_em": now,
            "fontes_alcancadas": [item["fonte"] for item in aggregated],
            "fontes_desconhecidas_ignoradas": unknown,
            "resultados_agregados": aggregated,
            "evidencias_unicas": list(unique_urls.values()),
            "validacao_cruzada": cross_validation,
            "fabricated_confidence": False,
        }
        if not successful_sources:
            report["motivo"] = "Nenhuma categoria conseguiu obter resultados reais."

        self._save_reach_report(topic, report)
        return report

    def _save_reach_report(self, topic: str, report: Dict[str, Any]) -> None:
        clean_topic = "".join(
            char if char.isalnum() or char in {"-", "_"} else "_"
            for char in topic
        )[:50]
        file_path = self.data_dir / (
            f"reach_{clean_topic}_{int(datetime.now(timezone.utc).timestamp())}.json"
        )
        file_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
