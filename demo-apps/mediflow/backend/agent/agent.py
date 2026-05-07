"""Strands Agent configuration for the medical receptionist."""

from datetime import datetime, timedelta

from strands import Agent
from strands.models.bedrock import BedrockModel

from backend.config import settings
from backend.agent.prompts import (
    DAY1_SYSTEM_PROMPT, DAY2_SYSTEM_PROMPT,
    PATIENT_MEMORY_SECTION, ACTIVE_SKILLS_SECTION,
    VIEW_CONTEXT_SECTION, CONVERSATION_HISTORY_SECTION,
)
from backend.agent.tool_logging_hook import ToolCallLoggingHook

# Import all tools
from backend.tools.calendar_tools import (
    check_availability,
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
    list_upcoming_appointments,
    get_appointment_details,
    mark_doctor_unavailable,
    get_doctor_conflicts,
    clear_doctor_unavailability,
    update_doctor_schedule,
    reschedule_all_patients_for_doctor,
)
from backend.tools.patient_tools import (
    search_patients,
    get_patient,
    get_patient_history,
    update_patient_notes,
    get_patient_memories,
    record_patient_memory,
)
from backend.tools.billing_tools import (
    get_outstanding_invoices,
    get_invoice,
    record_payment,
    send_payment_reminder,
)
from backend.tools.comms_tools import (
    send_appointment_reminder,
    send_message,
    get_comms_history,
)
from backend.tools.practice_tools import get_practice_info, get_doctor_info
from backend.tools.briefing_tools import get_doctor_schedule, check_pathology_results
from backend.tools.skill_tools import (
    get_pending_skills,
    enable_skill,
)
from backend.tools.ui_tools import (
    navigate_to_view,
    select_patient as ui_select_patient,
    select_doctor as ui_select_doctor,
    open_booking_for_patient,
    show_patient_tab,
    show_calendar_for_doctor,
    mark_doctor_sick_in_ui,
    highlight_element,
    send_patient_message,
    stage_skill_approval,
)

ALL_TOOLS = [
    check_availability,
    book_appointment,
    reschedule_appointment,
    cancel_appointment,
    list_upcoming_appointments,
    get_appointment_details,
    mark_doctor_unavailable,
    get_doctor_conflicts,
    clear_doctor_unavailability,
    update_doctor_schedule,
    reschedule_all_patients_for_doctor,
    search_patients,
    get_patient,
    get_patient_history,
    update_patient_notes,
    get_outstanding_invoices,
    get_invoice,
    record_payment,
    send_payment_reminder,
    send_appointment_reminder,
    send_message,
    get_comms_history,
    get_practice_info,
    get_doctor_info,
    get_doctor_schedule,
    check_pathology_results,
    get_pending_skills,
    enable_skill,
    # UI control tools
    navigate_to_view,
    ui_select_patient,
    ui_select_doctor,
    open_booking_for_patient,
    show_patient_tab,
    show_calendar_for_doctor,
    mark_doctor_sick_in_ui,
    highlight_element,
    send_patient_message,
    stage_skill_approval,
]

# Registry: tool name → function. Used to resolve skill tool_config dynamically.
TOOL_REGISTRY = {
    "check_availability": check_availability,
    "book_appointment": book_appointment,
    "reschedule_appointment": reschedule_appointment,
    "cancel_appointment": cancel_appointment,
    "list_upcoming_appointments": list_upcoming_appointments,
    "get_appointment_details": get_appointment_details,
    "mark_doctor_unavailable": mark_doctor_unavailable,
    "get_doctor_conflicts": get_doctor_conflicts,
    "clear_doctor_unavailability": clear_doctor_unavailability,
    "update_doctor_schedule": update_doctor_schedule,
    "reschedule_all_patients_for_doctor": reschedule_all_patients_for_doctor,
    "search_patients": search_patients,
    "get_patient": get_patient,
    "get_patient_history": get_patient_history,
    "update_patient_notes": update_patient_notes,
    "get_patient_memories": get_patient_memories,
    "record_patient_memory": record_patient_memory,
    "get_outstanding_invoices": get_outstanding_invoices,
    "get_invoice": get_invoice,
    "record_payment": record_payment,
    "send_payment_reminder": send_payment_reminder,
    "send_appointment_reminder": send_appointment_reminder,
    "send_message": send_message,
    "get_comms_history": get_comms_history,
    "get_practice_info": get_practice_info,
    "get_doctor_info": get_doctor_info,
    "get_doctor_schedule": get_doctor_schedule,
    "check_pathology_results": check_pathology_results,
    "get_pending_skills": get_pending_skills,
    "enable_skill": enable_skill,
}


def resolve_skill_tools(skills: list[dict]) -> list:
    """Resolve tool names from enabled skills' tool_config into functions.

    Returns only tools not already in ALL_TOOLS (additive tools from skills).
    """
    import json
    base_set = set(id(t) for t in ALL_TOOLS)
    extra = []
    seen = set()
    for sk in skills:
        raw = sk.get("tool_config") or "[]"
        try:
            names = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            continue
        for name in names:
            if name in seen:
                continue
            seen.add(name)
            fn = TOOL_REGISTRY.get(name)
            if fn and id(fn) not in base_set:
                extra.append(fn)
    return extra


def _build_week_dates() -> str:
    """Return an explicit weekday → absolute-date lookup covering today
    through the next 13 days. The model otherwise drifts by a day on
    relative references like 'Thursday morning' — anchoring each
    weekday to a concrete date eliminates the ambiguity.
    """
    today = datetime.now().date()
    lines = ["- This week's dates (use these verbatim when the user says a weekday name):"]
    for offset in range(14):
        d = today + timedelta(days=offset)
        tag = " (today)" if offset == 0 else " (tomorrow)" if offset == 1 else ""
        lines.append(f"  - {d.strftime('%A')}, {d.strftime('%B %d, %Y')} = {d.isoformat()}{tag}")
    return "\n".join(lines) + "\n"


def create_agent(
    day: int = 1,
    patient_context: str | None = None,
    active_skills: list[dict] | None = None,
    view_context: dict | None = None,
    conversation_history: list[dict] | None = None,
    session_id: str | None = None,
) -> Agent:
    """Create and return a configured Strands Agent.

    Args:
        day: 1 for Day 1 prompt, 2 for Day 2 prompt.
        patient_context: Formatted patient memories string to inject into the prompt.
        active_skills: Enabled non-scheduled skills to inject as behavioral directives.
        view_context: Current UI view info, e.g. {"view": "patients", "params": {"patientId": "pat-001"}}.
        conversation_history: Prior conversation turns as [{"role": "user"|"assistant", "content": "..."}].
        session_id: When provided, registers a hook that logs every tool call to tool_call_log.
    """
    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_default_region,
    )

    prompt_template = DAY1_SYSTEM_PROMPT if day == 1 else DAY2_SYSTEM_PROMPT

    # Build the patient memories section (or empty string)
    patient_memories = ""
    if patient_context:
        patient_memories = PATIENT_MEMORY_SECTION.format(memories=patient_context)

    # Build active skills section (enabled, non-scheduled skills)
    active_skills_str = ""
    if active_skills:
        skill_blocks = []
        for sk in active_skills:
            block = f"### {sk['name']}\n**Trigger:** {sk.get('trigger_description', 'On demand')}\n{sk.get('agent_prompt_template', '')}"
            skill_blocks.append(block)
        active_skills_str = ACTIVE_SKILLS_SECTION.format(skills="\n\n".join(skill_blocks))

    # Build the view context section (or empty string)
    view_ctx_str = ""
    if view_context:
        view_ctx_str = VIEW_CONTEXT_SECTION.format(
            view_description=_format_view_context(view_context)
        )

    # Build the conversation history section (or empty string)
    history_str = ""
    if conversation_history:
        turns = "\n".join(
            f"{'Receptionist' if t['role'] == 'user' else 'You'}: {t['content']}"
            for t in conversation_history[-20:]  # last 20 turns max
        )
        history_str = CONVERSATION_HISTORY_SECTION.format(turns=turns)

    system_prompt = prompt_template.format(
        current_date=datetime.now().strftime("%A, %B %d, %Y"),
        week_dates=_build_week_dates(),
        patient_memories=patient_memories,
        active_skills=active_skills_str,
        view_context=view_ctx_str,
        conversation_history=history_str,
    )

    tools = ALL_TOOLS + resolve_skill_tools(active_skills) if active_skills else ALL_TOOLS

    hooks = [ToolCallLoggingHook(session_id)] if session_id else None

    return Agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools,
        hooks=hooks,
    )


# View name → human-readable descriptions
_VIEW_LABELS = {
    "today": "the Today dashboard (daily overview)",
    "calendar": "the Calendar view",
    "patients": "the Patients view",
    "practitioners": "the Practitioners view",
    "comms": "the Communications view",
    "insights": "the Insights dashboard",
}


def _format_view_context(ctx: dict) -> str:
    """Turn frontend view context into a readable string for the prompt."""
    view = ctx.get("view", "unknown")
    params = ctx.get("params") or {}
    desc = _VIEW_LABELS.get(view, f"the {view} view")

    details = []
    if params.get("patientName"):
        details.append(f"Patient '{params['patientName']}' is selected")
    if params.get("patientId"):
        details.append(f"(ID: {params['patientId']})")
    if params.get("tab"):
        details.append(f"on the {params['tab'].title()} tab")
    if params.get("doctorId"):
        details.append(f"filtered to doctor ID {params['doctorId']}")
    if params.get("doctorName"):
        details.append(f"filtered to {params['doctorName']}")

    if details:
        return f"{desc} — {' '.join(details)}"
    return desc
