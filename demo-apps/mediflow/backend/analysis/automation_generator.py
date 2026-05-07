"""Generate unified Skills from detected patterns using LLM.

Stage 3 of the analysis pipeline. For each pattern with enriched context,
ask the LLM to produce a Skill definition and persist it to the unified
``skills`` table. Every skill carries:

* ``scheduled`` — boolean; whether the pattern has a predictable cadence
  (defaulted from pattern type if the LLM is unsure).
* When ``scheduled=True``: ``schedule_cadence``, ``schedule_time``,
  ``schedule_day`` inherited from the pattern's cadence hint or heuristics.
* ``batch_selection_hint`` — natural-language description of the
  population the skill operates over (replaces the old SQL
  ``selection_criteria``). Resolved at run time by the agent.
"""

import json
import logging
import uuid

from strands import Agent
from strands.models.bedrock import BedrockModel

from backend.config import settings
from backend.services.database import execute_db

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Tool schemas shared with the LLM so it can compose valid steps.
# ------------------------------------------------------------------
TOOL_SCHEMAS = [
    {"name": "get_patient", "description": "Look up a patient by ID", "parameters": {"patient_id": "string (required)"}},
    {"name": "search_patients", "description": "Search patients by name or other fields", "parameters": {"query": "string (required)"}},
    {"name": "get_patient_history", "description": "Retrieve full patient history including appointments and invoices", "parameters": {"patient_id": "string (required)"}},
    {"name": "get_patient_memories", "description": "Retrieve stored patient memories (preferences, behavioral patterns)", "parameters": {"patient_id": "string (required)"}},
    {"name": "record_patient_memory", "description": "Store a new observation about a patient", "parameters": {"patient_id": "string (required)", "memory_type": "string (preference|behavioral|medical_context|communication)", "content": "string (required)"}},
    {"name": "check_availability", "description": "Check a doctor's available slots for a date", "parameters": {"doctor_id": "string (required)", "date": "string YYYY-MM-DD (required)"}},
    {"name": "book_appointment", "description": "Book an appointment for a patient", "parameters": {"patient_id": "string", "doctor_id": "string", "date": "string YYYY-MM-DD", "time": "string HH:MM", "type": "string (optional)"}},
    {"name": "reschedule_appointment", "description": "Move an existing appointment to a new date/time", "parameters": {"appointment_id": "string", "new_date": "string YYYY-MM-DD", "new_time": "string HH:MM"}},
    {"name": "cancel_appointment", "description": "Cancel an existing appointment", "parameters": {"appointment_id": "string (required)", "reason": "string (optional)"}},
    {"name": "get_appointment_details", "description": "Get full details of an appointment", "parameters": {"appointment_id": "string (required)"}},
    {"name": "list_upcoming_appointments", "description": "List upcoming appointments, optionally filtered by doctor", "parameters": {"doctor_id": "string (optional)", "days": "integer (optional, default 7)"}},
    {"name": "send_appointment_reminder", "description": "Send a reminder to a patient about their upcoming appointment", "parameters": {"patient_id": "string", "appointment_id": "string"}},
    {"name": "send_message", "description": "Send a free-text message to a patient via their preferred channel", "parameters": {"patient_id": "string", "message": "string"}},
    {"name": "get_comms_history", "description": "Get communication history for a patient", "parameters": {"patient_id": "string (required)"}},
    {"name": "get_invoice", "description": "Look up an invoice by ID", "parameters": {"invoice_id": "string (required)"}},
    {"name": "get_outstanding_invoices", "description": "List outstanding (unpaid) invoices, optionally filtered by patient", "parameters": {"patient_id": "string (optional)"}},
    {"name": "send_payment_reminder", "description": "Send a payment reminder for an outstanding invoice", "parameters": {"invoice_id": "string (required)"}},
    {"name": "record_payment", "description": "Record a payment against an invoice", "parameters": {"invoice_id": "string", "amount": "number"}},
    {"name": "get_practice_info", "description": "Return practice metadata (hours, address, policies)", "parameters": {}},
    {"name": "get_doctor_info", "description": "Get details about a doctor/practitioner", "parameters": {"doctor_id": "string (required)"}},
    {"name": "get_doctor_schedule", "description": "Get a doctor's schedule for a date range", "parameters": {"doctor_id": "string (required)", "start_date": "string YYYY-MM-DD (optional)", "end_date": "string YYYY-MM-DD (optional)"}},
    {"name": "check_pathology_results", "description": "Check pathology/lab results for a patient", "parameters": {"patient_id": "string (required)"}},
]

_SYSTEM_PROMPT = """\
You are an automation architect for a medical practice. Your job is to turn \
detected receptionist patterns into agent-executable Skills.

A Skill is a single unit of improvement the AI agent can perform on demand \
(ad-hoc) or on a schedule. Each Skill has an agent prompt, a tool list, and \
optionally a natural-language hint describing what items to operate over.

Your output is always valid JSON — no markdown fences, no prose before or after.
"""

_SKILL_TEMPLATE = """\
A recurring pattern has been detected in the receptionist's daily work:

Pattern type: {pattern_type}
Action sequence: {tool_sequence}
Description: {description}
Occurrences: {occurrence_count}

Context analysis:
{conversation_context}

Generate a Skill definition as a JSON object with exactly these keys:

{{
  "name": "<short human-readable name>",
  "description": "<1-2 sentences: what this skill does and why it's valuable>",
  "trigger_description": "<when should this skill activate? Natural language.>",
  "agent_prompt_template": "<A detailed prompt fragment (3-8 sentences) the agent uses when executing this skill. Include: goal, step-by-step reasoning guidance, tools to use and when, how to personalise based on patient memories, when to ask for user confirmation. Use {{patient_name}}, {{doctor_name}}, {{date}} as placeholders.>",
  "tool_config": ["<list of tool names this skill needs>"],
  "batch_selection_hint": "<If this skill operates over a population (many patients/invoices/etc), describe in natural language what items to process. Leave empty string if the skill handles a single item per invocation.>",
  "example_scenario": "<A concrete worked example.>",
  "scheduled": <true|false — does this skill have a predictable cadence?>,
  "schedule_cadence": "<daily|weekdays|weekly|monthly, or null if scheduled=false>",
  "schedule_time": "<HH:MM 24-hour, or null>",
  "schedule_day": <0-6 for weekday, 1-28 for day-of-month, or null>,
  "status": "pending_review"
}}

Available tools:
{tool_schemas}

Return ONLY the JSON object.
"""


# ------------------------------------------------------------------
# Main entry point
# ------------------------------------------------------------------

def generate_automations(patterns: list[dict]) -> dict:
    """Generate a unified Skill for every pattern.

    Runs LLM calls in parallel (up to 5 concurrent) for speed.

    Returns
    -------
    dict
        ``{"skills": [...]}`` — workflows key is no longer emitted.
    """
    if not patterns:
        return {"skills": []}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_default_region,
    )
    tool_schemas_text = json.dumps(TOOL_SCHEMAS, indent=2)

    def _gen_one(pattern: dict) -> dict | None:
        agent = Agent(model=model, system_prompt=_SYSTEM_PROMPT)
        context = pattern.get("conversation_context") or {}
        context_text = json.dumps(context, indent=2) if isinstance(context, dict) else str(context)
        return _generate_skill(agent, pattern, context_text, tool_schemas_text)

    skills: list[dict] = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_gen_one, p): p for p in patterns}
        for future in as_completed(futures):
            skill = future.result()
            if skill:
                skills.append(skill)

    logger.info("Generated %d skills", len(skills))
    return {"skills": skills}


# ------------------------------------------------------------------
# Skill generation
# ------------------------------------------------------------------

def _generate_skill(
    agent: Agent,
    pattern: dict,
    context_text: str,
    tool_schemas_text: str,
) -> dict | None:
    """Generate a unified skill definition from a pattern."""
    prompt = _SKILL_TEMPLATE.format(
        pattern_type=pattern["pattern_type"],
        tool_sequence=" -> ".join(pattern.get("tool_sequence", []) or []),
        description=pattern.get("description", ""),
        occurrence_count=pattern.get("occurrence_count", 0),
        conversation_context=context_text,
        tool_schemas=tool_schemas_text,
    )

    try:
        response = agent(prompt)
        raw_text = str(response)
        skill_def = _parse_json_response(raw_text)
    except Exception:
        logger.exception("Skill generation failed for pattern %s", pattern["id"])
        return None

    if not skill_def or "name" not in skill_def:
        logger.warning("LLM returned unusable skill definition for pattern %s", pattern["id"])
        return None

    return _persist_skill(pattern, skill_def)


def _persist_skill(pattern: dict, skill_def: dict) -> dict | None:
    """Write a unified skill definition to the database."""
    skill_id = f"sk-{uuid.uuid4().hex[:8]}"

    scheduled_raw = skill_def.get("scheduled")
    if scheduled_raw is None:
        scheduled = _default_scheduled_for(pattern)
    else:
        scheduled = 1 if bool(scheduled_raw) else 0

    cadence = skill_def.get("schedule_cadence")
    time = skill_def.get("schedule_time")
    day = skill_def.get("schedule_day")

    if scheduled and not (cadence or time):
        cadence, time, day = _default_schedule_for(pattern, skill_def)
    if not scheduled:
        cadence = time = day = None

    batch_hint = skill_def.get("batch_selection_hint") or None
    if batch_hint == "":
        batch_hint = None

    try:
        execute_db(
            "INSERT INTO skills "
            "(id, pattern_id, name, description, trigger_description, "
            "agent_prompt_template, tool_config, batch_selection_hint, "
            "example_scenario, status, scheduled, schedule_cadence, "
            "schedule_time, schedule_day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                skill_id,
                pattern["id"],
                skill_def.get("name", "Unnamed skill"),
                skill_def.get("description", ""),
                skill_def.get("trigger_description", ""),
                skill_def.get("agent_prompt_template", ""),
                json.dumps(skill_def.get("tool_config", [])),
                batch_hint,
                skill_def.get("example_scenario", ""),
                skill_def.get("status", "pending_review"),
                scheduled,
                cadence,
                time,
                day,
            ),
        )
    except Exception:
        logger.exception("Failed to insert skill %s", skill_id)
        return None

    return {
        "id": skill_id,
        "pattern_id": pattern["id"],
        "name": skill_def.get("name", "Unnamed skill"),
        "description": skill_def.get("description", ""),
        "trigger_description": skill_def.get("trigger_description", ""),
        "scheduled": bool(scheduled),
        "schedule_cadence": cadence,
        "schedule_time": time,
        "status": skill_def.get("status", "pending_review"),
    }


def _default_scheduled_for(pattern: dict) -> int:
    """Heuristic: cross-source and data patterns with high occurrence
    counts tend to be scheduled; conversational one-off patterns tend to
    be ad-hoc."""
    ptype = pattern.get("pattern_type", "")
    if ptype in ("CROSS_SOURCE", "DATA_PATTERN"):
        return 1
    if ptype in ("BATCH", "UI_BATCH"):
        return 1
    return 0


def _default_schedule_for(pattern: dict, skill_def: dict) -> tuple[str, str, int | None]:
    """Default cadence/time/day when LLM didn't supply them."""
    name_lower = (skill_def.get("name") or "").lower()
    if "payment" in name_lower or "invoice" in name_lower or "follow-up" in name_lower:
        return "weekly", "09:00", 0  # Monday
    if "chronic" in name_lower or "monthly" in name_lower or "check-in" in name_lower:
        return "monthly", "08:30", 1
    if "briefing" in name_lower or "morning" in name_lower:
        return "weekdays", "08:00", None
    return "daily", "08:00", None


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _parse_json_response(text: str) -> dict:
    """Best-effort extraction of a JSON object from the LLM response."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Could not parse automation JSON from LLM response")
    return {}
