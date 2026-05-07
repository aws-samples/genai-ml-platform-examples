"""Communications service for patient messaging."""

import uuid

from backend.services.database import query_db, execute_db


def send_appointment_reminder(patient_id: str, appointment_id: str) -> dict:
    """Send an appointment reminder to a patient.

    Looks up appointment and patient details, creates a communications
    record, and marks the appointment's reminder_sent flag.

    Returns:
        The created communication record dict.
    """
    # Look up appointment
    appointments = query_db(
        """SELECT a.*, d.name AS doctor_name
           FROM appointments a
           JOIN doctors d ON a.doctor_id = d.id
           WHERE a.id = ?""",
        (appointment_id,),
    )
    if not appointments:
        return {"error": "Appointment not found", "appointment_id": appointment_id}
    apt = appointments[0]

    # Look up patient
    patients = query_db("SELECT * FROM patients WHERE id = ?", (patient_id,))
    if not patients:
        return {"error": "Patient not found", "patient_id": patient_id}
    patient = patients[0]

    channel = patient.get("preferred_contact") or "phone"
    message = (
        f"Reminder: You have an appointment with {apt['doctor_name']} "
        f"on {apt['date']} at {apt['time']}. "
        f"Please arrive 10 minutes early."
    )

    comm_id = f"comm-{uuid.uuid4().hex[:8]}"

    execute_db(
        """INSERT INTO communications (id, patient_id, channel, type, content, triggered_by)
           VALUES (?, ?, ?, 'reminder', ?, 'comms_service')""",
        (comm_id, patient_id, channel, message),
    )

    # Mark reminder as sent on the appointment
    execute_db(
        "UPDATE appointments SET reminder_sent = 1 WHERE id = ?",
        (appointment_id,),
    )

    rows = query_db("SELECT * FROM communications WHERE id = ?", (comm_id,))
    return rows[0] if rows else {"id": comm_id, "status": "sent"}


def send_message(patient_id: str, message: str, channel: str = None) -> dict:
    """Send an arbitrary message to a patient.

    Uses the patient's preferred_contact if *channel* is not supplied.

    Returns:
        The created communication record dict.
    """
    if not channel:
        patients = query_db("SELECT preferred_contact FROM patients WHERE id = ?", (patient_id,))
        channel = patients[0]["preferred_contact"] if patients else "phone"

    comm_id = f"comm-{uuid.uuid4().hex[:8]}"

    execute_db(
        """INSERT INTO communications (id, patient_id, channel, type, content, triggered_by)
           VALUES (?, ?, ?, 'general', ?, 'comms_service')""",
        (comm_id, patient_id, channel, message),
    )

    rows = query_db("SELECT * FROM communications WHERE id = ?", (comm_id,))
    return rows[0] if rows else {"id": comm_id, "status": "sent"}


def get_comms_history(patient_id: str) -> list:
    """Return all communications for a patient, most recent first."""
    return query_db(
        """SELECT * FROM communications
           WHERE patient_id = ?
           ORDER BY sent_at DESC""",
        (patient_id,),
    )
