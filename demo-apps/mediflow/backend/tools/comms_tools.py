"""Communications tool wrappers for the Strands agent."""

from strands import tool
from backend.services import comms_service


def _sanitize_comms_result(record) -> dict:
    """Rename 'content' key to avoid collision with Bedrock content block format."""
    if not isinstance(record, dict):
        record = dict(record)
    if "content" in record:
        d = {k: v for k, v in record.items() if k != "content"}
        d["message_text"] = record["content"]
        return d
    return dict(record)


@tool
def send_appointment_reminder(patient_id: str, appointment_id: str) -> dict:
    """Send an appointment reminder to a patient via their preferred contact method.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        appointment_id: Appointment ID to remind about (e.g. 'apt-abc12345')
    """
    return _sanitize_comms_result(comms_service.send_appointment_reminder(patient_id, appointment_id))


@tool
def send_message(patient_id: str, message: str, channel: str = "") -> dict:
    """Send a message to a patient. Uses their preferred contact method if channel not specified.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        message: Message text to send
        channel: Optional delivery channel - 'phone', 'email', or 'sms'. Defaults to patient preference.
    """
    return _sanitize_comms_result(comms_service.send_message(patient_id, message, channel or None))


@tool
def get_comms_history(patient_id: str) -> list:
    """Get the full communications history for a patient, most recent first.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
    """
    results = comms_service.get_comms_history(patient_id)
    return [_sanitize_comms_result(r) if isinstance(r, dict) else r for r in results]
