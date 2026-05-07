"""TASK-048: Migration tests for unified skills table.

Pins the contract that ``migrate_to_unified_skills()`` transforms legacy
``workflows``/``workflow_steps``/``workflow_items`` rows into unified
``skills`` rows with scheduled=1 and populated cadence, flattens the step
narrative into ``agent_prompt_template``, and drops the retired tables.

These tests must fail on today's code (the migration function does not
exist yet and the schema still carries the legacy columns/tables).
"""

import json

import pytest

from backend.services.database import (
    get_connection,
    execute_db,
    query_db,
)


def _table_exists(name: str) -> bool:
    rows = query_db(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    )
    return bool(rows)


def _columns(table: str) -> set[str]:
    conn = get_connection()
    try:
        cur = conn.execute(f"PRAGMA table_info({table})")
        return {row["name"] for row in cur.fetchall()}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Seed legacy data: one workflow + 3 steps + 2 items
# ---------------------------------------------------------------------------

def _seed_legacy_workflow():
    # Pattern
    execute_db(
        "INSERT INTO detected_patterns (id, pattern_type, description, "
        "tool_sequence, occurrence_count, confidence, status, classification) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "pat-legacy-001",
            "CROSS_SOURCE",
            "Morning briefing pattern",
            json.dumps(["get_doctor_schedule", "check_pathology_results"]),
            42,
            0.93,
            "new",
            "workflow",
        ),
    )
    # Workflow (with schedule columns)
    execute_db(
        "INSERT INTO workflows (id, pattern_id, name, description, "
        "selection_criteria, status, schedule_cadence, schedule_time, "
        "schedule_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "wf-legacy-001",
            "pat-legacy-001",
            "Morning Briefing",
            "Compiles the daily morning briefing",
            "SELECT id FROM doctors WHERE working_days LIKE '%Mon%'",
            "pending_review",
            "weekdays",
            "08:00",
            None,
        ),
    )
    # Steps
    for i, (tool, msg) in enumerate(
        [
            ("get_doctor_schedule", None),
            ("check_pathology_results", None),
            (None, "Compile briefing summary with flagged patients"),
        ],
        start=1,
    ):
        execute_db(
            "INSERT INTO workflow_steps (id, workflow_id, step_order, "
            "step_type, tool_name, prompt_template) VALUES (?, ?, ?, ?, ?, ?)",
            (
                f"ws-legacy-00{i}",
                "wf-legacy-001",
                i,
                "tool_call" if tool else "message_compose",
                tool,
                msg,
            ),
        )
    # Items (should be dropped in migration)
    for i in range(2):
        execute_db(
            "INSERT INTO workflow_items (id, workflow_id, entity_type, "
            "entity_id, status, priority_score) VALUES (?, ?, ?, ?, ?, ?)",
            (f"wi-legacy-00{i}", "wf-legacy-001", "doctor", f"dr-x{i}", "pending", 1.0),
        )


class TestMigrationCorrectness:
    """Legacy workflow rows survive as unified skills rows."""

    def test_migration_function_exists(self):
        from backend.services import database
        assert hasattr(database, "migrate_to_unified_skills"), (
            "backend.services.database.migrate_to_unified_skills must exist"
        )

    def test_workflow_row_becomes_scheduled_skill(self):
        _seed_legacy_workflow()
        from backend.services.database import migrate_to_unified_skills
        migrate_to_unified_skills()

        skills = query_db(
            "SELECT * FROM skills WHERE name = ?",
            ("Morning Briefing",),
        )
        assert len(skills) == 1, "Legacy workflow should migrate to exactly one skill row"
        sk = skills[0]
        assert sk["scheduled"] == 1
        assert sk["schedule_cadence"] == "weekdays"
        assert sk["schedule_time"] == "08:00"
        assert sk["pattern_id"] == "pat-legacy-001"

    def test_steps_flattened_into_agent_prompt_template(self):
        _seed_legacy_workflow()
        from backend.services.database import migrate_to_unified_skills
        migrate_to_unified_skills()

        skills = query_db(
            "SELECT agent_prompt_template FROM skills WHERE name = ?",
            ("Morning Briefing",),
        )
        tpl = skills[0]["agent_prompt_template"] or ""
        # All step content must be reachable as natural-language instruction
        assert "get_doctor_schedule" in tpl
        assert "check_pathology_results" in tpl
        assert "Compile briefing summary" in tpl

    def test_status_enabled_preserved_from_approved_workflow(self):
        """Workflows previously in 'approved' status migrate to scheduled skills
        that are ready to run. Spec allows either 'enabled' (pre-approved) or
        'pending_review' depending on source status — but 'pending_review'
        workflows must NOT come across as 'enabled'."""
        _seed_legacy_workflow()
        from backend.services.database import migrate_to_unified_skills
        migrate_to_unified_skills()

        sk = query_db(
            "SELECT status FROM skills WHERE name = ?",
            ("Morning Briefing",),
        )[0]
        # Source was 'pending_review' — must not auto-enable
        assert sk["status"] != "enabled"

    def test_legacy_tables_dropped(self):
        _seed_legacy_workflow()
        from backend.services.database import migrate_to_unified_skills
        migrate_to_unified_skills()

        assert not _table_exists("workflows"), "workflows table must be dropped"
        assert not _table_exists("workflow_steps"), "workflow_steps table must be dropped"
        assert not _table_exists("workflow_items"), "workflow_items table must be dropped"

    def test_unified_skills_schema_has_new_columns(self):
        cols = _columns("skills")
        for required in (
            "scheduled",
            "schedule_cadence",
            "schedule_time",
            "schedule_day",
            "batch_selection_hint",
            "enabled_at",
            "last_run_at",
        ):
            assert required in cols, f"skills table missing column '{required}'"

    def test_migration_is_idempotent(self):
        _seed_legacy_workflow()
        from backend.services.database import migrate_to_unified_skills
        migrate_to_unified_skills()
        migrate_to_unified_skills()  # second call must be a no-op

        skills = query_db(
            "SELECT COUNT(*) AS n FROM skills WHERE name = ?",
            ("Morning Briefing",),
        )
        assert skills[0]["n"] == 1

    def test_adhoc_skill_has_null_schedule(self):
        """Pre-existing skills (non-workflow origin) stay ad-hoc
        (scheduled=0, schedule_* = NULL) after migration."""
        execute_db(
            "INSERT INTO skills (id, name, description, status) "
            "VALUES (?, ?, ?, ?)",
            ("sk-adhoc-001", "Context-Aware Booking", "Adhoc", "pending_review"),
        )
        from backend.services.database import migrate_to_unified_skills
        migrate_to_unified_skills()

        sk = query_db("SELECT * FROM skills WHERE id = ?", ("sk-adhoc-001",))[0]
        assert sk["scheduled"] == 0
        assert sk["schedule_cadence"] is None
        assert sk["schedule_time"] is None
