"""
JARVIS - Adaptador Web legado no formato MCP-like

O modulo historico chamava isso de "Scrapling MCP stealth", mas nao executava
Scrapling, nao era um servidor MCP oficial e fabricava HTML/anti-bot.

Agora ele:
- usa o WebBrowserEngine real para buscar a pagina;
- nunca afirma bypass anti-bot;
- marca explicitamente que o envelope e legado e nao substitui o MCP oficial;
- retorna erro quando a captura real falha.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.web_browser_engine import WebBrowserEngine


class ScraplingMCPEngine:
    """Compatibilidade temporaria para clientes antigos do endpoint web."""

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        web_browser_engine: Optional[WebBrowserEngine] = None,
    ) -> None:
        self.data_dir = (
            Path(data_dir)
            if data_dir
            else Path(__file__).resolve().parents[1] / "data" / "scrapling_mcp"
        )
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.web_browser_engine = web_browser_engine or WebBrowserEngine()

    def scrape_stealth_mcp(
        self,
        target_url: str,
        mcp_tool_name: str = "web_fetch_page",
        stealth_level: str = "disabled",
    ) -> Dict[str, Any]:
        """Busca uma pagina real e devolve envelope legado auditavel."""

        now = datetime.now(timezone.utc).isoformat()
        fetched = self.web_browser_engine.fetch_page_content(target_url)
        success = fetched.get("status") == "sucesso"

        text = fetched.get("conteudo_texto_limpo") if success else None
        content = []
        if success and text:
            content.append(
                {
                    "type": "text",
                    "text": text,
                }
            )

        response = {
            "mcp_protocol_version": None,
            "mcp_compatibility": "legacy_envelope_not_official_mcp_server",
            "tool_call": mcp_tool_name,
            "timestamp": now,
            "request_metadata": {
                "target_url": target_url,
                "stealth_level_requested": stealth_level,
                "stealth_supported": False,
                "anti_bot_bypass": False,
            },
            "fetch": {
                "status": fetched.get("status"),
                "metodo": fetched.get("metodo"),
                "url_final": fetched.get("url"),
                "titulo": fetched.get("titulo"),
                "tamanho_texto_chars": fetched.get("tamanho_texto_chars"),
                "motivo": fetched.get("motivo"),
            },
            "content": content,
            "is_error": not success,
            "fabricated_content": False,
        }

        self._save_mcp_record(mcp_tool_name, response)
        return response

    def _save_mcp_record(self, tool_name: str, response: Dict[str, Any]) -> None:
        file_path = self.data_dir / (
            f"web_legacy_{tool_name}_{int(datetime.now(timezone.utc).timestamp())}.json"
        )
        file_path.write_text(
            json.dumps(response, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
