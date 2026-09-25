"""
JARVIS - Feed de Transmissão WebSocket em Tempo Real (WebSocket Live Streaming Feed)

Responsável por:
- permitir conexão bidirecional via WebSocket para transmissão ao vivo de eventos do sistema
- transmitir logs do ThoughtStream (monólogo privado do dono), status de sub-agentes corporativos e métricas de hardware
- eliminar a necessidade de polling HTTP e acelerar a experiência do usuário na Dashboard
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Set

from fastapi import WebSocket, WebSocketDisconnect

LOGGER = logging.getLogger("jarvis.interface.websocket")


class ConnectionManager:
    """Gerenciador central de conexões ativas de WebSocket para transmissão em tempo real."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Aceita a conexão WebSocket e armazena na lista de conexões ativas."""
        await websocket.accept()
        self.active_connections.add(websocket)
        LOGGER.info("[websocket] Nova conexão estabelecida. Total ativas: %d", len(self.active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a conexão WebSocket desconectada."""
        self.active_connections.discard(websocket)
        LOGGER.info("[websocket] Conexão encerrada. Total ativas: %d", len(self.active_connections))

    async def broadcast_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        """
        Transmite uma mensagem estruturada para todos os clientes conectados simultaneamente.
        """
        if not self.active_connections:
            return

        message = json.dumps({
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": payload,
        }, ensure_ascii=False)

        disconnected_clients = set()
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                LOGGER.warning("[websocket_broadcast_error] Falha ao enviar para cliente: %s", e)
                disconnected_clients.add(connection)

        for dead_client in disconnected_clients:
            self.disconnect(dead_client)


# Instância global do gerenciador de WebSocket
ws_manager = ConnectionManager()
