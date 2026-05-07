"""Skill management tool wrappers for the Strands agent.

These tools let the agent discover, enable, and run Skills during a conversation.
"""

from datetime import datetime

from strands import tool
from backend.services.database import query_db, execute_db


@tool
def get_pending_skills() -> list:
    """Get all skills that are pending review (not yet enabled).

    Returns a list of skills with status 'pending_review' or 'draft'.
    """
    skills = query_db(
        "SELECT * FROM skills WHERE status IN ('pending_review', 'draft') "
        "ORDER BY created_at DESC"
    )
    return skills


@tool
def enable_skill(skill_id: str) -> dict:
    """Enable a pending skill. For scheduled skills, this is the pre-approval
    for future runs — the scheduler can then execute without per-run approval.

    Args:
        skill_id: The skill ID to enable.
    """
    rows = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not rows:
        return {"error": "Skill not found", "skill_id": skill_id}

    now = datetime.now().isoformat()
    execute_db(
        "UPDATE skills SET status = 'enabled', enabled_at = ? WHERE id = ?",
        (now, skill_id),
    )
    return {**rows[0], "status": "enabled", "enabled_at": now}
