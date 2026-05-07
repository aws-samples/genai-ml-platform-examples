"""SQLite database module for the medical receptionist agent."""

import sqlite3
from backend.config import settings


def get_connection() -> sqlite3.Connection:
    """Return a SQLite connection with Row factory enabled."""
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query_db(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT query and return all rows as a list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def execute_db(sql: str, params: tuple = ()) -> int | None:
    """Execute a write query (INSERT/UPDATE/DELETE), commit, and return lastrowid."""
    conn = get_connection()
    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {r["name"] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()}  # nosec B608  # nosemgrep


def init_db() -> None:
    """Create all tables if they don't already exist."""
    conn = get_connection()
    try:
        conn.executescript(_SCHEMA_SQL)
        # Migrate existing detected_patterns tables that lack classification column
        cols = _columns(conn, "detected_patterns")
        if "classification" not in cols:
            conn.execute("ALTER TABLE detected_patterns ADD COLUMN classification TEXT")
            conn.commit()

        # Ensure tool_call_log has success/error columns
        tcl_cols = _columns(conn, "tool_call_log")
        if tcl_cols:
            if "success" not in tcl_cols:
                conn.execute("ALTER TABLE tool_call_log ADD COLUMN success INTEGER DEFAULT 1")
            if "error_message" not in tcl_cols:
                conn.execute("ALTER TABLE tool_call_log ADD COLUMN error_message TEXT")
            conn.commit()

        # Ensure unified skills columns exist on legacy skills tables
        sk_cols = _columns(conn, "skills")
        if sk_cols:
            for col, ddl in _SKILLS_COLUMN_ADDITIONS:
                if col not in sk_cols:
                    conn.execute(f"ALTER TABLE skills ADD COLUMN {ddl}")  # nosec B608  # nosemgrep
            conn.commit()

        # Ensure pipeline_state has skills_skipped column
        ps_cols = _columns(conn, "pipeline_state")
        if ps_cols and "skills_skipped" not in ps_cols:
            conn.execute("ALTER TABLE pipeline_state ADD COLUMN skills_skipped INTEGER DEFAULT 0")
            conn.commit()

        # Ensure skill_executions has observability columns
        se_cols = _columns(conn, "skill_executions")
        if se_cols:
            for col, ddl in [
                ("tokens_input", "tokens_input INTEGER"),
                ("tokens_output", "tokens_output INTEGER"),
                ("estimated_cost_usd", "estimated_cost_usd REAL"),
                ("llm_latency_ms", "llm_latency_ms INTEGER"),
            ]:
                if col not in se_cols:
                    conn.execute(f"ALTER TABLE skill_executions ADD COLUMN {ddl}")  # nosec B608  # nosemgrep
            conn.commit()
    finally:
        conn.close()


# Columns added to older `skills` tables as part of the unification work.
_SKILLS_COLUMN_ADDITIONS = [
    ("scheduled", "scheduled INTEGER DEFAULT 0"),
    ("schedule_cadence", "schedule_cadence TEXT"),
    ("schedule_time", "schedule_time TEXT"),
    ("schedule_day", "schedule_day INTEGER"),
    ("batch_selection_hint", "batch_selection_hint TEXT"),
    ("enabled_at", "enabled_at TEXT"),
    ("last_run_at", "last_run_at TEXT"),
    ("cached_items", "cached_items TEXT"),
    ("approval_threshold", "approval_threshold INTEGER DEFAULT 1"),
]




_SCHEMA_SQL = """
-- Core Domain
CREATE TABLE IF NOT EXISTS doctors (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    specialty TEXT,
    consultation_duration_mins INTEGER DEFAULT 30,
    working_days TEXT DEFAULT '["Monday","Tuesday","Wednesday","Thursday","Friday"]',
    hours_start TEXT DEFAULT '09:00',
    hours_end TEXT DEFAULT '17:00'
);

CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    dob TEXT,
    phone TEXT,
    email TEXT,
    preferred_contact TEXT DEFAULT 'phone',
    notes TEXT,
    no_show_count INTEGER DEFAULT 0,
    last_visit TEXT
);

CREATE TABLE IF NOT EXISTS appointments (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    doctor_id TEXT NOT NULL,
    date TEXT NOT NULL,
    time TEXT NOT NULL,
    duration_mins INTEGER DEFAULT 30,
    status TEXT DEFAULT 'scheduled',
    type TEXT DEFAULT 'standard',
    reminder_sent INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now')),
    notes TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (doctor_id) REFERENCES doctors(id)
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    appointment_id TEXT,
    amount REAL NOT NULL,
    amount_paid REAL DEFAULT 0,
    status TEXT DEFAULT 'outstanding',
    due_date TEXT,
    issued_date TEXT,
    chase_count INTEGER DEFAULT 0,
    last_chased TEXT,
    description TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE TABLE IF NOT EXISTS practice_info (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Communications
CREATE TABLE IF NOT EXISTS communications (
    id TEXT PRIMARY KEY,
    patient_id TEXT,
    channel TEXT NOT NULL,
    type TEXT,
    content TEXT,
    status TEXT DEFAULT 'sent',
    sent_at TEXT DEFAULT (datetime('now')),
    triggered_by TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);

-- Audit
CREATE TABLE IF NOT EXISTS tool_call_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    tool_name TEXT NOT NULL,
    tool_params TEXT,
    result_summary TEXT,
    duration_ms INTEGER,
    sequence_number INTEGER,
    success INTEGER DEFAULT 1,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS conversation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    role TEXT NOT NULL,
    content TEXT,
    tool_calls_in_turn TEXT,
    sequence_number INTEGER
);

-- Analysis Output
CREATE TABLE IF NOT EXISTS detected_patterns (
    id TEXT PRIMARY KEY,
    detected_at TEXT DEFAULT (datetime('now')),
    pattern_type TEXT,
    description TEXT,
    tool_sequence TEXT,
    conversation_context TEXT,
    occurrence_count INTEGER DEFAULT 0,
    example_session_ids TEXT,
    confidence REAL DEFAULT 0,
    status TEXT DEFAULT 'new',
    classification TEXT              -- legacy (no longer used)
);

-- UI Activity Tracking
CREATE TABLE IF NOT EXISTS ui_activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now')),
    action_type TEXT NOT NULL,
    action_detail TEXT,              -- JSON: what was clicked, context
    entity_type TEXT,
    entity_id TEXT,
    view TEXT,
    duration_ms INTEGER,
    metadata TEXT
);

-- Patient Memories
CREATE TABLE IF NOT EXISTS patient_memories (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    memory_type TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    confidence REAL DEFAULT 0.5,
    first_observed TEXT DEFAULT (datetime('now')),
    last_confirmed TEXT,
    observation_count INTEGER DEFAULT 1,
    status TEXT DEFAULT 'active',
    metadata TEXT
);

-- Unified Skills (agent-executed automations, ad-hoc or scheduled)
CREATE TABLE IF NOT EXISTS skills (
    id TEXT PRIMARY KEY,
    pattern_id TEXT REFERENCES detected_patterns(id),
    name TEXT NOT NULL,
    description TEXT,
    trigger_description TEXT,        -- when this skill should activate
    agent_prompt_template TEXT,      -- prompt fragment used at run time
    tool_config TEXT,                -- JSON list of tools needed
    batch_selection_hint TEXT,       -- natural-language "what to process"
    example_scenario TEXT,
    status TEXT DEFAULT 'draft',     -- draft | pending_review | enabled | disabled
    created_at TEXT DEFAULT (datetime('now')),
    tested_at TEXT,
    usage_count INTEGER DEFAULT 0,
    scheduled INTEGER DEFAULT 0,     -- 0 = ad-hoc, 1 = scheduled
    schedule_cadence TEXT,           -- daily | weekdays | weekly | monthly
    schedule_time TEXT,              -- HH:MM
    schedule_day INTEGER,            -- day-of-week (0=Mon) or day-of-month
    enabled_at TEXT,                 -- when the user flipped Enable
    last_run_at TEXT,
    cached_items TEXT                -- JSON list cached at stage time for ad-hoc skills
);

-- Doctor Availability — ad-hoc exceptions that win over the base schedule.
CREATE TABLE IF NOT EXISTS doctor_unavailability (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doctor_id TEXT NOT NULL REFERENCES doctors(id),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    reason TEXT NOT NULL,
    note TEXT,
    created_by TEXT NOT NULL DEFAULT 'user',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_doctor_unavailability_doctor_date
    ON doctor_unavailability (doctor_id, start_date);

CREATE TABLE IF NOT EXISTS pathology_results (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    test_name TEXT NOT NULL,
    result_value TEXT NOT NULL,
    reference_range TEXT,
    flagged INTEGER DEFAULT 0,
    flag_reason TEXT,
    ordering_doctor_id TEXT REFERENCES doctors(id),
    received_date TEXT NOT NULL,
    received_at TEXT DEFAULT (datetime('now')),
    reviewed INTEGER DEFAULT 0,
    reviewed_by TEXT,
    reviewed_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_pathology_results_date
    ON pathology_results (received_date, flagged);

-- Execution History
CREATE TABLE IF NOT EXISTS skill_executions (
    id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL DEFAULT 'running',
    trigger TEXT NOT NULL DEFAULT 'manual',
    items_total INTEGER DEFAULT 0,
    items_succeeded INTEGER DEFAULT 0,
    items_failed INTEGER DEFAULT 0,
    duration_ms INTEGER,
    summary TEXT,
    error TEXT,
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);

CREATE TABLE IF NOT EXISTS skill_execution_items (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    item_index INTEGER NOT NULL,
    entity_id TEXT,
    entity_name TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    tools_called TEXT,
    result_summary TEXT,
    error TEXT,
    duration_ms INTEGER,
    FOREIGN KEY (execution_id) REFERENCES skill_executions(id)
);

CREATE INDEX IF NOT EXISTS idx_skill_executions_skill
    ON skill_executions (skill_id, started_at DESC);

-- Pipeline state (singleton row)
CREATE TABLE IF NOT EXISTS pipeline_state (
    id TEXT PRIMARY KEY DEFAULT 'singleton',
    last_run_at TEXT,
    status TEXT DEFAULT 'idle',
    last_duration_ms INTEGER,
    patterns_detected INTEGER DEFAULT 0,
    skills_generated INTEGER DEFAULT 0,
    skills_skipped INTEGER DEFAULT 0,
    memories_generated INTEGER DEFAULT 0,
    next_scheduled_run TEXT,
    auto_enabled INTEGER DEFAULT 1,
    schedule_time TEXT DEFAULT '02:00',
    error_message TEXT,
    current_stage TEXT,
    stages_total INTEGER DEFAULT 4,
    stage_index INTEGER DEFAULT 0
);

INSERT OR IGNORE INTO pipeline_state (id) VALUES ('singleton');

-- Pipeline run history (one row per analysis run)
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    duration_ms INTEGER,
    status TEXT DEFAULT 'running',
    patterns_detected INTEGER DEFAULT 0,
    patterns_enriched INTEGER DEFAULT 0,
    skills_generated INTEGER DEFAULT 0,
    skills_skipped INTEGER DEFAULT 0,
    memories_generated INTEGER DEFAULT 0,
    error_message TEXT
);
"""
