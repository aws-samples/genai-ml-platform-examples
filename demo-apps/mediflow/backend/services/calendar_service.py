"""Calendar and appointment management service."""

import json
import uuid
from datetime import datetime, timedelta

from backend.services.database import get_connection, query_db, execute_db


VALID_UNAVAILABILITY_REASONS = {"sick", "leave", "other"}


def _get_unavailability_for(doctor_id: str, date: str) -> list[dict]:
    """Return doctor_unavailability rows whose inclusive range covers *date*."""
    return query_db(
        """
        SELECT *
        FROM doctor_unavailability
        WHERE doctor_id = ?
          AND start_date <= ?
          AND end_date >= ?
        """,
        (doctor_id, date, date),
    )


def _slot_blocked_by_unavailability(slot: str, rows: list[dict]) -> bool:
    """True if a given HH:MM slot falls inside any unavailability window.

    Full-day rows (both times NULL) block everything.
    Partial rows block slots where ``start_time <= slot < end_time``.
    """
    for r in rows:
        st, et = r.get("start_time"), r.get("end_time")
        if not st and not et:
            return True
        if st and et and st <= slot < et:
            return True
    return False


def check_availability(doctor_id: str, date: str, time_range: str = None) -> dict:
    """Return available 30-min slots for a doctor on a given date.

    Args:
        doctor_id: Doctor identifier.
        date: Date string in YYYY-MM-DD format.
        time_range: Optional filter - "morning" (09:00-12:00),
                    "afternoon" (12:00-17:00), or None for all day.

    Returns:
        Dict with doctor_id, date, and list of available_slots.
    """
    # Get doctor's working hours
    doctors = query_db("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    if not doctors:
        return {"doctor_id": doctor_id, "date": date, "available_slots": [], "error": "Doctor not found"}

    doctor = doctors[0]
    hours_start = doctor["hours_start"]
    hours_end = doctor["hours_end"]
    duration = doctor.get("consultation_duration_mins") or 30

    # Check working days
    working_days = json.loads(doctor.get("working_days") or '[]')
    requested_date = datetime.strptime(date, "%Y-%m-%d")
    day_name = requested_date.strftime("%A")
    if working_days and day_name not in working_days:
        return {"doctor_id": doctor_id, "date": date, "available_slots": [], "note": f"Doctor does not work on {day_name}"}

    # Apply time_range filter
    if time_range == "morning":
        range_start, range_end = "09:00", "12:00"
    elif time_range == "afternoon":
        range_start, range_end = "12:00", "17:00"
    else:
        range_start, range_end = hours_start, hours_end

    # Clamp to doctor's actual hours
    effective_start = max(range_start, hours_start)
    effective_end = min(range_end, hours_end)

    # Generate all possible slots at 30-min intervals
    all_slots = []
    current = datetime.strptime(effective_start, "%H:%M")
    end = datetime.strptime(effective_end, "%H:%M")
    while current + timedelta(minutes=duration) <= end:
        all_slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)

    # Get booked appointment times for this doctor+date
    booked = query_db(
        "SELECT time FROM appointments WHERE doctor_id = ? AND date = ? AND status != 'cancelled'",
        (doctor_id, date),
    )
    booked_times = {row["time"] for row in booked}

    unavail_rows = _get_unavailability_for(doctor_id, date)

    available = [
        slot for slot in all_slots
        if slot not in booked_times
        and not _slot_blocked_by_unavailability(slot, unavail_rows)
    ]

    return {"doctor_id": doctor_id, "date": date, "available_slots": available}


def book_appointment(
    patient_id: str,
    doctor_id: str,
    date: str,
    time: str,
    type: str = "standard",
) -> dict:
    """Book a new appointment.

    Returns:
        The created appointment as a dict.
    """
    apt_id = f"apt-{uuid.uuid4().hex[:8]}"

    # Get doctor's consultation duration
    doctors = query_db("SELECT consultation_duration_mins FROM doctors WHERE id = ?", (doctor_id,))
    duration = doctors[0]["consultation_duration_mins"] if doctors else 30

    execute_db(
        """INSERT INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, type, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'scheduled')""",
        (apt_id, patient_id, doctor_id, date, time, duration, type),
    )

    return {
        "id": apt_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "date": date,
        "time": time,
        "duration_mins": duration,
        "type": type,
        "status": "scheduled",
    }


def reschedule_appointment(appointment_id: str, new_date: str, new_time: str) -> dict:
    """Reschedule an existing appointment to a new date/time.

    Returns:
        The updated appointment dict.
    """
    execute_db(
        "UPDATE appointments SET date = ?, time = ?, status = 'rescheduled' WHERE id = ?",
        (new_date, new_time, appointment_id),
    )

    rows = query_db("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    if not rows:
        return {"error": "Appointment not found", "appointment_id": appointment_id}
    return rows[0]


def cancel_appointment(appointment_id: str, reason: str = None) -> dict:
    """Cancel an appointment and optionally record a reason.

    Returns:
        The updated appointment dict.
    """
    if reason:
        execute_db(
            "UPDATE appointments SET status = 'cancelled', notes = COALESCE(notes || '\\n', '') || ? WHERE id = ?",
            (f"Cancellation reason: {reason}", appointment_id),
        )
    else:
        execute_db(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            (appointment_id,),
        )

    rows = query_db("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
    if not rows:
        return {"error": "Appointment not found", "appointment_id": appointment_id}
    return rows[0]


def list_upcoming(
    doctor_id: str = None,
    patient_id: str = None,
    days: int = 7,
) -> list:
    """List upcoming appointments within *days* from today.

    Joins with patients and doctors tables for names.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")

    sql = """
        SELECT a.*,
               p.first_name || ' ' || p.last_name AS patient_name,
               d.name AS doctor_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.date >= ? AND a.date <= ?
          AND a.status != 'cancelled'
    """
    params: list = [today, end_date]

    if doctor_id:
        sql += " AND a.doctor_id = ?"
        params.append(doctor_id)
    if patient_id:
        sql += " AND a.patient_id = ?"
        params.append(patient_id)

    sql += " ORDER BY a.date, a.time"
    return query_db(sql, tuple(params))


def get_appointment_details(appointment_id: str) -> dict:
    """Return full appointment details with patient and doctor info."""
    rows = query_db(
        """
        SELECT a.*,
               p.first_name || ' ' || p.last_name AS patient_name,
               p.phone AS patient_phone,
               p.email AS patient_email,
               p.preferred_contact,
               d.name AS doctor_name,
               d.specialty AS doctor_specialty
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.id = ?
        """,
        (appointment_id,),
    )
    if not rows:
        return {"error": "Appointment not found", "appointment_id": appointment_id}
    return rows[0]


def get_affected_appointments(
    doctor_id: str,
    start_date: str,
    end_date: str,
    start_time: str | None = None,
    end_time: str | None = None,
) -> list[dict]:
    """List scheduled appointments for *doctor_id* inside the window.

    Cancelled appointments are excluded. If start_time/end_time are given,
    only appointments whose ``time`` falls in ``[start_time, end_time)`` are
    returned — matching the half-open semantics we use in check_availability.
    """
    sql = """
        SELECT a.*, p.first_name || ' ' || p.last_name AS patient_name,
               d.name AS doctor_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.doctor_id = ?
          AND a.date BETWEEN ? AND ?
          AND a.status NOT IN ('cancelled', 'no-show', 'no_show')
    """
    params: list = [doctor_id, start_date, end_date]
    if start_time:
        sql += " AND a.time >= ?"
        params.append(start_time)
    if end_time:
        sql += " AND a.time < ?"
        params.append(end_time)
    sql += " ORDER BY a.date, a.time"
    return query_db(sql, tuple(params))


def mark_doctor_unavailable(
    doctor_id: str,
    start_date: str,
    end_date: str,
    start_time: str | None,
    end_time: str | None,
    reason: str,
    note: str | None,
    created_by: str,
) -> dict:
    """Insert a doctor_unavailability row and return affected appointments.

    Returns dict with ``unavailability_id`` + ``affected_appointments``.
    If ``reason`` is invalid returns ``{error: ...}`` without writing.
    """
    if reason not in VALID_UNAVAILABILITY_REASONS:
        return {
            "error": f"Invalid reason '{reason}' — must be one of {sorted(VALID_UNAVAILABILITY_REASONS)}",
        }

    # Normalise empty strings to NULL for times
    st = start_time or None
    et = end_time or None

    # Idempotent: if a row already exists for this exact window, return it.
    existing = query_db(
        """SELECT id FROM doctor_unavailability
           WHERE doctor_id = ? AND start_date = ? AND end_date = ?
             AND (start_time IS ? OR start_time = ?)
             AND (end_time   IS ? OR end_time   = ?)
           LIMIT 1""",
        (doctor_id, start_date, end_date, st, st, et, et),
    )
    if existing:
        uid = existing[0]["id"]
        affected = get_affected_appointments(
            doctor_id, start_date, end_date, start_time=st, end_time=et
        )
        return {
            "unavailability_id": uid,
            "affected_appointments": affected,
            "already_existed": True,
        }

    uid = execute_db(
        """INSERT INTO doctor_unavailability
           (doctor_id, start_date, end_date, start_time, end_time, reason, note, created_by, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (doctor_id, start_date, end_date, st, et, reason, note, created_by),
    )
    affected = get_affected_appointments(
        doctor_id, start_date, end_date, start_time=st, end_time=et
    )
    return {
        "unavailability_id": uid,
        "affected_appointments": affected,
    }


def clear_doctor_unavailability(unavailability_id: int) -> dict:
    """Delete the unavailability row with the given id.

    Returns ``{deleted: N}``. Unknown ids return ``{deleted: 0}`` (no error).
    """
    rows = query_db(
        "SELECT id FROM doctor_unavailability WHERE id = ?",
        (unavailability_id,),
    )
    if not rows:
        return {"deleted": 0}
    execute_db(
        "DELETE FROM doctor_unavailability WHERE id = ?",
        (unavailability_id,),
    )
    return {"deleted": 1}


def list_doctor_unavailability(
    doctor_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """Return unavailability rows for doctor_id overlapping a window."""
    sql = "SELECT * FROM doctor_unavailability WHERE doctor_id = ?"
    params: list = [doctor_id]
    if start_date and end_date:
        # Row overlaps window if its range intersects [start_date, end_date]
        sql += " AND start_date <= ? AND end_date >= ?"
        params.extend([end_date, start_date])
    sql += " ORDER BY start_date"
    return query_db(sql, tuple(params))


def update_doctor_schedule(
    doctor_id: str,
    working_days: list[str] | None = None,
    hours_start: str | None = None,
    hours_end: str | None = None,
    consultation_duration_mins: int | None = None,
) -> dict:
    """Update a doctor's base (recurring) schedule. Partial updates allowed."""
    rows = query_db("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
    if not rows:
        return {"error": "Doctor not found", "doctor_id": doctor_id}

    sets: list[str] = []
    params: list = []
    if working_days is not None:
        sets.append("working_days = ?")
        params.append(json.dumps(working_days))
    if hours_start is not None:
        sets.append("hours_start = ?")
        params.append(hours_start)
    if hours_end is not None:
        sets.append("hours_end = ?")
        params.append(hours_end)
    if consultation_duration_mins is not None:
        sets.append("consultation_duration_mins = ?")
        params.append(consultation_duration_mins)

    if not sets:
        return {"updated": 0, "doctor_id": doctor_id}

    params.append(doctor_id)
    execute_db(
        f"UPDATE doctors SET {', '.join(sets)} WHERE id = ?",  # nosec B608 - column names from internal logic
        tuple(params),
    )
    return {"updated": 1, "doctor_id": doctor_id}


def get_today_conflicts(iso_date: str | None = None) -> list[dict]:
    """Aggregate today's (or given date's) unavailabilities + affected appts.

    Returns a list of dicts shaped for the /today payload and the agent.
    """
    from datetime import date as _date

    day = iso_date or _date.today().isoformat()
    rows = query_db(
        """
        SELECT u.*, d.name AS doctor_name
        FROM doctor_unavailability u
        JOIN doctors d ON d.id = u.doctor_id
        WHERE u.start_date <= ? AND u.end_date >= ?
        ORDER BY u.start_date
        """,
        (day, day),
    )
    conflicts = []
    for r in rows:
        affected = get_affected_appointments(
            r["doctor_id"], day, day,
            start_time=r.get("start_time"),
            end_time=r.get("end_time"),
        )
        conflicts.append({
            "unavailability_id": r["id"],
            "doctor_id": r["doctor_id"],
            "doctor_name": r["doctor_name"],
            "reason": r["reason"],
            "note": r.get("note"),
            "start_date": r["start_date"],
            "end_date": r["end_date"],
            "start_time": r.get("start_time"),
            "end_time": r.get("end_time"),
            "created_by": r.get("created_by"),
            "affected_appointments": affected,
        })
    return conflicts


def reschedule_all_patients_for_doctor(doctor_id: str, date: str) -> dict:
    """Bulk reschedule every scheduled appointment for *doctor_id* on *date*.

    For each affected appointment, reassigns to the first available slot on
    another doctor (nearest in time to the original), updates the DB row, and
    drafts an SMS notification to the patient. Returns a single structured
    payload suitable for rendering the reschedule-cascade chat card.
    """
    doctor_row = query_db("SELECT name FROM doctors WHERE id = ?", (doctor_id,))
    doctor_name = doctor_row[0]["name"] if doctor_row else doctor_id

    affected = query_db(
        """SELECT a.id, a.time, a.patient_id,
                  p.first_name || ' ' || p.last_name AS patient_name,
                  d.name AS original_doctor_name
             FROM appointments a
             JOIN patients p ON p.id = a.patient_id
             JOIN doctors d ON d.id = a.doctor_id
            WHERE a.doctor_id = ? AND a.date = ?
              AND a.status NOT IN ('cancelled', 'rescheduled')
            ORDER BY a.time ASC""",
        (doctor_id, date),
    )

    other_doctors = query_db(
        "SELECT id, name FROM doctors WHERE id != ? ORDER BY name",
        (doctor_id,),
    )
    # Cache availability per other doctor (list of free HH:MM slots on that date)
    availability_cache: dict[str, list[str]] = {}
    for d in other_doctors:
        avail = check_availability(d["id"], date).get("available_slots") or []
        availability_cache[d["id"]] = list(avail)

    def _nearest_slot(doctor_slots: list[str], original: str) -> str | None:
        if not doctor_slots:
            return None
        orig_min = int(original[:2]) * 60 + int(original[3:])
        best = min(
            doctor_slots,
            key=lambda s: abs((int(s[:2]) * 60 + int(s[3:])) - orig_min),
        )
        return best

    entries: list[dict] = []
    messages_drafted = 0
    for appt in affected:
        orig_time = appt["time"]
        # Greedy: score each candidate doctor by their nearest free slot's distance to orig_time.
        best_doctor_id: str | None = None
        best_doctor_name: str | None = None
        best_slot: str | None = None
        best_delta = 10_000
        for d in other_doctors:
            slot = _nearest_slot(availability_cache.get(d["id"], []), orig_time)
            if not slot:
                continue
            delta = abs(
                (int(slot[:2]) * 60 + int(slot[3:]))
                - (int(orig_time[:2]) * 60 + int(orig_time[3:]))
            )
            if delta < best_delta:
                best_delta = delta
                best_doctor_id = d["id"]
                best_doctor_name = d["name"]
                best_slot = slot

        if not best_doctor_id or not best_slot:
            entries.append({
                "appointment_id": appt["id"],
                "patient_id": appt["patient_id"],
                "patient_name": appt["patient_name"],
                "original_doctor_name": appt["original_doctor_name"],
                "original_time": orig_time,
                "new_doctor_id": None,
                "new_doctor_name": None,
                "new_time": None,
                "message_drafted": False,
                "note": "No available slot with another doctor on this date",
            })
            continue

        # Commit the reschedule: update appointment row + consume the slot from cache
        execute_db(
            """UPDATE appointments
                  SET doctor_id = ?, time = ?, status = 'rescheduled'
                WHERE id = ?""",
            (best_doctor_id, best_slot, appt["id"]),
        )
        availability_cache[best_doctor_id] = [
            s for s in availability_cache[best_doctor_id] if s != best_slot
        ]

        # Draft a notification message (recorded in communications table)
        content = (
            f"Hi {appt['patient_name'].split()[0]}, your appointment with "
            f"{appt['original_doctor_name']} at {orig_time} today has been moved to "
            f"{best_doctor_name} at {best_slot} — {appt['original_doctor_name']} "
            f"is unavailable today. Reply STOP to opt out."
        )
        comm_id = f"comm-{uuid.uuid4().hex[:8]}"
        execute_db(
            """INSERT INTO communications (id, patient_id, channel, type, content, triggered_by)
               VALUES (?, ?, 'sms', 'reschedule_notice', ?, 'reschedule_all')""",
            (comm_id, appt["patient_id"], content),
        )
        messages_drafted += 1

        entries.append({
            "appointment_id": appt["id"],
            "patient_id": appt["patient_id"],
            "patient_name": appt["patient_name"],
            "original_doctor_name": appt["original_doctor_name"],
            "original_time": orig_time,
            "new_doctor_id": best_doctor_id,
            "new_doctor_name": best_doctor_name,
            "new_time": best_slot,
            "message_drafted": True,
            "comm_id": comm_id,
        })

    return {
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "date": date,
        "total_affected": len(affected),
        "doctors_considered": len(other_doctors),
        "slots_considered": sum(len(v) for v in availability_cache.values())
            + sum(1 for e in entries if e["new_time"]),  # pre-consumed slots
        "entries": entries,
        "messages_drafted": messages_drafted,
    }

