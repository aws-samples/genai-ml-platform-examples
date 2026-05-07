"""Orchestrate the analysis pipeline.

Runs four stages in sequence:

1. **Pattern detection** (deterministic) — mines tool_call_log, ui_activity_log,
   and live database for recurring patterns.
2. **Context extraction** (LLM) — pulls evidence from the appropriate source
   and extracts intent, conditional logic, and cadence hint.
3. **Skill generation** (LLM) — produces a unified ``skills`` row for each
   pattern with ``scheduled`` flag and optional ``batch_selection_hint``.
4. **Patient memory detection** (deterministic) — scans data for behavioral
   patterns and stores them as patient memories.

The entry point is ``run_analysis()``.
"""

import logging
import threading
from collections import Counter

from backend.analysis.pattern_detector import detect_patterns
from backend.analysis.context_extractor import extract_context_for_patterns
from backend.analysis.automation_generator import generate_automations
from backend.services.memory_service import detect_behavioral_memories
from backend.services.database import query_db, execute_db

logger = logging.getLogger(__name__)

_cancel_event = threading.Event()

STAGES = [
    "Detecting patterns",
    "Extracting context",
    "Generating skills",
    "Detecting memories",
]


def cancel_analysis():
    """Signal the running pipeline to stop after the current stage."""
    _cancel_event.set()


def _update_stage(stage_index: int):
    """Write current stage to pipeline_state for frontend polling."""
    label = STAGES[stage_index] if stage_index < len(STAGES) else "Finishing"
    execute_db(
        "UPDATE pipeline_state SET current_stage = ?, stages_total = ?, stage_index = ? WHERE id = 'singleton'",
        (label, len(STAGES), stage_index),
    )


def _check_cancelled() -> bool:
    if _cancel_event.is_set():
        _cancel_event.clear()
        execute_db(
            "UPDATE pipeline_state SET status = 'cancelled', current_stage = NULL WHERE id = 'singleton'"
        )
        logger.info("Pipeline cancelled by user")
        return True
    return False

logger = logging.getLogger(__name__)


def _select_top_patterns(patterns: list[dict], max_count: int = 15) -> list[dict]:
    """Select top patterns ensuring type diversity and highest confidence."""
    by_type: dict[str, list[dict]] = {}
    for p in patterns:
        by_type.setdefault(p["pattern_type"], []).append(p)

    # Sort each type by confidence descending
    for ptype in by_type:
        by_type[ptype].sort(key=lambda p: p["confidence"], reverse=True)

    # Round-robin across types, then fill remaining slots by confidence
    selected: list[dict] = []
    seen_ids: set[str] = set()

    # Guarantee at least 2 from each type (if available)
    for ptype, pats in by_type.items():
        for p in pats[:2]:
            if p["id"] not in seen_ids:
                selected.append(p)
                seen_ids.add(p["id"])

    # Fill remaining slots from all patterns by confidence
    remaining = sorted(
        [p for p in patterns if p["id"] not in seen_ids],
        key=lambda p: p["confidence"],
        reverse=True,
    )
    for p in remaining:
        if len(selected) >= max_count:
            break
        selected.append(p)
        seen_ids.add(p["id"])

    return selected


def run_analysis() -> dict:
    """Run the complete analysis pipeline.

    Returns
    -------
    dict
        Summary with keys: ``status``, ``patterns_detected``, ``skills_generated``,
        ``memories_generated``, ``details``.
    """

    _cancel_event.clear()
    logger.info("=== Starting Analysis Pipeline ===")

    # ------------------------------------------------------------------
    # Stage 1: Pattern detection (deterministic)
    # ------------------------------------------------------------------
    _update_stage(0)
    logger.info("Stage 1: Detecting patterns...")
    patterns = detect_patterns(min_occurrences=2)
    logger.info("  Found %d patterns", len(patterns))

    if not patterns:
        logger.info("=== Analysis Complete: no patterns found ===")
        return {
            "status": "complete",
            "patterns_detected": 0,
            "patterns_by_type": {},
            "skills_generated": 0,
            "memories_generated": 0,
            "details": {"skills": [], "top_memories": []},
        }

    if _check_cancelled():
        return {"status": "cancelled"}

    # ------------------------------------------------------------------
    # Stage 2: Context extraction (LLM)
    # Select top patterns by confidence with type diversity for LLM stages.
    # ------------------------------------------------------------------
    _update_stage(1)
    logger.info("Stage 2: Extracting context and cadence hint...")
    top_patterns = _select_top_patterns(patterns, max_count=15)

    # Skip patterns that already have a generated skill.
    # Match on description since pattern IDs regenerate each run.
    existing_descriptions = {
        r["description"]
        for r in query_db(
            "SELECT dp.description FROM skills s "
            "JOIN detected_patterns dp ON dp.id = s.pattern_id "
            "WHERE s.pattern_id IS NOT NULL"
        )
    }
    new_patterns = [p for p in top_patterns if p["description"] not in existing_descriptions]
    skipped = len(top_patterns) - len(new_patterns)
    if skipped:
        logger.info("  Skipping %d patterns that already have skills", skipped)

    logger.info("  Selected %d new patterns for LLM stages (from %d total)", len(new_patterns), len(patterns))
    if new_patterns:
        new_patterns = extract_context_for_patterns(new_patterns)
    logger.info("  Context extracted for %d patterns", len(new_patterns))

    if _check_cancelled():
        return {"status": "cancelled"}

    # ------------------------------------------------------------------
    # Stage 3: Unified skill generation (LLM)
    # ------------------------------------------------------------------
    _update_stage(2)
    logger.info("Stage 3: Generating unified skills...")
    if new_patterns:
        automations = generate_automations(new_patterns)
        skills = automations["skills"]
    else:
        skills = []
    logger.info("  Generated %d skills", len(skills))

    if _check_cancelled():
        return {"status": "cancelled"}

    # ------------------------------------------------------------------
    # Stage 4: Patient memory detection (deterministic)
    # ------------------------------------------------------------------
    _update_stage(3)
    logger.info("Stage 4: Detecting patient memories...")
    memory_ids = detect_behavioral_memories()
    logger.info("  Created/updated %d patient memories", len(memory_ids))

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    patterns_by_type = dict(Counter(p["pattern_type"] for p in patterns))

    top_memories_rows = query_db(
        "SELECT id, patient_id, memory_type, content, confidence "
        "FROM patient_memories ORDER BY first_observed DESC LIMIT 10"
    )
    top_memories = [
        {
            "id": m["id"],
            "patient_id": m["patient_id"],
            "type": m["memory_type"],
            "content": m["content"],
            "confidence": m["confidence"],
        }
        for m in top_memories_rows
    ]

    summary = {
        "status": "complete",
        "patterns_detected": len(patterns),
        "patterns_by_type": patterns_by_type,
        "patterns_enriched": len(top_patterns),
        "skills_generated": len(skills),
        "skills_skipped": skipped,
        "memories_generated": len(memory_ids),
        "details": {
            "patterns": [
                {
                    "id": p["id"],
                    "type": p["pattern_type"],
                    "description": p["description"],
                    "occurrences": p["occurrence_count"],
                }
                for p in top_patterns
            ],
            "skills": [
                {
                    "id": s["id"],
                    "name": s["name"],
                    "trigger": s.get("trigger_description", ""),
                    "scheduled": s.get("scheduled", False),
                }
                for s in skills
            ],
            "top_memories": top_memories,
        },
    }

    logger.info(
        "=== Analysis Complete: %d patterns, %d skills, %d memories ===",
        len(patterns),
        len(skills),
        len(memory_ids),
    )
    return summary
