"""Execute skills by invoking a scoped Strands Agent.

This module replaces the scripted skill execution with real agent invocations.
The agent receives the skill's prompt template and only the tools listed in its
tool_config, then processes batch items by calling real tools. Results are
streamed back as SSE events matching the existing frontend contract.
"""

import json
import logging
import time
from collections.abc import AsyncGenerator
from datetime import datetime

from strands import Agent
from strands.models.bedrock import BedrockModel

from backend.agent.agent import TOOL_REGISTRY
from backend.config import settings
from backend.services.execution_history import (
    complete_execution,
    create_execution,
    record_item,
)
from backend.services.pricing import estimate_cost

logger = logging.getLogger(__name__)


SKILL_SYSTEM_PROMPT = """You are an autonomous medical receptionist AI executing a scheduled skill.
You have access to specific tools and must use them to complete the task.

## Skill: {skill_name}

{agent_prompt_template}

## Items to Process

{items_section}

## Execution Rules

- Process each item using the tools available to you.
- Work through items one at a time, in order.
- For each item, call the necessary tools then move to the next.
- Do NOT ask questions or request clarification — execute autonomously.
- If a tool call fails for one item, skip it and continue to the next.
- Be concise in your reasoning — focus on tool calls, not explanation.
"""

SINGLE_ITEM_PROMPT = """You are an autonomous medical receptionist AI executing a skill.
You have access to specific tools and must use them to complete the task.

## Skill: {skill_name}

{agent_prompt_template}

## Execution Rules

- Use the available tools to complete this task.
- Do NOT ask questions or request clarification — execute autonomously.
- Be concise in your reasoning — focus on tool calls, not explanation.
"""


def _resolve_tools(skill: dict) -> list:
    """Resolve tool_config names to actual tool functions via TOOL_REGISTRY."""
    raw = skill.get("tool_config") or "[]"
    try:
        names = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        return []

    tools = []
    for name in names:
        if isinstance(name, dict):
            name = name.get("name", "")
        fn = TOOL_REGISTRY.get(name)
        if fn:
            tools.append(fn)
        else:
            logger.warning("Skill %s references unknown tool: %s", skill.get("id"), name)
    return tools


def _format_items(items: list[dict]) -> str:
    """Format batch items as a numbered list for the agent prompt."""
    if not items:
        return "No specific items — use tools to discover what needs processing."
    lines = []
    for i, item in enumerate(items, 1):
        label = item.get("label") or item.get("id") or f"Item {i}"
        detail = item.get("detail") or ""
        lines.append(f"{i}. **{label}**" + (f" — {detail}" if detail else ""))
    return "\n".join(lines)


def _create_skill_agent(skill: dict) -> Agent:
    """Create a Strands Agent scoped to a skill's tool configuration."""
    tools = _resolve_tools(skill)
    if not tools:
        raise ValueError(f"Skill {skill.get('id')} has no resolvable tools in tool_config")

    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_default_region,
    )
    return Agent(model=model, tools=tools)


async def execute_skill(skill: dict, items: list[dict], trigger: str = "manual") -> AsyncGenerator[dict, None]:
    """Execute a skill via a real agent invocation, yielding SSE events.

    Yields dicts with "event" and "data" keys matching the skill execution
    SSE contract expected by the frontend ExecutionOverlay.
    """
    skill_id = skill.get("id", "unknown")
    skill_name = skill.get("name", "Unnamed Skill")
    tool_config_names = json.loads(skill.get("tool_config") or "[]") if isinstance(skill.get("tool_config"), str) else (skill.get("tool_config") or [])
    is_batch = bool(items)
    total_items = len(items) if items else 0

    # Create execution history record
    execution_id = create_execution(skill_id, trigger=trigger, items_total=total_items)

    # Emit start
    yield {
        "event": "start",
        "data": json.dumps({
            "skill_id": skill_id,
            "name": skill_name,
            "scheduled": bool(skill.get("scheduled")),
            "tools": tool_config_names,
            "item_count": total_items or len(tool_config_names),
        }),
    }

    # Build the agent
    try:
        agent = _create_skill_agent(skill)
    except ValueError as e:
        yield {"event": "error", "data": json.dumps({"error": str(e)})}
        return

    # Build the prompt
    prompt_template = skill.get("agent_prompt_template") or skill.get("description") or ""
    if is_batch:
        system_prompt = SKILL_SYSTEM_PROMPT.format(
            skill_name=skill_name,
            agent_prompt_template=prompt_template,
            items_section=_format_items(items),
        )
    else:
        system_prompt = SINGLE_ITEM_PROMPT.format(
            skill_name=skill_name,
            agent_prompt_template=prompt_template,
        )

    agent.system_prompt = system_prompt
    user_message = f"Execute the {skill_name} skill now. Today is {datetime.now().strftime('%A, %B %d, %Y')}."

    # Track execution state
    executed_count = 0
    tools_called = 0
    seen_tool_ids = set()
    current_item_idx = 0
    start_time = time.monotonic()
    last_tool_name = None
    is_briefing = "briefing" in skill_name.lower()
    briefing_sections_emitted = set()
    accumulated_text = ""

    try:
        async for event in agent.stream_async(user_message):
            if not isinstance(event, dict):
                continue

            # Capture text output from the agent (its reasoning/summary)
            if "data" in event and isinstance(event["data"], str):
                accumulated_text += event["data"]

            # Tool invocation — emit 'action' event
            if event.get("type") == "tool_use_stream" and "current_tool_use" in event:
                tu = event["current_tool_use"]
                tool_id = tu.get("toolUseId", "")
                if tool_id and tool_id not in seen_tool_ids:
                    seen_tool_ids.add(tool_id)
                    tool_name = tu.get("name", "unknown")
                    tools_called += 1

                    # For briefing-style skills, emit section dividers on tool transitions
                    if is_briefing and tool_name != last_tool_name:
                        section_label = _briefing_section_for_tool(tool_name)
                        if section_label and section_label not in briefing_sections_emitted:
                            briefing_sections_emitted.add(section_label)
                            yield {
                                "event": "section",
                                "data": json.dumps({"label": section_label}),
                            }
                    last_tool_name = tool_name

                    yield {
                        "event": "action",
                        "data": json.dumps({
                            "step": tools_called,
                            "tool": tool_name,
                        }),
                    }

                    # Heuristic: detect item boundaries for batch skills
                    if is_batch and _is_terminal_tool(tool_name, skill):
                        if current_item_idx < total_items:
                            item = items[current_item_idx]
                            executed_count += 1
                            current_item_idx += 1
                            record_item(
                                execution_id,
                                item_index=executed_count - 1,
                                entity_id=item.get("id"),
                                entity_name=item.get("label") or item.get("id"),
                                status="success",
                                tools_called=list(seen_tool_ids),
                            )
                            yield {
                                "event": "progress",
                                "data": json.dumps({
                                    "item_id": item.get("id", ""),
                                    "entity_name": item.get("label") or item.get("id") or f"Item {executed_count}",
                                    "entity_flag": item.get("detail"),
                                    "executed": executed_count,
                                    "total": total_items,
                                }),
                            }

    except Exception as e:
        logger.exception("Skill execution error for %s", skill_id)
        duration_ms = int((time.monotonic() - start_time) * 1000)
        complete_execution(
            execution_id,
            status="failed",
            items_succeeded=executed_count,
            items_failed=total_items - executed_count,
            duration_ms=duration_ms,
            error=str(e),
        )
        yield {"event": "error", "data": json.dumps({"error": str(e)})}
        return

    # If batch and we haven't emitted progress for all items (agent may have
    # processed them in a different pattern), emit remaining as completed
    if is_batch and executed_count < total_items:
        for i in range(executed_count, total_items):
            executed_count += 1
            item = items[i]
            record_item(
                execution_id,
                item_index=executed_count - 1,
                entity_id=item.get("id"),
                entity_name=item.get("label") or item.get("id"),
                status="success",
            )
            yield {
                "event": "progress",
                "data": json.dumps({
                    "item_id": item.get("id", ""),
                    "entity_name": item.get("label") or item.get("id") or f"Item {executed_count}",
                    "entity_flag": item.get("detail"),
                    "executed": executed_count,
                    "total": total_items,
                }),
            }

    # For briefing skills, emit a closing section
    if is_briefing:
        yield {"event": "section", "data": json.dumps({"label": "Briefing ready"})}

    # Emit the agent's text output as a summary
    if accumulated_text.strip():
        yield {
            "event": "summary",
            "data": json.dumps({"content": accumulated_text.strip()}),
        }

    duration_ms = int((time.monotonic() - start_time) * 1000)

    # Extract token/latency metrics from Strands telemetry
    _usage = agent.event_loop_metrics.accumulated_usage
    tokens_input = _usage.get("inputTokens", 0)
    tokens_output = _usage.get("outputTokens", 0)
    llm_latency_ms = agent.event_loop_metrics.accumulated_metrics.get("latencyMs", 0)
    estimated_cost_usd = estimate_cost(tokens_input, tokens_output)

    # Finalize execution history
    final_status = "completed" if executed_count == total_items or not is_batch else "partial"
    complete_execution(
        execution_id,
        status=final_status,
        items_succeeded=executed_count,
        items_failed=total_items - executed_count if is_batch else 0,
        duration_ms=duration_ms,
        summary=accumulated_text.strip() if accumulated_text.strip() else None,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        estimated_cost_usd=estimated_cost_usd,
        llm_latency_ms=llm_latency_ms,
    )

    # Emit optional CloudWatch metrics
    from backend.services.cloudwatch import emit_execution_metric
    emit_execution_metric(
        skill_id=skill_id,
        skill_name=skill_name,
        trigger=trigger,
        duration_ms=duration_ms,
        tokens_input=tokens_input,
        tokens_output=tokens_output,
        cost_usd=estimated_cost_usd,
        success=final_status != "failed",
    )

    yield {
        "event": "complete",
        "data": json.dumps({
            "skill_id": skill_id,
            "executed": executed_count if is_batch else tools_called,
            "total": total_items if is_batch else tools_called,
            "last_run_at": datetime.now().isoformat(),
            "duration_ms": duration_ms,
            "tokens_input": tokens_input,
            "tokens_output": tokens_output,
            "estimated_cost_usd": round(estimated_cost_usd, 6),
            "llm_latency_ms": llm_latency_ms,
        }),
    }


# Terminal tools indicate one batch item is "done"
_TERMINAL_TOOLS = {
    "send_payment_reminder",
    "send_message",
    "send_appointment_reminder",
    "book_appointment",
    "record_payment",
    "record_patient_memory",
}


def _is_terminal_tool(tool_name: str, skill: dict) -> bool:
    """Determine if a tool call signals completion of one batch item."""
    if tool_name in _TERMINAL_TOOLS:
        return True
    return False


# Maps tool names to briefing section labels
_BRIEFING_TOOL_SECTIONS = {
    "get_doctor_schedule": "Today's schedule",
    "check_pathology_results": "Overnight pathology",
    "get_patient_memories": "Patients to flag",
    "get_patient": "Patient review",
}


def _briefing_section_for_tool(tool_name: str) -> str | None:
    """Return the section label for a tool in a briefing-style skill."""
    return _BRIEFING_TOOL_SECTIONS.get(tool_name)
