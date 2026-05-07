"""TASK-048: Skill API route contract tests.

Pins:
- ``GET  /api/skills`` — unified list (ex-workflows included)
- ``POST /api/skills/{id}/run`` — bypasses stage-and-confirm; requires
  ``status='enabled'``; updates ``last_run_at``.
- ``POST /api/skills/{id}/execute`` — ad-hoc batch skills emit a
  ``skill_approval`` SSE event; single-item skills run directly (no approval).
- ``PATCH /api/skills/{id}/schedule`` — set cadence/time/day.
- ``PATCH /api/skills/{id}/enable`` — flip status to 'enabled' and set
  ``enabled_at`` (acts as pre-approval for scheduled skills).
- ``/api/workflows/*`` — hard-cut 404 (file deleted, router not registered).
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.database import execute_db, query_db


client = TestClient(app)


# ---------------------------------------------------------------------------
# Seed helpers — must insert into the unified schema shape
# ---------------------------------------------------------------------------

def _insert_scheduled_skill(
    skill_id: str = "sk-u-001",
    name: str = "Morning Briefing",
    status: str = "enabled",
):
    execute_db(
        "INSERT INTO skills (id, name, description, trigger_description, "
        "agent_prompt_template, tool_config, scheduled, schedule_cadence, "
        "schedule_time, schedule_day, status, batch_selection_hint) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            skill_id,
            name,
            "Daily weekday briefing",
            "Weekday mornings",
            "At 08:00 compile briefing ...",
            json.dumps(["get_doctor_schedule", "check_pathology_results"]),
            1,
            "weekdays",
            "08:00",
            None,
            status,
            "All doctors working today plus flagged patients",
        ),
    )


def _insert_adhoc_batch_skill(
    skill_id: str = "sk-u-batch",
    name: str = "Overdue Invoice Chase",
    status: str = "enabled",
):
    execute_db(
        "INSERT INTO skills (id, name, description, trigger_description, "
        "agent_prompt_template, tool_config, scheduled, status, "
        "batch_selection_hint) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            skill_id,
            name,
            "Chase overdue invoices",
            "When asked to chase",
            "For each overdue invoice, send tone-appropriate reminder",
            json.dumps(["send_payment_chase"]),
            0,
            status,
            "invoices WHERE status='outstanding' AND due_date < now",
        ),
    )


def _insert_adhoc_single_skill(
    skill_id: str = "sk-u-single",
    name: str = "Chase Single Invoice",
):
    """Ad-hoc skill with no batch_selection_hint = single-item."""
    execute_db(
        "INSERT INTO skills (id, name, description, trigger_description, "
        "agent_prompt_template, tool_config, scheduled, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            skill_id,
            name,
            "Chase one invoice",
            "When asked to chase Sarah's invoice",
            "Send a single tone-appropriate reminder to the patient",
            json.dumps(["send_payment_chase"]),
            0,
            "enabled",
        ),
    )


# ---------------------------------------------------------------------------
# /api/skills — unified list
# ---------------------------------------------------------------------------

class TestUnifiedSkillList:
    def test_list_includes_migrated_skills(self):
        _insert_scheduled_skill()
        _insert_adhoc_batch_skill()
        resp = client.get("/api/skills")
        assert resp.status_code == 200
        data = resp.json()
        names = [s["name"] for s in data["skills"]]
        assert "Morning Briefing" in names
        assert "Overdue Invoice Chase" in names

    def test_scheduled_field_exposed(self):
        _insert_scheduled_skill()
        resp = client.get("/api/skills")
        sk = next(s for s in resp.json()["skills"] if s["name"] == "Morning Briefing")
        assert sk.get("scheduled") in (1, True)
        assert sk.get("schedule_cadence") == "weekdays"
        assert sk.get("schedule_time") == "08:00"


# ---------------------------------------------------------------------------
# /api/skills/{id}/enable
# ---------------------------------------------------------------------------

class TestEnableSkill:
    def test_enable_flips_status_and_sets_enabled_at(self):
        _insert_scheduled_skill(status="pending_review")
        resp = client.patch("/api/skills/sk-u-001/enable")
        assert resp.status_code == 200

        sk = query_db("SELECT status, enabled_at FROM skills WHERE id = ?", ("sk-u-001",))[0]
        assert sk["status"] == "enabled"
        assert sk["enabled_at"] is not None

    def test_enable_unknown_skill_returns_404(self):
        resp = client.patch("/api/skills/does-not-exist/enable")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/skills/{id}/schedule
# ---------------------------------------------------------------------------

class TestScheduleSkill:
    def test_update_cadence_and_time(self):
        _insert_scheduled_skill()
        resp = client.patch(
            "/api/skills/sk-u-001/schedule",
            json={"cadence": "weekly", "time": "09:30", "day": 1},
        )
        assert resp.status_code == 200

        sk = query_db(
            "SELECT schedule_cadence, schedule_time, schedule_day FROM skills WHERE id = ?",
            ("sk-u-001",),
        )[0]
        assert sk["schedule_cadence"] == "weekly"
        assert sk["schedule_time"] == "09:30"
        assert sk["schedule_day"] == 1

    def test_invalid_cadence_rejected(self):
        _insert_scheduled_skill()
        resp = client.patch(
            "/api/skills/sk-u-001/schedule",
            json={"cadence": "bogus"},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /api/skills/{id}/run — scheduler / Run-now / Approve-and-Run path
# ---------------------------------------------------------------------------

class TestRunSkill:
    def test_run_requires_enabled_status(self):
        _insert_scheduled_skill(status="pending_review")
        resp = client.post("/api/skills/sk-u-001/run")
        assert resp.status_code == 400
        assert "enabled" in resp.text.lower()

    def test_run_enabled_skill_returns_stream(self):
        _insert_scheduled_skill(status="enabled")
        resp = client.post("/api/skills/sk-u-001/run")
        assert resp.status_code == 200
        # SSE content-type
        assert resp.headers.get("content-type", "").startswith("text/event-stream")

    def test_run_updates_last_run_at(self):
        _insert_scheduled_skill(status="enabled")
        resp = client.post("/api/skills/sk-u-001/run")
        # Consume the stream so the finaliser runs
        _ = resp.content
        sk = query_db("SELECT last_run_at, usage_count FROM skills WHERE id = ?", ("sk-u-001",))[0]
        assert sk["last_run_at"] is not None
        assert sk["usage_count"] >= 1

    def test_run_unknown_skill_returns_404(self):
        resp = client.post("/api/skills/missing/run")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# /api/skills/{id}/execute — ad-hoc stage-and-confirm protocol
# ---------------------------------------------------------------------------

def _collect_sse_events(content: bytes) -> list[tuple[str, dict]]:
    """Very loose SSE parser for the test."""
    text = content.decode("utf-8", errors="replace")
    events: list[tuple[str, dict]] = []
    event_name = None
    for line in text.splitlines():
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            payload = line.split(":", 1)[1].strip()
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                parsed = {"raw": payload}
            events.append((event_name or "message", parsed))
            event_name = None
    return events


class TestExecuteAdhocBatchSkill:
    def test_emits_skill_approval_event_for_batch(self):
        _insert_adhoc_batch_skill()
        resp = client.post("/api/skills/sk-u-batch/execute")
        assert resp.status_code == 200
        events = _collect_sse_events(resp.content)
        event_names = [e[0] for e in events]
        assert "skill_approval" in event_names, (
            f"Ad-hoc batch skill must emit a 'skill_approval' SSE event. Got: {event_names}"
        )

    def test_approval_event_contains_summary(self):
        _insert_adhoc_batch_skill()
        resp = client.post("/api/skills/sk-u-batch/execute")
        events = _collect_sse_events(resp.content)
        approval = next((data for name, data in events if name == "skill_approval"), None)
        assert approval is not None
        # Must include skill id/name and some representation of the staged items
        assert approval.get("skill_id") == "sk-u-batch"
        assert approval.get("name") == "Overdue Invoice Chase"
        # Either an item list or an item count should be present
        assert ("items" in approval) or ("item_count" in approval)


class TestExecuteAdhocSingleSkill:
    def test_single_item_skill_skips_approval(self):
        _insert_adhoc_single_skill()
        resp = client.post("/api/skills/sk-u-single/execute")
        assert resp.status_code == 200
        events = _collect_sse_events(resp.content)
        names = [e[0] for e in events]
        assert "skill_approval" not in names, (
            "Single-item ad-hoc skills must execute without an approval gate"
        )


# ---------------------------------------------------------------------------
# Workflow API is hard-cut
# ---------------------------------------------------------------------------

class TestWorkflowApiRetired:
    def test_list_workflows_returns_404(self):
        resp = client.get("/api/workflows")
        # Hard-cut — not 410 Gone, just unregistered → 404
        assert resp.status_code == 404

    def test_workflow_detail_returns_404(self):
        resp = client.get("/api/workflows/any-id")
        assert resp.status_code == 404

    def test_workflow_execute_returns_404(self):
        resp = client.post("/api/workflows/any-id/execute")
        assert resp.status_code == 404

    def test_workflow_routes_module_is_gone(self):
        """The file is deleted per spec (hard-cut)."""
        with pytest.raises(ImportError):
            __import__("backend.api.workflow_routes", fromlist=["router"])
