"""Testes do ponto 5: pesquisa, crawling e navegacao web reais."""

from types import SimpleNamespace
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from runtime.web_browser_engine import WebBrowserEngine
from runtime.web_stack import (
    SearXNGSearchBackend,
    SimpleHTTPExtractor,
    WebStackConfig,
    validate_fetchable_url,
)


class _FakeResponse:
    def __init__(self, payload, url="http://127.0.0.1:8080/search"):
        self._payload = payload
        self._url = url
        self.headers = _FakeHeaders()

    def read(self, amount=-1):
        data = self._payload if isinstance(self._payload, bytes) else self._payload.encode("utf-8")
        return data if amount < 0 else data[:amount]

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeHeaders:
    def get(self, key, default=None):
        if key.lower() == "content-type":
            return "application/json; charset=utf-8"
        return default

    def get_content_charset(self):
        return "utf-8"


class _FakeWebStack:
    def __init__(self, search_status="sucesso"):
        self.config = SimpleNamespace(allow_private_targets=False)
        self.search_status = search_status
        self.fetch_calls = []

    def search_web(self, query, max_results=5, category=None, time_range=None):
        if self.search_status != "sucesso":
            return {
                "status": "indisponivel",
                "resultados": [],
                "motivo": "SearXNG offline",
            }
        return {
            "status": "sucesso",
            "backend": "searxng",
            "resultados": [
                {
                    "posicao": 1,
                    "titulo": "Fonte A",
                    "url": "https://example.com/a",
                    "resumo_snippet": "Resumo A",
                    "engines": ["engine_a"],
                },
                {
                    "posicao": 2,
                    "titulo": "Fonte B",
                    "url": "https://example.org/b",
                    "resumo_snippet": "Resumo B",
                    "engines": ["engine_b"],
                },
            ][:max_results],
        }

    def fetch_page(self, url):
        self.fetch_calls.append(url)
        return {
            "status": "sucesso",
            "url": url,
            "titulo": "Página",
            "conteudo_texto_limpo": "Conteúdo real extraído.",
            "tamanho_texto_chars": 23,
            "truncado": False,
            "metodo": "fake-real-fetcher",
        }

    def render_page(self, url):
        return self.fetch_page(url)

    def status(self):
        return {
            "enabled": True,
            "search": {"available": True},
            "crawl": {"available": True},
            "browser": {"available": True},
            "fake_results": False,
        }


class WebStackConfigTests(unittest.TestCase):
    def test_defaults_do_not_enable_remote_search_silently(self):
        config = WebStackConfig.from_env({})
        self.assertFalse(config.enabled)
        self.assertIsNone(config.searxng_url)
        self.assertTrue(config.simple_http_enabled)
        self.assertFalse(config.allow_private_targets)

    def test_private_and_credential_urls_are_blocked(self):
        self.assertIsNotNone(validate_fetchable_url("http://127.0.0.1/test"))
        self.assertIsNotNone(validate_fetchable_url("http://169.254.169.254/latest"))
        self.assertIsNotNone(validate_fetchable_url("http://user:pass@example.com/"))

    def test_searxng_backend_parses_real_json_contract(self):
        payload = json.dumps(
            {
                "results": [
                    {
                        "title": "Resultado",
                        "url": "https://example.com/article",
                        "content": "Trecho verificável",
                        "engines": ["duckduckgo", "brave"],
                        "score": 1.5,
                    }
                ]
            }
        )
        config = WebStackConfig(
            enabled=True,
            searxng_url="http://127.0.0.1:8080",
        )
        backend = SearXNGSearchBackend(config)
        with patch("urllib.request.urlopen", return_value=_FakeResponse(payload)) as mocked:
            result = backend.search("jarvis", max_results=3)

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["quantidade"], 1)
        self.assertEqual(result["resultados"][0]["url"], "https://example.com/article")
        self.assertEqual(result["resultados"][0]["engines"], ["duckduckgo", "brave"])
        requested = mocked.call_args.args[0].full_url
        self.assertIn("format=json", requested)
        self.assertIn("q=jarvis", requested)

    def test_simple_http_blocks_private_destination_before_network(self):
        extractor = SimpleHTTPExtractor(WebStackConfig(simple_http_enabled=True))
        result = extractor.fetch("http://127.0.0.1/private")
        self.assertEqual(result["status"], "bloqueado")


class WebBrowserEngineTests(unittest.TestCase):
    def test_search_uses_real_sources_and_extracts_only_budgeted_pages(self):
        stack = _FakeWebStack()
        engine = WebBrowserEngine(web_stack=stack)

        result = engine.search_and_extract(
            "tema",
            max_results=2,
            extract_pages=True,
            max_pages_to_extract=1,
        )

        self.assertEqual(result["status"], "sucesso")
        self.assertEqual(result["total_fontes_encontradas"], 2)
        self.assertEqual(len(stack.fetch_calls), 1)
        self.assertEqual(result["fontes"][0]["extracao"]["metodo"], "fake-real-fetcher")
        self.assertIsNone(result["fontes"][1]["extracao"])

    def test_search_unavailable_never_creates_local_fake_source(self):
        engine = WebBrowserEngine(web_stack=_FakeWebStack(search_status="indisponivel"))
        result = engine.search_and_extract("tema")

        self.assertEqual(result["status"], "indisponivel")
        self.assertEqual(result["fontes"], [])
        self.assertEqual(result["total_fontes_encontradas"], 0)
        self.assertNotIn("pesquisa.local", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
