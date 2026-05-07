"""Tests for @tool-decorated functions — verifying wrappers and argument handling."""

import pytest

from backend.tools.calendar_tools import (
    check_availability,
    book_appointment,
    cancel_appointment,
    list_upcoming_appointments,
    get_appointment_details,
    reschedule_appointment,
)
from backend.tools.patient_tools import (
    search_patients,
    get_patient,
    get_patient_history,
    update_patient_notes,
)
from backend.tools.billing_tools import (
    get_outstanding_invoices,
    get_invoice,
    record_payment,
    send_payment_reminder,
)
from backend.tools.comms_tools import (
    send_appointment_reminder,
    send_message,
    get_comms_history,
)


class TestCalendarTools:
    """Verify that tool wrappers correctly delegate and handle empty strings."""

    def test_check_availability_calls_service(self, seed_data):
        result = check_availability(doctor_id="dr-chen", date="2026-03-16", time_range="")
        assert "available_slots" in result

    def test_check_availability_with_time_range(self, seed_data):
        result = check_availability(doctor_id="dr-chen", date="2026-03-16", time_range="afternoon")
        for slot in result["available_slots"]:
            assert slot >= "12:00"

    def test_book_appointment_via_tool(self, seed_data):
        result = book_appointment(patient_id="pat-001", doctor_id="dr-chen", date="2026-03-16", time="09:00")
        assert "id" in result
        assert result["status"] == "scheduled"

    def test_cancel_appointment_empty_reason_becomes_none(self, seed_data):
        result = cancel_appointment(appointment_id="apt-001", reason="")
        assert result["status"] == "cancelled"

    def test_list_upcoming_empty_strings(self, seed_data):
        result = list_upcoming_appointments(doctor_id="", patient_id="", days=30)
        assert isinstance(result, list)

    def test_reschedule_via_tool(self, seed_data):
        result = reschedule_appointment(appointment_id="apt-001", new_date="2026-03-17", new_time="10:00")
        assert result["status"] == "rescheduled"

    def test_get_details_via_tool(self, seed_data):
        result = get_appointment_details(appointment_id="apt-001")
        assert "patient_name" in result


class TestPatientTools:
    def test_search(self, seed_data):
        result = search_patients(query="Sarah")
        assert len(result) >= 1

    def test_get(self, seed_data):
        result = get_patient(patient_id="pat-001")
        assert result["first_name"] == "Sarah"

    def test_history(self, seed_data):
        result = get_patient_history(patient_id="pat-001")
        assert "appointments" in result

    def test_update_notes(self, seed_data):
        # Returns the updated patient dict
        result = update_patient_notes(patient_id="pat-001", notes="Allergic to penicillin")
        assert "notes" in result
        assert "Allergic to penicillin" in result["notes"]


class TestBillingTools:
    def test_outstanding(self, seed_data):
        result = get_outstanding_invoices(patient_id="")
        assert isinstance(result, list)

    def test_invoice_details(self, seed_data):
        result = get_invoice(invoice_id="inv-001")
        assert result["amount"] == 150.0

    def test_record_payment_via_tool(self, seed_data):
        # Returns updated invoice; full payment → status = "paid"
        result = record_payment(invoice_id="inv-001", amount=150.0)
        assert result["status"] == "paid"

    def test_send_chase_via_tool(self, seed_data):
        # Returns {"invoice": {...}, "communication": {...}}
        result = send_payment_reminder(invoice_id="inv-001")
        assert "invoice" in result
        assert "communication" in result


class TestCommsTools:
    def test_send_reminder_via_tool(self, seed_data):
        result = send_appointment_reminder(patient_id="pat-001", appointment_id="apt-001")
        assert result["type"] == "reminder"

    def test_send_message_via_tool(self, seed_data):
        result = send_message(patient_id="pat-001", message="Test", channel="")
        assert result["type"] == "general"

    def test_get_history_via_tool(self, seed_data):
        result = get_comms_history(patient_id="pat-001")
        assert isinstance(result, list)
