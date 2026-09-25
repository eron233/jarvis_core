"""
JARVIS - Feed de Dados de Mercado em Tempo Real (WDO / WIN)

Responsável por:
- simular ou conectar feed contínuo de dados de mercado (WebSocket/Stream)
- receber cotações de preços, ofertas do livro e saldo de agressão ao vivo
- enviar alertas para o analisador de mercado quando houver picos de volatilidade
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import random
from typing import Any, Dict, List, Optional


class MarketWebSocketFeed:
    """Simulador e conector de feed em tempo real de dados de mercado."""

    def __init__(self, asset: str = "WDO") -> None:
        self.asset = asset.upper()
        self.is_connected = False

    def connect(self) -> Dict[str, Any]:
        """
        'Conecta' ao feed de dados do ativo.

        IMPORTANTE: este módulo NÃO possui nenhuma conexão real com a B3 ou
        qualquer provedor de dados de mercado. Trata-se de um simulador local
        que gera cotações pseudoaleatórias. O campo "simulado": True e o nome
        do feed deixam isso explícito para quem consumir o retorno.
        """
        self.is_connected = True
        return {
            "status": "conectado",
            "ativo": self.asset,
            "feed": "simulador_local",
            "simulado": True,
            "conectado_em": datetime.now(timezone.utc).isoformat(),
        }

    def fetch_live_tick(self) -> Dict[str, Any]:
        """
        Retorna uma cotação/tick simulada do fluxo de ordens (Tape Reading).

        Os valores são gerados por um gerador pseudoaleatório local, NÃO por
        um feed real de mercado. Cada tick carrega "simulado": True e
        "fonte": "gerador_pseudoaleatorio_local" para deixar isso explícito.
        """
        if not self.is_connected:
            self.connect()

        base_price = 5.20 if self.asset == "WDO" else 128000.0
        variation = round(random.uniform(-0.02, 0.02), 2)
        current_price = round(base_price + variation, 2)
        side = random.choice(["buy", "sell"])
        volume = random.randint(10, 500)

        return {
            "ativo": self.asset,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "preco_atual": current_price,
            "agressao_lado": side,
            "volume_contratos": volume,
            "book_oferta": {
                "melhor_compra": round(current_price - 0.5, 2),
                "melhor_venda": round(current_price + 0.5, 2),
            },
            "simulado": True,
            "fonte": "gerador_pseudoaleatorio_local",
        }

    def disconnect(self) -> Dict[str, Any]:
        """Desconecta do feed."""
        self.is_connected = False
        return {"status": "desconectado", "ativo": self.asset}
