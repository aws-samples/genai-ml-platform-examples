"""Integration test for the unified analysis pipeline.

Mocks LLM-dependent stages (context extraction + skill generation)
and exercises the full orchestrator end-to-end. After TASK-048, the
pipeline is 4 stages and emits only unified Skills.
"""

import json
from unittest.mock import patch, MagicMock

import pytest

from backend.services.database import execute_db, query_db
from backend.services.audit_service import log_tool_call, log_conversation_turn
from backend.analysis.orchestrator import run_analysis


# ---------------------------------------------------------------------------
# Helpers — seed realistic tool-call and conversation logs
# ---------------------------------------------------------------------------

def _seed_reminder_pattern():
    """Create a batch reminder pattern across 4 sessions with conversation context."""
    for s in range(1, 5):
        sess = f"sess-day1-{s:02d}"

        log_conversation_turn(sess, "user", f"Send a reminder to patient {s} about their appointment tomorrow")
        log_tool_call(sess, "search_patients", {"query": f"Patient{s}"}, f"Found patient pat-{s:03d}", 80)
        for r in range(4):
            log_tool_call(sess, "send_appointment_reminder", {"patient_id": f"pat-{r:03d}", "appointment_id": f"apt-{r:03d}"}, "Sent", 100)
        log_conversation_turn(sess, "assistant", f"I've sent reminders to all patients.")

        if s == 2:
            log_conversation_turn(sess, "user", "Actually, he's been a no-show twice. Flag it.")
            log_conversation_turn(sess, "assistant", "Noted — I'll flag patients with repeated no-shows.")


def _seed_payment_pattern():
    """Create a sequence pattern across 3 sessions."""
    for s in range(1, 4):
        sess = f"sess-pay-{s:02d}"
        log_conversation_turn(sess, "user", "Chase the overdue invoices please")
        log_tool_call(sess, "get_outstanding_invoices", {}, "3 invoices", 60)
        log_tool_call(sess, "send_payment_reminder", {"invoice_id": f"inv-{s:03d}"}, "Sent", 90)
        log_conversation_turn(sess, "assistant", "Payment reminder sent.")


def _seed_domain_data():
    """Insert minimal domain data so the pipeline can run."""
    execute_db(
        "INSERT INTO doctors (id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("dr-chen", "Dr Sarah Chen", "General Practice", 30, '["Monday","Tuesday","Wednesday","Thursday","Friday"]', "08:00", "17:00"),
    )
    for i in range(1, 5):
        execute_db(
            "INSERT INTO patients (id, first_name, last_name, dob, phone, email, preferred_contact, notes, no_show_count) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"pat-{i:03d}", f"First{i}", f"Last{i}", "1990-01-01", f"041200000{i}", f"p{i}@test.com", "sms", "", i - 1),
        )
    for i in range(1, 4):
        execute_db(
            "INSERT INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"apt-{i:03d}", f"pat-{i:03d}", "dr-chen", "2026-03-14", f"{8 + i}:00", 30, "confirmed", "standard", 0),
        )
    for i in range(1, 4):
        execute_db(
            "INSERT INTO invoices (id, patient_id, appointment_id, amount, amount_paid, status, due_date, issued_date, chase_count, description) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"inv-{i:03d}", f"pat-{i:03d}", f"apt-{i:03d}", 150.0, 0.0, "outstanding", "2026-03-01", "2026-02-15", 0, "Consultation"),
        )


# ---------------------------------------------------------------------------
# Mock LLM responses
# ---------------------------------------------------------------------------

MOCK_CONTEXT = {
    "intent_nuances": "Receptionist sends reminders one by one each morning",
    "conditional_logic": "Patients with 2+ no-shows need special handling",
    "human_review_triggers": ["Elderly or unwell patients flagged for review"],
    "personalization_signals": ["Gentle tone for unwell patients"],
    "exceptions": "Some patients explicitly excluded from chasing",
    "cadence_hint": "weekday mornings 08:00",
}

MOCK_SKILL_DEF = {
    "name": "Morning Appointment Reminders",
    "description": "Batch send appointment reminders with personalisation",
    "trigger_description": "Weekday mornings before clinic opens",
    "agent_prompt_template": "For each appointment tomorrow, send a reminder unless the patient has opted out. Flag no-show-prone patients for human review first.",
    "tool_config": ["send_appointment_reminder", "get_patient"],
    "batch_selection_hint": "Patients with appointments tomorrow whose reminder has not yet been sent.",
    "example_scenario": "Monday 08:00 — 14 reminders go out; 2 patients with 3+ no-shows flagged.",
    "scheduled": True,
    "schedule_cadence": "weekdays",
    "schedule_time": "08:00",
    "schedule_day": None,
    "status": "pending_review",
}


class _MockResponse:
    """Mock that makes str(response) return the JSON payload."""

    def __init__(self, payload: dict):
        self._json = json.dumps(payload)

    def __str__(self):
        return self._json


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestUnifiedAnalysisPipeline:
    """End-to-end test: seed logs → run analysis → verify unified output."""

    def _run_with_mocks(self):
        _seed_domain_data()
        _seed_reminder_pattern()
        _seed_payment_pattern()

        mock_context_agent = MagicMock()
        mock_context_agent.return_value = _MockResponse(MOCK_CONTEXT)

        mock_skill_agent = MagicMock()
        mock_skill_agent.return_value = _MockResponse(MOCK_SKILL_DEF)

        with patch("backend.analysis.context_extractor.Agent", return_value=mock_context_agent), \
             patch("backend.analysis.context_extractor.BedrockModel"), \
             patch("backend.analysis.automation_generator.Agent", return_value=mock_skill_agent), \
             patch("backend.analysis.automation_generator.BedrockModel"):
            return run_analysis()

    def test_pipeline_returns_summary(self):
        result = self._run_with_mocks()
        assert result["status"] == "complete"
        assert result["patterns_detected"] >= 1
        assert result["skills_generated"] >= 1

    def test_patterns_detected(self):
        self._run_with_mocks()
        patterns = query_db("SELECT * FROM detected_patterns")
        assert len(patterns) >= 1
        batch = [p for p in patterns if p["pattern_type"] == "BATCH"]
        assert len(batch) >= 1

    def test_unified_skills_created(self):
        self._run_with_mocks()
        skills = query_db("SELECT * FROM skills")
        assert len(skills) >= 1
        for sk in skills:
            assert sk["name"] is not None
            assert sk["status"] in ("draft", "pending_review", "enabled")
            # Scheduled flag always present
            assert sk["scheduled"] in (0, 1)

    def test_scheduled_skills_have_cadence(self):
        self._run_with_mocks()
        scheduled_skills = query_db("SELECT * FROM skills WHERE scheduled = 1")
        for sk in scheduled_skills:
            assert sk["schedule_cadence"]


class TestPipelineIdempotency:
    """Running the pipeline twice shouldn't crash."""

    def test_no_crash_on_rerun(self):
        _seed_domain_data()
        _seed_reminder_pattern()

        mock_agent = MagicMock()
        mock_agent.return_value = _MockResponse(MOCK_CONTEXT)

        mock_skill_agent = MagicMock()
        mock_skill_agent.return_value = _MockResponse(MOCK_SKILL_DEF)

        with patch("backend.analysis.context_extractor.Agent", return_value=mock_agent), \
             patch("backend.analysis.context_extractor.BedrockModel"), \
             patch("backend.analysis.automation_generator.Agent", return_value=mock_skill_agent), \
             patch("backend.analysis.automation_generator.BedrockModel"):
            run_analysis()
            result2 = run_analysis()

        assert result2["status"] == "complete"
