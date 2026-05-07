"""Detect recurring patterns from tool-call logs, UI activity, and live data.

This module performs deterministic sequence mining over multiple data sources:

1. **BATCH / SEQUENCE** — tool_call_log patterns (same tool called 3+ times
   consecutively, or ordered multi-tool sequences recurring across sessions).
2. **UI_BATCH / UI_SEQUENCE** — same algorithms applied to ui_activity_log.
3. **CROSS_SOURCE** — correlations between UI actions and tool calls within
   overlapping time windows (±5 minutes) in the same session.
4. **DATA_PATTERN** — mines live database tables for behavioral patterns
   (cancellation day-of-week, appointment cascades, pediatric routing, etc.).

No LLM calls are made here — everything is pure data crunching.
"""

import json
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from backend.services.database import query_db, execute_db

# Parameters that typically vary per-entity (ignored when comparing tool calls)
_ENTITY_PARAMS = {"patient_id", "appointment_id", "invoice_id", "doctor_id", "entity_id"}

# Time window (minutes) for cross-source correlation
_CROSS_SOURCE_WINDOW_MINS = 5


def detect_patterns(min_occurrences: int = 2) -> list[dict]:
    """Mine all data sources for recurring patterns.

    Runs four independent detectors and merges results into the
    ``detected_patterns`` table.

    Returns
    -------
    list[dict]
        Newly detected patterns with keys: id, pattern_type, description,
        tool_sequence, occurrence_count, example_session_ids, confidence, status.
    """
    patterns: list[dict] = []
    seen_signatures: set[str] = set()

    # 1. Tool-call-log patterns (BATCH + SEQUENCE)
    patterns.extend(_detect_tool_patterns(min_occurrences, seen_signatures))

    # 2. UI activity patterns (UI_BATCH + UI_SEQUENCE)
    patterns.extend(_detect_ui_patterns(min_occurrences, seen_signatures))

    # 3. Cross-source correlations
    patterns.extend(_detect_cross_source_patterns(min_occurrences, seen_signatures))

    # 4. Data patterns (mines live DB tables)
    patterns.extend(_detect_data_patterns(seen_signatures))

    # Filter out noise (confidence below minimum threshold)
    patterns = [p for p in patterns if p["confidence"] >= 0.04]

    # Persist to detected_patterns
    for pat in patterns:
        execute_db(
            "INSERT OR REPLACE INTO detected_patterns "
            "(id, pattern_type, description, tool_sequence, occurrence_count, "
            "example_session_ids, confidence, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pat["id"],
                pat["pattern_type"],
                pat["description"],
                json.dumps(pat["tool_sequence"]),
                pat["occurrence_count"],
                json.dumps(pat["example_session_ids"]),
                pat["confidence"],
                pat["status"],
            ),
        )

    return patterns


# ======================================================================
# 1. Tool-call-log mining (BATCH + SEQUENCE) — original algorithm
# ======================================================================

def _detect_tool_patterns(min_occurrences: int, seen_signatures: set[str]) -> list[dict]:
    rows = query_db(
        "SELECT session_id, tool_name, tool_params "
        "FROM tool_call_log ORDER BY session_id, sequence_number"
    )
    if not rows:
        return []

    sessions: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        sessions[row["session_id"]].append(row)

    total_sessions = len(sessions)
    patterns: list[dict] = []

    # --- Batch detection ---
    batch_counter: Counter = Counter()
    batch_sessions: dict[str, list[str]] = defaultdict(list)

    for sid, calls in sessions.items():
        run_tool = None
        run_length = 0
        for call in calls:
            if call["tool_name"] == run_tool:
                run_length += 1
            else:
                if run_length >= 3 and run_tool is not None:
                    batch_counter[run_tool] += 1
                    batch_sessions[run_tool].append(sid)
                run_tool = call["tool_name"]
                run_length = 1
        if run_length >= 3 and run_tool is not None:
            batch_counter[run_tool] += 1
            batch_sessions[run_tool].append(sid)

    for tool_name, count in batch_counter.items():
        if count < min_occurrences:
            continue
        sig = f"BATCH:{tool_name}"
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        example_ids = batch_sessions[tool_name][:10]
        confidence = min(0.5, round(count / total_sessions, 3))
        patterns.append(
            _make_pattern(
                pattern_type="BATCH",
                tool_sequence=[tool_name],
                description=(
                    f"'{tool_name}' is called 3+ times consecutively in "
                    f"{count} session(s), suggesting a batch operation"
                ),
                occurrence_count=count,
                example_session_ids=example_ids,
                confidence=confidence,
            )
        )

    # --- Sequence detection ---
    subseq_sessions: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for sid, calls in sessions.items():
        tool_names = [c["tool_name"] for c in calls]
        for window_size in range(2, min(6, len(tool_names) + 1)):
            for i in range(len(tool_names) - window_size + 1):
                subseq = tuple(tool_names[i : i + window_size])
                if len(set(subseq)) >= 2:
                    subseq_sessions[subseq].add(sid)

    ranked = sorted(subseq_sessions.items(), key=lambda kv: len(kv[1]), reverse=True)
    for subseq, sid_set in ranked:
        count = len(sid_set)
        if count < min_occurrences:
            continue
        sig = f"SEQUENCE:{','.join(subseq)}"
        if sig in seen_signatures:
            continue
        is_subsumed = any(
            existing.startswith("SEQUENCE:") and ",".join(subseq) in existing.split(":", 1)[1]
            for existing in seen_signatures
        )
        if is_subsumed:
            continue
        seen_signatures.add(sig)
        example_ids = sorted(sid_set)[:10]
        confidence = min(0.5, round(count / total_sessions, 3))
        patterns.append(
            _make_pattern(
                pattern_type="SEQUENCE",
                tool_sequence=list(subseq),
                description=(
                    f"Sequence {' -> '.join(subseq)} appears in "
                    f"{count} session(s)"
                ),
                occurrence_count=count,
                example_session_ids=example_ids,
                confidence=confidence,
            )
        )

    return patterns


# ======================================================================
# 2. UI activity mining (UI_BATCH + UI_SEQUENCE)
# ======================================================================

def _detect_ui_patterns(min_occurrences: int, seen_signatures: set[str]) -> list[dict]:
    rows = query_db(
        "SELECT session_id, action_type, action_detail, entity_type, entity_id "
        "FROM ui_activity_log ORDER BY session_id, timestamp"
    )
    if not rows:
        return []

    sessions: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        sessions[row["session_id"]].append(row)

    total_sessions = len(sessions)
    patterns: list[dict] = []

    # --- UI Batch detection ---
    batch_counter: Counter = Counter()
    batch_sessions: dict[str, list[str]] = defaultdict(list)

    for sid, actions in sessions.items():
        run_action = None
        run_length = 0
        for act in actions:
            if act["action_type"] == run_action:
                run_length += 1
            else:
                if run_length >= 3 and run_action is not None:
                    batch_counter[run_action] += 1
                    batch_sessions[run_action].append(sid)
                run_action = act["action_type"]
                run_length = 1
        if run_length >= 3 and run_action is not None:
            batch_counter[run_action] += 1
            batch_sessions[run_action].append(sid)

    for action_type, count in batch_counter.items():
        if count < min_occurrences:
            continue
        sig = f"UI_BATCH:{action_type}"
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        example_ids = batch_sessions[action_type][:10]
        confidence = min(0.5, round(count / total_sessions, 3))
        patterns.append(
            _make_pattern(
                pattern_type="UI_BATCH",
                tool_sequence=[action_type],
                description=(
                    f"UI action '{action_type}' performed 3+ times consecutively in "
                    f"{count} session(s), suggesting a repetitive manual workflow"
                ),
                occurrence_count=count,
                example_session_ids=example_ids,
                confidence=confidence,
            )
        )

    # --- UI Sequence detection ---
    subseq_sessions: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for sid, actions in sessions.items():
        action_names = [a["action_type"] for a in actions]
        for window_size in range(2, min(6, len(action_names) + 1)):
            for i in range(len(action_names) - window_size + 1):
                subseq = tuple(action_names[i : i + window_size])
                if len(set(subseq)) >= 2:
                    subseq_sessions[subseq].add(sid)

    ranked = sorted(subseq_sessions.items(), key=lambda kv: len(kv[1]), reverse=True)
    for subseq, sid_set in ranked:
        count = len(sid_set)
        if count < min_occurrences:
            continue
        sig = f"UI_SEQUENCE:{','.join(subseq)}"
        if sig in seen_signatures:
            continue
        is_subsumed = any(
            existing.startswith("UI_SEQUENCE:") and ",".join(subseq) in existing.split(":", 1)[1]
            for existing in seen_signatures
        )
        if is_subsumed:
            continue
        seen_signatures.add(sig)
        example_ids = sorted(sid_set)[:10]
        confidence = min(0.5, round(count / total_sessions, 3))
        patterns.append(
            _make_pattern(
                pattern_type="UI_SEQUENCE",
                tool_sequence=list(subseq),
                description=(
                    f"UI sequence {' -> '.join(subseq)} appears in "
                    f"{count} session(s)"
                ),
                occurrence_count=count,
                example_session_ids=example_ids,
                confidence=confidence,
            )
        )

    return patterns


# ======================================================================
# 3. Cross-source correlation (UI action <-> tool call within ±5 min)
# ======================================================================

def _detect_cross_source_patterns(min_occurrences: int, seen_signatures: set[str]) -> list[dict]:
    ui_rows = query_db(
        "SELECT session_id, timestamp, action_type "
        "FROM ui_activity_log ORDER BY session_id, timestamp"
    )
    tool_rows = query_db(
        "SELECT session_id, timestamp, tool_name "
        "FROM tool_call_log ORDER BY session_id, timestamp"
    )
    if not ui_rows or not tool_rows:
        return []

    # Build per-session timelines
    ui_by_session: dict[str, list[dict]] = defaultdict(list)
    for row in ui_rows:
        ui_by_session[row["session_id"]].append(row)

    tool_by_session: dict[str, list[dict]] = defaultdict(list)
    for row in tool_rows:
        tool_by_session[row["session_id"]].append(row)

    # Find overlapping sessions
    common_sessions = set(ui_by_session.keys()) & set(tool_by_session.keys())
    if not common_sessions:
        return []

    # Count pairs: (ui_action, tool_name) that co-occur within the window
    pair_counter: Counter = Counter()
    pair_sessions: dict[tuple[str, str], list[str]] = defaultdict(list)

    window = timedelta(minutes=_CROSS_SOURCE_WINDOW_MINS)

    for sid in common_sessions:
        ui_events = ui_by_session[sid]
        tool_events = tool_by_session[sid]
        # Track pairs already found in this session to avoid double-counting
        found_pairs: set[tuple[str, str]] = set()

        for ui_evt in ui_events:
            ui_ts = _parse_ts(ui_evt["timestamp"])
            if ui_ts is None:
                continue
            for tool_evt in tool_events:
                tool_ts = _parse_ts(tool_evt["timestamp"])
                if tool_ts is None:
                    continue
                if abs(ui_ts - tool_ts) <= window:
                    pair = (ui_evt["action_type"], tool_evt["tool_name"])
                    if pair not in found_pairs:
                        found_pairs.add(pair)
                        pair_counter[pair] += 1
                        pair_sessions[pair].append(sid)

    patterns: list[dict] = []
    for (ui_action, tool_name), count in pair_counter.most_common():
        if count < min_occurrences:
            continue
        sig = f"CROSS_SOURCE:{ui_action}+{tool_name}"
        if sig in seen_signatures:
            continue
        seen_signatures.add(sig)
        example_ids = pair_sessions[(ui_action, tool_name)][:10]
        confidence = round(count / len(common_sessions), 3) if common_sessions else 0
        patterns.append(
            _make_pattern(
                pattern_type="CROSS_SOURCE",
                tool_sequence=[ui_action, tool_name],
                description=(
                    f"UI action '{ui_action}' and tool '{tool_name}' co-occur "
                    f"within {_CROSS_SOURCE_WINDOW_MINS} minutes in {count} session(s), "
                    f"suggesting a manual+agent paired workflow"
                ),
                occurrence_count=count,
                example_session_ids=example_ids,
                confidence=confidence,
            )
        )

    return patterns


# ======================================================================
# 4. Data pattern detection (mines live DB, not logs)
# ======================================================================

def _detect_data_patterns(seen_signatures: set[str]) -> list[dict]:
    """Mine live database tables for behavioral patterns."""
    results: list[dict] = []

    results.extend(_detect_cancellation_dow_patterns(seen_signatures))
    results.extend(_detect_appointment_cascades(seen_signatures))
    results.extend(_detect_pediatric_routing(seen_signatures))
    results.extend(_detect_follow_up_patterns(seen_signatures))
    results.extend(_detect_no_show_time_patterns(seen_signatures))

    return results


def _detect_cancellation_dow_patterns(seen_signatures: set[str]) -> list[dict]:
    """Per patient, find if >70% of cancellations fall on one day of week."""
    rows = query_db(
        "SELECT patient_id, date, status FROM appointments "
        "WHERE status IN ('cancelled', 'no_show')"
    )
    if not rows:
        return []

    # Group by patient
    patient_cancellations: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        patient_cancellations[row["patient_id"]].append(row["date"])

    patterns: list[dict] = []
    flagged_patients: list[str] = []

    for pid, dates in patient_cancellations.items():
        if len(dates) < 3:  # need at least 3 cancellations
            continue
        # Count by day of week
        dow_counts: Counter = Counter()
        for d in dates:
            try:
                dt = datetime.strptime(d, "%Y-%m-%d")
                dow_counts[dt.strftime("%A")] += 1
            except ValueError:
                continue

        total = sum(dow_counts.values())
        if total < 3:
            continue

        most_common_day, most_common_count = dow_counts.most_common(1)[0]
        ratio = most_common_count / total
        if ratio >= 0.70:
            flagged_patients.append(pid)

    if flagged_patients:
        sig = "DATA_PATTERN:cancellation_day_of_week"
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            # Look up patient names for description
            names = _get_patient_names(flagged_patients[:5])
            patterns.append(
                _make_pattern(
                    pattern_type="DATA_PATTERN",
                    tool_sequence=["cancellation_day_of_week"],
                    description=(
                        f"{len(flagged_patients)} patient(s) cancel/no-show >70% on the same "
                        f"day of week (e.g. {', '.join(names)}). Suggests scheduling should "
                        f"avoid their problem day."
                    ),
                    occurrence_count=len(flagged_patients),
                    example_session_ids=[f"patient:{pid}" for pid in flagged_patients],
                    confidence=min(0.5, round(len(flagged_patients) / len(patient_cancellations), 3)),
                )
            )

    return patterns


def _detect_appointment_cascades(seen_signatures: set[str]) -> list[dict]:
    """Find patients with recurring multi-appointment type sequences
    (e.g., blood_test -> follow_up -> standard repeating over time)."""
    rows = query_db(
        "SELECT patient_id, date, type FROM appointments "
        "WHERE status IN ('scheduled', 'completed') "
        "ORDER BY patient_id, date"
    )
    if not rows:
        return []

    patterns: list[dict] = []

    # Group by patient, get type sequences
    patient_sequences: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        patient_sequences[row["patient_id"]].append(row["type"])

    # Look for patients where a 3-step sequence repeats
    cascade_patients: list[str] = []
    cascade_examples: dict[str, tuple[str, ...]] = {}

    for pid, types in patient_sequences.items():
        if len(types) < 6:  # need at least 2 repetitions of a 3-step
            continue
        # Sliding window of size 3, count subsequences
        subseq_count: Counter = Counter()
        for i in range(len(types) - 2):
            sub = tuple(types[i : i + 3])
            if len(set(sub)) >= 2:  # at least 2 different types
                subseq_count[sub] += 1

        for sub, count in subseq_count.most_common(1):
            if count >= 2:
                cascade_patients.append(pid)
                cascade_examples[pid] = sub
                break

    if cascade_patients:
        sig = "DATA_PATTERN:appointment_type_cascade"
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            # Build example description from first patient
            example_pid = cascade_patients[0]
            example_seq = cascade_examples[example_pid]
            names = _get_patient_names(cascade_patients[:5])
            patterns.append(
                _make_pattern(
                    pattern_type="DATA_PATTERN",
                    tool_sequence=["appointment_type_cascade"],
                    description=(
                        f"{len(cascade_patients)} patient(s) follow recurring appointment "
                        f"cascades (e.g. {' -> '.join(example_seq)} for {names[0] if names else example_pid}). "
                        f"These could be auto-scheduled as a series."
                    ),
                    occurrence_count=len(cascade_patients),
                    example_session_ids=[f"patient:{pid}" for pid in cascade_patients],
                    confidence=min(0.5, round(len(cascade_patients) / len(patient_sequences), 3)),
                )
            )

    return patterns


def _detect_pediatric_routing(seen_signatures: set[str]) -> list[dict]:
    """Identify pediatric patients (<16) and check if they are consistently
    routed to the same doctor."""
    # Find patients under 16
    today = datetime.now().strftime("%Y-%m-%d")
    cutoff_date = (datetime.now() - timedelta(days=16 * 365)).strftime("%Y-%m-%d")

    patterns: list[dict] = []

    pediatric_patients = query_db(
        "SELECT id, first_name, last_name, dob FROM patients "
        "WHERE dob > ?",
        (cutoff_date,),
    )
    if not pediatric_patients:
        return []

    pediatric_ids = [p["id"] for p in pediatric_patients]
    if not pediatric_ids:
        return []

    # Check their doctor assignments
    placeholders = ",".join("?" * len(pediatric_ids))
    appt_rows = query_db(
        f"SELECT a.patient_id, a.doctor_id, d.name as doctor_name "
        f"FROM appointments a JOIN doctors d ON a.doctor_id = d.id "
        f"WHERE a.patient_id IN ({placeholders})",  # nosec B608 - placeholders are ? chars
        tuple(pediatric_ids),
    )
    if not appt_rows:
        return []

    # Count doctor assignments per patient
    patient_doctors: dict[str, Counter] = defaultdict(Counter)
    for row in appt_rows:
        patient_doctors[row["patient_id"]][row["doctor_id"]] += 1

    # Find patients where >80% of appointments are with one doctor
    routed_patients: list[str] = []
    primary_doctor = None
    primary_doctor_name = None
    for pid, doc_counts in patient_doctors.items():
        total = sum(doc_counts.values())
        if total < 2:
            continue
        top_doc, top_count = doc_counts.most_common(1)[0]
        if top_count / total >= 0.80:
            routed_patients.append(pid)
            if primary_doctor is None:
                primary_doctor = top_doc
                # Look up name
                for row in appt_rows:
                    if row["doctor_id"] == top_doc:
                        primary_doctor_name = row["doctor_name"]
                        break

    if len(routed_patients) >= 2:
        sig = "DATA_PATTERN:pediatric_routing"
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            names = _get_patient_names(routed_patients[:5])
            patterns.append(
                _make_pattern(
                    pattern_type="DATA_PATTERN",
                    tool_sequence=["pediatric_routing"],
                    description=(
                        f"{len(routed_patients)} pediatric patients are consistently "
                        f"routed to {primary_doctor_name or 'the same doctor'} "
                        f"(e.g. {', '.join(names)}). New pediatric bookings could "
                        f"auto-assign to this practitioner."
                    ),
                    occurrence_count=len(routed_patients),
                    example_session_ids=[f"patient:{pid}" for pid in routed_patients],
                    confidence=min(0.5, round(len(routed_patients) / len(patient_doctors), 3)),
                )
            )

    return patterns


def _detect_follow_up_patterns(seen_signatures: set[str]) -> list[dict]:
    """After new_patient appointments, check if there's always a follow_up
    within 14 days for the same patient."""
    new_patient_appts = query_db(
        "SELECT patient_id, date FROM appointments "
        "WHERE type = 'new_patient' AND status IN ('scheduled', 'completed') "
        "ORDER BY patient_id, date"
    )
    if not new_patient_appts:
        return []

    patterns: list[dict] = []
    follow_up_count = 0
    total_new_patients = 0
    example_patients: list[str] = []

    for appt in new_patient_appts:
        total_new_patients += 1
        try:
            appt_date = datetime.strptime(appt["date"], "%Y-%m-%d")
        except ValueError:
            continue
        window_end = (appt_date + timedelta(days=14)).strftime("%Y-%m-%d")
        # Check for a follow_up within 14 days
        follow_ups = query_db(
            "SELECT id FROM appointments "
            "WHERE patient_id = ? AND type = 'follow_up' "
            "AND date > ? AND date <= ? "
            "AND status IN ('scheduled', 'completed')",
            (appt["patient_id"], appt["date"], window_end),
        )
        if follow_ups:
            follow_up_count += 1
            if appt["patient_id"] not in example_patients:
                example_patients.append(appt["patient_id"])

    if total_new_patients >= 2 and follow_up_count / total_new_patients >= 0.50:
        sig = "DATA_PATTERN:new_patient_follow_up"
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            ratio_pct = round(follow_up_count / total_new_patients * 100)
            names = _get_patient_names(example_patients[:5])
            patterns.append(
                _make_pattern(
                    pattern_type="DATA_PATTERN",
                    tool_sequence=["new_patient_follow_up"],
                    description=(
                        f"{ratio_pct}% of new patient appointments are followed by a "
                        f"follow-up within 14 days ({follow_up_count}/{total_new_patients}). "
                        f"Follow-ups could be auto-scheduled at booking time."
                    ),
                    occurrence_count=follow_up_count,
                    example_session_ids=[f"patient:{pid}" for pid in example_patients],
                    confidence=min(0.5, round(follow_up_count / total_new_patients, 3)),
                )
            )

    return patterns


def _detect_no_show_time_patterns(seen_signatures: set[str]) -> list[dict]:
    """Detect patients who no-show disproportionately at early morning slots."""
    rows = query_db(
        "SELECT patient_id, time, status FROM appointments "
        "WHERE status IN ('no_show', 'completed')"
    )
    if not rows:
        return []

    patterns: list[dict] = []

    # Group by patient, then by status
    patient_slots: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        patient_slots[row["patient_id"]][row["status"]].append(row["time"])

    flagged_patients: list[str] = []

    for pid, status_times in patient_slots.items():
        no_shows = status_times.get("no_show", [])
        completed = status_times.get("completed", [])
        if len(no_shows) < 3:
            continue

        # Check if no-shows cluster in early morning (before 10:00)
        early_no_shows = sum(1 for t in no_shows if t < "10:00")
        early_ratio = early_no_shows / len(no_shows)

        if early_ratio >= 0.60:
            flagged_patients.append(pid)

    if flagged_patients:
        sig = "DATA_PATTERN:early_morning_no_show"
        if sig not in seen_signatures:
            seen_signatures.add(sig)
            names = _get_patient_names(flagged_patients[:5])
            patterns.append(
                _make_pattern(
                    pattern_type="DATA_PATTERN",
                    tool_sequence=["early_morning_no_show"],
                    description=(
                        f"{len(flagged_patients)} patient(s) no-show disproportionately "
                        f"at early morning slots (before 10am) — e.g. {', '.join(names)}. "
                        f"Consider scheduling these patients in later time slots."
                    ),
                    occurrence_count=len(flagged_patients),
                    example_session_ids=[f"patient:{pid}" for pid in flagged_patients],
                    confidence=min(0.5, round(len(flagged_patients) / len(patient_slots), 3)),
                )
            )

    return patterns


# ======================================================================
# Helpers
# ======================================================================

def _make_pattern(
    *,
    pattern_type: str,
    tool_sequence: list[str],
    description: str,
    occurrence_count: int,
    example_session_ids: list[str],
    confidence: float,
) -> dict:
    """Build a pattern dict with a generated ID."""
    return {
        "id": f"pat-{uuid.uuid4().hex[:8]}",
        "pattern_type": pattern_type,
        "description": description,
        "tool_sequence": tool_sequence,
        "conversation_context": None,
        "occurrence_count": occurrence_count,
        "example_session_ids": example_session_ids,
        "confidence": confidence,
        "status": "new",
    }


def _parse_ts(ts_str: str | None) -> datetime | None:
    """Parse an ISO-ish timestamp string, returning None on failure."""
    if not ts_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f"):
        try:
            return datetime.strptime(ts_str, fmt)
        except ValueError:
            continue
    return None


def _get_patient_names(patient_ids: list[str]) -> list[str]:
    """Look up patient names for a list of IDs."""
    if not patient_ids:
        return []
    placeholders = ",".join("?" * len(patient_ids))
    rows = query_db(
        f"SELECT id, first_name, last_name FROM patients WHERE id IN ({placeholders})",  # nosec B608
        tuple(patient_ids),
    )
    name_map = {r["id"]: f"{r['first_name']} {r['last_name']}" for r in rows}
    return [name_map.get(pid, pid) for pid in patient_ids]
