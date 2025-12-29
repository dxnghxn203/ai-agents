import asyncio
from app.services.sse import SSEManager


class EventEmitter:
    """Event emitter for SSE events"""

    async def emit_message(self, conversation_id: str, event_type: str, data: dict):
        """Emit a message via SSE"""
        await SSEManager.broadcast(conversation_id, event_type, data)


# Global event emitter instance
event_emitter = EventEmitter()