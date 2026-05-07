"""Patient Memory API routes."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.services.database import query_db
from backend.services.memory_service import (
    get_memories,
    add_memory,
    update_memory,
)

router = APIRouter(tags=["memories"])


class MemoryCreate(BaseModel):
    memory_type: str  # preference, behavioral, medical_context, communication
    content: str


class MemoryUpdate(BaseModel):
    content: str | None = None
    status: str | None = None   # active, dismissed
    source: str | None = None


@router.get("/api/patients/{patient_id}/memories")
def list_memories(patient_id: str, type: str | None = None):
    """List active memories for a patient, optionally filtered by type."""
    memories = get_memories(patient_id, memory_type=type)
    return {"memories": memories}


@router.post("/api/patients/{patient_id}/memories")
def create_memory(patient_id: str, body: MemoryCreate):
    """Manually add a memory (user-confirmed source)."""
    memory_id = add_memory(
        patient_id=patient_id,
        memory_type=body.memory_type,
        content=body.content,
        source="user_confirmed",
        confidence=1.0,
    )
    return {"id": memory_id, "status": "created"}


@router.put("/api/patients/{patient_id}/memories/{memory_id}")
def edit_memory(patient_id: str, memory_id: str, body: MemoryUpdate):
    """Update a memory — confirm, edit, or dismiss."""
    # If confirming (no status change but source update), boost confidence
    source = body.source
    confidence = None
    if source == "user_confirmed" or (body.status is None and body.content is not None):
        source = "user_confirmed"
        confidence = 1.0

    updated = update_memory(
        memory_id=memory_id,
        content=body.content,
        status=body.status,
        source=source,
        confidence=confidence,
    )
    if not updated and body.status is None and body.content is None and body.source is None:
        return {"error": "No fields to update"}
    return {"id": memory_id, "status": "updated"}


@router.delete("/api/patients/{patient_id}/memories/{memory_id}")
def dismiss_memory(patient_id: str, memory_id: str):
    """Soft-delete a memory by setting status to dismissed."""
    update_memory(memory_id=memory_id, status="dismissed")
    return {"id": memory_id, "status": "dismissed"}


@router.get("/api/memories/summary")
def memories_summary():
    """Aggregate memory stats for the Insights view."""
    # Order memories within each patient by type-rarity first (medical_context >
    # communication > preference > behavioral), then recency. This ensures the
    # preview (memories[0]) mixes across all four types instead of always leading
    # with the most-populous behavioral memories.
    rows = query_db(
        "SELECT pm.patient_id, (p.first_name || ' ' || p.last_name) AS patient_name, "
        "pm.memory_type, pm.content, pm.confidence, pm.source "
        "FROM patient_memories pm "
        "JOIN patients p ON p.id = pm.patient_id "
        "WHERE pm.status = 'active' "
        "ORDER BY CASE pm.memory_type "
        "  WHEN 'medical_context' THEN 0 "
        "  WHEN 'communication' THEN 1 "
        "  WHEN 'preference' THEN 2 "
        "  WHEN 'behavioral' THEN 3 "
        "  ELSE 4 END, "
        "pm.first_observed DESC"
    )
    # Group by patient
    patients = {}
    type_counts = {}
    for r in rows:
        pid = r["patient_id"]
        mtype = r["memory_type"]
        type_counts[mtype] = type_counts.get(mtype, 0) + 1
        if pid not in patients:
            patients[pid] = {
                "patient_id": pid,
                "patient_name": r["patient_name"],
                "memory_count": 0,
                "memories": [],
            }
        patients[pid]["memory_count"] += 1
        if len(patients[pid]["memories"]) < 3:  # top 3 per patient
            patients[pid]["memories"].append({
                "type": mtype,
                "content": r["content"],
                "confidence": r["confidence"],
                "source": r["source"],
            })

    return {
        "total_memories": len(rows),
        "patient_count": len(patients),
        "type_counts": type_counts,
        "patients": sorted(patients.values(), key=lambda p: p["memory_count"], reverse=True),
    }
