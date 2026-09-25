"""
JARVIS - Leitura de pagina publica empacotada no formato MCP

Responsavel por:
- baixar uma pagina publica (com guarda anti-SSRF) usando o WebBrowserEngine
- devolver o texto no formato de resultado de ferramenta do protocolo MCP

Nao faz evasao de anti-bot nem falsificacao de fingerprint: se o site bloquear,
o resultado vem com `is_error=True` e o motivo real.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, Optional

from runtime.web_browser_engine import WebBrowserEngine

LOGGER = logging.getLogger("jarvis.runtime.scrapling_mcp")


class ScraplingMCPEngine:
    """Leitor de paginas publicas com saida no formato MCP."""

    def __init__(self, data_dir: Optional[Path] = None, browser: Optional[WebBrowserEngine] = None) -> None:
        self.data_dir = Path(data_dir) if data_dir else Path(__file__).resolve().parents[1] / "data" / "scrapling_mcp"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.browser = browser or WebBrowserEngine()

    def scrape_stealth_mcp(
        self,
        target_url: str,
        mcp_tool_name: str = "fetch_page",
        stealth_level: str = "nenhum",
    ) -> Dict[str, Any]:
        """
        Baixa a pagina e empacota no formato MCP.

        `stealth_level` e aceito apenas por compatibilidade da API e e ignorado.
        """
        now = datetime.now(timezone.utc).isoformat()
        page = self.browser.fetch_page_content(target_url, max_chars=8000)
        succeeded = page.get("status") == "sucesso"

        content = [
            {
                "type": "text",
                "text": page.get("conteudo_texto_limpo", "") if succeeded else f"Falha ao ler a pagina: {page.get('motivo')}",
            }
        ]
        if succeeded:
            content.append(
                {
                    "type": "resource",
                    "resource": {
                        "uri": page.get("url_final") or target_url,
                        "mimeType": "text/plain",
                        "text": page.get("conteudo_texto_limpo", ""),
                    },
                }
            )

        mcp_response = {
            "mcp_protocol_version": "2024-11-05",
            "tool_call": mcp_tool_name,
            "timestamp": now,
            "request_metadata": {
                "target_url": target_url,
                "titulo": page.get("titulo", ""),
                "status_leitura": page.get("status"),
            },
            "content": content,
            "is_error": not succeeded,
        }

        self._save_mcp_record(mcp_tool_name, mcp_response)
        return mcp_response

    def _save_mcp_record(self, tool_name: str, response: Dict[str, Any]) -> None:
        """Salva a resposta em arquivo JSON para auditoria."""
        safe_name = re.sub(r"[^A-Za-z0-9_-]", "_", tool_name)[:40] or "ferramenta"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        file_path = self.data_dir / f"mcp_{safe_name}_{timestamp}.json"
        file_path.write_text(json.dumps(response, indent=2, ensure_ascii=False), encoding="utf-8")
