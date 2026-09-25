"""
JARVIS - SIMULADOR de feed de mercado (WDO / WIN)

ATENCAO: nao existe conexao com a B3 nem com qualquer corretora. Todos os precos,
volumes e lados de agressao sao gerados aleatoriamente para testar a interface.
Nunca use estes numeros para decidir operacoes reais. Toda resposta carrega
`simulado=True` e um aviso explicito.
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
        """Conecta ao feed de dados ao vivo do ativo."""
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
        Retorna uma cotação/tick ao vivo do fluxo de ordens (Tape Reading).
        """
        if not self.is_connected:
            self.connect()

        base_price = 5.20 if self.asset == "WDO" else 128000.0
        variation = round(random.uniform(-0.02, 0.02), 2)
        current_price = round(base_price + variation, 2)
        side = random.choice(["buy", "sell"])
        volume = random.randint(10, 500)

        return {
            "simulado": True,
            "aviso": "DADOS SIMULADOS (aleatorios). Sem conexao com a B3. Nao use para operar.",
            "ativo": self.asset,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "preco_atual": current_price,
            "agressao_lado": side,
            "volume_contratos": volume,
            "book_oferta": {
                "melhor_compra": round(current_price - 0.5, 2),
                "melhor_venda": round(current_price + 0.5, 2),
            },
        }

    def disconnect(self) -> Dict[str, Any]:
        """Desconecta do feed."""
        self.is_connected = False
        return {"status": "desconectado", "ativo": self.asset}
