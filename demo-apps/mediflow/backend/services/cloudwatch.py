"""Optional CloudWatch Embedded Metrics Format (EMF) emission.

When enabled via CLOUDWATCH_METRICS_ENABLED=true, writes structured JSON logs
that the CloudWatch agent automatically converts to metrics. Zero API calls,
zero additional dependencies — works by formatting to stdout.
"""

import json
import logging
import time

from backend.config import settings

_emf_logger = logging.getLogger("mediflow.metrics.emf")


def emit_execution_metric(
    skill_id: str,
    skill_name: str,
    trigger: str,
    duration_ms: int,
    tokens_input: int,
    tokens_output: int,
    cost_usd: float,
    success: bool,
) -> None:
    """Emit a single execution metric in CloudWatch EMF format."""
    if not settings.cloudwatch_metrics_enabled:
        return

    _emf_logger.info(
        json.dumps(
            {
                "_aws": {
                    "Timestamp": int(time.time() * 1000),
                    "CloudWatchMetrics": [
                        {
                            "Namespace": "MediFlow/SkillExecution",
                            "Dimensions": [["SkillId", "Trigger"]],
                            "Metrics": [
                                {"Name": "Duration", "Unit": "Milliseconds"},
                                {"Name": "TokensInput", "Unit": "Count"},
                                {"Name": "TokensOutput", "Unit": "Count"},
                                {"Name": "EstimatedCostUSD", "Unit": "None"},
                                {"Name": "Success", "Unit": "Count"},
                            ],
                        }
                    ],
                },
                "SkillId": skill_id,
                "SkillName": skill_name,
                "Trigger": trigger,
                "Duration": duration_ms,
                "TokensInput": tokens_input,
                "TokensOutput": tokens_output,
                "EstimatedCostUSD": cost_usd,
                "Success": 1 if success else 0,
            }
        )
    )
