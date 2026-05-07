"""Patient record tool wrappers for the Strands agent."""

from strands import tool
from backend.services import patient_service
from backend.services import memory_service


@tool
def search_patients(query: str) -> list:
    """Search for patients by name. Returns matching patient records.

    Args:
        query: Search string to match against first or last name (case-insensitive)
    """
    return patient_service.search_patients(query)


@tool
def get_patient(patient_id: str) -> dict:
    """Get full details of a specific patient.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
    """
    return patient_service.get_patient(patient_id)


@tool
def get_patient_history(patient_id: str) -> dict:
    """Get a patient's record along with their recent appointments and invoices.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
    """
    return patient_service.get_patient_history(patient_id)


@tool
def update_patient_notes(patient_id: str, notes: str) -> dict:
    """Add notes to a patient's record. New notes are appended, not replaced.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        notes: Text to append to the patient's notes
    """
    return patient_service.update_patient_notes(patient_id, notes)


@tool
def get_patient_memories(patient_id: str) -> dict:
    """Recall what you know about a patient — preferences, behaviour patterns, communication style, and medical context.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
    """
    memories = memory_service.get_memories(patient_id)
    if not memories:
        return {"patient_id": patient_id, "memories": [], "message": "No memories recorded for this patient yet."}
    return {
        "patient_id": patient_id,
        "memories": [
            {
                "id": m["id"],
                "type": m["memory_type"],
                "detail": m["content"],
                "confidence": m["confidence"],
                "observations": m["observation_count"],
            }
            for m in memories
        ],
    }


@tool
def record_patient_memory(patient_id: str, memory_type: str, content: str) -> dict:
    """Save a useful observation about a patient for future reference. Duplicates are automatically merged.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        memory_type: One of 'preference', 'behavioral', 'medical_context', 'communication'
        content: A concise, actionable statement (e.g. 'Prefers afternoon appointments')
    """
    valid_types = {"preference", "behavioral", "medical_context", "communication"}
    if memory_type not in valid_types:
        return {"error": f"Invalid memory_type '{memory_type}'. Must be one of: {', '.join(sorted(valid_types))}"}

    memory_id = memory_service.merge_or_create(
        patient_id=patient_id,
        memory_type=memory_type,
        content=content,
        source="agent_observed",
        confidence=0.5,
    )
    return {"memory_id": memory_id, "status": "saved", "patient_id": patient_id}
