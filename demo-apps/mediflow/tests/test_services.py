"""Tests for service modules — calendar, patient, billing, comms, audit."""

import pytest

from backend.services import (
    calendar_service,
    patient_service,
    billing_service,
    comms_service,
    audit_service,
)
from backend.services.database import query_db


# ── Calendar ───────────────────────────────────────────────────────────────

class TestCalendarService:
    def test_check_availability_returns_slots(self, seed_data):
        # Monday 2026-03-16 — dr-chen works Mon-Fri, hours 08:00-17:00
        result = calendar_service.check_availability("dr-chen", "2026-03-16")
        assert result["doctor_id"] == "dr-chen"
        assert len(result["available_slots"]) > 0
        assert "08:00" in result["available_slots"]

    def test_check_availability_afternoon(self, seed_data):
        result = calendar_service.check_availability("dr-chen", "2026-03-16", time_range="afternoon")
        for slot in result["available_slots"]:
            assert slot >= "12:00"

    def test_check_availability_morning(self, seed_data):
        result = calendar_service.check_availability("dr-chen", "2026-03-16", time_range="morning")
        for slot in result["available_slots"]:
            assert slot < "12:00"

    def test_check_availability_non_working_day(self, seed_data):
        # Saturday — dr-chen doesn't work
        result = calendar_service.check_availability("dr-chen", "2026-03-21")
        assert result["available_slots"] == []

    def test_book_appointment(self, seed_data):
        result = calendar_service.book_appointment("pat-001", "dr-chen", "2026-03-16", "10:00")
        # Returns dict with "id" key, status = "scheduled"
        assert "id" in result
        assert result["status"] == "scheduled"
        # Verify slot now taken
        avail = calendar_service.check_availability("dr-chen", "2026-03-16")
        assert "10:00" not in avail["available_slots"]

    def test_reschedule_appointment(self, seed_data):
        result = calendar_service.reschedule_appointment("apt-001", "2026-03-17", "11:00")
        assert result["status"] == "rescheduled"
        details = calendar_service.get_appointment_details("apt-001")
        assert details["date"] == "2026-03-17"
        assert details["time"] == "11:00"

    def test_cancel_appointment(self, seed_data):
        result = calendar_service.cancel_appointment("apt-001", reason="Patient request")
        assert result["status"] == "cancelled"

    def test_cancel_appointment_no_reason(self, seed_data):
        result = calendar_service.cancel_appointment("apt-002")
        assert result["status"] == "cancelled"

    def test_list_upcoming(self, seed_data):
        upcoming = calendar_service.list_upcoming(doctor_id="dr-chen", days=30)
        assert isinstance(upcoming, list)

    def test_get_appointment_details(self, seed_data):
        details = calendar_service.get_appointment_details("apt-001")
        assert details["patient_name"] == "Sarah Mitchell"

    def test_get_appointment_details_not_found(self, seed_data):
        details = calendar_service.get_appointment_details("apt-nonexistent")
        assert "error" in details


# ── Patient ────────────────────────────────────────────────────────────────

class TestPatientService:
    def test_search_patients(self, seed_data):
        results = patient_service.search_patients("Mitchell")
        assert len(results) == 1
        assert results[0]["first_name"] == "Sarah"

    def test_search_patients_partial(self, seed_data):
        results = patient_service.search_patients("Coo")
        assert len(results) == 1
        assert results[0]["last_name"] == "Cooper"

    def test_search_patients_no_match(self, seed_data):
        results = patient_service.search_patients("Nonexistent")
        assert results == []

    def test_get_patient(self, seed_data):
        patient = patient_service.get_patient("pat-001")
        assert patient["first_name"] == "Sarah"
        assert patient["last_name"] == "Mitchell"

    def test_get_patient_not_found(self, seed_data):
        result = patient_service.get_patient("pat-999")
        assert "error" in result

    def test_get_patient_history(self, seed_data):
        history = patient_service.get_patient_history("pat-001")
        assert "appointments" in history
        assert "invoices" in history

    def test_update_patient_notes(self, seed_data):
        # Returns the updated patient dict — not {"status": "updated"}
        result = patient_service.update_patient_notes("pat-001", "Prefers morning appointments")
        assert "notes" in result
        assert "Prefers morning appointments" in result["notes"]

    def test_update_patient_notes_appends(self, seed_data):
        patient_service.update_patient_notes("pat-003", "Needs wheelchair access")
        patient = patient_service.get_patient("pat-003")
        # Should contain both the original notes and the new ones
        assert "be gentle" in patient["notes"]
        assert "Needs wheelchair access" in patient["notes"]


# ── Billing ────────────────────────────────────────────────────────────────

class TestBillingService:
    def test_get_outstanding_invoices(self, seed_data):
        invoices = billing_service.get_outstanding_invoices()
        assert len(invoices) == 2  # inv-001 and inv-002
        for inv in invoices:
            assert inv["status"] == "outstanding"

    def test_get_outstanding_invoices_filtered(self, seed_data):
        invoices = billing_service.get_outstanding_invoices(patient_id="pat-002")
        assert len(invoices) == 1
        assert invoices[0]["id"] == "inv-001"

    def test_get_invoice(self, seed_data):
        inv = billing_service.get_invoice("inv-001")
        assert inv["amount"] == 150.0
        assert inv["patient_name"] == "James Cooper"

    def test_get_invoice_not_found(self, seed_data):
        result = billing_service.get_invoice("inv-999")
        assert "error" in result

    def test_record_payment_partial(self, seed_data):
        # Returns the updated invoice dict — status stays "outstanding" for partial
        result = billing_service.record_payment("inv-001", 50.0)
        assert result["status"] == "outstanding"
        assert result["amount_paid"] == 50.0

    def test_record_payment_full_marks_paid(self, seed_data):
        result = billing_service.record_payment("inv-001", 150.0)
        assert result["status"] == "paid"
        assert result["amount_paid"] == 150.0

    def test_send_payment_chase(self, seed_data):
        # Returns {"invoice": {...}, "communication": {...}}
        result = billing_service.send_payment_chase("inv-001")
        assert "invoice" in result
        assert "communication" in result
        assert result["invoice"]["chase_count"] == 1
        # Communication record created
        comms = query_db("SELECT * FROM communications WHERE patient_id = 'pat-002' AND type = 'payment_chase'")
        assert len(comms) == 1


# ── Comms ──────────────────────────────────────────────────────────────────

class TestCommsService:
    def test_send_appointment_reminder(self, seed_data):
        # Returns the communication record dict
        result = comms_service.send_appointment_reminder("pat-001", "apt-001")
        assert result["type"] == "reminder"
        assert result["patient_id"] == "pat-001"
        # Appointment reminder_sent flag set
        rows = query_db("SELECT reminder_sent FROM appointments WHERE id = 'apt-001'")
        assert rows[0]["reminder_sent"] == 1

    def test_send_message(self, seed_data):
        result = comms_service.send_message("pat-001", "Hello from the practice!")
        assert result["type"] == "general"
        assert result["patient_id"] == "pat-001"
        # Uses patient preferred_contact when channel not given
        assert result["channel"] == "sms"  # pat-001 preferred_contact

    def test_send_message_custom_channel(self, seed_data):
        result = comms_service.send_message("pat-001", "Test", channel="email")
        assert result["channel"] == "email"

    def test_get_comms_history(self, seed_data):
        comms_service.send_message("pat-001", "Message 1")
        comms_service.send_message("pat-001", "Message 2")
        history = comms_service.get_comms_history("pat-001")
        assert len(history) == 2


# ── Audit ──────────────────────────────────────────────────────────────────

class TestAuditService:
    def test_log_tool_call(self):
        audit_service.log_tool_call("sess-001", "check_availability", {"doctor_id": "dr-chen"}, "3 slots", 120)
        calls = audit_service.get_tool_calls("sess-001")
        assert len(calls) == 1
        assert calls[0]["tool_name"] == "check_availability"

    def test_log_tool_call_sequence_numbers(self):
        audit_service.log_tool_call("sess-002", "tool_a", {}, "ok", 10)
        audit_service.log_tool_call("sess-002", "tool_b", {}, "ok", 10)
        calls = audit_service.get_tool_calls("sess-002")
        assert calls[0]["sequence_number"] < calls[1]["sequence_number"]

    def test_log_conversation_turn(self):
        audit_service.log_conversation_turn("sess-003", "user", "Hello", None)
        audit_service.log_conversation_turn("sess-003", "assistant", "Hi there!", ["tc-1"])
        turns = audit_service.get_conversation("sess-003")
        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[1]["role"] == "assistant"

    def test_get_all_sessions(self):
        # get_all_sessions queries conversation_log, not tool_call_log
        audit_service.log_conversation_turn("sess-a", "user", "Hello", None)
        audit_service.log_conversation_turn("sess-b", "user", "Hi", None)
        sessions = audit_service.get_all_sessions()
        ids = [s["session_id"] for s in sessions]
        assert "sess-a" in ids
        assert "sess-b" in ids
