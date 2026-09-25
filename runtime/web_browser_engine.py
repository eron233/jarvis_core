"""
JARVIS - Motor de Pesquisa Ativa e Navegação Web

Responsável por:
- realizar pesquisas ativas na internet sobre tópicos informados
- buscar e extrair o conteúdo principal de páginas web de forma limpa
- tratar falhas de rede e timeouts de forma resiliente e HONESTA (sem inventar resultados)

Padrão de injeção para testes:
- `fetch_page_content` e `search_and_extract` aceitam um parâmetro opcional
  `html_content`. Quando fornecido, o HTML é usado diretamente (nenhuma
  requisição de rede é feita) — isso permite testar o parsing real sem
  depender de conectividade. Quando `html_content` é None, o motor baixa
  o conteúdo de verdade via urllib.
"""

from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
from typing import Any, Dict, List, Optional
import urllib.parse
import urllib.request


class _CleanTextHTMLParser(HTMLParser):
    """Extrai texto visível de um HTML, descartando script/style/noscript."""

    _SKIP_TAGS = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._chunks: List[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_startendtag(self, tag: str, attrs) -> None:  # noqa: ANN001
        # Tags auto-fechadas (ex.: <br/>) não afetam a pilha de skip.
        return

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data.strip())

    def get_text(self) -> str:
        text = " ".join(self._chunks)
        return re.sub(r"\s+", " ", text).strip()


class _DuckDuckGoResultsParser(HTMLParser):
    """Extrai título, URL e trecho (snippet) de uma página de resultados do DuckDuckGo HTML."""

    def __init__(self) -> None:
        super().__init__()
        self.results: List[Dict[str, str]] = []
        self._current: Optional[str] = None  # "titulo" | "snippet"
        self._buffer: List[str] = []
        self._pending_url: Optional[str] = None

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        classes = attrs_dict.get("class", "") or ""
        href = attrs_dict.get("href", "") or ""
        if "result__a" in classes or "result__url" in classes:
            self._current = "titulo"
            self._buffer = []
            self._pending_url = href
        elif "result__snippet" in classes:
            self._current = "snippet"
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._current:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current is None:
            return
        text = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
        if self._current == "titulo":
            self.results.append({"url": self._pending_url or "", "titulo": text, "resumo_snippet": ""})
        elif self._current == "snippet" and self.results:
            self.results[-1]["resumo_snippet"] = text
        self._current = None
        self._buffer = []


class WebBrowserEngine:
    """Motor de pesquisa, raspagem e extração limpa de conteúdo web."""

    def __init__(self, user_agent: Optional[str] = None) -> None:
        self.user_agent = user_agent or "JarvisActiveResearchEngine/1.0"

    def _download(self, url: str, timeout: int = 10) -> str:
        """Baixa o conteúdo bruto de uma URL (requisição de rede real)."""
        req = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")

    def search_and_extract(
        self,
        query: str,
        max_results: int = 3,
        html_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Realiza uma pesquisa e extrai os principais trechos dos resultados.

        Se `html_content` for fornecido, ele é usado diretamente como a página
        de resultados (útil em testes, sem tocar a rede). Caso contrário, a
        busca é feita de verdade no DuckDuckGo HTML.
        """
        now = datetime.now(timezone.utc).isoformat()
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        extracted_sources: List[Dict[str, Any]] = []
        try:
            raw_html = html_content if html_content is not None else self._download(search_url, timeout=8)

            parser = _DuckDuckGoResultsParser()
            parser.feed(raw_html)

            for i, item in enumerate(parser.results[:max_results]):
                url = item["url"]
                # Decodifica redirecionamento DuckDuckGo (uddg=...)
                if "uddg=" in url:
                    parsed_url = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                    url = parsed_url.get("uddg", [url])[0]

                extracted_sources.append({
                    "posicao": i + 1,
                    "url": url,
                    "titulo": item.get("titulo", ""),
                    "resumo_snippet": item.get("resumo_snippet") or "Sem trecho.",
                })

            return {
                "pesquisa": query,
                "realizada_em": now,
                "status": "sucesso",
                "total_fontes_encontradas": len(extracted_sources),
                "fontes": extracted_sources,
            }
        except Exception as e:
            # Falha honesta: NÃO fabricamos resultados falsos. Marcamos o
            # status como erro/offline e deixamos a lista de fontes vazia.
            return {
                "pesquisa": query,
                "realizada_em": now,
                "status": "erro",
                "offline": True,
                "motivo": str(e),
                "total_fontes_encontradas": 0,
                "fontes": [],
            }

    def fetch_page_content(self, url: str, html_content: Optional[str] = None) -> Dict[str, Any]:
        """
        Baixa uma página web e limpa as tags HTML para extrair apenas o texto relevante.

        Se `html_content` for fornecido, ele é usado diretamente (sem rede) —
        permite testar o parsing real de forma determinística.
        """
        now = datetime.now(timezone.utc).isoformat()
        try:
            raw_html = html_content if html_content is not None else self._download(url, timeout=10)

            parser = _CleanTextHTMLParser()
            parser.feed(raw_html)
            clean_text = parser.get_text()

            return {
                "status": "sucesso",
                "url": url,
                "baixado_em": now,
                "baixado_via_rede": html_content is None,
                "tamanho_texto_chars": len(clean_text),
                "conteudo_texto_limpo": clean_text[:2000],  # Primeiros 2k caracteres
            }
        except Exception as e:
            # Fallback honesto: não inventamos conteúdo. Sinalizamos o erro
            # explicitamente para quem consome este resultado.
            return {
                "status": "erro",
                "offline": True,
                "url": url,
                "motivo": str(e),
                "conteudo_texto_limpo": "",
                "tamanho_texto_chars": 0,
            }
