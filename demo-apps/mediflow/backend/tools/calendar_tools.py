"""Calendar tool wrappers for the Strands agent."""

import asyncio
from strands import tool
from backend.services import calendar_service


@tool
def check_availability(doctor_id: str, date: str, time_range: str = "") -> dict:
    """Check available appointment slots for a doctor on a given date.

    Args:
        doctor_id: Doctor ID (e.g. 'dr-chen', 'dr-patel', 'dr-kim', 'dr-nguyen')
        date: Date in YYYY-MM-DD format
        time_range: Optional - 'morning', 'afternoon', or empty for full day
    """
    return calendar_service.check_availability(doctor_id, date, time_range or None)


@tool
def book_appointment(
    patient_id: str, doctor_id: str, date: str, time: str, type: str = "standard"
) -> dict:
    """Book a new appointment for a patient with a doctor.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        doctor_id: Doctor ID (e.g. 'dr-chen')
        date: Date in YYYY-MM-DD format
        time: Time in HH:MM format (e.g. '09:30')
        type: Appointment type - 'standard', 'follow_up', 'urgent', or 'new_patient'
    """
    return calendar_service.book_appointment(patient_id, doctor_id, date, time, type)


@tool
def reschedule_appointment(appointment_id: str, new_date: str, new_time: str) -> dict:
    """Reschedule an existing appointment to a new date and/or time.

    Args:
        appointment_id: The appointment ID to reschedule (e.g. 'apt-abc12345')
        new_date: New date in YYYY-MM-DD format
        new_time: New time in HH:MM format
    """
    return calendar_service.reschedule_appointment(appointment_id, new_date, new_time)


@tool
def cancel_appointment(appointment_id: str, reason: str = "") -> dict:
    """Cancel an existing appointment.

    Args:
        appointment_id: The appointment ID to cancel (e.g. 'apt-abc12345')
        reason: Optional reason for cancellation
    """
    return calendar_service.cancel_appointment(appointment_id, reason or None)


@tool
def list_upcoming_appointments(
    doctor_id: str = "", patient_id: str = "", days: int = 7
) -> list:
    """List upcoming appointments within a number of days from today.

    Args:
        doctor_id: Optional doctor ID to filter by
        patient_id: Optional patient ID to filter by
        days: Number of days ahead to look (default 7)
    """
    return calendar_service.list_upcoming(
        doctor_id=doctor_id or None,
        patient_id=patient_id or None,
        days=days,
    )


@tool
def get_appointment_details(appointment_id: str) -> dict:
    """Get full details of a specific appointment including patient and doctor info.

    Args:
        appointment_id: The appointment ID (e.g. 'apt-abc12345')
    """
    return calendar_service.get_appointment_details(appointment_id)


@tool
def mark_doctor_unavailable(
    doctor_id: str,
    start_date: str,
    end_date: str,
    start_time: str = "",
    end_time: str = "",
    reason: str = "sick",
    note: str = "",
) -> dict:
    """Mark a doctor as unavailable for a window of time (sick day, leave, blocked).

    Use this when a doctor calls in sick, takes leave, or blocks out time. The
    tool returns the list of affected appointments so you can offer to
    reschedule them in the same turn.

    Args:
        doctor_id: Doctor ID (e.g. 'dr-patel', 'dr-chen')
        start_date: First unavailable day in YYYY-MM-DD format
        end_date: Last unavailable day in YYYY-MM-DD format (inclusive, same as start for a single day)
        start_time: Optional HH:MM — leave empty for a full day
        end_time: Optional HH:MM — leave empty for a full day
        reason: One of 'sick', 'leave', 'other'
        note: Optional freeform note describing the reason
    """
    return calendar_service.mark_doctor_unavailable(
        doctor_id=doctor_id,
        start_date=start_date,
        end_date=end_date,
        start_time=start_time or None,
        end_time=end_time or None,
        reason=reason,
        note=note or None,
        created_by="agent",
    )


@tool
def get_doctor_conflicts(date: str = "") -> dict:
    """Return today's (or a given date's) doctor-unavailability conflicts with affected appointments.

    Args:
        date: Optional YYYY-MM-DD date. Empty string means today.
    """
    conflicts = calendar_service.get_today_conflicts(date or None)
    return {"date": date or None, "conflicts": conflicts}


@tool
def clear_doctor_unavailability(unavailability_id: int) -> dict:
    """Clear (delete) a previously-recorded doctor unavailability row.

    Args:
        unavailability_id: The id of the unavailability row to delete.
    """
    return calendar_service.clear_doctor_unavailability(unavailability_id)


@tool
def update_doctor_schedule(
    doctor_id: str,
    working_days: list[str] = None,
    hours_start: str = "",
    hours_end: str = "",
    consultation_duration_mins: int = 0,
) -> dict:
    """Update a doctor's base (recurring) schedule — working days, hours, consultation length.

    Args:
        doctor_id: Doctor ID (e.g. 'dr-chen')
        working_days: Optional list of weekday names (e.g. ['Monday', 'Wednesday'])
        hours_start: Optional HH:MM start of day
        hours_end: Optional HH:MM end of day
        consultation_duration_mins: Optional consultation length in minutes (0 = unchanged)
    """
    return calendar_service.update_doctor_schedule(
        doctor_id=doctor_id,
        working_days=working_days if working_days else None,
        hours_start=hours_start or None,
        hours_end=hours_end or None,
        consultation_duration_mins=consultation_duration_mins or None,
    )


@tool
async def reschedule_all_patients_for_doctor(doctor_id: str, date: str):
    """Bulk-reschedule every scheduled appointment for a doctor on a given date.

    Use this ONCE — never loop over patients with reschedule_appointment — when
    a doctor is unavailable for a day (called in sick, leave, etc.). The tool
    reassigns each affected appointment to the nearest available slot on
    another doctor, drafts a patient SMS for each, and surfaces a single
    cascade card in the chat UI.

    Args:
        doctor_id: Doctor ID whose patients need rescheduling (e.g. 'dr-patel')
        date: Date in YYYY-MM-DD format
    """
    result = await asyncio.get_event_loop().run_in_executor(
        None, calendar_service.reschedule_all_patients_for_doctor, doctor_id, date,
    )
    # Emit a single UI event so the frontend renders the Option-C cascade card.
    yield {"ui_action": "reschedule_cascade", **result}
    # Also yield the final textual summary so the LLM receives it as tool output.
    yield {
        "total_affected": result["total_affected"],
        "messages_drafted": result["messages_drafted"],
        "entries": [
            {
                "patient_name": e["patient_name"],
                "new_doctor_name": e["new_doctor_name"],
                "new_time": e["new_time"],
            }
            for e in result["entries"]
        ],
    }
