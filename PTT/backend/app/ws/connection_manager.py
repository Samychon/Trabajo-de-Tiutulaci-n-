import asyncio
import json

from fastapi import WebSocket


class ConnectionManager:
    """Gestor en memoria para una sola instancia; en produccion con varias replicas, sustituir por Redis pub/sub."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, websocket: WebSocket) -> None:
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, message: dict) -> None:
        payload = json.dumps(message)
        for connection in list(self._connections):
            await connection.send_text(payload)

    def broadcast_sync(self, message: dict) -> None:
        """Permite emitir alertas desde codigo sincrono (endpoints REST) hacia los clientes WebSocket."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(message), self._loop)


alert_manager = ConnectionManager()
