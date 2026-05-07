"""Unified Skill API routes.

A Skill is the sole agent-executed unit in the unified model. Two
dimensions are independent:
* ``scheduled`` 0/1 — ad-hoc vs cron-like.
* batch vs single-item — inferred from ``batch_selection_hint`` and
  what the agent resolves at run time.

Endpoints:
* ``GET    /api/skills`` — unified list.
* ``GET    /api/skills/{id}`` — full detail + pattern context.
* ``POST   /api/skills/{id}/test`` — dry-run (returns proposed plan).
* ``POST   /api/skills/{id}/execute`` — ad-hoc invocation. For batch
  skills, emits a ``skill_approval`` SSE event and waits for the caller
  to POST to ``/run`` (Approve & Run) or drop the stream (Cancel).
* ``POST   /api/skills/{id}/run`` — scheduled / approved-batch / single
  execution path. Requires ``status='enabled'``. Updates ``last_run_at``.
* ``PATCH  /api/skills/{id}/schedule`` — cadence / time / day.
* ``PATCH  /api/skills/{id}/enable`` — set status to ``enabled`` and
  timestamp ``enabled_at``.
"""

import asyncio
import json
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from backend.services.database import execute_db, query_db

logger = logging.getLogger(__name__)
router = APIRouter()


VALID_CADENCES = {"daily", "weekdays", "weekly", "monthly"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_json_field(row: dict, field: str) -> None:
    if row.get(field):
        try:
            row[field] = json.loads(row[field])
        except (json.JSONDecodeError, TypeError):
            pass


def _tool_config(skill: dict) -> list:
    raw = skill.get("tool_config")
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []


def _is_batch(skill: dict) -> bool:
    hint = skill.get("batch_selection_hint")
    return bool(hint and str(hint).strip())


def _resolve_batch_items(skill: dict) -> list[dict]:
    """Best-effort resolution of what items this batch skill would act on.

    For the unified model, the agent resolves items at true run time. For
    the approval card we provide a short sample so the user can see the
    blast radius.
    """
    # Ad-hoc skills persist their staged items on the row so the run
    # stream can emit per-item progress without re-resolving.
    cached = skill.get("cached_items")
    if cached:
        try:
            parsed = json.loads(cached)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, TypeError):
            pass

    hint = (skill.get("batch_selection_hint") or "").lower()
    items: list[dict] = []

    if "invoice" in hint or "outstanding" in hint or "overdue" in hint:
        rows = query_db(
            "SELECT i.id AS invoice_id, i.amount, i.amount_paid, i.chase_count, "
            "i.due_date, p.first_name, p.last_name "
            "FROM invoices i LEFT JOIN patients p ON i.patient_id = p.id "
            "WHERE i.status = 'outstanding' ORDER BY i.due_date LIMIT 10"
        )
        for r in rows:
            outstanding = (r.get("amount") or 0) - (r.get("amount_paid") or 0)
            items.append({
                "id": r["invoice_id"],
                "label": f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or r["invoice_id"],
                "detail": f"${outstanding:.0f} · chase {(r.get('chase_count') or 0) + 1}",
            })
    elif "patient" in hint or "appointment" in hint or "reminder" in hint:
        rows = query_db(
            "SELECT a.id AS appointment_id, a.date, a.time, "
            "p.first_name, p.last_name "
            "FROM appointments a LEFT JOIN patients p ON a.patient_id = p.id "
            "WHERE a.status = 'scheduled' AND a.reminder_sent = 0 "
            "ORDER BY a.date, a.time LIMIT 10"
        )
        for r in rows:
            name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            items.append({
                "id": r["appointment_id"],
                "label": name or r["appointment_id"],
                "detail": f"{r.get('date')} {r.get('time')}",
            })
    elif "doctor" in hint or "briefing" in hint or "working_days" in hint:
        # Morning Briefing and similar — resolve to doctors working today.
        rows = query_db("SELECT id, name, specialty, working_days FROM doctors ORDER BY name")
        today_name = datetime.now().strftime("%A")  # e.g. "Monday"
        for r in rows:
            wd = r.get("working_days") or ""
            if today_name in wd:
                items.append({
                    "id": r["id"],
                    "label": r["name"],
                    "detail": r.get("specialty") or "working today",
                })

    return items


# ---------------------------------------------------------------------------
# List & detail
# ---------------------------------------------------------------------------

@router.get("/api/skills")
async def list_skills(status: str | None = None):
    """List all skills, optionally filtered by status."""
    if status:
        skills = query_db(
            "SELECT * FROM skills WHERE status = ? ORDER BY created_at DESC",
            (status,),
        )
    else:
        skills = query_db("SELECT * FROM skills ORDER BY created_at DESC")

    for sk in skills:
        _parse_json_field(sk, "tool_config")
        if sk.get("pattern_id"):
            patterns = query_db(
                "SELECT pattern_type, description AS pattern_description, occurrence_count "
                "FROM detected_patterns WHERE id = ?",
                (sk["pattern_id"],),
            )
            if patterns:
                sk["pattern_type"] = patterns[0]["pattern_type"]
                sk["pattern_description"] = patterns[0]["pattern_description"]
                sk["occurrence_count"] = patterns[0]["occurrence_count"]

    return {"skills": skills}


@router.get("/api/skills/{skill_id}")
async def get_skill(skill_id: str):
    """Get full skill details including source pattern."""
    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")

    sk = skills[0]
    _parse_json_field(sk, "tool_config")

    if sk.get("pattern_id"):
        patterns = query_db(
            "SELECT * FROM detected_patterns WHERE id = ?",
            (sk["pattern_id"],),
        )
        if patterns:
            pattern = patterns[0]
            _parse_json_field(pattern, "tool_sequence")
            _parse_json_field(pattern, "conversation_context")
            sk["pattern"] = pattern

    return sk


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------

@router.post("/api/skills/{skill_id}/test")
async def test_skill(skill_id: str):
    """Dry-run: return the skill's prompt template and proposed plan."""
    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")

    sk = skills[0]
    return {
        "skill_id": skill_id,
        "name": sk["name"],
        "mode": "dry_run",
        "prompt_template": sk.get("agent_prompt_template", ""),
        "tools_required": _tool_config(sk),
        "example_scenario": sk.get("example_scenario", ""),
    }


# ---------------------------------------------------------------------------
# Enable
# ---------------------------------------------------------------------------

@router.patch("/api/skills/{skill_id}/enable")
async def enable_skill(skill_id: str):
    """Flip a skill's status to ``enabled`` and timestamp ``enabled_at``.

    For scheduled skills, this is the pre-approval for future runs.
    """
    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")

    now = datetime.now().isoformat()
    execute_db(
        "UPDATE skills SET status = 'enabled', enabled_at = ? WHERE id = ?",
        (now, skill_id),
    )
    return {
        "success": True,
        "skill_id": skill_id,
        "status": "enabled",
        "enabled_at": now,
    }


@router.patch("/api/skills/{skill_id}/disable")
async def disable_skill(skill_id: str):
    """Revert a skill's status to ``pending_review``."""
    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")

    execute_db(
        "UPDATE skills SET status = 'pending_review' WHERE id = ?",
        (skill_id,),
    )
    return {
        "success": True,
        "skill_id": skill_id,
        "status": "pending_review",
    }


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

class ScheduleUpdate(BaseModel):
    cadence: str | None = None  # daily|weekdays|weekly|monthly
    time: str | None = None     # HH:MM (24h)
    day: int | None = None      # day-of-week (0=Mon) or day-of-month


@router.patch("/api/skills/{skill_id}/schedule")
async def update_schedule(skill_id: str, req: ScheduleUpdate):
    """Update the schedule configuration for a skill."""
    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")

    updates: list[str] = []
    params: list = []
    if req.cadence is not None:
        if req.cadence not in VALID_CADENCES:
            raise HTTPException(status_code=400, detail="Invalid cadence")
        updates.append("schedule_cadence = ?")
        params.append(req.cadence)
    if req.time is not None:
        updates.append("schedule_time = ?")
        params.append(req.time)
    if req.day is not None:
        updates.append("schedule_day = ?")
        params.append(req.day)

    # Any schedule change flips scheduled=1 so the skill is treated as scheduled.
    if updates:
        updates.append("scheduled = 1")
        params.append(skill_id)
        execute_db(
            f"UPDATE skills SET {', '.join(updates)} WHERE id = ?",  # nosec B608 - column names are hardcoded literals
            tuple(params),
        )

    sk = query_db(
        "SELECT schedule_cadence, schedule_time, schedule_day, scheduled FROM skills WHERE id = ?",
        (skill_id,),
    )[0]
    return {
        "success": True,
        "skill_id": skill_id,
        "schedule": {
            "cadence": sk["schedule_cadence"],
            "time": sk["schedule_time"],
            "day": sk["schedule_day"],
            "scheduled": bool(sk["scheduled"]),
        },
    }


def _morning_briefing_script() -> list[dict]:
    """Build a multi-phase Morning Briefing narrative from live data.

    Returns an ordered list of events — either ``{"section": label}``
    dividers or ``{"label": ..., "detail": ...}`` progress rows — that
    the run stream dispatches as SSE events with a ~0.8s cadence.
    """
    events: list[dict] = []
    today = datetime.now().strftime("%Y-%m-%d")
    today_name = datetime.now().strftime("%A")

    # Phase 1 — today's schedule (one row per working doctor)
    events.append({"section": "Today's schedule"})
    doctors = query_db("SELECT id, name, specialty, working_days, hours_start FROM doctors ORDER BY name")
    working = [d for d in doctors if today_name in (d.get("working_days") or "")]
    for d in working:
        appt_rows = query_db(
            "SELECT MIN(time) AS first_time, COUNT(*) AS cnt FROM appointments "
            "WHERE doctor_id = ? AND date = ? AND status = 'scheduled'",
            (d["id"], today),
        )
        cnt = appt_rows[0].get("cnt") if appt_rows else 0
        first_time = (appt_rows[0].get("first_time") if appt_rows else None) or d.get("hours_start") or "09:00"
        short_name = d["name"].replace("Dr ", "Dr ")
        detail = f"{cnt} appointments · first at {first_time}" if cnt else f"first slot {first_time}"
        events.append({"label": short_name, "detail": detail})

    # Phase 2 — overnight pathology (fabricated for demo; tied to real patient names)
    events.append({"section": "Overnight pathology"})
    path_rows = query_db(
        "SELECT p.first_name || ' ' || p.last_name AS name FROM patients p "
        "ORDER BY p.id LIMIT 3"
    )
    pathology = [
        ("HbA1c 9.2%", "elevated · Dr Chen to review"),
        ("eGFR 48", "declining · flag for Dr Patel"),
        ("CRP 4.1", "within range · no action needed"),
    ]
    for r, (test, flag) in zip(path_rows, pathology):
        events.append({"label": f"{r['name']} — {test}", "detail": flag})

    # Phase 3 — patients flagged for extra care (driven by memories)
    events.append({"section": "Patients to flag"})
    flagged = query_db(
        "SELECT DISTINCT p.first_name || ' ' || p.last_name AS name, pm.content "
        "FROM patient_memories pm JOIN patients p ON p.id = pm.patient_id "
        "WHERE pm.status = 'active' AND ("
        "  pm.content LIKE '%wheelchair%' OR pm.content LIKE '%interpret%' OR "
        "  pm.content LIKE '%mobility%' OR pm.content LIKE '%extra time%' OR "
        "  pm.content LIKE '%accompan%')"
        " LIMIT 4"
    )
    for f in flagged:
        reason = (f["content"] or "").split("—")[0].strip() or (f["content"] or "").split(".")[0].strip()
        if len(reason) > 60:
            reason = reason[:57].rstrip() + "…"
        events.append({"label": f["name"], "detail": reason})

    # Phase 4 — late-arrival risk (from behavioral memories)
    events.append({"section": "Likely late arrivals"})
    late_rows = query_db(
        "SELECT p.first_name || ' ' || p.last_name AS name, pm.content "
        "FROM patient_memories pm JOIN patients p ON p.id = pm.patient_id "
        "WHERE pm.status = 'active' AND ("
        "  pm.content LIKE '%no-show%' OR pm.content LIKE '%no show%' OR "
        "  pm.content LIKE '%runs late%' OR pm.content LIKE '%arrives late%' OR "
        "  pm.content LIKE '%chronically late%' OR pm.content LIKE '% min late%')"
        " LIMIT 3"
    )
    for r in late_rows:
        reason = (r["content"] or "").split("—")[0].strip() or (r["content"] or "").split(".")[0].strip()
        if len(reason) > 60:
            reason = reason[:57].rstrip() + "…"
        events.append({"label": r["name"], "detail": reason})

    # Phase 5 — summary
    events.append({"section": "Briefing ready"})
    total_appts = query_db(
        "SELECT COUNT(*) AS cnt FROM appointments WHERE date = ? AND status = 'scheduled'",
        (today,),
    )
    total = total_appts[0]["cnt"] if total_appts else 0
    path_ct = len(pathology[: len(path_rows)])
    flag_ct = len(flagged)
    late_ct = len(late_rows)
    events.append({
        "label": "Day shape",
        "detail": f"{total} appointments · {path_ct} pathology · {flag_ct} flagged · {late_ct} late-risk",
    })

    return events


async def _scripted_execution(sk: dict, items: list[dict]):
    """Fallback scripted execution when Bedrock is unavailable.

    Emits the same SSE events as the real executor but with simulated delays
    and pre-built data from _morning_briefing_script / _resolve_batch_items.
    """
    skill_id = sk["id"]
    tool_config = _tool_config(sk)
    is_morning_briefing = (sk.get("name") or "").strip().lower() == "morning briefing"
    briefing_events = _morning_briefing_script() if is_morning_briefing else []
    fallback_items = items if not is_morning_briefing else []

    yield {
        "event": "start",
        "data": json.dumps({
            "skill_id": skill_id,
            "name": sk["name"],
            "scheduled": bool(sk.get("scheduled")),
            "tools": tool_config,
            "item_count": len([e for e in briefing_events if "label" in e]) if briefing_events else len(fallback_items),
        }),
    }

    executed = 0
    if briefing_events:
        total = len([e for e in briefing_events if "label" in e])
        for evt in briefing_events:
            if "section" in evt:
                await asyncio.sleep(0.45)
                yield {"event": "section", "data": json.dumps({"label": evt["section"]})}
            else:
                await asyncio.sleep(0.35)
                executed += 1
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "item_id": evt.get("label", ""),
                        "entity_name": evt.get("label", ""),
                        "entity_flag": evt.get("detail"),
                        "executed": executed,
                        "total": total,
                    }),
                }
    elif fallback_items:
        total = len(fallback_items)
        for item in fallback_items:
            await asyncio.sleep(0.3)
            executed += 1
            yield {
                "event": "progress",
                "data": json.dumps({
                    "item_id": item.get("id", ""),
                    "entity_name": item.get("label") or item.get("id") or f"Item {executed}",
                    "entity_flag": item.get("detail"),
                    "executed": executed,
                    "total": total,
                }),
            }
    else:
        for i, tool in enumerate(tool_config or [None], 1):
            tool_name = tool if isinstance(tool, str) else (tool or {}).get("name") if tool else sk["name"]
            yield {"event": "action", "data": json.dumps({"step": i, "tool": tool_name})}
            await asyncio.sleep(0.2)
            executed = i

    yield {
        "event": "complete",
        "data": json.dumps({
            "skill_id": skill_id,
            "executed": executed,
            "total": len(fallback_items) if fallback_items else executed,
            "last_run_at": datetime.now().isoformat(),
        }),
    }


@router.post("/api/skills/{skill_id}/run")
async def run_skill(skill_id: str):
    """Run a skill without the stage-and-confirm approval gate.

    Called by the scheduler, the in-chat "Approve & Run" card, and the
    Insights "Run now" action for scheduled skills. Requires
    ``status='enabled'``.

    Invokes a real Strands Agent with the skill's prompt template and scoped
    tools. Falls back to scripted execution if Bedrock is unavailable.
    """
    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")

    sk = skills[0]
    if sk["status"] != "enabled":
        raise HTTPException(
            status_code=400,
            detail=f"Skill status is '{sk['status']}' — this skill must be enabled before it can run.",
        )

    if _is_batch(sk):
        from backend.agent.batch_resolver import resolve_batch
        items = await resolve_batch(sk)
        if not items:
            items = _resolve_batch_items(sk)
    else:
        items = []

    async def run_stream():
        from backend.agent.skill_executor import execute_skill

        try:
            async for event in execute_skill(sk, items):
                yield event
        except Exception as e:
            logger.warning("Agent execution failed, falling back to scripted: %s", e)
            yield {
                "event": "warning",
                "data": json.dumps({"message": f"Agent unavailable ({type(e).__name__}), using scripted execution"}),
            }
            async for event in _scripted_execution(sk, items):
                yield event

        # Update usage count
        now = datetime.now().isoformat()
        execute_db(
            "UPDATE skills SET usage_count = usage_count + 1, last_run_at = ? WHERE id = ?",
            (now, skill_id),
        )

    return EventSourceResponse(run_stream())


# ---------------------------------------------------------------------------
# Execute (ad-hoc; emits approval gate for batch)
# ---------------------------------------------------------------------------

@router.post("/api/skills/{skill_id}/execute")
async def execute_skill_adhoc(skill_id: str):
    """Ad-hoc execution path with approval gate for batch skills.

    For batch skills where item_count exceeds ``approval_threshold``,
    emits a ``skill_approval`` SSE event with the resolved items and
    pauses. The frontend renders an approval card; on Approve it calls
    ``POST /api/skills/{id}/approve/{execution_id}``.

    For single-item or below-threshold batch skills, runs directly.
    """
    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")

    sk = skills[0]
    tool_config = _tool_config(sk)
    is_batch = _is_batch(sk)
    threshold = sk.get("approval_threshold") or 1

    # Pre-resolve batch items before entering the stream generator
    if is_batch:
        from backend.agent.batch_resolver import resolve_batch
        resolved_items = await resolve_batch(sk)
        if not resolved_items:
            resolved_items = _resolve_batch_items(sk)
    else:
        resolved_items = []

    needs_approval = is_batch and len(resolved_items) >= threshold

    # If approval needed, create an execution record and cache items
    execution_id = None
    if needs_approval:
        from backend.services.execution_history import create_execution
        execution_id = create_execution(
            skill_id, trigger="manual", items_total=len(resolved_items)
        )
        execute_db(
            "UPDATE skill_executions SET status = 'awaiting_approval' WHERE id = ?",
            (execution_id,),
        )
        execute_db(
            "UPDATE skills SET cached_items = ? WHERE id = ?",
            (json.dumps(resolved_items), skill_id),
        )

    async def execute_stream():
        yield {
            "event": "start",
            "data": json.dumps({
                "skill_id": skill_id,
                "name": sk["name"],
                "scheduled": bool(sk.get("scheduled")),
                "tools": tool_config,
            }),
        }

        if needs_approval:
            yield {
                "event": "skill_approval",
                "data": json.dumps({
                    "skill_id": skill_id,
                    "execution_id": execution_id,
                    "name": sk["name"],
                    "description": sk.get("description", ""),
                    "trigger_description": sk.get("trigger_description", ""),
                    "batch_selection_hint": sk.get("batch_selection_hint", ""),
                    "items": resolved_items,
                    "item_count": len(resolved_items),
                }),
            }
            yield {
                "event": "awaiting_approval",
                "data": json.dumps({
                    "skill_id": skill_id,
                    "execution_id": execution_id,
                }),
            }
            return

        # No approval needed — run directly
        from backend.agent.skill_executor import execute_skill

        try:
            async for event in execute_skill(sk, resolved_items):
                yield event
        except Exception as e:
            logger.warning("Agent execution failed for ad-hoc, falling back: %s", e)
            yield {
                "event": "warning",
                "data": json.dumps({"message": f"Agent unavailable ({type(e).__name__}), using scripted execution"}),
            }
            async for event in _scripted_execution(sk, resolved_items):
                yield event

        now = datetime.now().isoformat()
        execute_db(
            "UPDATE skills SET usage_count = usage_count + 1, tested_at = ?, last_run_at = ? WHERE id = ?",
            (now, now, skill_id),
        )

    return EventSourceResponse(execute_stream())


# ---------------------------------------------------------------------------
# Approval Gate
# ---------------------------------------------------------------------------


class ApprovalAction(BaseModel):
    action: str  # "approve" | "reject"
    excluded_items: list[str] | None = None


@router.post("/api/skills/{skill_id}/approve/{execution_id}")
async def approve_execution(skill_id: str, execution_id: str, body: ApprovalAction):
    """Approve or reject a pending batch execution.

    On approve: filters out excluded items, executes the skill, streams
    results as SSE events.
    On reject: marks the execution as rejected, returns immediately.
    """
    from backend.services.execution_history import complete_execution

    skills = query_db("SELECT * FROM skills WHERE id = ?", (skill_id,))
    if not skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    sk = skills[0]

    executions = query_db(
        "SELECT * FROM skill_executions WHERE id = ? AND skill_id = ?",
        (execution_id, skill_id),
    )
    if not executions:
        raise HTTPException(status_code=404, detail="Execution not found")
    if executions[0]["status"] != "awaiting_approval":
        raise HTTPException(status_code=400, detail="Execution is not awaiting approval")

    if body.action == "reject":
        complete_execution(execution_id, status="rejected")
        return {"status": "rejected", "execution_id": execution_id}

    # Load cached items
    cached = sk.get("cached_items")
    if cached:
        try:
            items = json.loads(cached) if isinstance(cached, str) else cached
        except (json.JSONDecodeError, TypeError):
            items = []
    else:
        items = []

    # Filter out excluded items
    if body.excluded_items:
        excluded_set = set(body.excluded_items)
        items = [it for it in items if it.get("id") not in excluded_set]

    # Update execution to running
    execute_db(
        "UPDATE skill_executions SET status = 'running', items_total = ? WHERE id = ?",
        (len(items), execution_id),
    )

    async def approval_stream():
        from backend.agent.skill_executor import execute_skill

        try:
            async for event in execute_skill(sk, items):
                yield event
        except Exception as e:
            logger.warning("Agent execution failed post-approval, falling back: %s", e)
            yield {
                "event": "warning",
                "data": json.dumps({"message": f"Agent unavailable ({type(e).__name__}), using scripted execution"}),
            }
            async for event in _scripted_execution(sk, items):
                yield event

        now = datetime.now().isoformat()
        execute_db(
            "UPDATE skills SET usage_count = usage_count + 1, last_run_at = ?, cached_items = NULL WHERE id = ?",
            (now, skill_id),
        )

    return EventSourceResponse(approval_stream())


# ---------------------------------------------------------------------------
# Execution History
# ---------------------------------------------------------------------------

@router.get("/api/skills/{skill_id}/history")
async def skill_history(skill_id: str, limit: int = 20, offset: int = 0):
    from backend.services.execution_history import get_executions

    rows = query_db("SELECT id FROM skills WHERE id = ?", (skill_id,))
    if not rows:
        raise HTTPException(status_code=404, detail="Skill not found")
    executions = get_executions(skill_id, limit=min(limit, 100), offset=max(offset, 0))
    return {"executions": executions, "skill_id": skill_id}


@router.get("/api/skills/{skill_id}/history/{execution_id}")
async def skill_history_detail(skill_id: str, execution_id: str):
    from backend.services.execution_history import get_execution_detail

    detail = get_execution_detail(execution_id)
    if not detail or detail.get("skill_id") != skill_id:
        raise HTTPException(status_code=404, detail="Execution not found")
    return detail
