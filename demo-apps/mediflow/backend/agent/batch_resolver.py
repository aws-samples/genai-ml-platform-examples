"""Agent-driven batch item resolution.

Interprets a skill's `batch_selection_hint` using a lightweight agent call
to dynamically resolve target items, rather than relying on hardcoded SQL.
"""

import asyncio
import json
import logging
import re
from datetime import datetime

from strands import Agent
from strands.models.bedrock import BedrockModel

from backend.agent.agent import TOOL_REGISTRY
from backend.config import settings

logger = logging.getLogger(__name__)

RESOLUTION_PROMPT = """You are resolving a batch of items for an automated medical receptionist skill.

## Task
Interpret the batch description below and use the available query tools to find matching items.

## Batch description
{batch_selection_hint}

## Today's date
{today}

## Output format
After querying, return ONLY a JSON array of items. Each item must have:
- "id": the entity's primary key (string)
- "label": a short display name (e.g. patient name, doctor name)
- "detail": one-line context (e.g. "$120 outstanding", "Mon 9:30am", "GP")

Return at most {max_items} items. Return the JSON array and nothing else — no explanation, no markdown fences.
"""

_RESOLUTION_TOOLS = [
    "get_outstanding_invoices",
    "list_upcoming_appointments",
    "search_patients",
    "get_doctor_info",
    "get_doctor_schedule",
    "check_pathology_results",
]


def _build_resolver_agent() -> Agent:
    tools = [TOOL_REGISTRY[name] for name in _RESOLUTION_TOOLS if name in TOOL_REGISTRY]
    if not tools:
        raise ValueError("No resolution tools available")
    model = BedrockModel(
        model_id=settings.bedrock_model_id,
        region_name=settings.aws_default_region,
    )
    return Agent(model=model, tools=tools)


def _parse_items(text: str, max_items: int) -> list[dict]:
    """Extract JSON array from agent response text."""
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if not match:
        return []
    try:
        items = json.loads(match.group())
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(items, list):
        return []
    result = []
    for item in items[:max_items]:
        if isinstance(item, dict) and "id" in item:
            result.append({
                "id": str(item["id"]),
                "label": str(item.get("label") or item["id"]),
                "detail": str(item.get("detail") or ""),
            })
    return result


async def resolve_batch(skill: dict, max_items: int = 20, timeout: float = 30.0) -> list[dict]:
    """Resolve batch items using an agent that interprets batch_selection_hint.

    Returns a list of {"id", "label", "detail"} dicts, or empty list on failure.
    """
    hint = skill.get("batch_selection_hint") or ""
    if not hint.strip():
        return []

    try:
        agent = _build_resolver_agent()
    except ValueError as e:
        logger.warning("Cannot build resolver agent: %s", e)
        return []

    prompt = RESOLUTION_PROMPT.format(
        batch_selection_hint=hint,
        today=datetime.now().strftime("%A, %B %d, %Y"),
        max_items=max_items,
    )
    agent.system_prompt = prompt
    user_message = f"Find items matching: {hint}"

    try:
        async def _run():
            accumulated = ""
            async for event in agent.stream_async(user_message):
                if isinstance(event, dict) and "data" in event and isinstance(event["data"], str):
                    accumulated += event["data"]
            return accumulated

        text = await asyncio.wait_for(_run(), timeout=timeout)
        items = _parse_items(text, max_items)
        if items:
            logger.info("Batch resolver found %d items for skill %s", len(items), skill.get("id"))
        return items

    except asyncio.TimeoutError:
        logger.warning("Batch resolution timed out for skill %s", skill.get("id"))
        return []
    except Exception as e:
        logger.warning("Batch resolution failed for skill %s: %s", skill.get("id"), e)
        return []
