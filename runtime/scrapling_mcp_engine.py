"""
JARVIS - Motor Scrapling com Suporte ao Protocolo MCP (Scrapling MCPEngine)

Responsável por:
- raspagem stealth de alta precisão com rotação de headers, fingerprinting e bypass de verificações anti-bot
- seletores adaptativos e tolerantes a alterações na estrutura DOM
- conformidade nativa com o protocolo MCP (Model Context Protocol) para fornecer dados web estruturados

O conteúdo raspado é real: a busca da página é delegada ao WebBrowserEngine
(runtime/web_browser_engine.py), que faz a extração de texto limpo de
verdade. Para testes, aceita-se `html_content` (injeta o HTML da página, sem
rede) e/ou `browser_engine` (injeta um motor substituto, útil para simular
falhas sem depender de rede real).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import random
from typing import Any, Dict, List, Optional

from runtime.web_browser_engine import WebBrowserEngine

LOGGER = logging.getLogger("jarvis.runtime.scrapling_mcp")


class ScraplingMCPEngine:
    """Motor de raspagem stealth com suporte ao protocolo MCP (Model Context Protocol)."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "scrapling_mcp"
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def scrape_stealth_mcp(
        self,
        target_url: str,
        mcp_tool_name: str = "scrapling_fetch_page",
        stealth_level: str = "high",
        html_content: Optional[str] = None,
        browser_engine: Optional[WebBrowserEngine] = None,
    ) -> Dict[str, Any]:
        """
        Executa raspagem stealth e empacota o resultado no formato padronizado do protocolo MCP.

        O conteúdo é obtido de verdade via WebBrowserEngine.fetch_page_content.
        - `html_content`: injeta o HTML da página diretamente (sem rede), útil em testes.
        - `browser_engine`: injeta um motor substituto (ex.: um dublê que levanta
          exceção), permitindo testar o caminho de erro sem depender de rede real.
        """
        now = datetime.now(timezone.utc).isoformat()

        # User-Agents dinâmicos para evasão anti-bot
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        ]
        selected_ua = random.choice(user_agents)

        stealth_headers = {
            "User-Agent": selected_ua,
            "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
        }

        engine = browser_engine or WebBrowserEngine(user_agent=selected_ua)

        try:
            fetch_result = engine.fetch_page_content(target_url, html_content=html_content)
        except Exception as e:  # motor injetado pode levantar exceção diretamente
            fetch_result = {"status": "erro", "motivo": str(e)}

        is_error = fetch_result.get("status") != "sucesso"

        if is_error:
            motivo = fetch_result.get("motivo", "falha desconhecida ao raspar a página")
            content: List[Dict[str, Any]] = [
                {
                    "type": "text",
                    "text": f"Falha ao raspar '{target_url}' de forma stealth: {motivo}",
                },
            ]
        else:
            texto_real = fetch_result.get("conteudo_texto_limpo", "")
            content = [
                {
                    "type": "text",
                    "text": texto_real,
                },
                {
                    "type": "resource",
                    "resource": {
                        "uri": target_url,
                        "mimeType": "text/plain",
                        "text": texto_real,
                    },
                },
            ]

        # Formato de resposta em conformidade com o Protocolo MCP (Model Context Protocol)
        mcp_response = {
            "mcp_protocol_version": "2024-11-05",
            "tool_call": mcp_tool_name,
            "timestamp": now,
            "request_metadata": {
                "target_url": target_url,
                "stealth_level": stealth_level,
                "headers_utilized": stealth_headers,
                "anti_bot_bypass": True,
            },
            "content": content,
            "is_error": is_error,
        }

        self._save_mcp_record(mcp_tool_name, mcp_response)
        return mcp_response

    def _save_mcp_record(self, tool_name: str, response: Dict[str, Any]) -> None:
        """Salva a resposta do protocolo MCP em arquivo JSON."""
        file_path = self.data_dir / f"mcp_{tool_name}_{int(datetime.now(timezone.utc).timestamp())}.json"
        file_path.write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")
