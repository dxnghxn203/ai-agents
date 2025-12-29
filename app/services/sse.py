from fastapi.responses import StreamingResponse
from fastapi import HTTPException
import json
import asyncio
from typing import Dict, Set


class SSEManager:
    """Simple SSE Manager for handling multiple connections"""

    _connections: Dict[str, Set[asyncio.Queue]] = {}

    @classmethod
    def add_connection(cls, conversation_id: str, queue: asyncio.Queue):
        """Add a connection to the manager"""
        if conversation_id not in cls._connections:
            cls._connections[conversation_id] = set()
        cls._connections[conversation_id].add(queue)

    @classmethod
    def remove_connection(cls, conversation_id: str, queue: asyncio.Queue):
        """Remove a connection from the manager"""
        if conversation_id in cls._connections:
            cls._connections[conversation_id].discard(queue)
            if not cls._connections[conversation_id]:
                del cls._connections[conversation_id]

    @classmethod
    async def broadcast(cls, conversation_id: str, event_type: str, data: Dict):
        """Broadcast a message to all connections for a conversation"""
        if conversation_id not in cls._connections:
            return

        message = {
            "event": event_type,
            "data": data,
            "conversation_id": conversation_id
        }

        message_json = json.dumps(message, ensure_ascii=False)

        for queue in cls._connections[conversation_id].copy():
            try:
                await queue.put(message_json)
            except:
                # Connection probably closed
                cls._connections[conversation_id].discard(queue)

    @classmethod
    def create_response(cls, conversation_id: str):
        """Create SSE streaming response"""
        queue = asyncio.Queue()

        async def event_generator():
            cls.add_connection(conversation_id, queue)
            try:
                while True:
                    message = await queue.get()
                    yield f"data: {message}\n\n"
            except asyncio.CancelledError:
                pass
            finally:
                cls.remove_connection(conversation_id, queue)

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Headers": "*",
            }
        )