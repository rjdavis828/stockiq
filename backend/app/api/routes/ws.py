import asyncio
import logging

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.config import settings
from app.ws.manager import manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["realtime"])


def _validate_token(token: str) -> str | None:
    """Return user_id string if JWT is valid, else None."""
    try:
        from jose import jwt as jose_jwt

        data = jose_jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            audience="fastapi-users:auth",
        )
        return data.get("sub")
    except Exception:
        return None


async def _redis_forwarder(symbol: str, ws: WebSocket, redis_client: aioredis.Redis) -> None:
    channel = f"{settings.ws_bar_channel_prefix}:{symbol}"
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except Exception:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.aclose()


@router.websocket("/ws/bars/{symbol}")
async def ws_bars(
    symbol: str,
    websocket: WebSocket,
    token: str = Query(...),
) -> None:
    user_id = _validate_token(token)
    if user_id is None:
        await websocket.close(code=4001)
        return

    symbol = symbol.upper()
    redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)

    await manager.connect(symbol, user_id, websocket)
    forwarder = asyncio.create_task(_redis_forwarder(symbol, websocket, redis_client))

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        forwarder.cancel()
        manager.disconnect(symbol, user_id, websocket)
        await redis_client.aclose()
