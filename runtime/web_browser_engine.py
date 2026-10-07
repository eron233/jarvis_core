"""
JARVIS - Motor de Pesquisa e Navegacao Web

Facade de alto nivel sobre o stack web real:
- SearXNG para descoberta/metabusca
- Crawl4AI para crawling/Markdown quando disponivel
- Playwright para paginas JavaScript quando necessario
- HTTP stdlib como fallback leve e real

Nenhum caminho fabrica fontes, snippets ou conteudo.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from runtime.web_stack import WebStack, WebStackConfig, validate_fetchable_url


class WebBrowserEngine:
    """Pesquisa, recupera e renderiza paginas com backends substituiveis."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        config: Optional[WebStackConfig] = None,
        web_stack: Optional[WebStack] = None,
    ) -> None:
        if config is None:
            config = WebStackConfig.from_env()
        if user_agent:
            config = WebStackConfig(
                **{
                    **config.__dict__,
                    "user_agent": user_agent,
                }
            )
        self.web_stack = web_stack or WebStack(config=config)

    def search_and_extract(
        self,
        query: str,
        max_results: int = 3,
        *,
        category: Optional[str] = None,
        time_range: Optional[str] = None,
        extract_pages: bool = True,
        max_pages_to_extract: int = 2,
    ) -> Dict[str, Any]:
        """Pesquisa via SearXNG e opcionalmente extrai paginas reais."""

        now = datetime.now(timezone.utc).isoformat()
        clean_query = str(query).strip()
        if not clean_query:
            return {
                "status": "erro",
                "pesquisa": query,
                "realizada_em": now,
                "total_fontes_encontradas": 0,
                "fontes": [],
                "motivo": "A consulta nao pode ser vazia.",
            }

        search = self.web_stack.search_web(
            clean_query,
            max_results=max_results,
            category=category,
            time_range=time_range,
        )
        if search.get("status") != "sucesso":
            return {
                "status": search.get("status", "indisponivel"),
                "pesquisa": clean_query,
                "realizada_em": now,
                "total_fontes_encontradas": 0,
                "fontes": [],
                "backend_busca": "searxng",
                "motivo": search.get("motivo"),
            }

        sources = []
        extract_budget = max(0, int(max_pages_to_extract))
        for raw in search.get("resultados", []):
            source = dict(raw)
            source["extracao"] = None

            if extract_pages and extract_budget > 0:
                validation = validate_fetchable_url(
                    source.get("url", ""),
                    allow_private_targets=self.web_stack.config.allow_private_targets,
                    resolve_dns=True,
                )
                if validation:
                    source["extracao"] = {
                        "status": "bloqueado",
                        "motivo": validation,
                    }
                else:
                    page = self.web_stack.fetch_page(source["url"])
                    source["extracao"] = {
                        "status": page.get("status"),
                        "metodo": page.get("metodo"),
                        "titulo": page.get("titulo"),
                        "conteudo_texto_limpo": page.get("conteudo_texto_limpo"),
                        "tamanho_texto_chars": page.get("tamanho_texto_chars"),
                        "truncado": page.get("truncado"),
                        "motivo": page.get("motivo"),
                    }
                extract_budget -= 1

            sources.append(source)

        return {
            "status": "sucesso",
            "pesquisa": clean_query,
            "realizada_em": now,
            "total_fontes_encontradas": len(sources),
            "fontes": sources,
            "backend_busca": search.get("backend"),
            "extracao_paginas_habilitada": bool(extract_pages),
        }

    def fetch_page_content(self, url: str) -> Dict[str, Any]:
        """Recupera conteudo textual real de uma pagina."""

        now = datetime.now(timezone.utc).isoformat()
        result = self.web_stack.fetch_page(url)
        return {
            **result,
            "baixado_em": now if result.get("status") == "sucesso" else None,
            "avaliado_em": now,
        }

    def render_dynamic_page(self, url: str) -> Dict[str, Any]:
        """Forca renderizacao Playwright para paginas JS."""

        now = datetime.now(timezone.utc).isoformat()
        result = self.web_stack.render_page(url)
        return {**result, "avaliado_em": now}

    def describe_capabilities(self) -> Dict[str, Any]:
        return self.web_stack.status()
