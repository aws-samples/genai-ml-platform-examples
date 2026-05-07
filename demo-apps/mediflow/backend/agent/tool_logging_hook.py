"""Strands hook that logs every tool invocation to tool_call_log."""

import json
import logging
import time
from copy import deepcopy
from typing import Any

from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent
from strands.hooks.registry import HookRegistry

from backend.services.audit_service import log_tool_call

logger = logging.getLogger(__name__)

_PII_FIELDS = frozenset({
    "phone", "mobile", "email", "date_of_birth", "dob",
    "address", "medicare_number", "medicare", "credit_card",
})

_MAX_SUMMARY_LEN = 500


def _redact_pii(params: Any) -> dict:
    """Return a copy of params with known PII fields replaced."""
    if not isinstance(params, dict):
        return params
    redacted = {}
    for key, value in params.items():
        if key.lower() in _PII_FIELDS:
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = _redact_pii(value)
        else:
            redacted[key] = value
    return redacted


def _summarize_result(result: dict) -> str:
    """Extract a short summary from a ToolResult dict."""
    content = result.get("content", [])
    if not content:
        return ""

    parts = []
    for block in content:
        if isinstance(block, dict):
            if "text" in block:
                parts.append(block["text"])
            elif "json" in block:
                j = block["json"]
                if isinstance(j, (dict, list)):
                    parts.append(json.dumps(j, default=str))
                else:
                    parts.append(str(j))
    summary = " ".join(parts)
    if len(summary) > _MAX_SUMMARY_LEN:
        summary = summary[:_MAX_SUMMARY_LEN] + "…"
    return summary


class ToolCallLoggingHook:
    """Strands HookProvider that logs every tool call to tool_call_log."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self._start_times: dict[str, float] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeToolCallEvent, self._on_before)
        registry.add_callback(AfterToolCallEvent, self._on_after)

    def _on_before(self, event: BeforeToolCallEvent) -> None:
        self._start_times[event.tool_use["toolUseId"]] = time.monotonic()

    def _on_after(self, event: AfterToolCallEvent) -> None:
        tool_use_id = event.tool_use["toolUseId"]
        start = self._start_times.pop(tool_use_id, None)
        duration_ms = int((time.monotonic() - start) * 1000) if start else 0

        tool_name = event.tool_use["name"]
        raw_params = event.tool_use.get("input", {})
        tool_params = _redact_pii(raw_params) if isinstance(raw_params, dict) else raw_params

        success = event.exception is None and event.result.get("status") == "success"
        error_msg = str(event.exception) if event.exception else None
        result_summary = _summarize_result(event.result) if success else (error_msg or "")

        try:
            log_tool_call(
                session_id=self.session_id,
                tool_name=tool_name,
                tool_params=tool_params,
                result_summary=result_summary,
                duration_ms=duration_ms,
                success=success,
                error_message=error_msg,
            )
        except Exception:
            logger.debug("Failed to log tool call %s", tool_name, exc_info=True)
