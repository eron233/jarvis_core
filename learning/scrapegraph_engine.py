"""
JARVIS - Extracao Estruturada Web

Compatibilidade com o antigo ScrapeGraphEngine, agora baseada em extracao real
do Crawl4AI. O motor nao inventa campos ausentes nem valores de placeholder.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from runtime.web_stack import WebStack


class ScrapeGraphEngine:
    """Extracao estruturada auditavel a partir de HTML ja fornecido."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        web_stack: Optional[WebStack] = None,
    ) -> None:
        self.data_dir = (
            Path(data_dir)
            if data_dir
            else Path(__file__).resolve().parents[1] / "data" / "scrapegraph_nodes"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.web_stack = web_stack or WebStack()

    @staticmethod
    def _is_crawl4ai_schema(schema: Dict[str, Any]) -> bool:
        return bool(
            isinstance(schema, dict)
            and isinstance(schema.get("baseSelector"), str)
            and schema.get("baseSelector", "").strip()
            and isinstance(schema.get("fields"), list)
            and all(
                isinstance(field, dict)
                and isinstance(field.get("name"), str)
                and field.get("name", "").strip()
                for field in schema.get("fields", [])
            )
        )

    def extract_structured_graph(
        self,
        target_url: str,
        html_content: str,
        extraction_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Executa schema CSS real via Crawl4AI e registra a proveniencia."""

        now = datetime.now(timezone.utc).isoformat()
        parsed_url = urlparse(target_url)
        domain = parsed_url.netloc or "local"

        graph_nodes = [
            {
                "id": "node_root",
                "label": f"SiteRoot:{domain}",
                "tipo": "dominio",
            }
        ]
        edges = []

        if not self._is_crawl4ai_schema(extraction_schema):
            result = {
                "status": "indisponivel",
                "url_alvo": target_url,
                "dominio": domain,
                "schema_solicitado": extraction_schema,
                "grafo_extracao": {"nos": graph_nodes, "arestas": edges},
                "dados_estruturados_extraidos": None,
                "metodo": None,
                "motivo": (
                    "O schema legado baseado apenas em tipos nao prova como cada campo deve "
                    "ser extraido. Use schema Crawl4AI JSON-CSS com baseSelector e fields."
                ),
                "executado_em": now,
            }
            self._save_graph_snapshot(domain, result)
            return result

        for field in extraction_schema["fields"]:
            node_id = f"node_{field['name']}"
            graph_nodes.append(
                {
                    "id": node_id,
                    "label": field["name"],
                    "selector": field.get("selector"),
                    "tipo_extracao": field.get("type"),
                }
            )
            edges.append(
                {
                    "origem": "node_root",
                    "destino": node_id,
                    "relacao": "extrai_campo",
                }
            )

        extraction = self.web_stack.extract_structured_html(
            str(html_content),
            extraction_schema,
        )

        result = {
            "status": extraction.get("status", "erro"),
            "url_alvo": target_url,
            "dominio": domain,
            "schema_solicitado": extraction_schema,
            "grafo_extracao": {
                "nos": graph_nodes,
                "arestas": edges,
            },
            "dados_estruturados_extraidos": extraction.get("dados"),
            "metodo": extraction.get("metodo"),
            "motivo": extraction.get("motivo"),
            "executado_em": now,
            "fabricated_values": False,
        }
        self._save_graph_snapshot(domain, result)
        return result

    def _save_graph_snapshot(self, domain: str, result: Dict[str, Any]) -> None:
        clean_domain = domain.replace(":", "_").replace("/", "_")
        file_path = self.data_dir / f"scrapegraph_{clean_domain}.json"
        file_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
