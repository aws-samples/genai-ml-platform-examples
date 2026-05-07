"""Practice information tool wrappers for the Strands agent."""

from strands import tool
from backend.services.database import query_db


@tool
def get_practice_info(topic: str = "") -> dict:
    """Look up practice information such as hours, policies, fees, and services.

    Args:
        topic: Optional topic to filter by (e.g. 'hours', 'fees', 'parking'). If empty, returns all practice info.
    """
    if topic:
        rows = query_db(
            "SELECT key, value FROM practice_info WHERE key LIKE ?",
            (f"%{topic}%",),
        )
    else:
        rows = query_db("SELECT key, value FROM practice_info")

    return {row["key"]: row["value"] for row in rows}


@tool
def get_doctor_info(doctor_id: str = "") -> dict | list:
    """Get information about doctors at the practice.

    Args:
        doctor_id: Optional doctor ID (e.g. 'dr-chen'). If empty, returns all doctors.
    """
    if doctor_id:
        rows = query_db("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
        if not rows:
            return {"error": "Doctor not found", "doctor_id": doctor_id}
        return rows[0]
    else:
        return query_db("SELECT * FROM doctors ORDER BY name")
