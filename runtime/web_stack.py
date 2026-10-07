"""
JARVIS - Stack Web Modular

Backends locais/open-source:
- SearXNG: descoberta/metabusca via API JSON
- Crawl4AI: crawling e Markdown limpo, com extracao estruturada opcional
- Playwright: renderizacao deterministica de paginas JavaScript
- HTTP stdlib: fallback real e leve para paginas simples

Nenhum backend fabrica resultados quando rede, servico ou dependencia falham.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html.parser import HTMLParser
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import socket
import threading
from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import urlencode, urljoin, urlparse
import urllib.error
import urllib.request


_ALLOWED_SCHEMES = {"http", "https"}
_MAX_HTTP_BYTES_DEFAULT = 5 * 1024 * 1024


def _env_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "sim", "on"}


@dataclass(frozen=True)
class WebStackConfig:
    enabled: bool = False

    searxng_url: Optional[str] = None
    searxng_language: str = "pt-BR"
    searxng_safesearch: int = 1
    search_timeout_seconds: float = 10.0

    crawl4ai_enabled: bool = False
    crawl4ai_browser: str = "chromium"
    crawl4ai_headless: bool = True
    crawl_timeout_ms: int = 20000

    playwright_enabled: bool = False
    playwright_browser: str = "chromium"
    playwright_headless: bool = True
    playwright_timeout_ms: int = 20000

    simple_http_enabled: bool = True
    allow_private_targets: bool = False
    max_http_bytes: int = _MAX_HTTP_BYTES_DEFAULT
    max_content_chars: int = 100000
    user_agent: str = "JarvisResearchEngine/2.0"

    @classmethod
    def from_env(cls, environ: Optional[Mapping[str, str]] = None) -> "WebStackConfig":
        env = dict(environ or os.environ)
        searxng = (env.get("JARVIS_SEARXNG_URL") or "").strip() or None
        return cls(
            enabled=_env_bool(env.get("JARVIS_WEB_ADVANCED_ENABLED"), False),
            searxng_url=searxng,
            searxng_language=(env.get("JARVIS_SEARXNG_LANGUAGE") or "pt-BR").strip(),
            searxng_safesearch=max(0, min(2, int(env.get("JARVIS_SEARXNG_SAFESEARCH", "1")))),
            search_timeout_seconds=max(1.0, float(env.get("JARVIS_WEB_SEARCH_TIMEOUT_SECONDS", "10"))),
            crawl4ai_enabled=_env_bool(env.get("JARVIS_CRAWL4AI_ENABLED"), False),
            crawl4ai_browser=(env.get("JARVIS_CRAWL4AI_BROWSER") or "chromium").strip(),
            crawl4ai_headless=_env_bool(env.get("JARVIS_CRAWL4AI_HEADLESS"), True),
            crawl_timeout_ms=max(1000, int(env.get("JARVIS_CRAWL4AI_TIMEOUT_MS", "20000"))),
            playwright_enabled=_env_bool(env.get("JARVIS_PLAYWRIGHT_ENABLED"), False),
            playwright_browser=(env.get("JARVIS_PLAYWRIGHT_BROWSER") or "chromium").strip(),
            playwright_headless=_env_bool(env.get("JARVIS_PLAYWRIGHT_HEADLESS"), True),
            playwright_timeout_ms=max(1000, int(env.get("JARVIS_PLAYWRIGHT_TIMEOUT_MS", "20000"))),
            simple_http_enabled=_env_bool(env.get("JARVIS_SIMPLE_HTTP_ENABLED"), True),
            allow_private_targets=_env_bool(env.get("JARVIS_WEB_ALLOW_PRIVATE_TARGETS"), False),
            max_http_bytes=max(64 * 1024, int(env.get("JARVIS_WEB_MAX_HTTP_BYTES", str(_MAX_HTTP_BYTES_DEFAULT)))),
            max_content_chars=max(2000, int(env.get("JARVIS_WEB_MAX_CONTENT_CHARS", "100000"))),
            user_agent=(env.get("JARVIS_WEB_USER_AGENT") or "JarvisResearchEngine/2.0").strip(),
        )


def _is_disallowed_ip(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_fetchable_url(
    url: str,
    *,
    allow_private_targets: bool = False,
    resolve_dns: bool = True,
) -> Optional[str]:
    """Bloqueia esquemas nao-web, credenciais e destinos locais/privados."""

    try:
        parsed = urlparse(str(url).strip())
    except ValueError:
        return "Endereco invalido."

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return "Apenas URLs HTTP/HTTPS podem ser buscadas."
    if not parsed.hostname:
        return "Endereco sem host definido."
    if parsed.username is not None or parsed.password is not None:
        return "URLs contendo credenciais embutidas sao recusadas."

    hostname = parsed.hostname.strip().lower()
    if hostname in {"localhost", "localhost.localdomain"} and not allow_private_targets:
        return "Destino local recusado."

    try:
        literal = ipaddress.ip_address(hostname.strip("[]"))
        if _is_disallowed_ip(str(literal)) and not allow_private_targets:
            return "Destino IP privado/local/reservado recusado."
        return None
    except ValueError:
        pass

    if not resolve_dns or allow_private_targets:
        return None

    try:
        infos = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as exc:
        return f"DNS indisponivel para o host: {exc}"

    addresses = {info[4][0] for info in infos if info and info[4]}
    if not addresses:
        return "Host nao resolveu para nenhum endereco."
    for address in addresses:
        try:
            if _is_disallowed_ip(address):
                return "Host resolveu para endereco privado/local/reservado."
        except ValueError:
            return "Host resolveu para endereco invalido."
    return None


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip = 0
        self.parts: List[str] = []
        self.title_parts: List[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if lowered == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1
        if lowered == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        clean = " ".join(data.split())
        if not clean:
            return
        self.parts.append(clean)
        if self._in_title:
            self.title_parts.append(clean)


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    def __init__(self, allow_private_targets: bool) -> None:
        super().__init__()
        self.allow_private_targets = allow_private_targets

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        reason = validate_fetchable_url(
            newurl,
            allow_private_targets=self.allow_private_targets,
            resolve_dns=True,
        )
        if reason:
            raise urllib.error.URLError(f"Redirect recusado: {reason}")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class SearXNGSearchBackend:
    def __init__(self, config: WebStackConfig) -> None:
        self.config = config

    @property
    def available(self) -> bool:
        return bool(self.config.enabled and self.config.searxng_url)

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        category: Optional[str] = None,
        time_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.available:
            return {
                "status": "indisponivel",
                "resultados": [],
                "motivo": "SearXNG nao esta configurado.",
            }

        base = str(self.config.searxng_url).rstrip("/")
        endpoint = base if base.endswith("/search") else f"{base}/search"
        params: Dict[str, Any] = {
            "q": query,
            "format": "json",
            "language": self.config.searxng_language,
            "safesearch": self.config.searxng_safesearch,
        }
        if category:
            params["categories"] = category
        if time_range in {"day", "week", "month", "year"}:
            params["time_range"] = time_range

        request = urllib.request.Request(
            f"{endpoint}?{urlencode(params)}",
            headers={"User-Agent": self.config.user_agent, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.search_timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:
            return {
                "status": "erro",
                "resultados": [],
                "motivo": f"Falha real no SearXNG: {exc.__class__.__name__}: {exc}",
            }

        results: List[Dict[str, Any]] = []
        for raw in list(payload.get("results") or [])[: max(1, int(max_results))]:
            url = str(raw.get("url") or "").strip()
            if not url:
                continue
            engines = raw.get("engines") or raw.get("engine") or []
            if isinstance(engines, str):
                engines = [engines]
            results.append(
                {
                    "posicao": len(results) + 1,
                    "titulo": str(raw.get("title") or "").strip() or None,
                    "url": url,
                    "resumo_snippet": str(raw.get("content") or "").strip() or None,
                    "engines": list(engines),
                    "score": raw.get("score"),
                    "publicado_em": raw.get("publishedDate") or raw.get("published_date"),
                    "categoria": raw.get("category"),
                }
            )

        return {
            "status": "sucesso",
            "query": query,
            "resultados": results,
            "quantidade": len(results),
            "backend": "searxng",
        }


class SimpleHTTPExtractor:
    def __init__(self, config: WebStackConfig) -> None:
        self.config = config

    @property
    def available(self) -> bool:
        return self.config.simple_http_enabled

    def fetch(self, url: str) -> Dict[str, Any]:
        if not self.available:
            return {"status": "indisponivel", "url": url, "motivo": "HTTP leve desativado."}

        reason = validate_fetchable_url(
            url,
            allow_private_targets=self.config.allow_private_targets,
            resolve_dns=True,
        )
        if reason:
            return {"status": "bloqueado", "url": url, "motivo": reason}

        opener = urllib.request.build_opener(_SafeRedirectHandler(self.config.allow_private_targets))
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.config.user_agent,
                "Accept": "text/html,text/plain,application/xhtml+xml,application/json;q=0.9,*/*;q=0.1",
            },
        )
        try:
            with opener.open(request, timeout=self.config.search_timeout_seconds) as response:
                final_url = response.geturl()
                content_type = str(response.headers.get("Content-Type") or "").lower()
                raw = response.read(self.config.max_http_bytes + 1)
                if len(raw) > self.config.max_http_bytes:
                    return {
                        "status": "erro",
                        "url": url,
                        "motivo": "Resposta excede o limite de bytes configurado.",
                    }

                if not any(
                    token in content_type
                    for token in ("text/", "application/json", "application/xhtml+xml", "application/xml")
                ):
                    return {
                        "status": "indisponivel",
                        "url": final_url,
                        "motivo": f"Content-Type nao textual: {content_type or 'desconhecido'}.",
                    }

                charset = response.headers.get_content_charset() or "utf-8"
                decoded = raw.decode(charset, errors="replace")

            if "html" in content_type or "<html" in decoded[:1000].lower():
                parser = _VisibleTextParser()
                parser.feed(decoded)
                text_content = " ".join(parser.parts)
                title = " ".join(parser.title_parts).strip() or None
            else:
                text_content = " ".join(decoded.split())
                title = None

            return {
                "status": "sucesso",
                "url": final_url,
                "titulo": title,
                "conteudo_texto_limpo": text_content[: self.config.max_content_chars],
                "tamanho_texto_chars": min(len(text_content), self.config.max_content_chars),
                "truncado": len(text_content) > self.config.max_content_chars,
                "metodo": "http_stdlib",
                "content_type": content_type or None,
            }
        except Exception as exc:
            return {
                "status": "erro",
                "url": url,
                "motivo": f"Falha real no HTTP: {exc.__class__.__name__}: {exc}",
            }


def _run_coroutine_sync(coro: Any) -> Any:
    """Executa coroutine a partir de codigo sync, inclusive se ja houver loop ativo."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result: Dict[str, Any] = {}
    error: Dict[str, BaseException] = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except BaseException as exc:
            error["value"] = exc

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join()
    if error:
        raise error["value"]
    return result.get("value")


class Crawl4AIBackend:
    def __init__(self, config: WebStackConfig) -> None:
        self.config = config

    @property
    def package_available(self) -> bool:
        return importlib.util.find_spec("crawl4ai") is not None

    @property
    def available(self) -> bool:
        return bool(self.config.enabled and self.config.crawl4ai_enabled and self.package_available)

    async def _crawl_async(self, url: str) -> Dict[str, Any]:
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CacheMode, CrawlerRunConfig

        browser_config = BrowserConfig(
            browser_type=self.config.crawl4ai_browser,
            headless=self.config.crawl4ai_headless,
            verbose=False,
        )
        run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            page_timeout=self.config.crawl_timeout_ms,
            excluded_tags=["script", "style", "noscript"],
            remove_forms=True,
        )
        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=run_config)

        if not getattr(result, "success", False):
            return {
                "status": "erro",
                "url": url,
                "motivo": str(getattr(result, "error_message", None) or "Crawl4AI nao concluiu o crawl."),
            }

        markdown_obj = getattr(result, "markdown", None)
        markdown = None
        fit_markdown = None
        if markdown_obj is not None:
            markdown = getattr(markdown_obj, "raw_markdown", None)
            fit_markdown = getattr(markdown_obj, "fit_markdown", None)
            if markdown is None and isinstance(markdown_obj, str):
                markdown = markdown_obj

        metadata = getattr(result, "metadata", None)
        if not isinstance(metadata, dict):
            metadata = {}

        primary = str(fit_markdown or markdown or "").strip()
        return {
            "status": "sucesso",
            "url": str(getattr(result, "url", None) or url),
            "titulo": metadata.get("title"),
            "markdown": str(markdown or "").strip()[: self.config.max_content_chars] or None,
            "conteudo_texto_limpo": primary[: self.config.max_content_chars],
            "tamanho_texto_chars": min(len(primary), self.config.max_content_chars),
            "truncado": len(primary) > self.config.max_content_chars,
            "metodo": "crawl4ai",
            "links": getattr(result, "links", None),
            "metadata": metadata,
        }

    def fetch(self, url: str) -> Dict[str, Any]:
        if not self.available:
            return {
                "status": "indisponivel",
                "url": url,
                "motivo": "Crawl4AI nao esta instalado/ativado.",
            }
        reason = validate_fetchable_url(
            url,
            allow_private_targets=self.config.allow_private_targets,
            resolve_dns=True,
        )
        if reason:
            return {"status": "bloqueado", "url": url, "motivo": reason}
        try:
            return _run_coroutine_sync(self._crawl_async(url))
        except Exception as exc:
            return {
                "status": "erro",
                "url": url,
                "motivo": f"Falha real no Crawl4AI: {exc.__class__.__name__}: {exc}",
            }

    async def _extract_raw_html_async(self, html: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        from crawl4ai import AsyncWebCrawler, CacheMode, CrawlerRunConfig, JsonCssExtractionStrategy

        strategy = JsonCssExtractionStrategy(schema)
        config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            extraction_strategy=strategy,
        )
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(url="raw://" + html, config=config)

        if not getattr(result, "success", False):
            return {
                "status": "erro",
                "dados": None,
                "motivo": str(getattr(result, "error_message", None) or "Extracao Crawl4AI falhou."),
            }
        content = getattr(result, "extracted_content", None)
        try:
            data = json.loads(content) if isinstance(content, str) else content
        except Exception:
            data = content
        return {
            "status": "sucesso",
            "dados": data,
            "metodo": "crawl4ai_json_css",
        }

    def extract_raw_html(self, html: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        if not self.available:
            return {
                "status": "indisponivel",
                "dados": None,
                "motivo": "Crawl4AI nao esta instalado/ativado.",
            }
        if not isinstance(schema, dict) or not schema.get("baseSelector") or not isinstance(schema.get("fields"), list):
            return {
                "status": "erro",
                "dados": None,
                "motivo": "Schema Crawl4AI invalido: baseSelector e fields sao obrigatorios.",
            }
        try:
            return _run_coroutine_sync(self._extract_raw_html_async(html, schema))
        except Exception as exc:
            return {
                "status": "erro",
                "dados": None,
                "motivo": f"Falha real na extracao estruturada: {exc.__class__.__name__}: {exc}",
            }


class PlaywrightBackend:
    def __init__(self, config: WebStackConfig) -> None:
        self.config = config

    @property
    def package_available(self) -> bool:
        return importlib.util.find_spec("playwright") is not None

    @property
    def available(self) -> bool:
        return bool(self.config.enabled and self.config.playwright_enabled and self.package_available)

    def render(self, url: str) -> Dict[str, Any]:
        if not self.available:
            return {
                "status": "indisponivel",
                "url": url,
                "motivo": "Playwright nao esta instalado/ativado.",
            }
        reason = validate_fetchable_url(
            url,
            allow_private_targets=self.config.allow_private_targets,
            resolve_dns=True,
        )
        if reason:
            return {"status": "bloqueado", "url": url, "motivo": reason}

        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as runtime:
                browser_type = getattr(runtime, self.config.playwright_browser, None)
                if browser_type is None:
                    return {
                        "status": "erro",
                        "url": url,
                        "motivo": f"Browser Playwright desconhecido: {self.config.playwright_browser}.",
                    }
                browser = browser_type.launch(headless=self.config.playwright_headless)
                try:
                    page = browser.new_page()
                    page.goto(
                        url,
                        wait_until="domcontentloaded",
                        timeout=self.config.playwright_timeout_ms,
                    )
                    text_content = page.locator("body").inner_text(timeout=self.config.playwright_timeout_ms)
                    final_url = page.url
                    title = page.title()
                finally:
                    browser.close()

            text_content = " ".join(str(text_content).split())
            return {
                "status": "sucesso",
                "url": final_url,
                "titulo": title or None,
                "conteudo_texto_limpo": text_content[: self.config.max_content_chars],
                "tamanho_texto_chars": min(len(text_content), self.config.max_content_chars),
                "truncado": len(text_content) > self.config.max_content_chars,
                "metodo": "playwright",
            }
        except Exception as exc:
            return {
                "status": "erro",
                "url": url,
                "motivo": f"Falha real no Playwright: {exc.__class__.__name__}: {exc}",
            }


class WebStack:
    def __init__(self, config: Optional[WebStackConfig] = None) -> None:
        self.config = config or WebStackConfig.from_env()
        self.search = SearXNGSearchBackend(self.config)
        self.crawl = Crawl4AIBackend(self.config)
        self.playwright = PlaywrightBackend(self.config)
        self.simple_http = SimpleHTTPExtractor(self.config)

    def search_web(
        self,
        query: str,
        *,
        max_results: int = 5,
        category: Optional[str] = None,
        time_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        return self.search.search(
            query,
            max_results=max_results,
            category=category,
            time_range=time_range,
        )

    def fetch_page(self, url: str) -> Dict[str, Any]:
        if self.crawl.available:
            result = self.crawl.fetch(url)
            if result.get("status") == "sucesso":
                return result
        if self.playwright.available:
            result = self.playwright.render(url)
            if result.get("status") == "sucesso":
                return result
        return self.simple_http.fetch(url)

    def render_page(self, url: str) -> Dict[str, Any]:
        return self.playwright.render(url)

    def extract_structured_html(self, html: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        return self.crawl.extract_raw_html(html, schema)

    def status(self) -> Dict[str, Any]:
        return {
            "enabled": self.config.enabled,
            "search": {
                "backend": "searxng",
                "available": self.search.available,
                "endpoint_configured": bool(self.config.searxng_url),
            },
            "crawl": {
                "backend": "crawl4ai",
                "package_available": self.crawl.package_available,
                "available": self.crawl.available,
            },
            "browser": {
                "backend": "playwright",
                "package_available": self.playwright.package_available,
                "available": self.playwright.available,
            },
            "simple_http": {
                "available": self.simple_http.available,
            },
            "allow_private_targets": self.config.allow_private_targets,
            "fake_results": False,
        }
