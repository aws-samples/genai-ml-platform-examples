"""TASK-046 Part A — ui_action events that reference a patient must carry patient_id.

The frontend is migrating from name-based cross-links to id-based. Any backend SSE
event that targets a patient must include patient_id so the consuming view can
resolve the entity deterministically.

Current state (expected to FAIL before build):
- select_patient already emits patient_id          (ui_tools.py:51, 83, 102)
- open_booking already emits patient_id            (ui_tools.py:87)
- set_patient_tab already emits patient_id         (ui_tools.py:106)
- add_message emits ONLY patient_name              (ui_tools.py:155-168)  <-- this is the gap

This test locks the contract: every patient-bearing ui_action event MUST include a
non-empty patient_id field.
"""

import asyncio

import pytest

from backend.tools.ui_tools import (
    select_patient,
    open_booking_for_patient,
    show_patient_tab,
    send_patient_message,
)


PATIENT_BEARING_ACTIONS = {
    "select_patient",
    "open_booking",
    "set_patient_tab",
    "add_message",
}


def _drain(async_gen):
    """Collect every yielded dict from an async generator into a list."""
    async def _collect():
        out = []
        async for ev in async_gen:
            out.append(ev)
        return out

    return asyncio.run(_collect())


def _patient_events(events):
    """Filter to dicts whose ui_action is one of the patient-bearing ones."""
    return [
        e for e in events
        if isinstance(e, dict) and e.get("ui_action") in PATIENT_BEARING_ACTIONS
    ]


class TestPatientIdOnUiActions:
    """Every patient-bearing ui_action must carry patient_id."""

    def test_select_patient_emits_patient_id(self, seed_data):
        events = _drain(select_patient(patient_id="pat-001", patient_name="Sarah Mitchell"))
        patient_events = _patient_events(events)
        assert patient_events, "select_patient should emit at least one patient-bearing ui_action"
        for ev in patient_events:
            assert ev.get("patient_id"), (
                f"ui_action {ev.get('ui_action')!r} missing patient_id: {ev}"
            )

    def test_open_booking_emits_patient_id(self, seed_data):
        events = _drain(open_booking_for_patient(patient_id="pat-001", doctor_id="dr-chen"))
        patient_events = _patient_events(events)
        assert patient_events
        for ev in patient_events:
            assert ev.get("patient_id"), (
                f"ui_action {ev.get('ui_action')!r} missing patient_id: {ev}"
            )

    def test_show_patient_tab_emits_patient_id(self, seed_data):
        events = _drain(show_patient_tab(patient_id="pat-001", tab="invoices"))
        patient_events = _patient_events(events)
        assert patient_events
        for ev in patient_events:
            assert ev.get("patient_id"), (
                f"ui_action {ev.get('ui_action')!r} missing patient_id: {ev}"
            )

    def test_send_patient_message_add_message_carries_patient_id(self, seed_data):
        """add_message currently emits only patient_name — this test should fail
        until Builder adds patient_id to the payload in ui_tools.py send_patient_message."""
        events = _drain(send_patient_message(
            patient_id="pat-001",
            patient_name="Sarah Mitchell",
            message="Hi Sarah, your test reminder.",
            channel="sms",
        ))
        add_message_events = [e for e in events if e.get("ui_action") == "add_message"]
        assert add_message_events, "send_patient_message should emit an add_message ui_action"
        for ev in add_message_events:
            assert ev.get("patient_id") == "pat-001", (
                f"add_message ui_action missing or wrong patient_id: {ev}"
            )
