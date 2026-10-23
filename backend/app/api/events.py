"""FinShield AI — Server-Sent Events for real-time updates."""
import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core import logger
from app.database import get_db
from app.auth import get_current_user
from app.db_models import User

router = APIRouter()


async def event_stream(user_id: str) -> AsyncGenerator[str, None]:
    """Generate SSE events for real-time updates.
    
    This is a simplified implementation that sends periodic heartbeat events.
    In production, this would integrate with Redis pub/sub or a message queue
    to broadcast events when transactions are screened or cases are updated.
    """
    client_id = f"{user_id}-{datetime.utcnow().timestamp()}"
    logger.info(f"SSE client connected: {client_id}")
    
    try:
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'client_id': client_id})}\n\n"
        
        # Heartbeat every 30 seconds to keep connection alive
        while True:
            await asyncio.sleep(30)
            yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.utcnow().isoformat()})}\n\n"
    
    except asyncio.CancelledError:
        logger.info(f"SSE client disconnected: {client_id}")
        raise


@router.get("/events")
async def subscribe_to_events(
    current_user: User = Depends(get_current_user),
):
    """Subscribe to real-time events via Server-Sent Events.
    
    Events include:
    - New transactions screened
    - Case status changes
    - Credit balance updates
    - System notifications
    
    The client should handle reconnection with exponential backoff.
    """
    return StreamingResponse(
        event_stream(current_user.id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
