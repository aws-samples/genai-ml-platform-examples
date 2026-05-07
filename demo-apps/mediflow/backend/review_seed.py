"""Lightweight review seed — ensures minimum data for UI review screenshots.

Idempotent: only inserts if required records are missing.
Does NOT run the analysis pipeline or make LLM calls.
"""

import json
from datetime import date, timedelta
from backend.services.database import get_connection, init_db, query_db


def _count(table: str) -> int:
    rows = query_db(f"SELECT COUNT(*) as c FROM {table}")  # nosec B608 - table names are string literals
    return rows[0]["c"] if rows else 0


def _ensure_patients():
    if _count("patients") >= 3:
        return
    patients = [
        ("pat-rev-001", "Sarah", "Mitchell", "1985-03-14", "0412-555-001", "sarah.mitchell@email.com", "sms", "", 0, None),
        ("pat-rev-002", "James", "Chen", "1972-08-22", "0412-555-002", "james.chen@email.com", "email", "", 0, None),
        ("pat-rev-003", "Emily", "Rodriguez", "1990-11-05", "0412-555-003", "emily.r@email.com", "phone", "", 0, None),
    ]
    conn = get_connection()
    try:
        for p in patients:
            conn.execute(
                "INSERT OR IGNORE INTO patients (id, first_name, last_name, dob, phone, email, preferred_contact, notes, no_show_count, last_visit) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                p,
            )
        conn.commit()
    finally:
        conn.close()


def _ensure_doctors():
    if _count("doctors") >= 1:
        return
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO doctors (id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("doc-rev-001", "Dr. Review Test", "General Practice", 30, "Monday,Tuesday,Wednesday,Thursday,Friday", "09:00", "17:00"),
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_appointments():
    if _count("appointments") >= 5:
        return
    today = date.today()
    tomorrow = today + timedelta(days=1)
    appts = [
        ("apt-rev-001", "pat-rev-001", "doc-rev-001", today.isoformat(), "09:00", 30, "confirmed", "standard", 0, None, None),
        ("apt-rev-002", "pat-rev-002", "doc-rev-001", today.isoformat(), "10:00", 30, "confirmed", "follow_up", 0, None, None),
        ("apt-rev-003", "pat-rev-003", "doc-rev-001", today.isoformat(), "11:00", 30, "confirmed", "telehealth", 0, None, None),
        ("apt-rev-004", "pat-rev-001", "doc-rev-001", tomorrow.isoformat(), "09:00", 30, "confirmed", "standard", 0, None, None),
        ("apt-rev-005", "pat-rev-002", "doc-rev-001", tomorrow.isoformat(), "14:00", 30, "confirmed", "urgent", 0, None, None),
    ]
    conn = get_connection()
    try:
        for a in appts:
            conn.execute(
                "INSERT OR IGNORE INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent, created_at, notes) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                a,
            )
        conn.commit()
    finally:
        conn.close()


def _ensure_skills():
    if _count("skills") >= 1:
        return
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO skills (id, name, description, trigger_description, tool_config, status, scheduled) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "skill-rev-001",
                "Morning Reminder Batch",
                "Sends appointment reminders to all patients with appointments in the next 24 hours.",
                "Daily at 7:00 AM",
                json.dumps(["send_appointment_reminder", "list_upcoming_appointments"]),
                "enabled",
                1,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_comms():
    if _count("communications") >= 1:
        return
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO communications (id, patient_id, channel, type, content, status, sent_at, triggered_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "comm-rev-001",
                "pat-rev-001",
                "sms",
                "reminder",
                "Hi Sarah, reminder of your appointment tomorrow at 9:00 AM.",
                "sent",
                date.today().isoformat() + "T08:00:00",
                "system",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _ensure_activity_log():
    if _count("ui_activity_log") >= 1:
        return
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO ui_activity_log (session_id, timestamp, action_type, action_detail, entity_type, entity_id, view) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "review-session",
                date.today().isoformat() + "T09:15:00",
                "appointment_booked",
                "Appointment booked for Sarah Mitchell with Dr. Review Test",
                "appointment",
                "apt-rev-001",
                "today",
            ),
        )
        conn.commit()
    finally:
        conn.close()


def ensure_review_data():
    """Ensure minimum data exists for UI review. Idempotent."""
    init_db()
    _ensure_patients()
    _ensure_doctors()
    _ensure_appointments()
    _ensure_skills()
    _ensure_comms()
    _ensure_activity_log()
    print("  Review seed: data verified.")


if __name__ == "__main__":
    ensure_review_data()
