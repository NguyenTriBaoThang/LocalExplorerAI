"""Process-local WebSocket rooms for itinerary collaboration."""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import defaultdict

from fastapi.encoders import jsonable_encoder
from starlette.websockets import WebSocket


log = logging.getLogger(__name__)


class ItineraryCollaborationHub:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._loops: dict[str, asyncio.AbstractEventLoop] = {}
        self._lock = threading.RLock()

    async def connect(
        self,
        room_id: str,
        websocket: WebSocket,
        *,
        announce_presence: bool = True,
        accepted: bool = False,
    ) -> None:
        if not accepted:
            await websocket.accept()
        loop = asyncio.get_running_loop()
        with self._lock:
            self._rooms[room_id].add(websocket)
            self._loops[room_id] = loop
        if announce_presence:
            await self.broadcast_presence(room_id)

    async def broadcast_presence(self, room_id: str) -> None:
        with self._lock:
            count = len(self._rooms.get(room_id, ()))
        await self.broadcast(room_id, {"type": "presence", "count": count})

    async def disconnect(self, room_id: str, websocket: WebSocket) -> None:
        with self._lock:
            room = self._rooms.get(room_id)
            if room is None:
                return
            room.discard(websocket)
            count = len(room)
            if not room:
                self._rooms.pop(room_id, None)
                self._loops.pop(room_id, None)
        if count:
            await self.broadcast(room_id, {"type": "presence", "count": count})

    async def broadcast(self, room_id: str, event: dict) -> None:
        with self._lock:
            sockets = tuple(self._rooms.get(room_id, ()))
        if not sockets:
            return
        payload = jsonable_encoder(event)
        disconnected: list[WebSocket] = []
        for websocket in sockets:
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            await self.disconnect(room_id, websocket)

    async def close_room(self, room_id: str, code: int, *, event: dict | None = None) -> None:
        with self._lock:
            sockets = tuple(self._rooms.pop(room_id, ()))
            self._loops.pop(room_id, None)
        if event is not None:
            payload = jsonable_encoder(event)
            await asyncio.gather(
                *(websocket.send_json(payload) for websocket in sockets),
                return_exceptions=True,
            )
        await asyncio.gather(
            *(websocket.close(code=code) for websocket in sockets),
            return_exceptions=True,
        )

    def broadcast_from_sync(self, room_id: str, event: dict) -> None:
        """Schedule a broadcast from a synchronous API route after its DB commit."""
        with self._lock:
            loop = self._loops.get(room_id)
        if loop is None or loop.is_closed() or not loop.is_running():
            return
        future = asyncio.run_coroutine_threadsafe(self.broadcast(room_id, event), loop)
        future.add_done_callback(self._log_scheduled_error)

    @staticmethod
    def _log_scheduled_error(future) -> None:
        if future.cancelled():
            return
        error = future.exception()
        if error is not None:
            log.warning("itinerary collaboration broadcast failed: %s", error)


collaboration_hub = ItineraryCollaborationHub()
