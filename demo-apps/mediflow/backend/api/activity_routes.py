"""API routes for UI activity tracking."""

import logging
from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.activity_service import log_activities, get_activities

logger = logging.getLogger(__name__)
router = APIRouter()


class ActivityEvent(BaseModel):
    action_type: str
    action_detail: dict | str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    view: str | None = None
    duration_ms: int | None = None
    metadata: dict | str | None = None


class ActivityBatch(BaseModel):
    session_id: str
    events: list[ActivityEvent]


@router.post("/api/activity")
async def post_activity(batch: ActivityBatch):
    """Receive a batch of UI activity events."""
    count = log_activities(batch.session_id, [e.model_dump() for e in batch.events])
    logger.info("Logged %d UI activity events for session %s", count, batch.session_id)
    return {"ok": True, "count": count}


@router.get("/api/activity")
async def list_activity(
    session_id: str | None = None,
    action_type: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
):
    """Query UI activity events (used by pattern detector)."""
    return get_activities(
        session_id=session_id,
        action_type=action_type,
        start_time=start_time,
        end_time=end_time,
    )
