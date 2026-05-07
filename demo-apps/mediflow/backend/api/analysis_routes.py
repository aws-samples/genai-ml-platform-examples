"""Analysis API routes for triggering and monitoring the analysis pipeline."""

import logging
import asyncio
import time as _time
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from backend.analysis.orchestrator import run_analysis
from backend.services.database import query_db, execute_db

logger = logging.getLogger(__name__)
router = APIRouter()

_pipeline_lock = asyncio.Lock()


@router.get("/api/analysis/status")
async def pipeline_status():
    """Return current pipeline state — last run, next run, status."""
    rows = query_db("SELECT * FROM pipeline_state WHERE id = 'singleton'")
    if not rows:
        return {
            "status": "idle",
            "last_run_at": None,
            "last_duration_ms": None,
            "patterns_detected": 0,
            "skills_generated": 0,
            "memories_generated": 0,
            "next_scheduled_run": None,
            "auto_enabled": True,
            "schedule_time": "02:00",
            "error_message": None,
        }
    state = dict(rows[0])
    state["auto_enabled"] = bool(state.get("auto_enabled", 1))
    return state


@router.post("/api/analysis/run")
async def trigger_analysis():
    """Run the full analysis pipeline (pattern detection → skill generation).

    Updates pipeline_state with progress and results. Prevents concurrent runs
    via an asyncio lock. Records each run in pipeline_runs history.
    """
    if _pipeline_lock.locked():
        return {"status": "already_running", "message": "Pipeline is already running"}

    async with _pipeline_lock:
        execute_db(
            "UPDATE pipeline_state SET status = 'running', error_message = NULL WHERE id = 'singleton'"
        )

        started_at = datetime.now().isoformat()
        execute_db(
            "INSERT INTO pipeline_runs (started_at, status) VALUES (?, 'running')",
            (started_at,),
        )
        run_rows = query_db(
            "SELECT id FROM pipeline_runs WHERE started_at = ? ORDER BY id DESC LIMIT 1",
            (started_at,),
        )
        run_id = run_rows[0]["id"] if run_rows else None

        start = _time.time()
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_analysis)

            duration_ms = int((_time.time() - start) * 1000)
            final_status = result.get("status", "completed")
            if final_status == "cancelled":
                if run_id:
                    execute_db(
                        "UPDATE pipeline_runs SET status = 'cancelled', completed_at = ?, duration_ms = ? WHERE id = ?",
                        (datetime.now().isoformat(), duration_ms, run_id),
                    )
                return result

            execute_db(
                """UPDATE pipeline_state SET
                    status = 'completed',
                    last_run_at = ?,
                    last_duration_ms = ?,
                    patterns_detected = ?,
                    skills_generated = ?,
                    skills_skipped = ?,
                    memories_generated = ?,
                    error_message = NULL,
                    current_stage = NULL
                WHERE id = 'singleton'""",
                (
                    datetime.now().isoformat(),
                    duration_ms,
                    result.get("patterns_detected", 0),
                    result.get("skills_generated", 0),
                    result.get("skills_skipped", 0),
                    result.get("memories_generated", 0),
                ),
            )

            if run_id:
                execute_db(
                    """UPDATE pipeline_runs SET
                        status = 'completed',
                        completed_at = ?,
                        duration_ms = ?,
                        patterns_detected = ?,
                        patterns_enriched = ?,
                        skills_generated = ?,
                        skills_skipped = ?,
                        memories_generated = ?
                    WHERE id = ?""",
                    (
                        datetime.now().isoformat(),
                        duration_ms,
                        result.get("patterns_detected", 0),
                        result.get("patterns_enriched", 0),
                        result.get("skills_generated", 0),
                        result.get("skills_skipped", 0),
                        result.get("memories_generated", 0),
                        run_id,
                    ),
                )

            return result

        except Exception as e:
            duration_ms = int((_time.time() - start) * 1000)
            execute_db(
                """UPDATE pipeline_state SET
                    status = 'failed',
                    last_run_at = ?,
                    last_duration_ms = ?,
                    error_message = ?,
                    current_stage = NULL
                WHERE id = 'singleton'""",
                (datetime.now().isoformat(), duration_ms, str(e)),
            )
            if run_id:
                execute_db(
                    "UPDATE pipeline_runs SET status = 'failed', completed_at = ?, duration_ms = ?, error_message = ? WHERE id = ?",
                    (datetime.now().isoformat(), duration_ms, str(e), run_id),
                )
            logger.error("Pipeline failed: %s", e)
            return {"status": "failed", "error": str(e), "duration_ms": duration_ms}


@router.post("/api/analysis/cancel")
async def cancel_analysis_run():
    """Signal the running pipeline to stop after the current stage."""
    from backend.analysis.orchestrator import cancel_analysis

    rows = query_db("SELECT status FROM pipeline_state WHERE id = 'singleton'")
    if not rows or rows[0]["status"] != "running":
        return {"status": "not_running"}

    cancel_analysis()
    return {"status": "cancel_requested"}


class PipelineConfig(BaseModel):
    auto_enabled: bool | None = None
    schedule_time: str | None = None


@router.patch("/api/analysis/config")
async def update_pipeline_config(body: PipelineConfig):
    """Toggle auto-trigger or change the overnight schedule time."""
    from backend.scheduler import (
        enable_scheduler,
        disable_scheduler,
        reschedule_pipeline,
    )

    if body.auto_enabled is not None:
        if body.auto_enabled:
            enable_scheduler()
        else:
            disable_scheduler()

    if body.schedule_time is not None:
        execute_db(
            "UPDATE pipeline_state SET schedule_time = ? WHERE id = 'singleton'",
            (body.schedule_time,),
        )
        reschedule_pipeline(body.schedule_time)

    rows = query_db("SELECT * FROM pipeline_state WHERE id = 'singleton'")
    state = dict(rows[0])
    state["auto_enabled"] = bool(state.get("auto_enabled", 1))
    return state


@router.get("/api/analysis/runs")
async def list_pipeline_runs(limit: int = 20):
    """Return recent pipeline run history, newest first."""
    rows = query_db(
        "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT ?",
        (min(limit, 100),),
    )
    return {"runs": [dict(r) for r in rows]}
