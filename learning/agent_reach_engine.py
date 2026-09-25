"""
JARVIS - Agregacao de contexto multi-fonte (Agent Reach)

Responsavel por:
- consultar a busca web real com variacoes do topico
- agregar fontes unicas por dominio e medir concordancia simples entre elas
- nunca inventar fontes, porcentagens ou "sinais de tendencia"
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import urllib.parse

from runtime.web_browser_engine import WebBrowserEngine

LOGGER = logging.getLogger("jarvis.learning.agent_reach")

DEFAULT_QUERY_VARIANTS = ("{topic}", "{topic} noticias", "{topic} estudo OR pesquisa")


class AgentReachEngine:
    """Agrega resultados reais de busca em varias consultas sobre o mesmo topico."""

    def __init__(self, data_dir: Optional[Path] = None, browser: Optional[WebBrowserEngine] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "agent_reach_reports"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.browser = browser or WebBrowserEngine()

    def reach_multi_source_context(
        self,
        topic_query: str,
        sources_to_reach: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Executa as consultas e agrega fontes unicas com os trechos retornados."""

        now = datetime.now(timezone.utc).isoformat()
        variants = sources_to_reach or [v.format(topic=topic_query) for v in DEFAULT_QUERY_VARIANTS]

        aggregated_results: List[Dict[str, Any]] = []
        seen_urls: set[str] = set()
        failures: List[str] = []
        for query in variants:
            search = self.browser.search_and_extract(query, max_results=5)
            if search.get("status") == "indisponivel":
                failures.append(search.get("motivo", "indisponivel"))
                continue
            for source in search.get("fontes", []):
                url = source.get("url", "")
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)
                aggregated_results.append({
                    "consulta": query,
                    "dominio": urllib.parse.urlparse(url).hostname or "",
                    "titulo": source.get("titulo", ""),
                    "url": url,
                    "trecho": source.get("resumo_snippet", ""),
                })

        domains = {item["dominio"] for item in aggregated_results if item["dominio"]}
        topic_terms = {t for t in re.findall(r"\w{4,}", topic_query.lower())}
        mentioning = [
            item for item in aggregated_results
            if topic_terms and topic_terms & set(re.findall(r"\w{4,}", (item["titulo"] + " " + item["trecho"]).lower()))
        ]

        status = "sucesso" if aggregated_results else ("indisponivel" if failures else "sem_resultados")
        report = {
            "topico_pesquisado": topic_query,
            "executado_em": now,
            "status": status,
            "consultas_executadas": variants,
            "falhas": failures,
            "resultados_agregados": aggregated_results,
            "cobertura": {
                "fontes_unicas": len(aggregated_results),
                "dominios_distintos": len(domains),
                "fontes_que_citam_o_topico": len(mentioning),
            },
            "sintese_alcance_ptbr": (
                f"{len(aggregated_results)} fonte(s) unica(s) em {len(domains)} dominio(s) para '{topic_query}'."
                if aggregated_results
                else f"Nenhuma fonte obtida para '{topic_query}'."
            ),
        }

        self._save_reach_report(topic_query, report)
        return report

    def _save_reach_report(self, topic: str, report: Dict[str, Any]) -> None:
        """Salva o relatorio em arquivo JSON."""
        clean_topic = re.sub(r"[^A-Za-z0-9_-]", "_", topic)[:30] or "topico"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        file_path = self.data_dir / f"reach_{clean_topic}_{timestamp}.json"
        file_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
