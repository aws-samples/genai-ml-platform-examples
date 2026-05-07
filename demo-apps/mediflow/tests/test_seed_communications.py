"""TASK-054 — hand-seeded communications fixture + API direction inference.

These tests exercise the real fixture file + loader + API route, so they
protect:
  1. The loader actually inserts the hand-seeded rows into the DB.
  2. /api/data/comms enriches every row with a `direction` field.
  3. The top-sorted threads are the hand-seeded ones (so the Comms view
     opens to a varied conversation mix, not duplicate reminders).
"""

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.seed.seed_data import load_communications_fixtures
from backend.services.database import execute_db, query_db


client = TestClient(app)


FIXTURE_PATH = (
    Path(__file__).parent.parent
    / "backend"
    / "seed"
    / "fixtures"
    / "communications.json"
)


@pytest.fixture(autouse=True)
def _seed_fixture_patients():
    """The comms fixture references patient IDs via FK; seed stub patients
    for every patient_id the fixture uses so INSERTs don't fail on FK."""
    entries = json.load(open(FIXTURE_PATH))
    pids = sorted({c["patient_id"] for c in entries})
    for pid in pids:
        execute_db(
            "INSERT INTO patients (id, first_name, last_name, dob, phone, email, preferred_contact, notes, no_show_count) VALUES (?,?,?,?,?,?,?,?,?)",
            (pid, "Test", pid, "1990-01-01", "0400000000", f"{pid}@example.com", "sms", "", 0),
        )


def test_communications_fixture_loaded():
    """Loader inserts >= 8 hand-seeded rows distinguishable from comms_service output."""
    load_communications_fixtures()

    rows = query_db(
        "SELECT * FROM communications WHERE triggered_by != 'comms_service'"
    )

    # At least 8 hand-seeded rows (actually 22 in fixture, spanning 8 patients)
    assert len(rows) >= 8, (
        f"Expected >= 8 hand-seeded rows (triggered_by != 'comms_service'), got {len(rows)}"
    )

    distinct_patients = {r["patient_id"] for r in rows}
    assert len(distinct_patients) >= 8, (
        f"Expected hand-seeded rows across >= 8 patients, got {len(distinct_patients)}: {distinct_patients}"
    )


def test_comms_api_returns_direction():
    """/api/data/comms enriches every row with direction ∈ {outbound, inbound}."""
    load_communications_fixtures()

    resp = client.get("/api/data/comms")
    assert resp.status_code == 200

    comms = resp.json()["communications"]
    assert len(comms) > 0, "No comms returned — fixture didn't load"

    for c in comms:
        assert "direction" in c, f"Row missing direction field: {c}"
        assert c["direction"] in ("outbound", "inbound"), (
            f"Invalid direction {c['direction']!r} on row {c['id']}"
        )

    # Sanity: inbound inference requires triggered_by == 'patient'
    for c in comms:
        if c.get("triggered_by") == "patient":
            assert c["direction"] == "inbound", (
                f"patient-triggered row {c['id']} should be inbound, got {c['direction']}"
            )
        else:
            assert c["direction"] == "outbound", (
                f"non-patient row {c['id']} should be outbound, got {c['direction']}"
            )


def test_top_threads_are_varied():
    """The first 8 distinct patient_ids (by sent_at DESC) are the hand-seeded ones,
    and the top 5 last-messages are not all the same reminder template."""
    load_communications_fixtures()

    resp = client.get("/api/data/comms")
    assert resp.status_code == 200

    comms = resp.json()["communications"]

    # Walk the DESC-sorted list collecting unique patients in order
    seen = []
    for c in comms:
        pid = c["patient_id"]
        if pid not in seen:
            seen.append(pid)
        if len(seen) == 8:
            break

    assert len(seen) == 8, (
        f"Expected >= 8 distinct patient threads in /api/data/comms response, got {len(seen)}"
    )

    # All top-8 patients should come from hand-seeded rows (triggered_by != comms_service)
    hand_seeded_patients = {
        r["patient_id"]
        for r in query_db(
            "SELECT DISTINCT patient_id FROM communications WHERE triggered_by != 'comms_service'"
        )
    }
    for pid in seen:
        assert pid in hand_seeded_patients, (
            f"Top thread patient {pid} is not from the hand-seeded fixture — "
            f"comms_service reminders are sorting above the hand-seeded set."
        )

    # Variety check: the top-5 threads' most-recent message contents should not
    # all be identical (the original bug: 27 identical reminders).
    top_5_last_msgs = []
    seen_pids = set()
    for c in comms:
        if c["patient_id"] in seen_pids:
            continue
        seen_pids.add(c["patient_id"])
        top_5_last_msgs.append(c["content"])
        if len(top_5_last_msgs) == 5:
            break

    assert len(set(top_5_last_msgs)) >= 4, (
        f"Expected >= 4 distinct last-messages among top-5 threads, got "
        f"{len(set(top_5_last_msgs))}: {top_5_last_msgs}"
    )
