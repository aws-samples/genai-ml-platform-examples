"""Evidently reports with one explicit drift-score contract.

New Lab 5 runs use Jensen-Shannon distance for every comparable feature.
``drift_magnitude`` is the raw score divided by its threshold, so 1.0 is the
boundary and larger values always mean more drift. The parser also understands
p-value methods for callers that explicitly choose one, but it never invents a
score for an unavailable feature.
"""

import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
from evidently import Report
from evidently.core.datasets import BinaryClassification, DataDefinition, Dataset
from evidently.presets import ClassificationPreset, DataDriftPreset

from src.config.config import DATA_DRIFT_THRESHOLD

logger = logging.getLogger(__name__)

DRIFT_NUM_METHOD = "jensenshannon"
DRIFT_CAT_METHOD = "jensenshannon"
DRIFT_SCORE_THRESHOLD = 0.1
MIN_FEATURE_SAMPLES = 300  # Below this, JS distance on undrifted data often exceeds 0.1

LOWER_IS_MORE_DRIFT = "lower_is_more_drift"
HIGHER_IS_MORE_DRIFT = "higher_is_more_drift"
UNKNOWN_DRIFT_DIRECTION = "unknown"


def _drift_score_direction(method: str) -> str:
    """Return the comparison direction encoded by an Evidently method name."""
    normalized = str(method or "").lower().replace("_", " ").replace("-", " ")
    if "p value" in normalized or any(
        token in normalized
        for token in ("kolmogorov", "k s", "ks", "chisquare", "chi square", "z test")
    ):
        return LOWER_IS_MORE_DRIFT
    if any(
        token in normalized
        for token in (
            "distance",
            "wasserstein",
            "jensen",
            "jensenshannon",
            "psi",
            "hellinger",
            "kullback",
            "total variation",
            "tvd",
        )
    ):
        return HIGHER_IS_MORE_DRIFT
    return UNKNOWN_DRIFT_DIRECTION


def normalize_drift_score(
    drift_score: Any,
    threshold: Any,
    method: str,
) -> Dict[str, Any]:
    """Normalize an Evidently score to one finite, directional chart metric.

    The feature verdict is strict: equality is the decision boundary and does
    not count as feature drift. Missing, non-finite, negative, or unknown-method
    values retain an unavailable magnitude/verdict.
    """
    direction = _drift_score_direction(method)
    result: Dict[str, Any] = {
        "drift_score": None,
        "drifted": None,
        "method": str(method or ""),
        "threshold": None,
        "direction": direction,
        "drift_magnitude": None,
    }

    try:
        numeric_threshold = float(threshold)
    except (TypeError, ValueError):
        return result
    if not math.isfinite(numeric_threshold) or numeric_threshold <= 0:
        return result
    result["threshold"] = numeric_threshold

    if drift_score is None:
        return result
    try:
        numeric_score = float(drift_score)
    except (TypeError, ValueError):
        return result
    if not math.isfinite(numeric_score) or numeric_score < 0:
        return result
    result["drift_score"] = numeric_score

    if direction == LOWER_IS_MORE_DRIFT:
        result["drifted"] = numeric_score < numeric_threshold
        if numeric_score > 0:
            result["drift_magnitude"] = numeric_threshold / numeric_score
    elif direction == HIGHER_IS_MORE_DRIFT:
        result["drifted"] = numeric_score > numeric_threshold
        result["drift_magnitude"] = numeric_score / numeric_threshold

    return result


def _prepare_drift_inputs(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    min_samples: int,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Dict[str, Any]]]:
    """Return comparable inputs plus explicit unavailable feature records."""
    prepared_baseline: Dict[str, pd.Series] = {}
    prepared_current: Dict[str, pd.Series] = {}
    per_column: Dict[str, Dict[str, Any]] = {}

    for column in baseline_df.columns:
        base_series = baseline_df[column]
        current_series = current_df[column] if column in current_df.columns else None
        numeric = pd.api.types.is_numeric_dtype(base_series) or (
            current_series is not None and pd.api.types.is_numeric_dtype(current_series)
        )
        if numeric:
            base_series = pd.to_numeric(base_series, errors="coerce").replace(
                [float("inf"), float("-inf")], pd.NA
            )
            if current_series is not None:
                current_series = pd.to_numeric(current_series, errors="coerce").replace(
                    [float("inf"), float("-inf")], pd.NA
                )

        baseline_count = int(base_series.notna().sum())
        current_count = int(current_series.notna().sum()) if current_series is not None else 0
        unavailable_reason = None
        if current_series is None:
            unavailable_reason = "missing_from_current"
        elif baseline_count == 0:
            unavailable_reason = "all_null_baseline"
        elif current_count == 0:
            unavailable_reason = "all_null_current"
        elif baseline_count < min_samples:
            unavailable_reason = "insufficient_baseline_samples"
        elif current_count < min_samples:
            unavailable_reason = "insufficient_current_samples"

        per_column[column] = {
            **normalize_drift_score(None, DRIFT_SCORE_THRESHOLD, DRIFT_NUM_METHOD),
            "comparable": unavailable_reason is None,
            "unavailable_reason": unavailable_reason,
            "baseline_sample_size": baseline_count,
            "current_sample_size": current_count,
        }
        if unavailable_reason is None:
            prepared_baseline[column] = base_series
            prepared_current[column] = current_series

    return (
        pd.DataFrame(prepared_baseline, index=baseline_df.index),
        pd.DataFrame(prepared_current, index=current_df.index),
        per_column,
    )


def run_data_drift_report(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    output_path: Optional[str] = None,
    min_samples: int = MIN_FEATURE_SAMPLES,
) -> Dict[str, Any]:
    """Compare baseline and current feature distributions.

    Dataset count/share use only features with at least ``min_samples``
    non-null observations on both sides. Requested but unavailable features
    remain in ``per_column`` with null score, magnitude, and verdict so Athena
    and QuickSight do not turn missing evidence into a zero.
    """
    if min_samples < 1:
        raise ValueError("min_samples must be at least 1")

    comparable_baseline, comparable_current, per_column = _prepare_drift_inputs(
        baseline_df, current_df, min_samples
    )
    result: Dict[str, Any] = {
        "snapshot": None,
        "drift_detected": None,
        "drifted_columns_count": 0,
        "drifted_columns_share": None,
        "drift_share_threshold": DATA_DRIFT_THRESHOLD,
        "features_requested": len(per_column),
        "features_analyzed": 0,
        "sample_size": len(current_df),
        "per_column": per_column,
    }

    if comparable_baseline.empty or comparable_baseline.shape[1] == 0:
        logger.warning("No features have enough non-null samples for drift analysis")
        return result

    report = Report(
        metrics=[
            DataDriftPreset(
                num_method=DRIFT_NUM_METHOD,
                cat_method=DRIFT_CAT_METHOD,
                num_threshold=DRIFT_SCORE_THRESHOLD,
                cat_threshold=DRIFT_SCORE_THRESHOLD,
                drift_share=DATA_DRIFT_THRESHOLD,
            )
        ]
    )
    snapshot = report.run(
        reference_data=comparable_baseline,
        current_data=comparable_current,
    )
    result["snapshot"] = snapshot

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        snapshot.save_html(output_path)
        logger.info("Data drift report saved to %s", output_path)

    for metric in snapshot.dict().get("metrics", []):
        name = metric.get("metric_name", "")
        config = metric.get("config", {})
        if "DriftedColumnsCount" in name:
            try:
                result["drift_share_threshold"] = float(
                    config.get("drift_share", DATA_DRIFT_THRESHOLD)
                )
            except (TypeError, ValueError):
                result["drift_share_threshold"] = DATA_DRIFT_THRESHOLD
        elif "ValueDrift" in name:
            column = config.get("column", "unknown")
            if column not in result["per_column"]:
                continue
            normalized = normalize_drift_score(
                drift_score=metric.get("value"),
                threshold=config.get("threshold"),
                method=config.get("method", ""),
            )
            result["per_column"][column].update(normalized)
            if normalized["drifted"] is None:
                result["per_column"][column]["comparable"] = False
                result["per_column"][column]["unavailable_reason"] = "metric_unavailable"

    compared = [
        values
        for values in result["per_column"].values()
        if values.get("comparable") and values.get("drifted") is not None
    ]
    result["features_analyzed"] = len(compared)
    result["drifted_columns_count"] = sum(
        values["drifted"] is True for values in compared
    )
    if compared:
        share = result["drifted_columns_count"] / len(compared)
        result["drifted_columns_share"] = share
        result["drift_detected"] = share >= result["drift_share_threshold"]

    logger.info(
        "Data drift report: %s/%s comparable columns drifted (share=%s, overall=%s)",
        result["drifted_columns_count"],
        result["features_analyzed"],
        result["drifted_columns_share"],
        result["drift_detected"],
    )
    return result


def run_classification_report(
    baseline_df: pd.DataFrame,
    current_df: pd.DataFrame,
    target_column: str = "target",
    prediction_column: str = "prediction",
    probability_column: Optional[str] = "probability",
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Run an Evidently binary-classification comparison on paired rows.

    Labels, predictions, and optional positive-class probabilities are cleaned
    together in each input frame, preserving row pairing. Both target and
    predicted labels must contain classes 0 and 1 on each side; unavailable
    cases fail with a descriptive ``ValueError`` instead of producing a chart.
    """
    required = [target_column, prediction_column]
    if probability_column:
        required.append(probability_column)

    cleaned = []
    for label, frame in (("baseline_df", baseline_df), ("current_df", current_df)):
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"{label} is missing required column(s): {missing}")
        work = frame.dropna(subset=required).copy()
        if probability_column:
            work[probability_column] = pd.to_numeric(
                work[probability_column], errors="coerce"
            )
            work = work.dropna(subset=[probability_column])
            if not work[probability_column].between(0.0, 1.0).all():
                raise ValueError(
                    f"{label}.{probability_column} must contain probabilities in [0, 1]"
                )
        for column in (target_column, prediction_column):
            work[column] = work[column].astype(float).round().astype(int)
            values = set(work[column].unique().tolist())
            if not values.issubset({0, 1}):
                raise ValueError(f"{label}.{column} contains non-binary labels: {sorted(values)}")
            if values != {0, 1}:
                raise ValueError(
                    f"{label}.{column} has classes {sorted(values)}; both 0 and 1 "
                    "are required for classification metrics"
                )
        if work.empty:
            raise ValueError(f"{label} has no complete paired classification rows")
        cleaned.append(work)

    baseline_clean, current_clean = cleaned
    definition = DataDefinition(
        classification=[
            BinaryClassification(
                target=target_column,
                prediction_labels=prediction_column,
                prediction_probas=probability_column,
                pos_label=1,
            )
        ]
    )
    reference = Dataset.from_pandas(baseline_clean, data_definition=definition)
    current = Dataset.from_pandas(current_clean, data_definition=definition)
    snapshot = Report(metrics=[ClassificationPreset()]).run(
        reference_data=reference,
        current_data=current,
    )

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        snapshot.save_html(output_path)
        logger.info("Classification report saved to %s", output_path)

    logger.info(
        "Classification report generated from %s baseline and %s current paired rows",
        len(baseline_clean),
        len(current_clean),
    )
    return {
        "snapshot": snapshot,
        "metrics": snapshot.dict().get("metrics", []),
        "baseline_sample_size": len(baseline_clean),
        "current_sample_size": len(current_clean),
        "probability_column": probability_column,
    }
