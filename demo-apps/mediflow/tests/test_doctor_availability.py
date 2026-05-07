"""Tests for TASK-047 — Doctor availability construct.

These tests cover:
  - Schema (new `doctor_unavailability` table + index)
  - Service helpers on `backend.services.calendar_service`:
        mark_doctor_unavailable
        get_affected_appointments
        clear_doctor_unavailability
        check_availability (updated to honour unavailability windows)
  - HTTP routes mounted under `/api/data`:
        GET /api/data/today  (new `conflicts` array)
        POST /api/data/doctors/{id}/unavailability
        DELETE /api/data/doctors/{id}/unavailability/{uid}
        PATCH /api/data/doctors/{id}
        GET /api/data/doctors/{id}/availability
  - Agent tool wrappers in `backend.tools.calendar_tools`:
        mark_doctor_unavailable, get_doctor_conflicts,
        clear_doctor_unavailability, update_doctor_schedule
  - Registration of the four new tools in `backend.agent.agent.ALL_TOOLS`

All tests use the temp-DB fixture from conftest (`_tmp_database` autouse) and
the `seed_data` fixture where appropriate. Tests are expected to fail until
TASK-047 is implemented.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.services import calendar_service
from backend.services.database import execute_db, get_connection, query_db


TODAY = date.today()
TODAY_ISO = TODAY.isoformat()
TOMORROW_ISO = (TODAY + timedelta(days=1)).isoformat()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _insert_doctor(
    id_="dr-patel",
    name="Dr Raj Patel",
    specialty="General Practice",
    working_days='["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]',
    hours_start="09:00",
    hours_end="17:00",
    duration=30,
):
    execute_db(
        "INSERT INTO doctors (id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end) VALUES (?,?,?,?,?,?,?)",
        (id_, name, specialty, duration, working_days, hours_start, hours_end),
    )


def _insert_patient(id_, first, last):
    execute_db(
        "INSERT INTO patients (id, first_name, last_name, dob, phone, email, preferred_contact, notes, no_show_count) VALUES (?,?,?,?,?,?,?,?,?)",
        (id_, first, last, "1985-01-01", "0412000000", f"{first.lower()}@example.com", "sms", "", 0),
    )


def _insert_appt(id_, patient_id, doctor_id, date_iso, time_str, status="scheduled"):
    execute_db(
        "INSERT INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent) VALUES (?,?,?,?,?,?,?,?,?)",
        (id_, patient_id, doctor_id, date_iso, time_str, 30, status, "standard", 0),
    )


def _seed_dr_patel_with_11_today():
    """Seed Dr Patel + 11 scheduled appointments today (mirrors the demo seed)."""
    _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
    times = [
        "09:00", "09:30", "10:00", "10:30", "11:00",
        "11:30", "13:00", "13:30", "14:00", "14:30", "15:00",
    ]
    assert len(times) == 11
    for i, t in enumerate(times):
        pat_id = f"pat-{i:03d}"
        _insert_patient(pat_id, f"First{i}", f"Last{i}")
        _insert_appt(f"apt-t{i:02d}", pat_id, "dr-patel", TODAY_ISO, t, status="scheduled")


def _get_test_client():
    """Build a TestClient for the FastAPI app with data_routes mounted."""
    from fastapi import FastAPI

    from backend.api.data_routes import router as data_router

    app = FastAPI()
    app.include_router(data_router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

class TestSchema:
    def test_doctor_unavailability_table_exists(self):
        conn = get_connection()
        try:
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='doctor_unavailability'"
            ).fetchone()
            assert row is not None, "doctor_unavailability table must be created by init_db()"

            cols = {r["name"] for r in conn.execute("PRAGMA table_info(doctor_unavailability)").fetchall()}
            expected = {
                "id", "doctor_id", "start_date", "end_date",
                "start_time", "end_time", "reason", "note",
                "created_by", "created_at",
            }
            missing = expected - cols
            assert not missing, f"doctor_unavailability missing columns: {missing}"
        finally:
            conn.close()

    def test_doctor_unavailability_has_doctor_date_index(self):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name='doctor_unavailability'"
            ).fetchall()
            sql_blobs = " ".join((r["sql"] or "") for r in rows).lower()
            assert "doctor_id" in sql_blobs and "start_date" in sql_blobs, (
                "Expected an index covering (doctor_id, start_date) on doctor_unavailability"
            )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Service — mark_doctor_unavailable / get_affected_appointments
# ---------------------------------------------------------------------------

class TestMarkDoctorUnavailable:
    def test_full_day_returns_all_affected(self):
        _seed_dr_patel_with_11_today()

        result = calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )
        assert "unavailability_id" in result
        assert "affected_appointments" in result
        assert len(result["affected_appointments"]) == 11

        # Row persisted
        rows = query_db(
            "SELECT * FROM doctor_unavailability WHERE id = ?",
            (result["unavailability_id"],),
        )
        assert len(rows) == 1
        row = rows[0]
        assert row["doctor_id"] == "dr-patel"
        assert row["start_date"] == TODAY_ISO
        assert row["end_date"] == TODAY_ISO
        assert row["reason"] == "sick"
        assert row["created_by"] == "agent"

    def test_partial_window_filters_affected(self):
        _seed_dr_patel_with_11_today()

        # Block 13:00–14:00 inclusive start, exclusive end.
        # Appointments at 13:00 and 13:30 are affected; 14:00 is NOT.
        result = calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time="13:00",
            end_time="14:00",
            reason="other",
            note="Conference",
            created_by="user",
        )
        affected_times = sorted(a["time"] for a in result["affected_appointments"])
        assert affected_times == ["13:00", "13:30"]

    def test_multi_day_returns_entire_range(self):
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        _insert_patient("pat-m1", "Alice", "One")
        _insert_patient("pat-m2", "Bob", "Two")
        d1 = TODAY_ISO
        d2 = (TODAY + timedelta(days=1)).isoformat()
        d3 = (TODAY + timedelta(days=2)).isoformat()
        _insert_appt("apt-m1", "pat-m1", "dr-patel", d1, "10:00")
        _insert_appt("apt-m2", "pat-m2", "dr-patel", d3, "11:00")

        result = calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=d1,
            end_date=d3,
            start_time=None,
            end_time=None,
            reason="leave",
            note=None,
            created_by="user",
        )
        assert len(result["affected_appointments"]) == 2

    def test_invalid_reason_rejected(self):
        _insert_doctor()
        try:
            result = calendar_service.mark_doctor_unavailable(
                doctor_id="dr-patel",
                start_date=TODAY_ISO,
                end_date=TODAY_ISO,
                start_time=None,
                end_time=None,
                reason="vacation",  # not in {sick, leave, other}
                note=None,
                created_by="agent",
            )
            # Either raise, or return an error sentinel — no row should be inserted.
            assert isinstance(result, dict) and "error" in result
        except (ValueError, AssertionError):
            pass

        rows = query_db("SELECT * FROM doctor_unavailability")
        assert rows == []


class TestGetAffectedAppointments:
    def test_full_day(self):
        _seed_dr_patel_with_11_today()
        affected = calendar_service.get_affected_appointments(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
        )
        assert len(affected) == 11

    def test_excludes_cancelled(self):
        _seed_dr_patel_with_11_today()
        # Cancel one of the 11
        execute_db(
            "UPDATE appointments SET status = 'cancelled' WHERE id = ?",
            ("apt-t00",),
        )
        affected = calendar_service.get_affected_appointments(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
        )
        assert len(affected) == 10

    def test_partial_window(self):
        _seed_dr_patel_with_11_today()
        affected = calendar_service.get_affected_appointments(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time="13:00",
            end_time="14:00",
        )
        times = sorted(a["time"] for a in affected)
        assert times == ["13:00", "13:30"]

    def test_other_doctor_untouched(self):
        _seed_dr_patel_with_11_today()
        _insert_doctor(id_="dr-chen", name="Dr Sarah Chen")
        _insert_patient("pat-ch", "Chen", "Patient")
        _insert_appt("apt-ch1", "pat-ch", "dr-chen", TODAY_ISO, "09:00")

        affected = calendar_service.get_affected_appointments(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
        )
        for a in affected:
            assert a["doctor_id"] == "dr-patel"


# ---------------------------------------------------------------------------
# Service — check_availability honours unavailability
# ---------------------------------------------------------------------------

class TestCheckAvailabilityUnavailability:
    def test_full_day_unavailability_removes_all_slots(self):
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        # First sanity-check slots exist for today
        before = calendar_service.check_availability("dr-patel", TODAY_ISO)
        assert len(before["available_slots"]) > 0

        calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )
        after = calendar_service.check_availability("dr-patel", TODAY_ISO)
        assert after["available_slots"] == []

    def test_partial_window_removes_only_inside(self):
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time="12:00",
            end_time="14:00",
            reason="other",
            note=None,
            created_by="user",
        )
        result = calendar_service.check_availability("dr-patel", TODAY_ISO)
        slots = result["available_slots"]
        # Inside window — removed
        for blocked in ("12:00", "12:30", "13:00", "13:30"):
            assert blocked not in slots, f"{blocked} should be blocked by unavailability"
        # Just outside — still offered (pending other bookings)
        assert "11:30" in slots
        assert "14:00" in slots

    def test_other_dates_unaffected(self):
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )
        result = calendar_service.check_availability("dr-patel", TOMORROW_ISO)
        # Tomorrow — doctor still works assuming tomorrow is a working day.
        # We use a fully-open working_days list, so slots should exist.
        assert len(result["available_slots"]) > 0


# ---------------------------------------------------------------------------
# Service — clear_doctor_unavailability
# ---------------------------------------------------------------------------

class TestClearDoctorUnavailability:
    def test_delete_row(self):
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        marked = calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )
        uid = marked["unavailability_id"]

        result = calendar_service.clear_doctor_unavailability(uid)
        # Either returns {deleted: 1} or the cleared row; just confirm no error.
        assert not (isinstance(result, dict) and result.get("error"))

        rows = query_db("SELECT * FROM doctor_unavailability WHERE id = ?", (uid,))
        assert rows == []

        # Slots return
        avail = calendar_service.check_availability("dr-patel", TODAY_ISO)
        assert len(avail["available_slots"]) > 0

    def test_unknown_id_noop(self):
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        # Should not raise.
        result = calendar_service.clear_doctor_unavailability(99999)
        # Fine for either {deleted: 0} or {error}; just no exception.
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# Routes — bundled /today conflicts + CRUD endpoints
# ---------------------------------------------------------------------------

class TestTodayConflicts:
    def test_today_includes_conflicts_when_seeded(self):
        _seed_dr_patel_with_11_today()
        calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )

        client = _get_test_client()
        r = client.get("/api/data/today")
        assert r.status_code == 200
        body = r.json()
        assert "conflicts" in body, "/api/data/today must include a `conflicts` array"
        assert isinstance(body["conflicts"], list)
        assert len(body["conflicts"]) == 1
        c = body["conflicts"][0]
        assert c["doctor_id"] == "dr-patel"
        assert c["reason"] == "sick"
        assert c.get("doctor_name") == "Dr Raj Patel"
        assert len(c["affected_appointments"]) == 11

    def test_today_conflicts_empty_when_no_unavailability(self):
        _insert_doctor()
        client = _get_test_client()
        r = client.get("/api/data/today")
        assert r.status_code == 200
        body = r.json()
        assert body.get("conflicts", []) == []


class TestUnavailabilityRoutes:
    def test_post_unavailability_returns_affected(self):
        _seed_dr_patel_with_11_today()
        client = _get_test_client()

        r = client.post(
            "/api/data/doctors/dr-patel/unavailability",
            json={
                "start_date": TODAY_ISO,
                "end_date": TODAY_ISO,
                "reason": "sick",
                "created_by": "agent",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "unavailability_id" in body
        assert len(body["affected_appointments"]) == 11

        rows = query_db("SELECT * FROM doctor_unavailability")
        assert len(rows) == 1

    def test_post_unavailability_rejects_bad_reason(self):
        _insert_doctor()
        client = _get_test_client()
        r = client.post(
            "/api/data/doctors/dr-patel/unavailability",
            json={
                "start_date": TODAY_ISO,
                "end_date": TODAY_ISO,
                "reason": "vacation",
                "created_by": "agent",
            },
        )
        # 400/422 or body with `error` key. No DB row either way.
        assert r.status_code >= 400 or "error" in r.json()
        rows = query_db("SELECT * FROM doctor_unavailability")
        assert rows == []

    def test_delete_unavailability_removes_row(self):
        _insert_doctor()
        marked = calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )
        uid = marked["unavailability_id"]

        client = _get_test_client()
        r = client.delete(f"/api/data/doctors/dr-patel/unavailability/{uid}")
        assert r.status_code == 200, r.text

        rows = query_db("SELECT * FROM doctor_unavailability WHERE id = ?", (uid,))
        assert rows == []


class TestPatchDoctorSchedule:
    def test_full_update(self):
        _insert_doctor(id_="dr-chen", name="Dr Sarah Chen")
        client = _get_test_client()
        r = client.patch(
            "/api/data/doctors/dr-chen",
            json={
                "working_days": ["Monday", "Tuesday"],
                "hours_start": "10:00",
                "hours_end": "15:00",
                "consultation_duration_mins": 45,
            },
        )
        assert r.status_code == 200, r.text

        g = client.get("/api/data/doctors/dr-chen")
        body = g.json()
        assert body["working_days"] == ["Monday", "Tuesday"]
        assert body["hours_start"] == "10:00"
        assert body["hours_end"] == "15:00"
        assert body["consultation_duration_mins"] == 45

    def test_partial_update(self):
        _insert_doctor(id_="dr-chen", name="Dr Sarah Chen", hours_start="09:00", hours_end="17:00")
        client = _get_test_client()
        r = client.patch("/api/data/doctors/dr-chen", json={"hours_end": "14:00"})
        assert r.status_code == 200, r.text

        g = client.get("/api/data/doctors/dr-chen")
        body = g.json()
        assert body["hours_start"] == "09:00", "hours_start must not be clobbered by partial PATCH"
        assert body["hours_end"] == "14:00"


class TestGetDoctorAvailabilityWindow:
    def test_returns_recurring_and_exceptions(self):
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note="Called in",
            created_by="agent",
        )
        client = _get_test_client()
        end = (TODAY + timedelta(days=7)).isoformat()
        r = client.get(f"/api/data/doctors/dr-patel/availability?start={TODAY_ISO}&end={end}")
        assert r.status_code == 200, r.text
        body = r.json()
        assert "recurring" in body
        assert "unavailability" in body
        assert len(body["unavailability"]) == 1
        assert body["unavailability"][0]["reason"] == "sick"


# ---------------------------------------------------------------------------
# Agent tools — wrappers + registration
# ---------------------------------------------------------------------------

class TestAgentTools:
    def test_mark_doctor_unavailable_tool_callable(self):
        from backend.tools import calendar_tools as ct

        assert hasattr(ct, "mark_doctor_unavailable"), (
            "calendar_tools.mark_doctor_unavailable tool must exist"
        )
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        result = ct.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time="",
            end_time="",
            reason="sick",
            note="",
        )
        assert "unavailability_id" in result
        assert "affected_appointments" in result

    def test_get_doctor_conflicts_tool_defaults_to_today(self):
        from backend.tools import calendar_tools as ct

        assert hasattr(ct, "get_doctor_conflicts"), (
            "calendar_tools.get_doctor_conflicts tool must exist"
        )
        _seed_dr_patel_with_11_today()
        calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )
        result = ct.get_doctor_conflicts(date="")
        # Expect an aggregated structure — list of conflicts or dict with list
        if isinstance(result, dict):
            conflicts = result.get("conflicts", result.get("items", []))
        else:
            conflicts = result
        assert len(conflicts) == 1
        # Either 11 affected appointments, or a summary count of 11
        c = conflicts[0]
        if "affected_appointments" in c:
            assert len(c["affected_appointments"]) == 11
        else:
            assert c.get("affected_count") == 11

    def test_clear_doctor_unavailability_tool(self):
        from backend.tools import calendar_tools as ct

        assert hasattr(ct, "clear_doctor_unavailability")
        _insert_doctor(id_="dr-patel", name="Dr Raj Patel")
        marked = calendar_service.mark_doctor_unavailable(
            doctor_id="dr-patel",
            start_date=TODAY_ISO,
            end_date=TODAY_ISO,
            start_time=None,
            end_time=None,
            reason="sick",
            note=None,
            created_by="agent",
        )
        uid = marked["unavailability_id"]
        ct.clear_doctor_unavailability(unavailability_id=uid)
        rows = query_db("SELECT * FROM doctor_unavailability WHERE id = ?", (uid,))
        assert rows == []

    def test_update_doctor_schedule_tool(self):
        from backend.tools import calendar_tools as ct

        assert hasattr(ct, "update_doctor_schedule")
        _insert_doctor(id_="dr-chen", name="Dr Sarah Chen", hours_start="09:00", hours_end="17:00")
        ct.update_doctor_schedule(
            doctor_id="dr-chen",
            working_days=["Monday", "Tuesday"],
            hours_start="10:00",
            hours_end="15:00",
        )
        rows = query_db("SELECT * FROM doctors WHERE id = ?", ("dr-chen",))
        assert rows[0]["hours_start"] == "10:00"
        assert rows[0]["hours_end"] == "15:00"

    def test_new_tools_registered_in_agent(self):
        from backend.agent.agent import ALL_TOOLS

        # Tools are @tool-decorated objects; inspect by the underlying function name
        # via the Strands AgentTool spec. We check by string representation / __name__.
        names = set()
        for t in ALL_TOOLS:
            for attr in ("tool_name", "name", "__name__"):
                v = getattr(t, attr, None)
                if v:
                    names.add(v)
                    break
            else:
                # Last resort — fall back to string repr
                names.add(str(t))

        expected = {
            "mark_doctor_unavailable",
            "get_doctor_conflicts",
            "clear_doctor_unavailability",
            "update_doctor_schedule",
        }
        missing = expected - names
        assert not missing, f"ALL_TOOLS missing new tools: {missing}. Registered: {sorted(names)}"
