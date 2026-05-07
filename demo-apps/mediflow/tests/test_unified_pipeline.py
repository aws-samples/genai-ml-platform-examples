"""TASK-048: Pipeline tests for unified-skills generation.

After the migration Stage 3 must emit only rows in ``skills`` (no workflow
rows anywhere); Stage 4 (workflow_populator) must be removed from the
orchestrator; and Stage 2 (``context_extractor``) must no longer emit
``recommended_classification``/``skill_indicators``/``workflow_indicators``.
"""

import inspect
import json
from unittest.mock import patch, MagicMock

import pytest

from backend.services.database import execute_db, query_db


class _MockResponse:
    def __init__(self, payload: dict):
        self._json = json.dumps(payload)

    def __str__(self):
        return self._json


MOCK_CONTEXT_UNIFIED = {
    "intent_nuances": "Morning briefing routine",
    "conditional_logic": "Predictable weekday cadence",
    "human_review_triggers": [],
    "personalization_signals": ["flagged patients"],
    "exceptions": "",
    # No skill_indicators / workflow_indicators / recommended_classification
    "cadence_hint": "weekdays 08:00",
}

MOCK_SKILL_DEF_SCHEDULED = {
    "name": "Morning Briefing",
    "description": "Briefs Rada every weekday",
    "trigger_description": "Weekdays at 08:00",
    "agent_prompt_template": "At 08:00 on each weekday, compile ...",
    "tool_config": ["get_doctor_schedule", "check_pathology_results"],
    "batch_selection_hint": "All doctors working today plus flagged patients",
    "example_scenario": "Monday 08:00 → briefing composed for Rada",
    "scheduled": True,
    "schedule_cadence": "weekdays",
    "schedule_time": "08:00",
    "schedule_day": None,
    "status": "pending_review",
}


def _seed_min_pattern():
    """Seed a single pattern to drive generate_automations."""
    execute_db(
        "INSERT INTO detected_patterns (id, pattern_type, description, "
        "tool_sequence, occurrence_count, confidence, status, "
        "conversation_context) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "pat-u-001",
            "CROSS_SOURCE",
            "Morning routine",
            json.dumps(["get_doctor_schedule", "check_pathology_results"]),
            42,
            0.93,
            "new",
            json.dumps({"intent_nuances": "daily", "cadence_hint": "weekdays 08:00"}),
        ),
    )


class TestStage3EmitsOnlySkills:
    def test_generate_automations_returns_skills_only(self):
        """Stage 3 return contract: {'skills': [...]} with no 'workflows' key,
        OR workflows key present but always empty."""
        _seed_min_pattern()
        from backend.analysis import automation_generator

        mock_agent = MagicMock()
        mock_agent.return_value = _MockResponse(MOCK_SKILL_DEF_SCHEDULED)

        patterns = query_db("SELECT * FROM detected_patterns")
        # Decode conversation_context for the pipeline
        for p in patterns:
            if p.get("conversation_context"):
                p["conversation_context"] = json.loads(p["conversation_context"])
            if p.get("tool_sequence"):
                p["tool_sequence"] = json.loads(p["tool_sequence"])

        with patch.object(automation_generator, "Agent", return_value=mock_agent), \
             patch.object(automation_generator, "BedrockModel"):
            result = automation_generator.generate_automations(patterns)

        assert "skills" in result
        # workflows key either absent or empty
        assert not result.get("workflows"), (
            "Stage 3 must not emit workflow rows in unified model"
        )
        assert len(result["skills"]) >= 1

    def test_no_workflow_rows_written(self):
        """DB invariant: after Stage 3, workflow-related tables are empty
        (or don't exist, post-migration)."""
        _seed_min_pattern()
        from backend.analysis import automation_generator

        mock_agent = MagicMock()
        mock_agent.return_value = _MockResponse(MOCK_SKILL_DEF_SCHEDULED)

        patterns = query_db("SELECT * FROM detected_patterns")
        for p in patterns:
            if p.get("conversation_context"):
                p["conversation_context"] = json.loads(p["conversation_context"])
            if p.get("tool_sequence"):
                p["tool_sequence"] = json.loads(p["tool_sequence"])

        with patch.object(automation_generator, "Agent", return_value=mock_agent), \
             patch.object(automation_generator, "BedrockModel"):
            automation_generator.generate_automations(patterns)

        # Either table is gone (post migration schema drop) or present+empty.
        tables = query_db(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='workflows'"
        )
        if tables:
            rows = query_db("SELECT COUNT(*) AS n FROM workflows")
            assert rows[0]["n"] == 0, "No workflow rows may be created in unified model"

    def test_scheduled_flag_persisted(self):
        _seed_min_pattern()
        from backend.analysis import automation_generator

        mock_agent = MagicMock()
        mock_agent.return_value = _MockResponse(MOCK_SKILL_DEF_SCHEDULED)

        patterns = query_db("SELECT * FROM detected_patterns")
        for p in patterns:
            if p.get("conversation_context"):
                p["conversation_context"] = json.loads(p["conversation_context"])
            if p.get("tool_sequence"):
                p["tool_sequence"] = json.loads(p["tool_sequence"])

        with patch.object(automation_generator, "Agent", return_value=mock_agent), \
             patch.object(automation_generator, "BedrockModel"):
            automation_generator.generate_automations(patterns)

        rows = query_db("SELECT scheduled, schedule_cadence, schedule_time FROM skills")
        assert len(rows) == 1
        assert rows[0]["scheduled"] == 1
        assert rows[0]["schedule_cadence"] == "weekdays"
        assert rows[0]["schedule_time"] == "08:00"


class TestStage4Retired:
    """Stage 4 workflow populator must no longer be invoked from orchestrator."""

    def test_orchestrator_does_not_import_workflow_populator(self):
        source = inspect.getsource(
            __import__("backend.analysis.orchestrator", fromlist=["*"])
        )
        assert "populate_workflows" not in source, (
            "orchestrator.py must not import/call populate_workflows — Stage 4 retired"
        )
        assert "workflow_populator" not in source, (
            "orchestrator.py must not reference the workflow_populator module"
        )

    def test_orchestrator_run_analysis_returns_no_workflow_keys(self):
        """Summary payload is shaped for the unified model."""
        from backend.analysis import orchestrator

        with patch.object(orchestrator, "detect_patterns", return_value=[]):
            summary = orchestrator.run_analysis()

        assert summary["status"] == "complete"
        # Must not report workflow/item counts — construct has been retired
        assert "workflows_generated" not in summary
        assert "workflow_items" not in summary


class TestContextExtractorSimplified:
    """Stage 2 no longer classifies skill vs workflow."""

    def test_prompt_template_has_no_classification_fields(self):
        from backend.analysis import context_extractor
        # The user template used to ask the LLM for these keys. In the unified
        # model only a cadence hint should be requested.
        tpl = getattr(context_extractor, "_EXTRACTION_USER_TEMPLATE", "")
        assert "recommended_classification" not in tpl
        assert "skill_indicators" not in tpl
        assert "workflow_indicators" not in tpl

    def test_fallback_context_has_no_classification_fields(self):
        from backend.analysis.context_extractor import _fallback_context
        ctx = _fallback_context()
        assert "recommended_classification" not in ctx
        assert "skill_indicators" not in ctx
        assert "workflow_indicators" not in ctx
