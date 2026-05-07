import json
from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.database import query_db, execute_db
from backend.services import calendar_service
from backend.services.calendar_service import (
    check_availability as cal_check_availability,
    book_appointment as cal_book_appointment,
    VALID_UNAVAILABILITY_REASONS,
)

router = APIRouter(prefix="/api/data", tags=["data"])


_STATUS_BUCKETS = {
    "scheduled": "confirmed",
    "confirmed": "confirmed",
    "pending": "pending",
    "pending_reply": "pending",
    "needs_reschedule": "needs_reschedule",
    "rescheduling": "needs_reschedule",
    "cancelled": "cancelled",
    "no_show": "cancelled",
    "no-show": "cancelled",
    "completed": "completed",
}


def _bucket_status(raw: str) -> str:
    if not raw:
        return "pending"
    return _STATUS_BUCKETS.get(raw.lower(), "pending")


@router.get("/today")
def get_today():
    today_date = date.today()
    today = today_date.isoformat()

    appointments = query_db(
        """
        SELECT a.id, a.time, a.status, a.type, a.duration_mins, a.doctor_id,
               a.patient_id,
               p.first_name || ' ' || p.last_name AS patient_name,
               d.name AS doctor_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.date = ?
        ORDER BY a.time
        """,
        (today,),
    )

    # Tasks: overdue invoices + pending appointments
    overdue_invoices = query_db(
        """
        SELECT i.id, i.amount, i.due_date, i.chase_count, i.patient_id,
               p.first_name || ' ' || p.last_name AS patient_name
        FROM invoices i
        JOIN patients p ON i.patient_id = p.id
        WHERE i.status IN ('outstanding', 'overdue') AND i.due_date < ?
        ORDER BY i.due_date
        LIMIT 10
        """,
        (today,),
    )

    tasks = []
    for inv in overdue_invoices:
        tasks.append({
            "text": f"Chase invoice {inv['id']} ({inv['patient_name']} - ${inv['amount']:.2f})",
            "priority": "urgent",
            "done": False,
            "agent": False,
        })

    no_show_patients = query_db(
        "SELECT first_name || ' ' || last_name AS name FROM patients WHERE no_show_count > 1 LIMIT 3"
    )
    for ns in no_show_patients:
        tasks.append({
            "text": f"Call {ns['name']} re: missed appointments",
            "priority": "urgent",
            "done": False,
            "agent": False,
        })

    tasks.extend([
        {"text": "Send appointment reminders for tomorrow", "priority": "suggested", "done": False, "agent": True},
        {"text": "Follow up on outstanding invoices", "priority": "suggested", "done": False, "agent": True},
    ])

    # Stats
    patients_today = len(appointments)
    revenue = query_db(
        """
        SELECT COALESCE(SUM(i.amount), 0) AS total FROM invoices i
        JOIN appointments a ON i.appointment_id = a.id
        WHERE a.date = ?
        """,
        (today,),
    )
    no_shows = query_db(
        "SELECT COUNT(*) AS cnt FROM appointments WHERE date = ? AND status = 'no_show'",
        (today,),
    )
    outstanding = query_db(
        "SELECT COALESCE(SUM(amount - amount_paid), 0) AS total FROM invoices WHERE status IN ('outstanding', 'overdue')"
    )

    # -------- TASK-043 dashboard extensions --------

    # Appointment status buckets
    status_counts = {
        "confirmed": 0, "pending": 0, "needs_reschedule": 0,
        "cancelled": 0, "completed": 0,
    }
    for a in appointments:
        status_counts[_bucket_status(a.get("status"))] += 1

    # Invoices outstanding top 5 (sorted by days_overdue DESC)
    invoice_rows = query_db(
        """
        SELECT i.id, i.amount, i.amount_paid, i.due_date, i.status, i.patient_id,
               p.first_name || ' ' || p.last_name AS patient_name
        FROM invoices i
        JOIN patients p ON i.patient_id = p.id
        WHERE i.status IN ('outstanding', 'overdue')
        """
    )
    invoices_outstanding = []
    for row in invoice_rows:
        due_iso = row.get("due_date")
        try:
            due = date.fromisoformat(due_iso) if due_iso else None
            days_overdue = (today_date - due).days if due else 0
        except (ValueError, TypeError):
            days_overdue = 0
        invoices_outstanding.append({
            "id": row["id"],
            "patient_id": row.get("patient_id"),
            "patient_name": row["patient_name"],
            "amount": row["amount"],
            "due_date": due_iso,
            "days_overdue": days_overdue,
            "status": row["status"],
        })
    invoices_outstanding.sort(key=lambda r: r["days_overdue"], reverse=True)
    invoices_outstanding = invoices_outstanding[:5]

    # Total outstanding (across all outstanding/overdue, remaining amount)
    total_outstanding_row = query_db(
        "SELECT COALESCE(SUM(amount - amount_paid), 0) AS total FROM invoices WHERE status IN ('outstanding', 'overdue')"
    )
    invoices_total_outstanding = total_outstanding_row[0]["total"] if total_outstanding_row else 0
    if isinstance(invoices_total_outstanding, float) and invoices_total_outstanding.is_integer():
        invoices_total_outstanding = int(invoices_total_outstanding)

    # Revenue snapshot (global, not week-bounded)
    paid_row = query_db(
        "SELECT COALESCE(SUM(amount_paid), 0) AS total FROM invoices"
    )
    out_row = query_db(
        "SELECT COALESCE(SUM(amount - amount_paid), 0) AS total FROM invoices WHERE status = 'outstanding'"
    )
    over_row = query_db(
        "SELECT COALESCE(SUM(amount - amount_paid), 0) AS total FROM invoices WHERE status = 'overdue'"
    )

    def _norm(v):
        try:
            f = float(v)
            if f < 0:
                f = 0.0
            return int(f) if f.is_integer() else f
        except (TypeError, ValueError):
            return 0

    rev_paid = _norm(paid_row[0]["total"] if paid_row else 0)
    rev_out = _norm(out_row[0]["total"] if out_row else 0)
    rev_over = _norm(over_row[0]["total"] if over_row else 0)
    rev_total = _norm(rev_paid + rev_out + rev_over)

    revenue_snapshot = {
        "paid": rev_paid,
        "outstanding": rev_out,
        "overdue": rev_over,
        "total": rev_total,
    }

    # Weekly trend — Mon–Fri counts for current and prior ISO week
    monday_this = today_date - timedelta(days=today_date.weekday())
    monday_last = monday_this - timedelta(days=7)

    def _week_counts(monday):
        friday = monday + timedelta(days=4)
        rows = query_db(
            """
            SELECT date, COUNT(*) AS cnt
            FROM appointments
            WHERE date BETWEEN ? AND ?
              AND status NOT IN ('cancelled', 'no_show', 'no-show')
            GROUP BY date
            """,
            (monday.isoformat(), friday.isoformat()),
        )
        by_date = {r["date"]: r["cnt"] for r in rows}
        counts = []
        for i in range(5):
            d = (monday + timedelta(days=i)).isoformat()
            counts.append(by_date.get(d, 0))
        return counts

    this_week = _week_counts(monday_this)
    last_week = _week_counts(monday_last)
    weekly_trend = {
        "this_week": this_week,
        "last_week": last_week,
        "delta": sum(this_week) - sum(last_week),
    }

    # Suggestions — rules-based, up to 3
    suggestions = []

    # 1) Outstanding invoices → route suggestion
    if invoices_outstanding:
        n = len(invoices_outstanding)
        suggestions.append({
            "label": f"Follow up on {n} outstanding invoice{'s' if n != 1 else ''}",
            "action": {
                "type": "route",
                "view": "patients",
                "params": {"filter": "outstanding"},
            },
        })

    # 2) Fill in with generics up to 3
    generic_pool = [
        {
            "label": "Send appointment reminders for tomorrow",
            "action": {
                "type": "prompt",
                "text": "Send appointment reminders to all patients with appointments tomorrow",
            },
        },
        {
            "label": "Check in with patients who flagged concerns",
            "action": {
                "type": "prompt",
                "text": "Show me patients whose recent notes flagged concerns and draft check-in messages",
            },
        },
        {
            "label": "Review this week's no-shows",
            "action": {
                "type": "prompt",
                "text": "List patients who no-showed this week and suggest follow-up actions",
            },
        },
    ]
    for g in generic_pool:
        if len(suggestions) >= 3:
            break
        # avoid label duplicates
        if any(s["label"] == g["label"] for s in suggestions):
            continue
        suggestions.append(g)

    suggestions = suggestions[:3]

    return {
        "appointments": appointments,
        "tasks": tasks,
        "stats": {
            "patients_today": patients_today,
            "revenue_today": int(revenue[0]["total"]) if revenue else 0,
            "no_shows": no_shows[0]["cnt"] if no_shows else 0,
            "outstanding": int(outstanding[0]["total"]) if outstanding else 0,
        },
        # NEW
        "appointment_status_counts": status_counts,
        "invoices_outstanding": invoices_outstanding,
        "invoices_total_outstanding": invoices_total_outstanding,
        "revenue_this_week": revenue_snapshot,
        "weekly_trend": weekly_trend,
        "suggestions": suggestions,
        "conflicts": calendar_service.get_today_conflicts(today),
    }


@router.get("/calendar")
def get_calendar(week: str = None, doctor_id: str = None):
    """Get calendar appointments for a given week, optionally filtered by doctor.

    Args:
        week: ISO date string (YYYY-MM-DD) for any day in the desired week.
              Defaults to current week.
        doctor_id: Optional doctor ID to filter appointments.
    """
    if week:
        try:
            ref = date.fromisoformat(week)
        except ValueError:
            ref = date.today()
    else:
        ref = date.today()

    monday = ref - timedelta(days=ref.weekday())
    friday = monday + timedelta(days=4)

    params = [monday.isoformat(), friday.isoformat()]
    doctor_filter = ""
    if doctor_id:
        doctor_filter = " AND a.doctor_id = ?"
        params.append(doctor_id)

    appointments = query_db(
        f"""
        SELECT a.id, a.date, a.time, a.status, a.type, a.duration_mins,
               a.doctor_id, a.patient_id,
               p.first_name || ' ' || p.last_name AS patient_name,
               d.name AS doctor_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.date BETWEEN ? AND ?{doctor_filter}
        ORDER BY a.date, a.time
        """,  # nosec B608 - doctor_filter is a static string literal, not user input
        tuple(params),
    )

    # Map to day/slot indices for the calendar grid
    enriched = []
    for appt in appointments:
        appt_date = date.fromisoformat(appt["date"])
        day_index = (appt_date - monday).days
        if day_index < 0 or day_index > 4:
            continue

        # Convert time to slot index (8:00=0, 8:30=1, 9:00=2, etc.)
        try:
            t = datetime.strptime(appt["time"], "%H:%M")
            slot_index = (t.hour - 8) * 2 + (1 if t.minute >= 30 else 0)
        except Exception:
            slot_index = 0

        enriched.append({
            **appt,
            "day_index": day_index,
            "slot_index": slot_index,
        })

    return {
        "week_start": monday.isoformat(),
        "week_end": friday.isoformat(),
        "appointments": enriched,
    }


@router.get("/patients")
def list_patients(q: str = None):
    overdue_subq = """
        (SELECT COUNT(*) FROM invoices
         WHERE invoices.patient_id = patients.id AND invoices.status = 'overdue'
        ) AS overdue_invoice_count
    """
    if q:
        like = f"%{q}%"
        patients = query_db(
            f"""
            SELECT patients.*, {overdue_subq}
            FROM patients
            WHERE first_name LIKE ? OR last_name LIKE ?
               OR (first_name || ' ' || last_name) LIKE ?
            ORDER BY last_name
            LIMIT 50
            """,  # nosec B608 - overdue_subq is a static subquery defined above
            (like, like, like),
        )
    else:
        patients = query_db(
            f"SELECT patients.*, {overdue_subq} FROM patients ORDER BY last_name LIMIT 50"  # nosec B608
        )

    return {"patients": patients}


@router.get("/patients/{patient_id}")
def get_patient(patient_id: str):
    rows = query_db("SELECT * FROM patients WHERE id = ?", (patient_id,))
    if not rows:
        return {"error": "Patient not found"}

    patient = dict(rows[0])

    appointments = query_db(
        """
        SELECT a.*, d.name AS doctor_name
        FROM appointments a
        JOIN doctors d ON a.doctor_id = d.id
        WHERE a.patient_id = ?
        ORDER BY a.date DESC, a.time DESC
        LIMIT 10
        """,
        (patient_id,),
    )
    invoices = query_db(
        "SELECT * FROM invoices WHERE patient_id = ? ORDER BY issued_date DESC LIMIT 10",
        (patient_id,),
    )

    patient["appointments"] = appointments
    patient["invoices"] = invoices
    return patient


@router.get("/comms")
def list_comms():
    comms = query_db(
        """
        SELECT c.*, p.first_name || ' ' || p.last_name AS patient_name
        FROM communications c
        LEFT JOIN patients p ON c.patient_id = p.id
        ORDER BY c.sent_at DESC
        LIMIT 50
        """
    )

    enriched = []
    for c in comms:
        d = dict(c)
        try:
            dt = datetime.fromisoformat(d.get("sent_at", ""))
            d["sent_time"] = dt.strftime("%-I:%M%p").lower()
        except Exception:
            d["sent_time"] = d.get("sent_at", "")
        d["subject"] = d.get("type", "Message")
        d["direction"] = "inbound" if d.get("triggered_by") == "patient" else "outbound"
        enriched.append(d)

    return {"communications": enriched}


@router.get("/doctors")
def list_doctors():
    """List all doctors with summary stats."""
    doctors = query_db(
        """
        SELECT d.id, d.name, d.specialty, d.consultation_duration_mins,
               d.working_days, d.hours_start, d.hours_end
        FROM doctors d
        ORDER BY d.name
        """
    )

    today = date.today().isoformat()
    monday = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    friday = (date.today() - timedelta(days=date.today().weekday()) + timedelta(days=4)).isoformat()

    enriched = []
    for d in doctors:
        d = dict(d)
        # Parse working_days from JSON string
        try:
            d["working_days"] = json.loads(d["working_days"]) if isinstance(d["working_days"], str) else d["working_days"]
        except (json.JSONDecodeError, TypeError):
            d["working_days"] = []

        # Today's appointment count
        today_count = query_db(
            "SELECT COUNT(*) AS cnt FROM appointments WHERE doctor_id = ? AND date = ? AND status != 'cancelled'",
            (d["id"], today),
        )
        d["appointments_today"] = today_count[0]["cnt"] if today_count else 0

        # This week's appointment count
        week_count = query_db(
            "SELECT COUNT(*) AS cnt FROM appointments WHERE doctor_id = ? AND date BETWEEN ? AND ? AND status != 'cancelled'",
            (d["id"], monday, friday),
        )
        d["appointments_this_week"] = week_count[0]["cnt"] if week_count else 0

        enriched.append(d)

    return {"doctors": enriched}


@router.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: str):
    """Get doctor detail with schedule and patient list."""
    rows = query_db(
        "SELECT id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end FROM doctors WHERE id = ?",
        (doctor_id,),
    )
    if not rows:
        return {"error": "Doctor not found"}

    doctor = dict(rows[0])
    try:
        doctor["working_days"] = json.loads(doctor["working_days"]) if isinstance(doctor["working_days"], str) else doctor["working_days"]
    except (json.JSONDecodeError, TypeError):
        doctor["working_days"] = []

    today = date.today()
    monday = today - timedelta(days=today.weekday())
    friday = monday + timedelta(days=4)

    # This week's appointments
    appointments = query_db(
        """
        SELECT a.id, a.date, a.time, a.status, a.type, a.duration_mins,
               a.patient_id,
               p.first_name || ' ' || p.last_name AS patient_name
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.doctor_id = ? AND a.date BETWEEN ? AND ?
        ORDER BY a.date, a.time
        """,
        (doctor_id, monday.isoformat(), friday.isoformat()),
    )
    doctor["schedule"] = appointments

    # Stats
    month_start = today.replace(day=1).isoformat()
    month_patients = query_db(
        "SELECT COUNT(DISTINCT patient_id) AS cnt FROM appointments WHERE doctor_id = ? AND date >= ? AND status = 'completed'",
        (doctor_id, month_start),
    )
    doctor["patients_this_month"] = month_patients[0]["cnt"] if month_patients else 0

    total_appts = query_db(
        "SELECT COUNT(*) AS cnt FROM appointments WHERE doctor_id = ? AND status != 'cancelled'",
        (doctor_id,),
    )
    no_shows = query_db(
        "SELECT COUNT(*) AS cnt FROM appointments WHERE doctor_id = ? AND status = 'no-show'",
        (doctor_id,),
    )
    total = total_appts[0]["cnt"] if total_appts else 0
    ns = no_shows[0]["cnt"] if no_shows else 0
    doctor["no_show_rate"] = round(ns / total * 100, 1) if total > 0 else 0

    # Unique patients seen
    patient_list = query_db(
        """
        SELECT DISTINCT p.id, p.first_name, p.last_name, MAX(a.date) AS last_seen
        FROM appointments a
        JOIN patients p ON a.patient_id = p.id
        WHERE a.doctor_id = ? AND a.status = 'completed'
        GROUP BY p.id
        ORDER BY last_seen DESC
        LIMIT 30
        """,
        (doctor_id,),
    )
    doctor["patients"] = patient_list

    return doctor


@router.get("/availability")
def get_availability(doctor_id: str, date: str):
    result = cal_check_availability(doctor_id, date)
    # Also include doctor name for display
    doctors = query_db("SELECT name FROM doctors WHERE id = ?", (doctor_id,))
    if doctors:
        result["doctor_name"] = doctors[0]["name"]
    return result


class BookAppointmentRequest(BaseModel):
    patient_id: str
    doctor_id: str
    date: str
    time: str
    type: str = "standard"


@router.post("/appointments")
def create_appointment(req: BookAppointmentRequest):
    result = cal_book_appointment(
        patient_id=req.patient_id,
        doctor_id=req.doctor_id,
        date=req.date,
        time=req.time,
        type=req.type,
    )
    # Include doctor name in response for frontend display
    doctors = query_db("SELECT name FROM doctors WHERE id = ?", (req.doctor_id,))
    if doctors:
        result["doctor_name"] = doctors[0]["name"]
    return result


# ---------------------------------------------------------------------------
# TASK-047 — Doctor availability
# ---------------------------------------------------------------------------


class DoctorUnavailabilityRequest(BaseModel):
    start_date: str
    end_date: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    reason: str
    note: Optional[str] = None
    created_by: str = "user"


class DoctorScheduleUpdate(BaseModel):
    working_days: Optional[list[str]] = None
    hours_start: Optional[str] = None
    hours_end: Optional[str] = None
    consultation_duration_mins: Optional[int] = None


@router.post("/doctors/{doctor_id}/unavailability")
def post_doctor_unavailability(doctor_id: str, req: DoctorUnavailabilityRequest):
    """Mark a doctor unavailable for a window. Returns affected appointments."""
    # Validate doctor exists
    doctors = query_db("SELECT id FROM doctors WHERE id = ?", (doctor_id,))
    if not doctors:
        raise HTTPException(status_code=404, detail="Doctor not found")

    if req.reason not in VALID_UNAVAILABILITY_REASONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid reason '{req.reason}' — must be one of {sorted(VALID_UNAVAILABILITY_REASONS)}",
        )

    result = calendar_service.mark_doctor_unavailable(
        doctor_id=doctor_id,
        start_date=req.start_date,
        end_date=req.end_date,
        start_time=req.start_time,
        end_time=req.end_time,
        reason=req.reason,
        note=req.note,
        created_by=req.created_by,
    )
    return result


@router.delete("/doctors/{doctor_id}/unavailability/{unavailability_id}")
def delete_doctor_unavailability(doctor_id: str, unavailability_id: int):
    """Clear a specific unavailability row for a doctor."""
    rows = query_db(
        "SELECT id FROM doctor_unavailability WHERE id = ? AND doctor_id = ?",
        (unavailability_id, doctor_id),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Unavailability row not found")
    return calendar_service.clear_doctor_unavailability(unavailability_id)


@router.patch("/doctors/{doctor_id}")
def patch_doctor(doctor_id: str, req: DoctorScheduleUpdate):
    """Update a doctor's base recurring schedule (partial updates allowed)."""
    result = calendar_service.update_doctor_schedule(
        doctor_id=doctor_id,
        working_days=req.working_days,
        hours_start=req.hours_start,
        hours_end=req.hours_end,
        consultation_duration_mins=req.consultation_duration_mins,
    )
    if isinstance(result, dict) and result.get("error"):
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/doctors/{doctor_id}/availability")
def get_doctor_availability_window(doctor_id: str, start: str, end: str):
    """Return recurring schedule + unavailability rows overlapping [start, end]."""
    rows = query_db(
        "SELECT id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end FROM doctors WHERE id = ?",
        (doctor_id,),
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Doctor not found")

    doc = dict(rows[0])
    try:
        working_days = json.loads(doc["working_days"]) if isinstance(doc["working_days"], str) else doc["working_days"]
    except (json.JSONDecodeError, TypeError):
        working_days = []

    recurring = {
        "working_days": working_days,
        "hours_start": doc["hours_start"],
        "hours_end": doc["hours_end"],
        "consultation_duration_mins": doc["consultation_duration_mins"],
    }
    unavailability = calendar_service.list_doctor_unavailability(doctor_id, start, end)
    return {
        "doctor_id": doctor_id,
        "doctor_name": doc.get("name"),
        "recurring": recurring,
        "unavailability": unavailability,
    }
