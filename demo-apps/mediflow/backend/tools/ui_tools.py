"""UI control tools — async generator tools that yield SSE ui_action events.

These tools let the agent visually control the webapp: navigating views,
selecting patients/doctors, opening booking flows, and highlighting elements.
Each yielded dict becomes a ToolStreamEvent that the SSE endpoint forwards
to the frontend in real-time.
"""

import asyncio
import json
import uuid
from strands import tool
from strands.types.tools import ToolContext
from backend.services import comms_service
from backend.services.database import execute_db, query_db
from backend.tools.comms_tools import _sanitize_comms_result


async def _nav(view: str, params: dict = None):
    """Emit pre_highlight → pause → navigate sequence."""
    yield {"ui_action": "pre_highlight", "target": "nav", "id": view, "duration": 1000}
    await asyncio.sleep(1.0)
    nav = {"ui_action": "navigate", "view": view}
    if params:
        nav["params"] = params
    yield nav
    await asyncio.sleep(0.4)


@tool(context=True)
async def navigate_to_view(view: str, tool_context: ToolContext = None):
    """Navigate the receptionist's screen to a specific view.

    Args:
        view: View name - 'today', 'calendar', 'patients', 'practitioners', 'comms', 'insights'
    """
    async for event in _nav(view):
        yield event


@tool(context=True)
async def select_patient(patient_id: str, patient_name: str = "", tool_context: ToolContext = None):
    """Select and show a patient's details on screen. Navigates to Patients view automatically.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        patient_name: Optional display name for UI feedback
    """
    async for event in _nav("patients"):
        yield event
    yield {"ui_action": "pre_highlight", "target": "list_item", "id": patient_id, "duration": 800}
    await asyncio.sleep(0.8)
    yield {"ui_action": "select_patient", "patient_id": patient_id, "patient_name": patient_name}
    await asyncio.sleep(0.3)
    yield {"ui_action": "illuminate", "type": "patient", "id": patient_id, "duration": 800}


@tool(context=True)
async def select_doctor(doctor_id: str, doctor_name: str = "", tool_context: ToolContext = None):
    """Select and show a doctor's details on screen. Navigates to Practitioners view automatically.

    Args:
        doctor_id: Doctor ID (e.g. 'dr-chen', 'dr-patel', 'dr-kim', 'dr-nguyen')
        doctor_name: Optional display name for UI feedback
    """
    async for event in _nav("practitioners"):
        yield event
    yield {"ui_action": "pre_highlight", "target": "list_item", "id": doctor_id, "duration": 800}
    await asyncio.sleep(0.8)
    yield {"ui_action": "select_doctor", "doctor_id": doctor_id, "doctor_name": doctor_name}
    await asyncio.sleep(0.3)
    yield {"ui_action": "illuminate", "type": "doctor", "id": doctor_id, "duration": 800}


@tool(context=True)
async def open_booking_for_patient(patient_id: str, doctor_id: str = "", tool_context: ToolContext = None):
    """Open the appointment booking panel for a patient. Navigates to the patient and opens the booking flow.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        doctor_id: Optional pre-selected doctor ID
    """
    async for event in _nav("patients"):
        yield event
    yield {"ui_action": "select_patient", "patient_id": patient_id}
    await asyncio.sleep(0.4)
    yield {"ui_action": "pre_highlight", "target": "button", "id": "book-appointment", "duration": 800}
    await asyncio.sleep(0.8)
    yield {"ui_action": "open_booking", "patient_id": patient_id, "doctor_id": doctor_id}
    await asyncio.sleep(0.3)
    yield {"ui_action": "illuminate", "type": "booking_panel", "id": patient_id, "duration": 1000}


@tool(context=True)
async def show_patient_tab(patient_id: str, tab: str, tool_context: ToolContext = None):
    """Switch to a specific tab in the patient detail view.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        tab: Tab name - 'appointments', 'invoices', 'messages', 'memory'
    """
    async for event in _nav("patients"):
        yield event
    yield {"ui_action": "select_patient", "patient_id": patient_id}
    await asyncio.sleep(0.3)
    yield {"ui_action": "pre_highlight", "target": "tab", "id": tab, "duration": 800}
    await asyncio.sleep(0.8)
    yield {"ui_action": "set_patient_tab", "patient_id": patient_id, "tab": tab}


@tool(context=True)
async def show_calendar_for_doctor(doctor_id: str, tool_context: ToolContext = None):
    """Navigate to the Calendar view filtered to a specific doctor's schedule.

    Args:
        doctor_id: Doctor ID (e.g. 'dr-chen', 'dr-patel', 'dr-kim', 'dr-nguyen')
    """
    async for event in _nav("calendar", {"doctorId": doctor_id}):
        yield event
    yield {"ui_action": "illuminate", "type": "calendar_filter", "id": doctor_id, "duration": 800}


@tool(context=True)
async def mark_doctor_sick_in_ui(
    doctor_id: str,
    note: str = "",
    tool_context: ToolContext = None,
):
    """Mark a doctor as unavailable (sick day, full day today) with a
    visible, theatrical UI flow. Use this INSTEAD of `mark_doctor_unavailable`
    when the receptionist reports a doctor calling in sick: the agent
    navigates to Practitioners, selects the doctor, switches to the
    Availability tab, clicks "+ Add time off", fills out the form (reason
    + note), then submits — the receptionist sees every step happen.

    The form submission hits the real `POST /api/data/doctors/{id}/
    unavailability` endpoint, so a proper row is persisted. Returns the
    row + affected appointments so the agent can follow up with
    `reschedule_all_patients_for_doctor`.

    Args:
        doctor_id: Doctor ID (e.g. 'dr-patel')
        note: Optional freeform note (e.g. 'Called in sick this morning').
    """
    from backend.services import calendar_service
    from datetime import date as _date

    today_iso = _date.today().isoformat()
    note_text = note or "Called in sick today"

    # 1. Navigate to Practitioners
    async for event in _nav("practitioners"):
        yield event

    # 2. Select the doctor (pre-highlight → select → illuminate)
    doctors = query_db("SELECT id, name FROM doctors WHERE id = ?", (doctor_id,))
    doctor_name = doctors[0]["name"] if doctors else doctor_id
    yield {"ui_action": "pre_highlight", "target": "list_item", "id": doctor_id, "duration": 800}
    await asyncio.sleep(0.8)
    yield {"ui_action": "select_doctor", "doctor_id": doctor_id, "doctor_name": doctor_name}
    await asyncio.sleep(0.4)

    # 3. Switch to the Availability tab
    yield {"ui_action": "pre_highlight", "target": "tab", "id": "availability", "duration": 600}
    await asyncio.sleep(0.6)
    yield {"ui_action": "set_doctor_tab", "doctor_id": doctor_id, "tab": "availability"}
    await asyncio.sleep(0.6)

    # 4. Pre-highlight the "+ Add time off" button, then open the form
    yield {"ui_action": "pre_highlight", "target": "button", "id": "add-time-off", "duration": 700}
    await asyncio.sleep(0.7)
    yield {"ui_action": "open_time_off_form", "doctor_id": doctor_id}
    await asyncio.sleep(0.5)

    # 5. Fill the form visibly — reason dropdown first, note second, so the
    #    receptionist sees the fields populate in sequence.
    yield {
        "ui_action": "fill_time_off_form",
        "doctor_id": doctor_id,
        "fields": {"reason": "sick"},
    }
    await asyncio.sleep(0.6)
    yield {
        "ui_action": "fill_time_off_form",
        "doctor_id": doctor_id,
        "fields": {"note": note_text},
    }
    await asyncio.sleep(0.6)

    # 6. Submit — frontend hits the real endpoint; the row appears via the
    #    form's own fetchUnavail() on success.
    yield {"ui_action": "submit_time_off_form", "doctor_id": doctor_id}
    # Give the POST round-trip a moment to complete before the LLM moves on
    await asyncio.sleep(1.2)

    # 7. Read back the freshly-inserted row for the LLM result (the form's
    #    POST is idempotent — mark_doctor_unavailable returns existing row
    #    on duplicate, so this is safe to co-read).
    result = calendar_service.mark_doctor_unavailable(
        doctor_id=doctor_id,
        start_date=today_iso,
        end_date=today_iso,
        start_time=None,
        end_time=None,
        reason="sick",
        note=note_text,
        created_by="agent",
    )
    yield {
        "unavailability_id": result.get("unavailability_id"),
        "affected_appointments": result.get("affected_appointments", []),
        "doctor_id": doctor_id,
        "doctor_name": doctor_name,
        "date": today_iso,
    }


@tool(context=True)
async def highlight_element(element_type: str, element_id: str, tool_context: ToolContext = None):
    """Highlight a UI element to draw the receptionist's attention to it.

    Args:
        element_type: Type of element - 'patient', 'doctor', 'appointment', 'invoice', 'nav_item'
        element_id: The element identifier
    """
    yield {"ui_action": "illuminate", "type": element_type, "id": element_id, "duration": 1200}


@tool(context=True)
async def send_patient_message(patient_id: str, patient_name: str, message: str, channel: str = "", tool_context: ToolContext = None):
    """Send a message to a patient AND show it appearing on screen in real time.

    IMPORTANT: Before calling this, first call show_patient_tab(patient_id, "messages") so the
    receptionist can see the Messages tab. Then call this tool to send and display the message.

    Args:
        patient_id: Patient ID (e.g. 'pat-001')
        patient_name: Patient's full name (e.g. 'Fatima Al-Hassan')
        message: Message text to send
        channel: Optional - 'phone', 'email', or 'sms'. Defaults to patient preference.
    """
    # Send via backend
    result = comms_service.send_message(patient_id, message, channel or None)
    sanitized = _sanitize_comms_result(result)
    msg_id = sanitized.get("id", f"c-agent-{id(result)}")
    channel_used = sanitized.get("channel", "sms")

    # Short pause so the user sees the tab is ready
    await asyncio.sleep(0.5)

    # Show the message appearing with "sending" status
    yield {
        "ui_action": "add_message",
        "patient_id": patient_id,
        "patient_name": patient_name,
        "message": {
            "id": msg_id,
            "patient_name": patient_name,
            "content": message,
            "sent_time": "Just now",
            "status": "sending",
            "triggered_by": "agent",
            "direction": "outbound",
            "channel": channel_used,
        },
    }
    await asyncio.sleep(1.2)

    # Update status to delivered
    yield {
        "ui_action": "update_message",
        "message_id": msg_id,
        "updates": {"status": "delivered"},
    }
    await asyncio.sleep(0.3)
    yield {"ui_action": "illuminate", "type": "message", "id": msg_id, "duration": 800}


@tool(context=True)
async def stage_skill_approval(
    skill_id: str = "",
    name: str = "",
    summary: str = "",
    items: list = None,
    item_count: int = 0,
    tool_context: ToolContext = None,
):
    """Stage an ad-hoc batch Skill for human approval. MUST be called
    BEFORE taking any batch action that affects more than one record.

    Use this whenever the receptionist asks you to run a Skill that
    operates over a population — e.g. "chase all overdue invoices",
    "run the overdue invoice chase", "send weekly check-in messages",
    "remind everyone about tomorrow's appointments". Call this INSTEAD
    of describing the plan in prose and asking "shall I proceed?" — a
    text summary is NOT a substitute: the UI only shows the approval
    card when this tool is called.

    This tool emits a ``skill_approval`` rich card in the chat with the
    sample recipients and a count, and pauses for the user to Approve
    or Cancel. Do NOT call this for single-item skills (e.g. "chase
    Sarah's invoice") — act directly in that case.

    Args:
        skill_id: The Skill ID to stage, if known (e.g. 'sk-u-batch').
            Optional — if the skill does not yet exist as a row in the
            Skills table, pass an empty string and fill in ``name`` /
            ``summary`` / ``items`` directly.
        name: Display name for the card (e.g. "Overdue Invoice Chase").
            Required when ``skill_id`` is not provided or not found.
        summary: Short human-readable description of what will happen
            (e.g. "Send personalised reminders to 4 patients with
            outstanding invoices."). Required when ``skill_id`` is not
            provided.
        items: Sample of affected items to preview on the card. Each
            item is a dict with ``label`` (patient/record name) and
            optional ``detail`` (e.g. "$85 · 1st chase"). Pass 3-5
            items for the preview.
        item_count: Total number of items that will be acted on.
            Defaults to ``len(items)`` when not provided.
    """
    items = items or []

    sk_name = name or ""
    sk_description = summary or ""
    sk_trigger = ""

    # Name → id fallback: if the agent passed a name but no skill_id,
    # try to resolve it from the DB so Approve & Run has a real target.
    if not skill_id and sk_name:
        matches = query_db(
            "SELECT id FROM skills WHERE LOWER(name) = LOWER(?) LIMIT 1",
            (sk_name,),
        )
        if not matches:
            matches = query_db(
                "SELECT id FROM skills WHERE LOWER(name) LIKE LOWER(?) LIMIT 1",
                (f"%{sk_name}%",),
            )
        if matches:
            skill_id = matches[0]["id"]

    if skill_id:
        skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
        if skills:
            sk = skills[0]
            sk_name = sk_name or sk["name"]
            sk_description = sk_description or sk.get("description", "") or ""
            sk_trigger = sk.get("trigger_description", "") or ""

            # Auto-resolve batch from hint if caller didn't supply items
            if not items:
                hint = (sk.get("batch_selection_hint") or "").lower()
                if "invoice" in hint or "outstanding" in hint or "overdue" in hint:
                    rows = query_db(
                        "SELECT i.id AS invoice_id, i.amount, i.amount_paid, i.chase_count, "
                        "p.first_name, p.last_name "
                        "FROM invoices i LEFT JOIN patients p ON i.patient_id = p.id "
                        "WHERE i.status = 'outstanding' ORDER BY i.due_date LIMIT 10"
                    )
                    for r in rows:
                        outstanding = (r.get("amount") or 0) - (r.get("amount_paid") or 0)
                        items.append({
                            "id": r["invoice_id"],
                            "label": f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or r["invoice_id"],
                            "detail": f"${outstanding:.0f} · chase {(r.get('chase_count') or 0) + 1}",
                        })
                elif "patient" in hint or "appointment" in hint or "reminder" in hint:
                    rows = query_db(
                        "SELECT a.id AS appointment_id, a.date, a.time, "
                        "p.first_name, p.last_name "
                        "FROM appointments a LEFT JOIN patients p ON a.patient_id = p.id "
                        "WHERE a.status = 'scheduled' AND a.reminder_sent = 0 "
                        "ORDER BY a.date, a.time LIMIT 10"
                    )
                    for r in rows:
                        nm = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
                        items.append({
                            "id": r["appointment_id"],
                            "label": nm or r["appointment_id"],
                            "detail": f"{r.get('date')} {r.get('time')}",
                        })

    if not sk_name:
        yield {"status": "error", "error": "stage_skill_approval requires either skill_id or name."}
        return

    # Ad-hoc skill: agent named a skill that doesn't exist as a DB row yet.
    # Persist it so Approve & Run (/api/skills/{id}/run) has a real target.
    # The approval-card items are cached on the row so the run-stream can
    # emit per-item progress events without re-resolving from a hint.
    if not skill_id:
        skill_id = f"sk-adhoc-{uuid.uuid4().hex[:10]}"
        execute_db(
            """INSERT INTO skills
               (id, name, description, trigger_description,
                batch_selection_hint, cached_items, status, scheduled)
               VALUES (?, ?, ?, ?, ?, ?, 'enabled', 0)""",
            (
                skill_id,
                sk_name,
                sk_description,
                sk_trigger,
                "adhoc",
                json.dumps(items),
            ),
        )

    total = item_count or len(items)

    await asyncio.sleep(0.3)
    yield {
        "ui_action": "skill_approval",
        "skill_id": skill_id or "",
        "name": sk_name,
        "description": sk_description,
        "trigger_description": sk_trigger,
        "items": items[:5],
        "item_count": total,
    }
