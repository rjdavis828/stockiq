import asyncio
import json
from collections import defaultdict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._symbol_conns: dict[str, set[WebSocket]] = defaultdict(set)
        self._user_conns: dict[str, set[WebSocket]] = defaultdict(set)

    async def connect(self, symbol: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        self._symbol_conns[symbol].add(ws)
        self._user_conns[user_id].add(ws)

    def disconnect(self, symbol: str, user_id: str, ws: WebSocket) -> None:
        self._symbol_conns[symbol].discard(ws)
        self._user_conns[user_id].discard(ws)

    async def broadcast(self, symbol: str, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._symbol_conns.get(symbol, [])):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._symbol_conns[symbol].discard(ws)

    async def broadcast_user(self, user_id: str, payload: dict) -> None:
        dead: list[WebSocket] = []
        for ws in list(self._user_conns.get(user_id, [])):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(ws)
        for ws in dead:
            self._user_conns[user_id].discard(ws)


manager = ConnectionManager()
