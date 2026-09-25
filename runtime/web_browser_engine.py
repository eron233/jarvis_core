"""
JARVIS - Motor de Pesquisa Ativa e Navegação Web

Responsável por:
- realizar pesquisas ativas na internet sobre tópicos informados
- buscar e extrair o conteúdo principal de páginas web de forma limpa
- tratar falhas de rede e timeouts de forma resiliente
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Dict, List, Optional
import urllib.error
import urllib.parse

from runtime.net_guard import BlockedUrlError, fetch_public_url


class WebBrowserEngine:
    """Motor de pesquisa (DuckDuckGo HTML) e extracao de texto de paginas publicas."""

    def __init__(self, user_agent: Optional[str] = None) -> None:
        self.user_agent = user_agent or "JarvisActiveResearchEngine/1.0"

    def search_and_extract(self, query: str, max_results: int = 3) -> Dict[str, Any]:
        """
        Pesquisa na web e retorna titulos/links/trechos reais.

        Sem rede, retorna `status="indisponivel"` e zero fontes, nunca resultado inventado.
        """
        now = datetime.now(timezone.utc).isoformat()
        encoded_query = urllib.parse.quote(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        extracted_sources: List[Dict[str, Any]] = []
        try:
            _, html_content = fetch_public_url(search_url, self.user_agent, timeout=8)
        except (BlockedUrlError, urllib.error.URLError, OSError, ValueError) as exc:
            return {
                "pesquisa": query,
                "realizada_em": now,
                "status": "indisponivel",
                "motivo": f"Busca web indisponivel: {exc}",
                "total_fontes_encontradas": 0,
                "fontes": [],
            }

        links = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_content, flags=re.DOTALL)
        snippets = re.findall(r'<a[^>]+class="result__snippet[^"]*"[^>]*>(.*?)</a>', html_content, flags=re.DOTALL)

        for index, (url, raw_title) in enumerate(links[:max_results]):
            if "uddg=" in url:
                parsed_url = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                url = parsed_url.get("uddg", [url])[0]
            snippet = snippets[index] if index < len(snippets) else ""
            extracted_sources.append({
                "posicao": index + 1,
                "titulo": _strip_html(raw_title),
                "url": url,
                "resumo_snippet": _strip_html(snippet) or "Sem trecho.",
            })

        return {
            "pesquisa": query,
            "realizada_em": now,
            "status": "sucesso" if extracted_sources else "sem_resultados",
            "total_fontes_encontradas": len(extracted_sources),
            "fontes": extracted_sources,
        }

    def fetch_page_content(self, url: str, max_chars: int = 2000) -> Dict[str, Any]:
        """Baixa uma pagina publica (bloqueando redes internas) e extrai o texto visivel."""

        now = datetime.now(timezone.utc).isoformat()
        try:
            final_url, raw_html = fetch_public_url(url, self.user_agent, timeout=10)
        except BlockedUrlError as exc:
            return {"status": "bloqueado", "url": url, "motivo": str(exc)}
        except (urllib.error.URLError, OSError, ValueError) as exc:
            return {"status": "erro", "url": url, "motivo": str(exc)}

        title_match = re.search(r"<title[^>]*>(.*?)</title>", raw_html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<script.*?>.*?</script>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
        clean_text = re.sub(r"<style.*?>.*?</style>", "", clean_text, flags=re.DOTALL | re.IGNORECASE)
        clean_text = _strip_html(clean_text)

        return {
            "status": "sucesso",
            "url": url,
            "url_final": final_url,
            "titulo": _strip_html(title_match.group(1)) if title_match else "",
            "baixado_em": now,
            "tamanho_texto_chars": len(clean_text),
            "conteudo_texto_limpo": clean_text[:max_chars],
        }


def _strip_html(value: str) -> str:
    import html as html_lib

    text = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", html_lib.unescape(text)).strip()
