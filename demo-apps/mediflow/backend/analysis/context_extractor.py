"""Extract conversation context around detected patterns using LLM.

For each detected pattern, this module pulls surrounding evidence from the
appropriate data source (conversation logs, UI activity, or live database)
and asks Claude (via Bedrock) to extract nuances and classify the pattern.
"""

import json
import logging

from strands import Agent
from strands.models.bedrock import BedrockModel

from backend.config import settings
from backend.services.database import query_db, execute_db

logger = logging.getLogger(__name__)

_EXTRACTION_SYSTEM_PROMPT = """\
You are an expert analyst at a medical practice. You analyse evidence \
from a receptionist's daily work — conversation transcripts, UI activity logs, \
or aggregated patient data — and extract nuanced context about *why* certain \
patterns occur. Your output is always valid JSON — no markdown fences, no prose \
before or after.
"""

_EXTRACTION_USER_TEMPLATE = """\
Below is evidence of a recurring pattern observed at a medical practice. \
The pattern was detected from {source_label}.

Pattern type: {pattern_type}
Tool/action sequence: {tool_sequence}
Pattern description: {description}

--- EVIDENCE START ---
{excerpts}
--- EVIDENCE END ---

Analyse this evidence and return a JSON object with exactly these keys:

{{
  "intent_nuances": "<string> Why does this action occur? What is the underlying goal?",
  "conditional_logic": "<string> Are there cases where different decisions are made? What conditions matter?",
  "human_review_triggers": ["<string> Situations where a human should review or override"],
  "personalization_signals": ["<string> Patient-specific context that influences the action"],
  "exceptions": "<string> Cases where the pattern is explicitly skipped or handled differently.",
  "cadence_hint": "<string> When does this pattern typically occur? For BATCH patterns, always provide a cadence (e.g. 'weekdays 08:00-10:00', 'when booking multiple patients', 'during morning admin'). For SEQUENCE patterns, describe timing if predictable or 'on demand' if event-driven."
}}

Return ONLY the JSON object.
"""


def extract_context_for_patterns(patterns: list[dict]) -> list[dict]:
    """For each pattern, pull surrounding evidence and extract nuances via LLM.

    Runs LLM calls in parallel (up to 5 concurrent) for speed.

    Parameters
    ----------
    patterns : list[dict]
        Patterns produced by ``detect_patterns``.  Each must have
        ``example_session_ids``, ``tool_sequence``, and ``pattern_type``.

    Returns
    -------
    list[dict]
        The same pattern dicts, now with ``conversation_context`` populated.
    """
    if not patterns:
        return patterns

    from concurrent.futures import ThreadPoolExecutor, as_completed

    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_default_region,
    )

    def _extract_one(pattern: dict) -> tuple[str, dict]:
        agent = Agent(model=model, system_prompt=_EXTRACTION_SYSTEM_PROMPT)
        session_ids = pattern.get("example_session_ids", [])
        tool_sequence = pattern.get("tool_sequence", [])
        pattern_type = pattern.get("pattern_type", "SEQUENCE")

        if not session_ids and pattern_type != "DATA_PATTERN":
            return pattern["id"], _fallback_context()

        excerpts, source_label = _build_evidence(pattern_type, session_ids, tool_sequence)

        if not excerpts.strip():
            logger.warning("No evidence found for pattern %s – skipping", pattern["id"])
            return pattern["id"], _fallback_context()

        prompt = _EXTRACTION_USER_TEMPLATE.format(
            source_label=source_label,
            pattern_type=pattern_type,
            tool_sequence=" -> ".join(tool_sequence),
            description=pattern.get("description", ""),
            excerpts=excerpts,
        )

        try:
            response = agent(prompt)
            raw_text = str(response)
            context = _parse_json_response(raw_text)
        except Exception:
            logger.exception("LLM extraction failed for pattern %s", pattern["id"])
            context = _fallback_context()

        context.setdefault("cadence_hint", "")
        return pattern["id"], context

    # Run in parallel
    results: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_extract_one, p): p for p in patterns}
        for future in as_completed(futures):
            pattern_id, context = future.result()
            results[pattern_id] = context

    # Apply results back to patterns
    for pattern in patterns:
        context = results.get(pattern["id"], _fallback_context())
        pattern["conversation_context"] = context
        execute_db(
            "UPDATE detected_patterns SET conversation_context = ? WHERE id = ?",
            (json.dumps(context), pattern["id"]),
        )

    return patterns


# ------------------------------------------------------------------
# Evidence builders
# ------------------------------------------------------------------

def _build_evidence(
    pattern_type: str,
    session_ids: list[str],
    tool_sequence: list[str],
) -> tuple[str, str]:
    """Dispatch to the appropriate evidence builder based on pattern type.

    Returns (excerpts_text, source_label).
    """
    if pattern_type in ("BATCH", "SEQUENCE"):
        return _build_tool_excerpts(session_ids, tool_sequence), "agent chat / tool-call logs"

    if pattern_type in ("UI_BATCH", "UI_SEQUENCE"):
        return _build_ui_excerpts(session_ids), "manual UI activity logs"

    if pattern_type == "CROSS_SOURCE":
        return _build_cross_source_excerpts(session_ids), "combined UI + agent activity (same session)"

    if pattern_type == "DATA_PATTERN":
        return _build_data_evidence(tool_sequence, session_ids), "aggregated patient/appointment data"

    # Fallback
    return _build_tool_excerpts(session_ids, tool_sequence), "agent chat / tool-call logs"


def _build_tool_excerpts(session_ids: list[str], tool_sequence: list[str]) -> str:
    """Pull conversation + tool-call logs for the given sessions."""
    parts: list[str] = []

    for sid in session_ids[:5]:
        conv_rows = query_db(
            "SELECT role, content FROM conversation_log "
            "WHERE session_id = ? ORDER BY sequence_number",
            (sid,),
        )
        tool_rows = query_db(
            "SELECT tool_name, tool_params, result_summary FROM tool_call_log "
            "WHERE session_id = ? ORDER BY sequence_number",
            (sid,),
        )

        if not conv_rows:
            continue

        section = [f"[Session: {sid}]"]
        for row in conv_rows:
            section.append(f"  {row['role'].upper()}: {row['content']}")
        if tool_rows:
            section.append("  TOOLS CALLED:")
            for tr in tool_rows:
                params_str = tr["tool_params"] or "{}"
                section.append(f"    - {tr['tool_name']}({params_str})")
        parts.append("\n".join(section))

    return "\n\n".join(parts)


def _build_ui_excerpts(session_ids: list[str]) -> str:
    """Pull UI activity log entries and format as a readable activity trace."""
    parts: list[str] = []

    for sid in session_ids[:5]:
        rows = query_db(
            "SELECT action_type, action_detail, entity_type, entity_id, view, timestamp "
            "FROM ui_activity_log "
            "WHERE session_id = ? ORDER BY timestamp",
            (sid,),
        )
        if not rows:
            continue

        section = [f"[UI Session: {sid}]"]
        for row in rows:
            detail = ""
            if row["action_detail"]:
                try:
                    detail_obj = json.loads(row["action_detail"]) if isinstance(row["action_detail"], str) else row["action_detail"]
                    detail = f" — {json.dumps(detail_obj)}" if detail_obj else ""
                except (json.JSONDecodeError, TypeError):
                    detail = f" — {row['action_detail']}"

            entity_str = ""
            if row["entity_type"] and row["entity_id"]:
                # Try to resolve entity name
                name = _resolve_entity_name(row["entity_type"], row["entity_id"])
                entity_str = f" [{row['entity_type']}: {name}]"

            section.append(
                f"  {row['timestamp']} | {row['action_type']}{entity_str}{detail} (in {row['view'] or '?'})"
            )
        parts.append("\n".join(section))

    return "\n\n".join(parts)


def _build_cross_source_excerpts(session_ids: list[str]) -> str:
    """Interleave UI activity and tool-call events chronologically."""
    parts: list[str] = []

    for sid in session_ids[:5]:
        ui_rows = query_db(
            "SELECT timestamp, 'UI' as source, action_type as action, "
            "action_detail as detail, entity_type, entity_id "
            "FROM ui_activity_log WHERE session_id = ? ORDER BY timestamp",
            (sid,),
        )
        tool_rows = query_db(
            "SELECT timestamp, 'AGENT' as source, tool_name as action, "
            "tool_params as detail, NULL as entity_type, NULL as entity_id "
            "FROM tool_call_log WHERE session_id = ? ORDER BY timestamp",
            (sid,),
        )
        if not ui_rows and not tool_rows:
            continue

        # Merge and sort by timestamp
        all_events = list(ui_rows) + list(tool_rows)
        all_events.sort(key=lambda e: e["timestamp"] or "")

        section = [f"[Cross-Source Session: {sid}]"]
        for evt in all_events:
            source = evt["source"]
            action = evt["action"]
            ts = evt["timestamp"] or "?"
            detail = ""
            if evt["detail"]:
                try:
                    detail = f" — {evt['detail'][:100]}"
                except Exception:
                    pass
            section.append(f"  {ts} [{source}] {action}{detail}")
        parts.append("\n".join(section))

    return "\n\n".join(parts)


def _build_data_evidence(tool_sequence: list[str], example_ids: list[str]) -> str:
    """Pull relevant database records as evidence for data-mined patterns."""
    pattern_key = tool_sequence[0] if tool_sequence else ""

    if pattern_key == "cancellation_day_of_week":
        return _evidence_cancellation_dow(example_ids)
    if pattern_key == "appointment_type_cascade":
        return _evidence_appointment_cascades(example_ids)
    if pattern_key == "pediatric_routing":
        return _evidence_pediatric_routing(example_ids)
    if pattern_key == "new_patient_follow_up":
        return _evidence_follow_up(example_ids)
    if pattern_key == "early_morning_no_show":
        return _evidence_early_no_show(example_ids)

    return f"Data pattern '{pattern_key}' with {len(example_ids)} examples."


def _evidence_cancellation_dow(example_ids: list[str]) -> str:
    """Show cancellation day-of-week breakdown for flagged patients."""
    from datetime import datetime
    from collections import Counter

    parts = []
    for ref in example_ids[:5]:
        pid = ref.replace("patient:", "")
        name = _resolve_entity_name("patient", pid)
        rows = query_db(
            "SELECT date, status FROM appointments WHERE patient_id = ? AND status IN ('cancelled', 'no_show')",
            (pid,),
        )
        dow_counts: Counter = Counter()
        for r in rows:
            try:
                dt = datetime.strptime(r["date"], "%Y-%m-%d")
                dow_counts[dt.strftime("%A")] += 1
            except ValueError:
                continue
        total_appts = query_db(
            "SELECT COUNT(*) as cnt FROM appointments WHERE patient_id = ?", (pid,)
        )[0]["cnt"]
        breakdown = ", ".join(f"{day}: {c}" for day, c in dow_counts.most_common())
        parts.append(
            f"Patient {name} ({pid}): {sum(dow_counts.values())} cancellations/no-shows "
            f"out of {total_appts} total appointments. By day: {breakdown}"
        )
    return "\n".join(parts)


def _evidence_appointment_cascades(example_ids: list[str]) -> str:
    """Show recurring appointment type sequences for flagged patients."""
    parts = []
    for ref in example_ids[:5]:
        pid = ref.replace("patient:", "")
        name = _resolve_entity_name("patient", pid)
        rows = query_db(
            "SELECT date, type, status FROM appointments "
            "WHERE patient_id = ? AND status IN ('scheduled', 'completed') "
            "ORDER BY date",
            (pid,),
        )
        types = [f"{r['type']} ({r['date']})" for r in rows[:12]]
        parts.append(f"Patient {name}: {' -> '.join(types)}")
    return "\n".join(parts)


def _evidence_pediatric_routing(example_ids: list[str]) -> str:
    """Show doctor assignments for pediatric patients."""
    parts = []
    for ref in example_ids[:5]:
        pid = ref.replace("patient:", "")
        name = _resolve_entity_name("patient", pid)
        rows = query_db(
            "SELECT d.name as doctor, COUNT(*) as cnt "
            "FROM appointments a JOIN doctors d ON a.doctor_id = d.id "
            "WHERE a.patient_id = ? GROUP BY a.doctor_id ORDER BY cnt DESC",
            (pid,),
        )
        dob = query_db("SELECT dob FROM patients WHERE id = ?", (pid,))
        dob_str = dob[0]["dob"] if dob else "?"
        doc_breakdown = ", ".join(f"{r['doctor']}: {r['cnt']} appts" for r in rows)
        parts.append(f"Patient {name} (DOB: {dob_str}): {doc_breakdown}")
    return "\n".join(parts)


def _evidence_follow_up(example_ids: list[str]) -> str:
    """Show new_patient → follow_up sequences."""
    parts = []
    for ref in example_ids[:5]:
        pid = ref.replace("patient:", "")
        name = _resolve_entity_name("patient", pid)
        new_appts = query_db(
            "SELECT date FROM appointments WHERE patient_id = ? AND type = 'new_patient' ORDER BY date",
            (pid,),
        )
        follow_ups = query_db(
            "SELECT date FROM appointments WHERE patient_id = ? AND type = 'follow_up' ORDER BY date",
            (pid,),
        )
        new_dates = [a["date"] for a in new_appts]
        fu_dates = [a["date"] for a in follow_ups]
        parts.append(f"Patient {name}: new_patient on {', '.join(new_dates[:3])} → follow_ups on {', '.join(fu_dates[:3])}")
    return "\n".join(parts)


def _evidence_early_no_show(example_ids: list[str]) -> str:
    """Show no-show times for patients with early-morning clustering."""
    parts = []
    for ref in example_ids[:5]:
        pid = ref.replace("patient:", "")
        name = _resolve_entity_name("patient", pid)
        rows = query_db(
            "SELECT time, status FROM appointments WHERE patient_id = ? AND status IN ('no_show', 'completed') ORDER BY time",
            (pid,),
        )
        no_shows = [f"{r['time']} (no-show)" for r in rows if r["status"] == "no_show"]
        completed = [f"{r['time']} (completed)" for r in rows if r["status"] == "completed"]
        parts.append(f"Patient {name}: No-shows: {', '.join(no_shows)}. Completed: {', '.join(completed[:5])}")
    return "\n".join(parts)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _resolve_entity_name(entity_type: str, entity_id: str) -> str:
    """Try to look up a human-readable name for an entity."""
    if entity_type == "patient":
        rows = query_db(
            "SELECT first_name, last_name FROM patients WHERE id = ?", (entity_id,)
        )
        if rows:
            return f"{rows[0]['first_name']} {rows[0]['last_name']}"
    if entity_type == "doctor":
        rows = query_db("SELECT name FROM doctors WHERE id = ?", (entity_id,))
        if rows:
            return rows[0]["name"]
    return entity_id


def _fallback_context() -> dict:
    """Return a fallback context dict when extraction fails."""
    return {
        "intent_nuances": "Extraction failed",
        "conditional_logic": "",
        "human_review_triggers": [],
        "personalization_signals": [],
        "exceptions": "",
        "cadence_hint": "",
    }


def _parse_json_response(text: str) -> dict:
    """Best-effort parse of a JSON object from the LLM response."""
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

    logger.warning("Could not parse LLM response as JSON – using raw text fallback")
    return {
        "intent_nuances": text[:500],
        "conditional_logic": "",
        "human_review_triggers": [],
        "personalization_signals": [],
        "exceptions": "",
        "cadence_hint": "",
    }
