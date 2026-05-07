"""Observability & telemetry API routes."""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from backend.services.database import query_db

logger = logging.getLogger(__name__)
router = APIRouter(tags=["metrics"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/api/metrics/summary")
async def metrics_summary():
    """Aggregate health metrics across all skill executions."""
    now = _utc_now()
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    cutoff_7d = (now - timedelta(days=7)).isoformat()
    cutoff_30d = (now - timedelta(days=30)).isoformat()

    def _count(since: str) -> int:
        rows = query_db(
            "SELECT COUNT(*) AS cnt FROM skill_executions WHERE started_at >= ?",
            (since,),
        )
        return rows[0]["cnt"] if rows else 0

    executions_24h = _count(cutoff_24h)
    executions_7d = _count(cutoff_7d)
    executions_30d = _count(cutoff_30d)

    # Success rate (7d)
    stats_7d = query_db(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS succeeded
           FROM skill_executions WHERE started_at >= ?""",
        (cutoff_7d,),
    )
    total_7d = stats_7d[0]["total"] if stats_7d else 0
    succeeded_7d = stats_7d[0]["succeeded"] if stats_7d else 0
    success_rate_7d = round(succeeded_7d / total_7d, 3) if total_7d > 0 else 1.0

    # Averages (7d)
    avgs_7d = query_db(
        """SELECT
             AVG(duration_ms) AS avg_duration,
             SUM(tokens_input) AS total_input,
             SUM(tokens_output) AS total_output,
             SUM(estimated_cost_usd) AS total_cost
           FROM skill_executions WHERE started_at >= ?""",
        (cutoff_7d,),
    )
    avg_duration_7d = round(avgs_7d[0]["avg_duration"] or 0)
    total_tokens_input_7d = avgs_7d[0]["total_input"] or 0
    total_tokens_output_7d = avgs_7d[0]["total_output"] or 0
    total_cost_7d = round(avgs_7d[0]["total_cost"] or 0, 4)

    # Daily cost breakdown (last 14 days)
    cutoff_14d = (now - timedelta(days=14)).isoformat()
    daily_rows = query_db(
        """SELECT
             DATE(started_at) AS date,
             SUM(estimated_cost_usd) AS cost_usd,
             COUNT(*) AS executions
           FROM skill_executions
           WHERE started_at >= ?
           GROUP BY DATE(started_at)
           ORDER BY date""",
        (cutoff_14d,),
    )
    daily_cost = [
        {"date": r["date"], "cost_usd": round(r["cost_usd"] or 0, 4), "executions": r["executions"]}
        for r in daily_rows
    ]

    return {
        "executions_24h": executions_24h,
        "executions_7d": executions_7d,
        "executions_30d": executions_30d,
        "success_rate_7d": success_rate_7d,
        "avg_duration_ms_7d": avg_duration_7d,
        "total_tokens_input_7d": total_tokens_input_7d,
        "total_tokens_output_7d": total_tokens_output_7d,
        "total_cost_7d_usd": total_cost_7d,
        "daily_cost": daily_cost,
    }


@router.get("/api/metrics/skills/{skill_id}")
async def metrics_skill(skill_id: str):
    """Per-skill execution metrics."""
    rows = query_db(
        """SELECT
             COUNT(*) AS total,
             SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS succeeded,
             AVG(duration_ms) AS avg_duration,
             AVG(tokens_input) AS avg_tokens_input,
             AVG(tokens_output) AS avg_tokens_output,
             SUM(estimated_cost_usd) AS total_cost
           FROM skill_executions WHERE skill_id = ?""",
        (skill_id,),
    )
    agg = rows[0] if rows else {}

    total = agg.get("total", 0) or 0
    succeeded = agg.get("succeeded", 0) or 0

    # Skill name
    skill_rows = query_db("SELECT name FROM skills WHERE id = ?", (skill_id,))
    skill_name = skill_rows[0]["name"] if skill_rows else skill_id

    # Last 10 executions
    recent = query_db(
        """SELECT started_at, duration_ms, tokens_input, tokens_output,
                  estimated_cost_usd, status
           FROM skill_executions WHERE skill_id = ?
           ORDER BY started_at DESC LIMIT 10""",
        (skill_id,),
    )

    return {
        "skill_id": skill_id,
        "skill_name": skill_name,
        "total_executions": total,
        "success_rate": round(succeeded / total, 3) if total > 0 else 1.0,
        "avg_duration_ms": round(agg.get("avg_duration") or 0),
        "avg_tokens_input": round(agg.get("avg_tokens_input") or 0),
        "avg_tokens_output": round(agg.get("avg_tokens_output") or 0),
        "total_cost_usd": round(agg.get("total_cost") or 0, 4),
        "last_10": recent,
    }


@router.get("/api/metrics/cost")
async def metrics_cost():
    """Cost breakdown by skill and time."""
    now = _utc_now()

    # Month-to-date
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    mtd_rows = query_db(
        "SELECT SUM(estimated_cost_usd) AS total FROM skill_executions WHERE started_at >= ?",
        (month_start,),
    )
    total_cost_mtd = round((mtd_rows[0]["total"] or 0) if mtd_rows else 0, 4)

    # Last month
    first_of_month = now.replace(day=1)
    last_month_end = first_of_month
    last_month_start = (first_of_month - timedelta(days=1)).replace(day=1)
    lm_rows = query_db(
        "SELECT SUM(estimated_cost_usd) AS total FROM skill_executions WHERE started_at >= ? AND started_at < ?",
        (last_month_start.isoformat(), last_month_end.isoformat()),
    )
    total_cost_last_month = round((lm_rows[0]["total"] or 0) if lm_rows else 0, 4)

    # By skill
    by_skill = query_db(
        """SELECT
             se.skill_id,
             s.name AS skill_name,
             SUM(se.estimated_cost_usd) AS cost_usd,
             COUNT(*) AS executions
           FROM skill_executions se
           LEFT JOIN skills s ON s.id = se.skill_id
           WHERE se.estimated_cost_usd IS NOT NULL
           GROUP BY se.skill_id
           ORDER BY cost_usd DESC"""
    )

    # Daily trend (last 30 days)
    cutoff_30d = (now - timedelta(days=30)).isoformat()
    daily_rows = query_db(
        """SELECT DATE(started_at) AS date, SUM(estimated_cost_usd) AS cost_usd
           FROM skill_executions WHERE started_at >= ?
           GROUP BY DATE(started_at) ORDER BY date""",
        (cutoff_30d,),
    )
    daily_trend = [
        {"date": r["date"], "cost_usd": round(r["cost_usd"] or 0, 4)}
        for r in daily_rows
    ]

    return {
        "total_cost_mtd_usd": total_cost_mtd,
        "total_cost_last_month_usd": total_cost_last_month,
        "by_skill": [
            {
                "skill_id": r["skill_id"],
                "skill_name": r["skill_name"] or r["skill_id"],
                "cost_usd": round(r["cost_usd"] or 0, 4),
                "executions": r["executions"],
            }
            for r in by_skill
        ],
        "daily_trend": daily_trend,
    }
