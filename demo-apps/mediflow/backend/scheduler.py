"""Background scheduler for the overnight analysis pipeline.

Runs a single APScheduler CronTrigger job that executes the full
pattern-detection → skill-generation pipeline at a configured time
(default 02:00). The schedule is persisted in the `pipeline_state`
table and survives app restarts.
"""

import asyncio
import logging
import time as _time
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.services.database import query_db, execute_db

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None
_JOB_ID = "pipeline-overnight"


def _get_state() -> dict:
    rows = query_db("SELECT * FROM pipeline_state WHERE id = 'singleton'")
    return dict(rows[0]) if rows else {}


def _compute_next_run(schedule_time: str) -> str:
    hour, minute = schedule_time.split(":")
    now = datetime.now()
    next_run = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run.isoformat()


async def run_pipeline_job():
    """Execute the analysis pipeline as a scheduled background job."""
    from backend.analysis.orchestrator import run_analysis

    logger.info("Scheduled pipeline run starting...")
    execute_db(
        "UPDATE pipeline_state SET status = 'running', error_message = NULL WHERE id = 'singleton'"
    )

    start = _time.time()
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, run_analysis)

        duration_ms = int((_time.time() - start) * 1000)
        execute_db(
            """UPDATE pipeline_state SET
                status = 'completed',
                last_run_at = ?,
                last_duration_ms = ?,
                patterns_detected = ?,
                skills_generated = ?,
                memories_generated = ?,
                error_message = NULL
            WHERE id = 'singleton'""",
            (
                datetime.now().isoformat(),
                duration_ms,
                result.get("patterns_detected", 0),
                result.get("skills_generated", 0),
                result.get("memories_generated", 0),
            ),
        )
        logger.info(
            "Pipeline complete: %d patterns, %d skills, %d memories (%dms)",
            result.get("patterns_detected", 0),
            result.get("skills_generated", 0),
            result.get("memories_generated", 0),
            duration_ms,
        )
    except Exception as e:
        duration_ms = int((_time.time() - start) * 1000)
        execute_db(
            """UPDATE pipeline_state SET
                status = 'failed',
                last_run_at = ?,
                last_duration_ms = ?,
                error_message = ?
            WHERE id = 'singleton'""",
            (datetime.now().isoformat(), duration_ms, str(e)),
        )
        logger.error("Pipeline failed: %s", e)


def start_scheduler():
    """Start the background scheduler with the overnight pipeline job."""
    global _scheduler

    state = _get_state()
    if not state.get("auto_enabled", 1):
        logger.info("Pipeline auto-trigger disabled — scheduler not started")
        return

    schedule_time = state.get("schedule_time", "02:00")
    hour, minute = schedule_time.split(":")

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        run_pipeline_job,
        CronTrigger(hour=int(hour), minute=int(minute)),
        id=_JOB_ID,
        replace_existing=True,
    )
    _scheduler.start()

    next_run = _compute_next_run(schedule_time)
    execute_db(
        "UPDATE pipeline_state SET next_scheduled_run = ? WHERE id = 'singleton'",
        (next_run,),
    )
    logger.info("Scheduler started — pipeline scheduled at %s (next: %s)", schedule_time, next_run)


def stop_scheduler():
    """Shut down the scheduler gracefully."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def reschedule_pipeline(schedule_time: str):
    """Update the overnight job to a new time."""
    global _scheduler
    if not _scheduler:
        start_scheduler()
        return

    hour, minute = schedule_time.split(":")
    _scheduler.reschedule_job(_JOB_ID, trigger=CronTrigger(hour=int(hour), minute=int(minute)))

    next_run = _compute_next_run(schedule_time)
    execute_db(
        "UPDATE pipeline_state SET next_scheduled_run = ? WHERE id = 'singleton'",
        (next_run,),
    )
    logger.info("Pipeline rescheduled to %s (next: %s)", schedule_time, next_run)


def enable_scheduler():
    """Enable auto-trigger and start scheduler if not running."""
    execute_db("UPDATE pipeline_state SET auto_enabled = 1 WHERE id = 'singleton'")
    if not _scheduler:
        start_scheduler()


def disable_scheduler():
    """Disable auto-trigger and stop scheduler."""
    execute_db(
        "UPDATE pipeline_state SET auto_enabled = 0, next_scheduled_run = NULL WHERE id = 'singleton'"
    )
    stop_scheduler()
