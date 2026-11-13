"""Synthetic monitoring history so Lab 5E trend charts render immediately.

Dev/test only. The governance dashboard groups trend visuals by DAY, but a
workshop participant's Lab 5D runs all land on the same day, so every line
chart collapses to one point. This module inserts one backdated
``monitoring_responses`` row per prior day, anchored on the latest *real*
Lab 5D run for the endpoint:

* lineage (model package, snapshots, model_version) and baseline ROC-AUC are
  copied from that run, so the history is attributed to the serving model;
* per-feature drift reuses the run's feature set and method, with each
  feature's threshold-normalized magnitude ramped from mild up to the real
  value, so ``feature_drift_detail`` and the Feature Drift sheet trend too;
* every verdict is recomputed with the live rules — feature drift is
  ``magnitude > 1.0``, dataset drift is ``share >= DATA_DRIFT_THRESHOLD`` and
  model drift uses :func:`evaluate_model_drift` — so synthetic rows never
  contradict the thresholds the dashboard explains.

Rows carry ``monitoring_run_id = 'backfill-drift-day<N>-<YYYYMMDD>'`` and
``detection_engine = 'evidently-backfill'``. They have no inference rows, so
inference counts for them are 0 in the joined dataset. In a scheduled
deployment each daily run appends its own row and none of this is needed.
"""

from __future__ import annotations

import json
import math
from datetime import timedelta
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_MONITORING_RESPONSES_TABLE,
    DATA_DRIFT_THRESHOLD,
    ENDPOINT_NAME,
    resolve_endpoint_name,
)
from src.drift_monitoring.evidently_reports import (
    HIGHER_IS_MORE_DRIFT,
    LOWER_IS_MORE_DRIFT,
)
from src.drift_monitoring.monitoring_session import (
    _naive_utc,
    _sql_string,
    _sql_value,
    evaluate_model_drift,
)

BACKFILL_PREFIX = "backfill-drift"
BACKFILL_ENGINE = "evidently-backfill"
DEFAULT_BACKFILL_DAYS = 7

COLUMNS = [
    "monitoring_run_id", "monitoring_timestamp", "endpoint_name",
    "model_version", "model_package_arn", "evaluation_snapshot_id",
    "training_snapshot_id", "data_drift_detected",
    "drifted_columns_count", "drifted_columns_share", "features_analyzed",
    "data_sample_size", "model_drift_detected", "baseline_roc_auc",
    "current_roc_auc", "roc_auc_degradation", "roc_auc_degradation_pct",
    "accuracy", "precision", "recall", "f1_score", "model_sample_size",
    "per_feature_drift_scores", "evidently_report_s3_path", "mlflow_run_id",
    "alert_sent", "detection_engine", "created_at",
]


def _clean(value: Any) -> Any:
    """Map pandas/NumPy missing values to None and scalars to Python types."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        return value.item()
    return value


def _float(value: Any) -> Optional[float]:
    value = _clean(value)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def drift_factors(days: int) -> List[float]:
    """Ramp factors for the ``days - 1`` backfilled days, oldest first.

    The real run is factor 1.0 and is not backfilled. The convex ramp keeps
    early days near healthy and steepens toward the real run, which reads as
    a drift building up rather than a straight line.
    """
    if days < 2:
        raise ValueError("days must be at least 2 (the real run plus history)")
    steps = days - 1
    return [round(0.15 + 0.80 * (i / max(steps - 1, 1)) ** 1.5, 4) for i in range(steps)]


def scale_per_feature(
    per_feature: Dict[str, Dict[str, Any]], factor: float
) -> Dict[str, Dict[str, Any]]:
    """Scale each comparable feature's magnitude and recompute score/verdict."""
    scaled: Dict[str, Dict[str, Any]] = {}
    for column, info in per_feature.items():
        entry = dict(info)
        magnitude = _float(info.get("magnitude"))
        threshold = _float(info.get("threshold"))
        direction = info.get("direction")
        if (
            info.get("comparable")
            and magnitude is not None
            and threshold is not None
            and direction in (HIGHER_IS_MORE_DRIFT, LOWER_IS_MORE_DRIFT)
        ):
            new_magnitude = magnitude * factor
            entry["magnitude"] = round(new_magnitude, 6)
            if direction == HIGHER_IS_MORE_DRIFT:
                entry["score"] = round(new_magnitude * threshold, 6)
            elif new_magnitude > 0:
                entry["score"] = round(threshold / new_magnitude, 6)
            # Same strict boundary as normalize_drift_score: equality is not drift.
            entry["drifted"] = new_magnitude > 1.0
        scaled[column] = entry
    return scaled


def _dataset_verdict(per_feature: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    compared = [
        v for v in per_feature.values()
        if v.get("comparable") and v.get("drifted") is not None
    ]
    if not compared:
        return {"count": None, "share": None, "detected": None}
    count = sum(1 for v in compared if v["drifted"] is True)
    share = count / len(compared)
    return {"count": count, "share": share, "detected": share >= DATA_DRIFT_THRESHOLD}


def build_backfill_rows(template: Dict[str, Any], days: int) -> List[Dict[str, Any]]:
    """Build backdated rows from the latest real monitoring run (pure function)."""
    anchor_ts = _naive_utc(template["monitoring_timestamp"])
    raw_per_feature = _clean(template.get("per_feature_drift_scores"))
    per_feature = json.loads(raw_per_feature) if raw_per_feature else {}

    baseline_auc = _float(template.get("baseline_roc_auc"))
    real_auc = _float(template.get("current_roc_auc"))
    real_loss = (
        (baseline_auc - real_auc) / baseline_auc
        if baseline_auc and real_auc is not None else None
    )

    rows: List[Dict[str, Any]] = []
    factors = drift_factors(days)
    for index, factor in enumerate(factors):
        day_offset = len(factors) - index  # oldest first: N-1 ... 1
        run_ts = anchor_ts - timedelta(days=day_offset)
        day_features = scale_per_feature(per_feature, factor) if per_feature else {}
        data = _dataset_verdict(day_features)

        current_auc = None
        ratio = 1.0
        if real_loss is not None:
            current_auc = baseline_auc * (1 - real_loss * factor)
            ratio = current_auc / real_auc if real_auc else 1.0
        model = evaluate_model_drift(baseline_auc, current_auc)

        def _metric(name: str) -> Optional[float]:
            value = _float(template.get(name))
            return None if value is None else round(min(max(value * ratio, 0.0), 1.0), 6)

        precision, recall = _metric("precision"), _metric("recall")
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall > 0
            else _metric("f1_score")
        )
        verdicts = [v for v in (data["detected"], model["model_drift_detected"]) if v is not None]

        rows.append({
            "monitoring_run_id": f"{BACKFILL_PREFIX}-day{day_offset}-{run_ts:%Y%m%d}",
            "monitoring_timestamp": run_ts,
            "endpoint_name": _clean(template.get("endpoint_name")),
            "model_version": _clean(template.get("model_version")),
            "model_package_arn": _clean(template.get("model_package_arn")),
            "evaluation_snapshot_id": _clean(template.get("evaluation_snapshot_id")),
            "training_snapshot_id": _clean(template.get("training_snapshot_id")),
            "data_drift_detected": data["detected"],
            "drifted_columns_count": data["count"],
            "drifted_columns_share": data["share"],
            "features_analyzed": _clean(template.get("features_analyzed")),
            "data_sample_size": _clean(template.get("data_sample_size")),
            "model_drift_detected": model["model_drift_detected"],
            "baseline_roc_auc": baseline_auc,
            "current_roc_auc": current_auc,
            "roc_auc_degradation": model["roc_auc_degradation"],
            "roc_auc_degradation_pct": model["roc_auc_degradation_pct"],
            "accuracy": _metric("accuracy"),
            "precision": precision,
            "recall": recall,
            "f1_score": f1,
            "model_sample_size": _clean(template.get("model_sample_size")),
            "per_feature_drift_scores": (
                json.dumps(day_features, allow_nan=False) if day_features else None
            ),
            "evidently_report_s3_path": None,
            "mlflow_run_id": None,
            "alert_sent": any(verdicts) if verdicts else None,
            "detection_engine": BACKFILL_ENGINE,
            "created_at": run_ts,
        })
    return rows


def _table() -> str:
    return f"{ATHENA_DATABASE}.{ATHENA_MONITORING_RESPONSES_TABLE}"


def history_summary(athena_client: Any, endpoint_name: str) -> pd.DataFrame:
    """Return every monitoring row for the endpoint, oldest first."""
    return athena_client.execute_query(f"""
        SELECT DATE(monitoring_timestamp)        AS run_date,
               monitoring_run_id,
               ROUND(current_roc_auc, 3)         AS roc_auc,
               ROUND(roc_auc_degradation_pct, 1) AS auc_loss_pct,
               ROUND(drifted_columns_share, 2)   AS drift_share,
               data_drift_detected               AS data_drift,
               model_drift_detected              AS model_drift,
               detection_engine
        FROM {_table()}
        WHERE endpoint_name = {_sql_string(endpoint_name)}
        ORDER BY monitoring_timestamp
    """)


def backfill_monitoring_history(
    days: int = DEFAULT_BACKFILL_DAYS,
    force: bool = False,
    endpoint_name: Optional[str] = None,
    athena_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """Insert ``days - 1`` backdated runs before the latest real Lab 5D run.

    Idempotent: existing backfill rows for the endpoint are kept unless
    ``force`` is True, in which case they are deleted and rebuilt from the
    current latest real run (useful after more Lab 5D runs).
    """
    if athena_client is None:
        from src.train_pipeline.athena.athena_client import AthenaClient

        athena_client = AthenaClient()
    endpoint = endpoint_name or ENDPOINT_NAME or resolve_endpoint_name()
    if not endpoint:
        raise RuntimeError("No endpoint resolved. Configure endpoint.name or run Lab 4/5D.")
    endpoint_sql = _sql_string(endpoint)
    prefix_sql = _sql_string(f"{BACKFILL_PREFIX}-%")

    existing = athena_client.execute_query(
        f"SELECT COUNT(*) AS n FROM {_table()} "
        f"WHERE endpoint_name = {endpoint_sql} AND monitoring_run_id LIKE {prefix_sql}"
    )
    existing_count = int(existing["n"].iloc[0]) if not existing.empty else 0
    result: Dict[str, Any] = {
        "endpoint_name": endpoint, "existing": existing_count,
        "deleted": 0, "inserted": 0, "skipped": False, "anchor_run_id": None,
    }
    if existing_count and not force:
        result["skipped"] = True
        result["summary"] = history_summary(athena_client, endpoint)
        return result

    latest = athena_client.execute_query(f"""
        SELECT * FROM {_table()}
        WHERE endpoint_name = {endpoint_sql}
          AND monitoring_run_id NOT LIKE {prefix_sql}
        ORDER BY monitoring_timestamp DESC
        LIMIT 1
    """)
    if latest is None or latest.empty:
        raise RuntimeError(
            f"No Lab 5D monitoring run found for {endpoint}. Run Lab 5D first; the "
            "backfill is anchored on a real run's lineage and drift profile."
        )
    template = latest.iloc[0].to_dict()
    result["anchor_run_id"] = template["monitoring_run_id"]

    if existing_count:
        athena_client.execute_query(
            f"DELETE FROM {_table()} WHERE endpoint_name = {endpoint_sql} "
            f"AND monitoring_run_id LIKE {prefix_sql}",
            return_results=False,
        )
        result["deleted"] = existing_count

    rows = build_backfill_rows(template, days)
    values = ",\n".join(
        "(" + ", ".join(_sql_value(row[c]) for c in COLUMNS) + ")" for row in rows
    )
    athena_client.execute_query(
        f"INSERT INTO {_table()} ({', '.join(COLUMNS)}) VALUES\n{values}",
        return_results=False,
    )
    result["inserted"] = len(rows)
    result["summary"] = history_summary(athena_client, endpoint)
    return result
