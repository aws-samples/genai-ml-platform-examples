"""Tests for deterministic pattern detection on tool-call logs."""

import json

import pytest

from backend.services.database import execute_db, query_db
from backend.analysis.pattern_detector import detect_patterns


def _log_tool(session_id: str, tool_name: str, params: dict, seq: int):
    """Insert a synthetic tool_call_log row."""
    execute_db(
        "INSERT INTO tool_call_log (session_id, timestamp, tool_name, tool_params, result_summary, duration_ms, sequence_number) "
        "VALUES (?, datetime('now'), ?, ?, 'ok', 50, ?)",
        (session_id, tool_name, json.dumps(params), seq),
    )


class TestBatchPatternDetection:
    """Batch = same tool called 3+ times consecutively in a session."""

    def test_detects_batch_pattern(self):
        # Create 3 sessions each with 4 consecutive calls of the same tool
        for s in range(1, 4):
            for i in range(4):
                _log_tool(f"sess-batch-{s}", "send_appointment_reminder", {"patient_id": f"pat-{i:03d}"}, i)

        patterns = detect_patterns(min_occurrences=3)
        batch_patterns = [p for p in patterns if p["pattern_type"] == "BATCH"]
        assert len(batch_patterns) >= 1

        # The detected batch should reference send_appointment_reminder
        tool_seqs = [p["tool_sequence"] for p in batch_patterns]
        assert any("send_appointment_reminder" in seq for seq in tool_seqs)

    def test_no_batch_below_threshold(self):
        # Only 2 consecutive calls — below batch run-length threshold of 3
        _log_tool("sess-short-1", "get_patient", {"patient_id": "pat-001"}, 0)
        _log_tool("sess-short-1", "get_patient", {"patient_id": "pat-002"}, 1)

        patterns = detect_patterns(min_occurrences=1)
        batch_patterns = [p for p in patterns if p["pattern_type"] == "BATCH"]
        # Should not detect a 2-call run as batch
        short_batches = [
            p for p in batch_patterns
            if p["tool_sequence"] == ["get_patient"]
        ]
        assert len(short_batches) == 0


class TestSequencePatternDetection:
    """Sequence = ordered multi-tool sequence recurring across sessions."""

    def test_detects_sequence_pattern(self):
        # The sequence [search_patients, check_availability, book_appointment]
        # appears in 4 sessions
        for s in range(1, 5):
            _log_tool(f"sess-seq-{s}", "search_patients", {"query": "Smith"}, 0)
            _log_tool(f"sess-seq-{s}", "check_availability", {"doctor_id": "dr-chen"}, 1)
            _log_tool(f"sess-seq-{s}", "book_appointment", {"patient_id": "pat-001"}, 2)

        patterns = detect_patterns(min_occurrences=3)
        seq_patterns = [p for p in patterns if p["pattern_type"] == "SEQUENCE"]
        assert len(seq_patterns) >= 1

        # At least one should involve search_patients
        seqs = [p["tool_sequence"] for p in seq_patterns]
        assert any("search_patients" in s for s in seqs)

    def test_no_sequence_from_single_session(self):
        # A sequence appearing only once shouldn't be detected
        _log_tool("sess-once-1", "get_practice_info", {}, 0)
        _log_tool("sess-once-1", "get_doctor_info", {"doctor_id": "dr-chen"}, 1)

        patterns = detect_patterns(min_occurrences=3)
        # Should not find a sequence from just one session
        for p in patterns:
            if p["pattern_type"] == "SEQUENCE":
                assert p["occurrence_count"] >= 3


class TestPatternPersistence:
    """Verify patterns are written to the detected_patterns table."""

    def test_patterns_persisted_to_db(self):
        for s in range(1, 5):
            for i in range(4):
                _log_tool(f"sess-persist-{s}", "send_payment_reminder", {"invoice_id": f"inv-{i}"}, i)

        detect_patterns(min_occurrences=3)
        rows = query_db("SELECT * FROM detected_patterns")
        assert len(rows) >= 1
        # Each row should have the required fields
        for row in rows:
            assert row["pattern_type"] in ("BATCH", "SEQUENCE")
            assert row["tool_sequence"] is not None
            assert row["occurrence_count"] >= 1
