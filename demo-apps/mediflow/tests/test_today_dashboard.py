"""Tests for TASK-043 — /api/data/today dashboard extensions.

These tests exercise `backend.api.data_routes.get_today()` directly against
the temp DB provided by `conftest._tmp_database`. They assume the following
new response fields will be added by the builder:

    appointment_status_counts: dict[str, int]
    invoices_outstanding: list[dict]  # top 5, sorted days_overdue DESC
    invoices_total_outstanding: int
    revenue_this_week: {paid, outstanding, overdue, total}  # global snapshot
    weekly_trend: {this_week: [5 ints], last_week: [5 ints], delta: int}
    suggestions: list[{label, action}]  # <=3 items, action.type in {route, prompt}

Existing fields (`appointments`, `tasks`, `stats`) must remain unchanged in
shape for back-compat.
"""

from datetime import date, timedelta

import pytest

from backend.api.data_routes import get_today
from backend.services.database import execute_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date.today()
TODAY_ISO = TODAY.isoformat()


def _insert_doctor(id_="dr-chen", name="Dr Sarah Chen"):
    execute_db(
        "INSERT INTO doctors (id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end) VALUES (?,?,?,?,?,?,?)",
        (id_, name, "General Practice", 30, '["Monday","Tuesday","Wednesday","Thursday","Friday"]', "08:00", "17:00"),
    )


def _insert_patient(id_, first, last):
    execute_db(
        "INSERT INTO patients (id, first_name, last_name, dob, phone, email, preferred_contact, notes, no_show_count) VALUES (?,?,?,?,?,?,?,?,?)",
        (id_, first, last, "1985-01-01", "0412000000", f"{first.lower()}@example.com", "sms", "", 0),
    )


def _insert_appt(id_, patient_id, doctor_id, date_iso, time_str, status, appt_type="standard"):
    execute_db(
        "INSERT INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent) VALUES (?,?,?,?,?,?,?,?,?)",
        (id_, patient_id, doctor_id, date_iso, time_str, 30, status, appt_type, 0),
    )


def _insert_invoice(id_, patient_id, amount, amount_paid, status, due_date, issued_date=None, appointment_id=None):
    execute_db(
        "INSERT INTO invoices (id, patient_id, appointment_id, amount, amount_paid, status, due_date, issued_date, chase_count, description) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (id_, patient_id, appointment_id, amount, amount_paid, status, due_date, issued_date or "2026-01-01", 0, "Test invoice"),
    )


# ---------------------------------------------------------------------------
# Empty DB — shape and defaults
# ---------------------------------------------------------------------------

class TestEmptyDB:
    def test_response_shape_empty(self):
        """All new keys present with safe zero/empty defaults."""
        r = get_today()

        # New fields
        assert "appointment_status_counts" in r
        assert "invoices_outstanding" in r
        assert "invoices_total_outstanding" in r
        assert "revenue_this_week" in r
        assert "weekly_trend" in r
        assert "suggestions" in r

        # Defaults
        assert isinstance(r["appointment_status_counts"], dict)
        assert r["invoices_outstanding"] == []
        assert r["invoices_total_outstanding"] == 0
        assert isinstance(r["revenue_this_week"], dict)
        for k in ("paid", "outstanding", "overdue", "total"):
            assert k in r["revenue_this_week"]
            assert r["revenue_this_week"][k] == 0
        assert r["weekly_trend"]["this_week"] == [0, 0, 0, 0, 0]
        assert r["weekly_trend"]["last_week"] == [0, 0, 0, 0, 0]
        assert r["weekly_trend"]["delta"] == 0
        assert isinstance(r["suggestions"], list)
        assert len(r["suggestions"]) <= 3

    def test_backcompat_existing_keys(self):
        """Existing fields still present with same shapes."""
        r = get_today()
        assert "appointments" in r and isinstance(r["appointments"], list)
        assert "tasks" in r and isinstance(r["tasks"], list)
        assert "stats" in r and isinstance(r["stats"], dict)
        for k in ("patients_today", "revenue_today", "no_shows", "outstanding"):
            assert k in r["stats"]


# ---------------------------------------------------------------------------
# Appointment status counts
# ---------------------------------------------------------------------------

class TestAppointmentStatusCounts:
    def test_status_bucket_mapping(self):
        _insert_doctor()
        for i, name in enumerate([
            ("p1", "A", "One"), ("p2", "B", "Two"), ("p3", "C", "Three"),
            ("p4", "D", "Four"), ("p5", "E", "Five"), ("p6", "F", "Six"),
            ("p7", "G", "Seven"), ("p8", "H", "Eight"), ("p9", "I", "Nine"),
        ]):
            _insert_patient(*name)

        # 2 confirmed (scheduled + confirmed raw)
        _insert_appt("a1", "p1", "dr-chen", TODAY_ISO, "09:00", "scheduled")
        _insert_appt("a2", "p2", "dr-chen", TODAY_ISO, "09:30", "confirmed")
        # 2 pending (pending + pending_reply)
        _insert_appt("a3", "p3", "dr-chen", TODAY_ISO, "10:00", "pending")
        _insert_appt("a4", "p4", "dr-chen", TODAY_ISO, "10:30", "pending_reply")
        # 1 needs_reschedule
        _insert_appt("a5", "p5", "dr-chen", TODAY_ISO, "11:00", "needs_reschedule")
        # 2 cancelled (cancelled + no_show)
        _insert_appt("a6", "p6", "dr-chen", TODAY_ISO, "11:30", "cancelled")
        _insert_appt("a7", "p7", "dr-chen", TODAY_ISO, "12:00", "no_show")
        # 1 completed
        _insert_appt("a8", "p8", "dr-chen", TODAY_ISO, "12:30", "completed")
        # 1 unknown status -> pending fallback
        _insert_appt("a9", "p9", "dr-chen", TODAY_ISO, "13:00", "weird_status")

        counts = get_today()["appointment_status_counts"]
        assert counts.get("confirmed", 0) == 2
        assert counts.get("pending", 0) == 3  # 2 pending + 1 unknown fallback
        assert counts.get("needs_reschedule", 0) == 1
        assert counts.get("cancelled", 0) == 2
        assert counts.get("completed", 0) == 1

    def test_only_today_counted(self):
        _insert_doctor()
        _insert_patient("p1", "Only", "Today")
        _insert_patient("p2", "Not", "Today")
        yesterday = (TODAY - timedelta(days=1)).isoformat()
        _insert_appt("a1", "p1", "dr-chen", TODAY_ISO, "09:00", "confirmed")
        _insert_appt("a2", "p2", "dr-chen", yesterday, "09:00", "confirmed")

        counts = get_today()["appointment_status_counts"]
        assert counts.get("confirmed", 0) == 1


# ---------------------------------------------------------------------------
# Invoices outstanding
# ---------------------------------------------------------------------------

class TestInvoicesOutstanding:
    def test_top_5_sorted_by_days_overdue_desc(self):
        _insert_doctor()
        for pid, first, last in [
            ("p1", "One", "Oldest"), ("p2", "Two", "Old"), ("p3", "Three", "Mid"),
            ("p4", "Four", "Recent"), ("p5", "Five", "Newest"), ("p6", "Six", "NotOverdue"),
            ("p7", "Seven", "Paid"),
        ]:
            _insert_patient(pid, first, last)

        # Vary due_date: oldest overdue first
        due_oldest = (TODAY - timedelta(days=60)).isoformat()
        due_old = (TODAY - timedelta(days=40)).isoformat()
        due_mid = (TODAY - timedelta(days=20)).isoformat()
        due_recent = (TODAY - timedelta(days=10)).isoformat()
        due_newest = (TODAY - timedelta(days=3)).isoformat()
        due_future = (TODAY + timedelta(days=7)).isoformat()

        _insert_invoice("i1", "p1", 100, 0, "overdue", due_oldest)
        _insert_invoice("i2", "p2", 200, 0, "overdue", due_old)
        _insert_invoice("i3", "p3", 50, 0, "outstanding", due_mid)
        _insert_invoice("i4", "p4", 75, 0, "outstanding", due_recent)
        _insert_invoice("i5", "p5", 120, 0, "outstanding", due_newest)
        _insert_invoice("i6", "p6", 300, 0, "outstanding", due_future)  # not yet overdue
        _insert_invoice("i7", "p7", 999, 999, "paid", due_oldest)  # excluded

        r = get_today()
        rows = r["invoices_outstanding"]
        assert len(rows) <= 5
        # Should return 5 (not paid, not future-only excluded — future is still outstanding)
        assert len(rows) == 5
        # Oldest first (largest days_overdue)
        assert rows[0]["patient_name"] == "One Oldest"
        assert rows[0]["days_overdue"] == 60
        assert rows[1]["days_overdue"] == 40
        assert rows[2]["days_overdue"] == 20
        assert rows[3]["days_overdue"] == 10
        assert rows[4]["days_overdue"] == 3
        # days_overdue monotonically decreasing
        ods = [row["days_overdue"] for row in rows]
        assert ods == sorted(ods, reverse=True)

    def test_row_shape(self):
        _insert_doctor()
        _insert_patient("p1", "Robert", "MacLeod")
        due = (TODAY - timedelta(days=42)).isoformat()
        _insert_invoice("inv-1847", "p1", 175, 0, "overdue", due)

        rows = get_today()["invoices_outstanding"]
        assert len(rows) == 1
        row = rows[0]
        assert row["id"] == "inv-1847"
        assert row["patient_name"] == "Robert MacLeod"
        assert row["amount"] == 175.0
        assert row["due_date"] == due
        assert row["days_overdue"] == 42
        assert row["status"] == "overdue"

    def test_excludes_paid(self):
        _insert_doctor()
        _insert_patient("p1", "Paid", "Patient")
        _insert_invoice("i1", "p1", 100, 100, "paid", (TODAY - timedelta(days=100)).isoformat())
        assert get_today()["invoices_outstanding"] == []

    def test_empty_returns_empty_list(self):
        assert get_today()["invoices_outstanding"] == []


# ---------------------------------------------------------------------------
# Invoices total outstanding
# ---------------------------------------------------------------------------

class TestInvoicesTotalOutstanding:
    def test_sum_of_remaining_on_outstanding_and_overdue(self):
        _insert_doctor()
        _insert_patient("p1", "A", "One")
        _insert_patient("p2", "B", "Two")
        _insert_patient("p3", "C", "Three")
        # outstanding: 200 - 50 = 150
        _insert_invoice("i1", "p1", 200, 50, "outstanding", "2026-03-01")
        # overdue: 175 - 0 = 175
        _insert_invoice("i2", "p2", 175, 0, "overdue", "2026-02-01")
        # paid: excluded
        _insert_invoice("i3", "p3", 999, 999, "paid", "2026-02-01")

        total = get_today()["invoices_total_outstanding"]
        # Allow int or float equality at the numeric value
        assert total == 325 or total == 325.0


# ---------------------------------------------------------------------------
# Revenue snapshot (key stays revenue_this_week)
# ---------------------------------------------------------------------------

class TestRevenueSnapshot:
    def test_paid_outstanding_overdue_total(self):
        _insert_doctor()
        for pid in ("p1", "p2", "p3", "p4"):
            _insert_patient(pid, pid.upper(), "Patient")

        # Paid: SUM(amount_paid) across all invoices = 100 + 50 + 999 = 1149
        # Outstanding: SUM(amount - amount_paid) WHERE status='outstanding' = (200-50) = 150
        # Overdue: SUM(amount - amount_paid) WHERE status='overdue' = (175-0) = 175
        # Total = 1149 + 150 + 175 = 1474
        _insert_invoice("i1", "p1", 100, 100, "paid", "2026-02-01")
        _insert_invoice("i2", "p2", 200, 50, "outstanding", "2026-03-01")
        _insert_invoice("i3", "p3", 175, 0, "overdue", "2026-02-01")
        _insert_invoice("i4", "p4", 999, 999, "paid", "2026-01-01")

        rev = get_today()["revenue_this_week"]
        assert rev["paid"] == 1149 or rev["paid"] == 1149.0
        assert rev["outstanding"] == 150 or rev["outstanding"] == 150.0
        assert rev["overdue"] == 175 or rev["overdue"] == 175.0
        assert rev["total"] == rev["paid"] + rev["outstanding"] + rev["overdue"]

    def test_values_non_negative(self):
        rev = get_today()["revenue_this_week"]
        for k in ("paid", "outstanding", "overdue", "total"):
            assert rev[k] >= 0


# ---------------------------------------------------------------------------
# Weekly trend
# ---------------------------------------------------------------------------

class TestWeeklyTrend:
    def test_shape(self):
        wt = get_today()["weekly_trend"]
        assert isinstance(wt["this_week"], list) and len(wt["this_week"]) == 5
        assert isinstance(wt["last_week"], list) and len(wt["last_week"]) == 5
        assert wt["delta"] == 0

    def test_counts_by_dow_and_delta(self):
        _insert_doctor()
        _insert_patient("p1", "A", "One")

        monday_this = TODAY - timedelta(days=TODAY.weekday())
        monday_last = monday_this - timedelta(days=7)

        # This week: 3 on Mon, 1 on Wed (non-cancelled)
        _insert_appt("t1", "p1", "dr-chen", monday_this.isoformat(), "09:00", "confirmed")
        _insert_appt("t2", "p1", "dr-chen", monday_this.isoformat(), "09:30", "scheduled")
        _insert_appt("t3", "p1", "dr-chen", monday_this.isoformat(), "10:00", "completed")
        _insert_appt("t4", "p1", "dr-chen", (monday_this + timedelta(days=2)).isoformat(), "09:00", "confirmed")
        # Cancelled on Tue — excluded
        _insert_appt("t5", "p1", "dr-chen", (monday_this + timedelta(days=1)).isoformat(), "09:00", "cancelled")

        # Last week: 2 on Tue
        _insert_appt("l1", "p1", "dr-chen", (monday_last + timedelta(days=1)).isoformat(), "09:00", "confirmed")
        _insert_appt("l2", "p1", "dr-chen", (monday_last + timedelta(days=1)).isoformat(), "09:30", "completed")

        wt = get_today()["weekly_trend"]
        # this_week: [Mon=3, Tue=0 (cancelled excluded), Wed=1, Thu=0, Fri=0]
        assert wt["this_week"][0] == 3
        assert wt["this_week"][1] == 0
        assert wt["this_week"][2] == 1
        assert wt["this_week"][3] == 0
        assert wt["this_week"][4] == 0
        # last_week: [0, 2, 0, 0, 0]
        assert wt["last_week"][1] == 2
        # delta = 4 - 2 = 2
        assert wt["delta"] == sum(wt["this_week"]) - sum(wt["last_week"])
        assert wt["delta"] == 2


# ---------------------------------------------------------------------------
# Suggestions
# ---------------------------------------------------------------------------

class TestSuggestions:
    def test_shape_and_max_three(self):
        s = get_today()["suggestions"]
        assert isinstance(s, list)
        assert len(s) <= 3
        for item in s:
            assert "label" in item and isinstance(item["label"], str)
            assert "action" in item and isinstance(item["action"], dict)
            assert item["action"].get("type") in ("route", "prompt")

    def test_route_actions_carry_view(self):
        s = get_today()["suggestions"]
        for item in s:
            if item["action"]["type"] == "route":
                assert "view" in item["action"]

    def test_prompt_actions_carry_text(self):
        s = get_today()["suggestions"]
        for item in s:
            if item["action"]["type"] == "prompt":
                assert "text" in item["action"]
                assert isinstance(item["action"]["text"], str)
                assert len(item["action"]["text"]) > 0

    def test_outstanding_invoices_produces_route_suggestion(self):
        """When outstanding invoices exist, the list should contain at least one
        route suggestion pointing to patients with filter=outstanding."""
        _insert_doctor()
        _insert_patient("p1", "Debt", "Owed")
        _insert_invoice("i1", "p1", 200, 0, "overdue", (TODAY - timedelta(days=30)).isoformat())

        s = get_today()["suggestions"]
        matching = [
            item for item in s
            if item["action"]["type"] == "route"
            and item["action"].get("view") == "patients"
            and (item["action"].get("params") or {}).get("filter") == "outstanding"
        ]
        assert len(matching) >= 1, f"Expected a route→patients filter=outstanding suggestion, got: {s}"
