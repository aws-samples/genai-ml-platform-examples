"""Shared test fixtures — temp database, sample data."""

import json
import tempfile
from pathlib import Path

import pytest

from backend.config import settings
from backend.services.database import init_db, execute_db


@pytest.fixture(autouse=True)
def _tmp_database(tmp_path, monkeypatch):
    """Redirect all DB access to a temporary SQLite file and init schema."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_path", db_file)
    init_db()
    yield


# ---------------------------------------------------------------------------
# Sample data helpers
# ---------------------------------------------------------------------------

def _insert_doctors():
    doctors = [
        ("dr-chen", "Dr Sarah Chen", "General Practice", 30, '["Monday","Tuesday","Wednesday","Thursday","Friday"]', "08:00", "17:00"),
        ("dr-patel", "Dr Raj Patel", "General Practice", 30, '["Monday","Tuesday","Wednesday","Thursday"]', "09:00", "16:00"),
    ]
    for d in doctors:
        execute_db(
            "INSERT INTO doctors (id, name, specialty, consultation_duration_mins, working_days, hours_start, hours_end) VALUES (?,?,?,?,?,?,?)",
            d,
        )


def _insert_patients():
    patients = [
        ("pat-001", "Sarah", "Mitchell", "1985-03-15", "0412000001", "sarah@example.com", "sms", "", 0),
        ("pat-002", "James", "Cooper", "1990-07-22", "0412000002", "james@example.com", "email", "", 3),
        ("pat-003", "Margaret", "Park", "1948-11-02", "0412000003", "margaret@example.com", "phone", "Elderly patient, be gentle", 0),
        ("pat-004", "David", "Torres", "1978-01-30", "0412000004", "david@example.com", "sms", "", 1),
    ]
    for p in patients:
        execute_db(
            "INSERT INTO patients (id, first_name, last_name, dob, phone, email, preferred_contact, notes, no_show_count) VALUES (?,?,?,?,?,?,?,?,?)",
            p,
        )


def _insert_appointments():
    appointments = [
        ("apt-001", "pat-001", "dr-chen", "2026-03-14", "09:00", 30, "confirmed", "standard", 0),
        ("apt-002", "pat-002", "dr-chen", "2026-03-14", "14:00", 30, "confirmed", "standard", 0),
        ("apt-003", "pat-003", "dr-patel", "2026-03-14", "10:00", 30, "confirmed", "follow-up", 0),
    ]
    for a in appointments:
        execute_db(
            "INSERT INTO appointments (id, patient_id, doctor_id, date, time, duration_mins, status, type, reminder_sent) VALUES (?,?,?,?,?,?,?,?,?)",
            a,
        )


def _insert_invoices():
    invoices = [
        ("inv-001", "pat-002", "apt-002", 150.00, 0.0, "outstanding", "2026-03-01", "2026-02-15", 0, "Standard consultation"),
        ("inv-002", "pat-004", "apt-001", 200.00, 50.0, "outstanding", "2026-02-20", "2026-02-01", 2, "Follow-up consultation"),
        ("inv-003", "pat-001", None, 100.00, 100.0, "paid", "2026-02-10", "2026-01-15", 0, "Blood work"),
    ]
    for inv in invoices:
        execute_db(
            "INSERT INTO invoices (id, patient_id, appointment_id, amount, amount_paid, status, due_date, issued_date, chase_count, description) VALUES (?,?,?,?,?,?,?,?,?,?)",
            inv,
        )


@pytest.fixture()
def seed_data():
    """Insert a standard set of sample data into the temp DB."""
    _insert_doctors()
    _insert_patients()
    _insert_appointments()
    _insert_invoices()
