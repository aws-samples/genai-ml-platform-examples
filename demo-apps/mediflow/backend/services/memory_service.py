"""Patient Memory service — three creation paths.

1. Agent-observed — lightweight LLM extraction after conversations.
2. System-detected — behavioural analysis during the pipeline.
3. User-confirmed — staff confirm/edit/dismiss via API.
"""

import json
import logging
import uuid
from datetime import datetime

from strands import Agent
from strands.models.bedrock import BedrockModel

from backend.config import settings
from backend.services.database import query_db, execute_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------

def get_memories(
    patient_id: str,
    memory_type: str | None = None,
    status: str = "active",
) -> list[dict]:
    """List memories for a patient, optionally filtered by type."""
    sql = "SELECT * FROM patient_memories WHERE patient_id = ? AND status = ?"
    params: list = [patient_id, status]
    if memory_type:
        sql += " AND memory_type = ?"
        params.append(memory_type)
    sql += " ORDER BY observation_count DESC, last_confirmed DESC"
    return query_db(sql, tuple(params))


def get_memories_for_context(patient_id: str) -> str:
    """Return a formatted string of active memories for agent prompt injection."""
    memories = get_memories(patient_id)
    if not memories:
        return ""
    lines = []
    for m in memories:
        conf = f" (confidence {m['confidence']:.0%})" if m["confidence"] < 1.0 else ""
        lines.append(f"- [{m['memory_type']}] {m['content']}{conf}")
    return "\n".join(lines)


def add_memory(
    patient_id: str,
    memory_type: str,
    content: str,
    source: str,
    confidence: float = 0.5,
    metadata: dict | None = None,
) -> str:
    """Create a new memory. Returns the memory id."""
    memory_id = f"mem-{uuid.uuid4().hex[:8]}"
    now = datetime.now().isoformat()
    execute_db(
        """INSERT INTO patient_memories
           (id, patient_id, memory_type, content, source, confidence,
            first_observed, last_confirmed, observation_count, status, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 'active', ?)""",
        (
            memory_id,
            patient_id,
            memory_type,
            content,
            source,
            confidence,
            now,
            now,
            json.dumps(metadata) if metadata else None,
        ),
    )
    return memory_id


def update_memory(
    memory_id: str,
    content: str | None = None,
    status: str | None = None,
    source: str | None = None,
    confidence: float | None = None,
) -> bool:
    """Update fields on an existing memory. Returns True if a row was changed."""
    sets, params = [], []
    if content is not None:
        sets.append("content = ?")
        params.append(content)
    if status is not None:
        sets.append("status = ?")
        params.append(status)
    if source is not None:
        sets.append("source = ?")
        params.append(source)
    if confidence is not None:
        sets.append("confidence = ?")
        params.append(confidence)
    if not sets:
        return False
    sets.append("last_confirmed = ?")
    params.append(datetime.now().isoformat())
    params.append(memory_id)
    execute_db(f"UPDATE patient_memories SET {', '.join(sets)} WHERE id = ?", tuple(params))  # nosec B608
    return True


def merge_or_create(
    patient_id: str,
    memory_type: str,
    content: str,
    source: str,
    confidence: float = 0.5,
) -> str:
    """Deduplicate: if a similar active memory exists, bump its count; else create."""
    existing = query_db(
        """SELECT id, content, observation_count FROM patient_memories
           WHERE patient_id = ? AND memory_type = ? AND status = 'active'""",
        (patient_id, memory_type),
    )
    # Simple similarity: check if the new content is substantially contained
    # in an existing memory or vice-versa (lowercased substring match).
    content_lower = content.lower()
    for mem in existing:
        existing_lower = mem["content"].lower()
        # If >60% overlap by word set, consider it a duplicate
        new_words = set(content_lower.split())
        old_words = set(existing_lower.split())
        if not new_words or not old_words:
            continue
        overlap = len(new_words & old_words) / max(len(new_words), len(old_words))
        if overlap > 0.6:
            now = datetime.now().isoformat()
            new_count = mem["observation_count"] + 1
            # Boost confidence with repeated observations (cap at 0.95 for system)
            new_conf = min(0.95, 0.5 + 0.1 * new_count)
            execute_db(
                """UPDATE patient_memories
                   SET observation_count = ?, last_confirmed = ?, confidence = ?
                   WHERE id = ?""",
                (new_count, now, new_conf, mem["id"]),
            )
            logger.info("Merged memory into %s (count=%d)", mem["id"], new_count)
            return mem["id"]

    return add_memory(patient_id, memory_type, content, source, confidence)


# ---------------------------------------------------------------------------
# Path 1: Agent-observed (post-conversation LLM extraction)
# ---------------------------------------------------------------------------

_MEMORY_EXTRACTION_SYSTEM = """\
You are a medical practice assistant that extracts patient-specific memories \
from conversation transcripts. Memories are facts about a patient that would be \
useful to remember for future interactions.

Categories:
- preference: How the patient likes to be addressed, scheduling preferences, etc.
- behavioral: Patterns like cancellation habits, punctuality, payment behaviour.
- medical_context: Relevant non-clinical context (e.g., "recovering from knee surgery").
- communication: How the patient prefers to be contacted, response patterns.

Return a JSON array of objects with keys: patient_id, memory_type, content.
If no memories can be extracted, return an empty array [].
Return ONLY the JSON array — no markdown fences, no prose.
"""

_MEMORY_EXTRACTION_TEMPLATE = """\
Below is a conversation between a medical receptionist AI and a staff member. \
Extract any patient-specific memories that would be useful to remember.

--- CONVERSATION ---
{conversation}
--- END ---

Return a JSON array of extracted memories. Each object must have:
- "patient_id": the patient ID mentioned (or null if unclear)
- "memory_type": one of "preference", "behavioral", "medical_context", "communication"
- "content": a concise, actionable statement about the patient
"""


def extract_memories_from_conversation(session_id: str) -> list[str]:
    """Analyse a completed conversation and extract patient memories.

    Called as a background task after chat SSE completes.
    Returns list of created/merged memory IDs.
    """
    # Pull the conversation
    rows = query_db(
        "SELECT role, content FROM conversation_log WHERE session_id = ? ORDER BY sequence_number",
        (session_id,),
    )
    if not rows:
        return []

    conversation = "\n".join(f"{r['role'].upper()}: {r['content']}" for r in rows)

    # Quick check: does the conversation even mention patients?
    # Look for tool calls that reference patient operations
    tool_rows = query_db(
        "SELECT tool_name, tool_params FROM tool_call_log WHERE session_id = ?",
        (session_id,),
    )
    patient_ids_mentioned = set()
    for tr in tool_rows:
        params = tr.get("tool_params", "")
        if params:
            try:
                p = json.loads(params) if isinstance(params, str) else params
                if isinstance(p, dict) and "patient_id" in p:
                    patient_ids_mentioned.add(p["patient_id"])
            except (json.JSONDecodeError, TypeError):
                pass

    if not patient_ids_mentioned:
        logger.debug("No patient references in session %s — skipping memory extraction", session_id)
        return []

    # Call LLM
    try:
        model = BedrockModel(
            model_id=settings.bedrock_model_id,
            region_name=settings.aws_default_region,
        )
        agent = Agent(model=model, system_prompt=_MEMORY_EXTRACTION_SYSTEM)
        prompt = _MEMORY_EXTRACTION_TEMPLATE.format(conversation=conversation)
        response = agent(prompt)
        raw = str(response).strip()

        memories = _parse_json_array(raw)
    except Exception:
        logger.exception("Memory extraction LLM call failed for session %s", session_id)
        return []

    created_ids = []
    for mem in memories:
        pid = mem.get("patient_id")
        mtype = mem.get("memory_type", "preference")
        content = mem.get("content", "")
        if not pid or not content:
            continue
        # Validate patient exists
        if not query_db("SELECT id FROM patients WHERE id = ?", (pid,)):
            continue
        mid = merge_or_create(pid, mtype, content, "agent_observed", confidence=0.5)
        created_ids.append(mid)

    logger.info("Extracted %d memories from session %s", len(created_ids), session_id)
    return created_ids


# ---------------------------------------------------------------------------
# Path 2: System-detected (behavioural analysis from data)
# ---------------------------------------------------------------------------

def detect_behavioral_memories() -> list[str]:
    """Scan appointment, communication, and invoice history for behavioural patterns.

    Called during the analysis pipeline (Step 4.5).
    Returns list of created/merged memory IDs.
    """
    created_ids = []

    # --- Cancellation patterns (day-of-week) ---
    cancellation_rows = query_db(
        """SELECT a.patient_id,
                  CASE CAST(strftime('%w', a.date) AS INTEGER)
                      WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday'
                      WHEN 2 THEN 'Tuesday' WHEN 3 THEN 'Wednesday'
                      WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
                      WHEN 6 THEN 'Saturday'
                  END AS dow,
                  COUNT(*) AS cnt
           FROM appointments a
           WHERE a.status = 'cancelled'
           GROUP BY a.patient_id, dow
           HAVING cnt >= 2
           ORDER BY cnt DESC"""
    )
    for row in cancellation_rows:
        mid = merge_or_create(
            row["patient_id"],
            "behavioral",
            f"Tends to cancel {row['dow']} appointments ({row['cnt']} times)",
            "system_detected",
            confidence=min(0.9, 0.5 + 0.1 * row["cnt"]),
        )
        created_ids.append(mid)

    # --- No-show patterns ---
    no_show_rows = query_db(
        """SELECT patient_id, COUNT(*) AS cnt
           FROM appointments WHERE status = 'no_show'
           GROUP BY patient_id HAVING cnt >= 2"""
    )
    for row in no_show_rows:
        mid = merge_or_create(
            row["patient_id"],
            "behavioral",
            f"Has a no-show history ({row['cnt']} missed appointments)",
            "system_detected",
            confidence=min(0.9, 0.5 + 0.1 * row["cnt"]),
        )
        created_ids.append(mid)

    # --- Communication response patterns ---
    comm_rows = query_db(
        """SELECT patient_id, channel, COUNT(*) AS cnt
           FROM communications
           WHERE patient_id IS NOT NULL
           GROUP BY patient_id, channel
           HAVING cnt >= 3
           ORDER BY cnt DESC"""
    )
    # Find patients with a strong channel preference
    patient_channels: dict[str, list] = {}
    for row in comm_rows:
        patient_channels.setdefault(row["patient_id"], []).append(
            (row["channel"], row["cnt"])
        )
    for pid, channels in patient_channels.items():
        if len(channels) == 1:
            ch, cnt = channels[0]
            mid = merge_or_create(
                pid,
                "communication",
                f"Primarily contacted via {ch} ({cnt} messages)",
                "system_detected",
                confidence=0.6,
            )
            created_ids.append(mid)
        elif len(channels) >= 2:
            channels.sort(key=lambda x: x[1], reverse=True)
            top_ch, top_cnt = channels[0]
            total = sum(c for _, c in channels)
            pct = top_cnt / total * 100
            if pct >= 60:
                mid = merge_or_create(
                    pid,
                    "communication",
                    f"Prefers {top_ch} ({pct:.0f}% of communications)",
                    "system_detected",
                    confidence=0.6,
                )
                created_ids.append(mid)

    # --- Doctor preference patterns ---
    doctor_pref_rows = query_db(
        """SELECT a.patient_id, d.name AS doctor_name, a.doctor_id,
                  COUNT(*) AS cnt
           FROM appointments a
           JOIN doctors d ON a.doctor_id = d.id
           WHERE a.status IN ('completed', 'scheduled')
           GROUP BY a.patient_id, a.doctor_id
           HAVING cnt >= 3
           ORDER BY cnt DESC"""
    )
    # Check if patient consistently sees one doctor
    patient_doctors: dict[str, list] = {}
    for row in doctor_pref_rows:
        patient_doctors.setdefault(row["patient_id"], []).append(
            (row["doctor_name"], row["cnt"])
        )
    for pid, doctors in patient_doctors.items():
        # Skip single-doctor patients: "Regularly sees Dr X (N appointments)" is
        # low-signal filler that crowds out richer memory types in the Insights view.
        if len(doctors) >= 2:
            doctors.sort(key=lambda x: x[1], reverse=True)
            top_name, top_cnt = doctors[0]
            total = sum(c for _, c in doctors)
            pct = top_cnt / total * 100
            if pct >= 70:
                mid = merge_or_create(
                    pid,
                    "preference",
                    f"Prefers {top_name} ({pct:.0f}% of visits)",
                    "system_detected",
                    confidence=0.7,
                )
                created_ids.append(mid)

    # --- Payment behaviour ---
    payment_rows = query_db(
        """SELECT patient_id,
                  COUNT(*) AS total,
                  SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) AS overdue,
                  SUM(CASE WHEN chase_count >= 2 THEN 1 ELSE 0 END) AS multi_chased
           FROM invoices
           GROUP BY patient_id
           HAVING total >= 3"""
    )
    for row in payment_rows:
        total = row["total"]
        overdue = row["overdue"] or 0
        multi_chased = row["multi_chased"] or 0
        if overdue == 0 and multi_chased == 0:
            mid = merge_or_create(
                row["patient_id"],
                "behavioral",
                "Consistently pays invoices on time",
                "system_detected",
                confidence=0.7,
            )
            created_ids.append(mid)
        elif overdue >= 2 or multi_chased >= 2:
            mid = merge_or_create(
                row["patient_id"],
                "behavioral",
                f"Often has overdue invoices ({overdue} overdue, {multi_chased} required multiple chases)",
                "system_detected",
                confidence=min(0.9, 0.5 + 0.1 * overdue),
            )
            created_ids.append(mid)

    logger.info("Detected %d behavioural memories across patients", len(created_ids))
    return created_ids


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_array(text: str) -> list:
    """Best-effort parse of a JSON array from LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, ValueError):
        pass

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass

    logger.warning("Could not parse LLM response as JSON array")
    return []
