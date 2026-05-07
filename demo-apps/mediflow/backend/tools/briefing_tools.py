"""Briefing tools — schedule overview and pathology results for Morning Briefing skill."""

from datetime import datetime

from strands import tool
from backend.services.database import query_db


@tool
def get_doctor_schedule(doctor_id: str = "", date: str = "") -> dict | list:
    """Get a doctor's appointment schedule for a given date.

    Args:
        doctor_id: Doctor ID (e.g. 'dr-chen'). If empty, returns all doctors working today.
        date: Date in YYYY-MM-DD format. Defaults to today.
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")
    target_day_name = datetime.strptime(target_date, "%Y-%m-%d").strftime("%A")

    if doctor_id:
        doctor = query_db("SELECT * FROM doctors WHERE id = ?", (doctor_id,))
        if not doctor:
            return {"error": "Doctor not found", "doctor_id": doctor_id}
        d = doctor[0]
        appointments = query_db(
            "SELECT id, patient_id, time, type, status, notes "
            "FROM appointments WHERE doctor_id = ? AND date = ? AND status = 'scheduled' "
            "ORDER BY time",
            (doctor_id, target_date),
        )
        return {
            "doctor_id": d["id"],
            "doctor_name": d["name"],
            "date": target_date,
            "working": target_day_name in (d.get("working_days") or ""),
            "hours_start": d.get("hours_start"),
            "hours_end": d.get("hours_end"),
            "appointment_count": len(appointments),
            "first_appointment": appointments[0]["time"] if appointments else None,
            "appointments": appointments,
        }

    doctors = query_db("SELECT * FROM doctors ORDER BY name")
    working_doctors = [d for d in doctors if target_day_name in (d.get("working_days") or "")]
    results = []
    for d in working_doctors:
        appts = query_db(
            "SELECT MIN(time) AS first_time, COUNT(*) AS cnt "
            "FROM appointments WHERE doctor_id = ? AND date = ? AND status = 'scheduled'",
            (d["id"], target_date),
        )
        cnt = appts[0]["cnt"] if appts else 0
        first_time = (appts[0].get("first_time") if appts else None) or d.get("hours_start") or "09:00"
        results.append({
            "doctor_id": d["id"],
            "doctor_name": d["name"],
            "specialty": d.get("specialty"),
            "appointment_count": cnt,
            "first_appointment": first_time,
        })
    return {"date": target_date, "doctors_working": results}


@tool
def check_pathology_results(date: str = "", patient_id: str = "") -> dict:
    """Check overnight pathology/lab results that need review.

    Args:
        date: Date in YYYY-MM-DD format. Defaults to today (shows results received overnight).
        patient_id: Optional patient ID to filter results for a specific patient.
    """
    target_date = date or datetime.now().strftime("%Y-%m-%d")

    if patient_id:
        rows = query_db(
            "SELECT * FROM pathology_results WHERE patient_id = ? ORDER BY received_at DESC",
            (patient_id,),
        )
    else:
        rows = query_db(
            "SELECT pr.*, p.first_name || ' ' || p.last_name AS patient_name "
            "FROM pathology_results pr "
            "JOIN patients p ON p.id = pr.patient_id "
            "WHERE pr.received_date = ? "
            "ORDER BY pr.flagged DESC, pr.received_at DESC",
            (target_date,),
        )

    if not rows:
        return {"date": target_date, "results": [], "message": "No pathology results for this date."}

    return {
        "date": target_date,
        "total_results": len(rows),
        "flagged_count": sum(1 for r in rows if r.get("flagged")),
        "results": rows,
    }
