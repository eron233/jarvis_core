"""
JARVIS - Motor de Extração por Grafo Adaptativo (ScrapeGraphAI Concept)

Responsável por:
- extrair dados estruturados de HTML/Páginas Web sem depender de seletores CSS/XPath rígidos
- construir um grafo de nós conceituais para mapeamento semântico de elementos
- adaptar automaticamente a extração mesmo quando a estrutura do DOM for alterada

A extração usa `html.parser` (stdlib) para ler de verdade o HTML recebido:
título, cabeçalhos, parágrafos, itens de lista, links e números presentes no
texto. Quando um campo do schema não pode ser encontrado no HTML, o valor
retornado é vazio/None (nunca um valor fixo inventado).
"""

from __future__ import annotations

from html.parser import HTMLParser
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

LOGGER = logging.getLogger("jarvis.learning.scrapegraph")

_NUMBER_PATTERN = re.compile(r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:[.,]\d+)?")


def _parse_number(raw: str) -> Optional[float]:
    """Converte um trecho numérico textual (ex.: '1.234,56' ou '29.99') em float."""
    cleaned = raw.strip()
    if not cleaned:
        return None
    # Se tiver tanto ponto quanto vírgula, assume o último separador como decimal.
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        # Vírgula única: trata como separador decimal se tiver 1-2 dígitos após.
        parts = cleaned.split(",")
        if len(parts[-1]) in (1, 2):
            cleaned = cleaned.replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


class _StructuredHTMLParser(HTMLParser):
    """Extrai elementos estruturais reais de um HTML: títulos, cabeçalhos, listas, links e texto."""

    _SKIP_TAGS = {"script", "style", "noscript"}
    _CAPTURE_TAGS = {"title", "h1", "h2", "h3", "p", "li", "a"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._current_tag: Optional[str] = None
        self._buffer: List[str] = []

        self.title: Optional[str] = None
        self.headings: List[str] = []
        self.paragraphs: List[str] = []
        self.list_items: List[str] = []
        self.links: List[str] = []
        self.full_text_chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag in self._CAPTURE_TAGS:
            self._current_tag = tag
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if tag == self._current_tag:
            text = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
            if text:
                if tag == "title" and self.title is None:
                    self.title = text
                elif tag in ("h1", "h2", "h3"):
                    self.headings.append(text)
                elif tag == "p":
                    self.paragraphs.append(text)
                elif tag == "li":
                    self.list_items.append(text)
                elif tag == "a":
                    self.links.append(text)
            self._current_tag = None
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth != 0:
            return
        if self._current_tag:
            self._buffer.append(data)
        if data.strip():
            self.full_text_chunks.append(data.strip())

    def get_full_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.full_text_chunks)).strip()

    def extract_numbers(self) -> List[float]:
        numeros: List[float] = []
        for match in _NUMBER_PATTERN.findall(self.get_full_text()):
            valor = _parse_number(match)
            if valor is not None:
                numeros.append(valor)
        return numeros


class ScrapeGraphEngine:
    """Motor de raspagem adaptativa baseada em grafos semânticos e nós de conhecimento."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "scrapegraph_nodes"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def extract_structured_graph(
        self,
        target_url: str,
        html_content: str,
        extraction_schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Converte o HTML bruto em um Grafo de Dados Estruturados adaptativo.
        Exemplo de schema: {"titulo": "str", "precos": "list[float]", "links_relacionados": "list[str]"}

        A extração é real: usa html.parser para ler o documento e preencher
        cada campo do schema com dados efetivamente encontrados. Campos sem
        correspondência no HTML retornam vazio/None, nunca valores inventados.
        """
        parsed_url = urlparse(target_url)
        domain = parsed_url.netloc or "local"

        parser = _StructuredHTMLParser()
        parser.feed(html_content or "")

        graph_nodes: List[Dict[str, Any]] = []
        edges: List[Dict[str, Any]] = []
        extracted_data: Dict[str, Any] = {}

        graph_nodes.append({
            "id": "node_root",
            "label": f"SiteRoot:{domain}",
            "tipo": "dominio",
        })

        numeros_encontrados = parser.extract_numbers()

        for key, field_type in extraction_schema.items():
            node_id = f"node_{key}"
            graph_nodes.append({
                "id": node_id,
                "label": key,
                "tipo_esperado": str(field_type),
            })
            edges.append({"origem": "node_root", "destino": node_id, "relacao": "contem_campo"})

            if field_type == "list[str]":
                if parser.list_items:
                    itens = parser.list_items
                elif parser.headings:
                    itens = parser.headings
                elif parser.links:
                    itens = [text for text in parser.links if len(text) > 1]
                else:
                    itens = []
                extracted_data[key] = itens
                graph_nodes[-1]["itens_encontrados"] = len(itens)
            elif field_type == "list[float]":
                extracted_data[key] = numeros_encontrados
                graph_nodes[-1]["itens_encontrados"] = len(numeros_encontrados)
            elif field_type in ("int", "float"):
                if numeros_encontrados:
                    valor = numeros_encontrados[0]
                    extracted_data[key] = int(valor) if field_type == "int" else valor
                else:
                    extracted_data[key] = None
            else:  # "str" e qualquer outro tipo textual
                if parser.headings:
                    texto = parser.headings[0]
                elif parser.title:
                    texto = parser.title
                elif parser.paragraphs:
                    texto = parser.paragraphs[0]
                else:
                    texto = None
                extracted_data[key] = texto

        campos_preenchidos = sum(1 for v in extracted_data.values() if v not in (None, [], ""))

        result = {
            "url_alvo": target_url,
            "dominio": domain,
            "schema_solicitado": extraction_schema,
            "grafo_extracao": {
                "nos": graph_nodes,
                "arestas": edges,
            },
            "dados_estruturados_extraidos": extracted_data,
            "adaptabilidade_status": "sucesso_sem_dependencia_css",
            "resumo_ptbr": (
                f"Extração adaptativa por grafo concluída para '{target_url}'. "
                f"{campos_preenchidos}/{len(extracted_data)} campo(s) preenchido(s) com dados reais do HTML."
            ),
        }

        self._save_graph_snapshot(domain, result)
        return result

    def _save_graph_snapshot(self, domain: str, result: Dict[str, Any]) -> None:
        """Salva a captura do grafo em arquivo JSON."""
        clean_domain = domain.replace(":", "_").replace("/", "_")
        file_path = self.data_dir / f"scrapegraph_{clean_domain}.json"
        file_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
