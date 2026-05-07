"""Dashboard API routes for analysis summary and stats."""

import logging
from fastapi import APIRouter

from backend.services.database import query_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/dashboard/summary")
async def dashboard_summary():
    """Return a summary of analysis results for the dashboard."""
    sessions = query_db(
        "SELECT COUNT(DISTINCT session_id) AS cnt FROM conversation_log"
    )
    session_count = sessions[0]["cnt"] if sessions else 0

    tool_calls = query_db("SELECT COUNT(*) AS cnt FROM tool_call_log")
    tool_call_count = tool_calls[0]["cnt"] if tool_calls else 0

    patterns = query_db("SELECT * FROM detected_patterns ORDER BY occurrence_count DESC")
    skills = query_db("SELECT * FROM skills ORDER BY created_at DESC")

    memory_rows = query_db("SELECT COUNT(*) AS cnt FROM patient_memories")
    memory_count = memory_rows[0]["cnt"] if memory_rows else 0
    patients_with_memories = query_db(
        "SELECT COUNT(DISTINCT patient_id) AS cnt FROM patient_memories"
    )
    patients_with_memory_count = patients_with_memories[0]["cnt"] if patients_with_memories else 0

    last_run_row = query_db(
        "SELECT MAX(detected_at) AS ts FROM detected_patterns"
    )
    last_analysis_run = last_run_row[0]["ts"] if last_run_row and last_run_row[0]["ts"] else None

    # Rough impact estimate: 2 min saved per scheduled skill's enabled run.
    scheduled_skills = [s for s in skills if s.get("scheduled")]
    estimated_minutes_saved = len(scheduled_skills) * 10

    return {
        "sessions_analysed": session_count,
        "interactions_analysed": tool_call_count,
        "patterns_detected": len(patterns),
        "skills_generated": len(skills),
        "estimated_minutes_saved": estimated_minutes_saved,
        "memories": {
            "total": memory_count,
            "patients_with_memories": patients_with_memory_count,
        },
        "last_analysis_run": last_analysis_run,
        "patterns": patterns,
        "skills": skills,
    }
