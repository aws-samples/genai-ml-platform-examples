"""Cohesive, importable orchestration for the Lab 5D fresh-run workflow.

The notebook deliberately delegates mechanics to :class:`MonitoringSession`.
Each session starts a new capture window before endpoint traffic, waits for the
expected capture rows, tags those rows once, and uses that persisted tag for
ground truth, drift reports, model metrics, and dashboard persistence.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
import numpy as np
import pandas as pd

from src.config import schema
from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_EVALUATION_TABLE,
    ATHENA_GROUND_TRUTH_UPDATES_TABLE,
    ATHENA_INFERENCE_TABLE,
    ATHENA_MONITORING_RESPONSES_TABLE,
    ATHENA_TRAINING_TABLE,
    AWS_DEFAULT_REGION,
    CSV_DRIFTED_DATA,
    DATA_DRIFT_THRESHOLD,
    ENDPOINT_NAME,
    GROUND_TRUTH_SIM_ACCURACY,
    GROUND_TRUTH_SIM_FEATURE_DRIFT_IMPACT,
    GROUND_TRUTH_SIM_MODEL_DRIFT_MAG,
    MIN_ROC_AUC_THRESHOLD,
    MLFLOW_MODEL_NAME,
    MODEL_DRIFT_THRESHOLD,
    PREDICTION_COLUMN,
    PROBABILITY_COLUMN,
    resolve_endpoint_name,
)
from src.train_pipeline.athena.athena_client import AthenaClient

MIN_MONITORING_SAMPLES = 50


def _sql_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _naive_utc(value: Any) -> datetime:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
    return timestamp.to_pydatetime()


def _timestamp_literal(value: datetime) -> str:
    return f"TIMESTAMP '{value.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}'"


def _sql_value(value: Any) -> str:
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return "NULL"
    if isinstance(value, (bool, np.bool_)):
        return "TRUE" if value else "FALSE"
    if isinstance(value, str):
        return _sql_string(value)
    if isinstance(value, (datetime, pd.Timestamp)):
        return _timestamp_literal(_naive_utc(value))
    return str(value)


def evaluate_model_drift(
    baseline_roc_auc: Any,
    current_roc_auc: Any,
    threshold: float = MODEL_DRIFT_THRESHOLD,
) -> Dict[str, Any]:
    """Return relative ROC-AUC loss and inclusive threshold verdict."""
    try:
        baseline = float(baseline_roc_auc)
        current = float(current_roc_auc)
    except (TypeError, ValueError):
        return {
            "roc_auc_degradation": None,
            "roc_auc_degradation_pct": None,
            "model_drift_detected": None,
        }
    if not np.isfinite(baseline) or not np.isfinite(current) or baseline <= 0:
        return {
            "roc_auc_degradation": None,
            "roc_auc_degradation_pct": None,
            "model_drift_detected": None,
        }
    degradation = baseline - current
    degradation_fraction = degradation / baseline
    return {
        "roc_auc_degradation": degradation,
        "roc_auc_degradation_pct": degradation_fraction * 100,
        "model_drift_detected": degradation_fraction >= threshold,
    }


@dataclass
class CaptureWindow:
    """Membership boundary and row counts for one fresh monitoring run."""

    monitoring_run_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    expected_rows: int = 0
    tagged_rows: int = 0

    @property
    def is_closed(self) -> bool:
        return self.ended_at is not None and self.tagged_rows == self.expected_rows


class MonitoringSession:
    """Run the Lab 5D endpoint-to-dashboard path for one isolated row set.

    ``monitoring_run_id`` is the durable batch key. After capture closes, every
    downstream query selects by this key rather than by a rolling lookback or a
    previous monitoring-table timestamp. This makes an empty monitoring table
    and repeated notebook runs behave the same way and prevents pre-run or
    late-arriving rows from leaking into the comparison.
    """

    def __init__(
        self,
        endpoint_name: Optional[str] = None,
        athena_client: Optional[AthenaClient] = None,
        runtime_client: Optional[Any] = None,
        glue_client: Optional[Any] = None,
        region: str = AWS_DEFAULT_REGION,
        min_samples: int = MIN_MONITORING_SAMPLES,
    ) -> None:
        self.region = region
        self.endpoint_name = endpoint_name or ENDPOINT_NAME or resolve_endpoint_name()
        if not self.endpoint_name:
            raise RuntimeError(
                "No InService endpoint found. Deploy Lab 3A or configure endpoint.name."
            )
        self.athena = athena_client or AthenaClient()
        self.runtime = runtime_client or boto3.client(
            "sagemaker-runtime", region_name=region
        )
        self.glue = glue_client or boto3.client("glue", region_name=region)
        self.min_samples = min_samples
        self.features = schema.feature_names()
        self.target_column = schema.target_column()
        self.window: Optional[CaptureWindow] = None
        self.baseline: Dict[str, Any] = {}
        self.data_drift_results: Optional[Dict[str, Any]] = None
        self.model_results: Optional[Dict[str, Any]] = None
        self.mlflow_result: Optional[Dict[str, Any]] = None

    def summary(self) -> Dict[str, Any]:
        """Return the resolved inputs and visible statistical thresholds."""
        return {
            "region": self.region,
            "endpoint_name": self.endpoint_name,
            "athena_database": ATHENA_DATABASE,
            "feature_count": len(self.features),
            "target_column": self.target_column,
            "minimum_samples": self.min_samples,
            "feature_drift_method": "jensenshannon",
            "feature_drift_score_threshold": 0.1,
            "dataset_drift_share_threshold": DATA_DRIFT_THRESHOLD,
            "model_drift_relative_auc_threshold": MODEL_DRIFT_THRESHOLD,
        }

    def verify_monitoring_tables(self) -> Dict[str, bool]:
        """Read Glue metadata and report whether required tables exist."""
        required = (
            ATHENA_INFERENCE_TABLE,
            ATHENA_MONITORING_RESPONSES_TABLE,
            ATHENA_GROUND_TRUTH_UPDATES_TABLE,
        )
        status: Dict[str, bool] = {}
        for table in required:
            try:
                self.glue.get_table(DatabaseName=ATHENA_DATABASE, Name=table)
                status[table] = True
            except Exception:
                status[table] = False
        return status

    def _athena_now(self) -> datetime:
        result = self.athena.execute_query(
            "SELECT CAST(CURRENT_TIMESTAMP AS TIMESTAMP(3)) AS now_utc"
        )
        if result.empty or pd.isna(result["now_utc"].iloc[0]):
            raise RuntimeError("Athena did not return a capture timestamp")
        return _naive_utc(result["now_utc"].iloc[0])

    def start_run(self) -> CaptureWindow:
        """Open a new server-timed capture window before endpoint traffic."""
        if self.window and not self.window.is_closed:
            raise RuntimeError("The current capture window is still open")
        started_at = self._athena_now()
        run_id = f"notebook-drift-{started_at:%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:8]}"
        existing = self.athena.execute_query(
            f"SELECT COUNT(*) AS n FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} "
            f"WHERE monitoring_run_id = {_sql_string(run_id)}"
        )
        if int(existing["n"].iloc[0]) != 0:
            raise RuntimeError(f"Generated monitoring_run_id already exists: {run_id}")
        self.window = CaptureWindow(run_id, started_at)
        self.data_drift_results = None
        self.model_results = None
        self.mlflow_result = None
        return self.window

    def load_baseline(self) -> Dict[str, Any]:
        """Resolve baseline snapshots from the model actually serving traffic."""
        from src.drift_monitoring.baseline import load_baseline_from_registry

        self.baseline = load_baseline_from_registry() or {}
        return {
            "model_package_arn": self.baseline.get("model_package_arn"),
            "training_table": self.baseline.get("training_table") or ATHENA_TRAINING_TABLE,
            "training_snapshot_id": self.baseline.get("training_snapshot_id"),
            "evaluation_table": self.baseline.get("evaluation_table")
            or ATHENA_EVALUATION_TABLE,
            "evaluation_snapshot_id": self.baseline.get("evaluation_snapshot_id"),
            "baseline_roc_auc": self.baseline.get("metrics", {}).get("roc_auc"),
        }

    def generate_drifted_data(self) -> Path:
        """Generate the configured deterministic drift CSV using the existing module."""
        from src.drift_monitoring.generate_drift_dataset import generate_drifted_dataset

        generate_drifted_dataset()
        if not Path(CSV_DRIFTED_DATA).exists():
            raise RuntimeError(f"Drift generator did not create {CSV_DRIFTED_DATA}")
        return Path(CSV_DRIFTED_DATA)

    def invoke_endpoint(self, feature_values: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke the endpoint and return its paired label/probability response."""
        payload = json.dumps(feature_values, allow_nan=False)
        started = time.monotonic()
        response = self.runtime.invoke_endpoint(
            EndpointName=self.endpoint_name,
            ContentType="application/json",
            Body=payload,
        )
        latency_ms = (time.monotonic() - started) * 1000
        body = json.loads(response["Body"].read().decode())
        prediction = int(body["predictions"][0])
        probabilities = body.get("probabilities", {})
        for key in ("yes", "positive", "fraud"):
            if key in probabilities and probabilities[key]:
                probability = float(probabilities[key][0])
                break
        else:
            raise KeyError(
                f"No positive-class probability in endpoint response: {sorted(probabilities)}"
            )
        return {
            "prediction": prediction,
            "probability_positive": probability,
            "latency_ms": latency_ms,
        }

    def send_drift_traffic(
        self,
        count: int = 101,
        csv_path: Path = CSV_DRIFTED_DATA,
        random_state: int = 123,
    ) -> Dict[str, Any]:
        """Send complete generated rows after opening a fresh capture window."""
        if self.window is None:
            self.start_run()
        elif self.window.ended_at is not None:
            raise RuntimeError("Capture has already closed; start a new session run")

        drifted = pd.read_csv(csv_path)
        missing = [feature for feature in self.features if feature not in drifted.columns]
        if missing:
            raise ValueError(f"Drift CSV is missing model feature(s): {missing}")
        for feature in self.features:
            drifted[feature] = pd.to_numeric(drifted[feature], errors="coerce")
        complete = drifted.dropna(subset=self.features)
        if len(complete) < count:
            raise ValueError(
                f"Only {len(complete)} complete drift rows are available; requested {count}"
            )
        samples = complete.sample(n=count, random_state=random_state)

        responses = []
        errors = []
        for _, row in samples.iterrows():
            try:
                responses.append(self.invoke_endpoint(row[self.features].to_dict()))
            except Exception as exc:
                errors.append(str(exc))
        if errors:
            raise RuntimeError(
                f"{len(errors)} of {count} endpoint invocations failed; capture was not closed. "
                f"First error: {errors[0]}"
            )

        self.window.expected_rows = len(responses)
        predictions = [item["prediction"] for item in responses]
        return {
            "sent": len(responses),
            "errors": 0,
            "predicted_classes": sorted(set(predictions)),
            "model_drift_classification_ready": set(predictions) == {0, 1},
            "positive_predictions": sum(value == 1 for value in predictions),
            "latency_p50_ms": float(np.percentile([r["latency_ms"] for r in responses], 50)),
            "latency_p95_ms": float(np.percentile([r["latency_ms"] for r in responses], 95)),
        }

    def close_capture(
        self,
        timeout_seconds: int = 240,
        poll_seconds: int = 10,
    ) -> Dict[str, Any]:
        """Wait for exactly the sent rows, close the window, and tag membership.

        The method fails if more than the expected number appears in the window,
        which detects concurrent traffic instead of silently mixing it into this
        run. Rows arriving after the chosen upper bound remain untagged and are
        excluded from every downstream query.
        """
        if self.window is None or self.window.expected_rows <= 0:
            raise RuntimeError("Send drift traffic before closing capture")
        if self.window.is_closed:
            return self.capture_evidence()

        endpoint = _sql_string(self.endpoint_name)
        lower = _timestamp_literal(self.window.started_at)
        deadline = time.monotonic() + timeout_seconds
        observed = 0
        last = pd.DataFrame()
        while time.monotonic() <= deadline:
            query = f"""
                SELECT COUNT(*) AS n,
                       CAST(MIN(request_timestamp) AS TIMESTAMP(3)) AS first_seen,
                       CAST(MAX(request_timestamp) AS TIMESTAMP(3)) AS last_seen
                FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
                WHERE endpoint_name = {endpoint}
                  AND monitoring_run_id IS NULL
                  AND request_timestamp >= {lower}
            """
            last = self.athena.execute_query(query)
            observed = int(last["n"].iloc[0]) if not last.empty else 0
            if observed > self.window.expected_rows:
                raise RuntimeError(
                    f"Capture saw {observed} rows but sent {self.window.expected_rows}. "
                    "Stop concurrent endpoint traffic and start a new run."
                )
            if observed == self.window.expected_rows:
                break
            time.sleep(poll_seconds)
        else:
            raise TimeoutError(
                f"Capture timed out with {observed}/{self.window.expected_rows} rows"
            )

        ended_at = _naive_utc(last["last_seen"].iloc[0])
        upper = _timestamp_literal(ended_at)
        run_id = _sql_string(self.window.monitoring_run_id)
        tag_sql = f"""
            UPDATE {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            SET monitoring_run_id = {run_id}
            WHERE endpoint_name = {endpoint}
              AND monitoring_run_id IS NULL
              AND request_timestamp >= {lower}
              AND request_timestamp <= {upper}
        """
        self.athena.execute_query(tag_sql, return_results=False)
        self.window.ended_at = ended_at
        evidence = self.capture_evidence()
        if evidence["tagged_rows"] != self.window.expected_rows:
            raise RuntimeError(
                f"Tagged {evidence['tagged_rows']} rows; expected {self.window.expected_rows}"
            )
        self.window.tagged_rows = evidence["tagged_rows"]
        return evidence

    def capture_evidence(self) -> Dict[str, Any]:
        """Read persisted run membership and its effective timestamp bounds."""
        if self.window is None:
            raise RuntimeError("No run has started")
        result = self.athena.execute_query(
            f"""
            SELECT COUNT(*) AS tagged_rows,
                   CAST(MIN(request_timestamp) AS TIMESTAMP(3)) AS first_seen,
                   CAST(MAX(request_timestamp) AS TIMESTAMP(3)) AS last_seen,
                   SUM(CASE WHEN ground_truth IS NULL THEN 1 ELSE 0 END) AS unlabeled_rows
            FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            WHERE monitoring_run_id = {_sql_string(self.window.monitoring_run_id)}
            """
        )
        row = result.iloc[0]
        return {
            "monitoring_run_id": self.window.monitoring_run_id,
            "capture_window_start": self.window.started_at,
            "capture_window_end": self.window.ended_at,
            "tagged_rows": int(row["tagged_rows"]),
            "first_tagged_timestamp": row["first_seen"],
            "last_tagged_timestamp": row["last_seen"],
            "unlabeled_rows": int(row["unlabeled_rows"] or 0),
        }

    def apply_simulated_ground_truth(self, seed: int = 42) -> Dict[str, Any]:
        """Create and merge labels only for this run's tagged inference rows."""
        if self.window is None or not self.window.is_closed:
            raise RuntimeError("Close capture before applying ground truth")
        from src.drift_monitoring.simulate_ground_truth_from_athena import (
            GroundTruthSimulator,
        )
        from src.drift_monitoring.update_ground_truth import GroundTruthUpdater

        simulator = GroundTruthSimulator(
            athena_client=self.athena,
            endpoint_name=self.endpoint_name,
            accuracy=GROUND_TRUTH_SIM_ACCURACY,
            feature_drift_impact=GROUND_TRUTH_SIM_FEATURE_DRIFT_IMPACT,
            model_drift_magnitude=GROUND_TRUTH_SIM_MODEL_DRIFT_MAG,
            seed=seed,
            monitoring_run_id=self.window.monitoring_run_id,
            batch_id=self.window.monitoring_run_id,
        )
        simulation = simulator.simulate_and_write(limit=None)
        if simulation["updates_created"] != self.window.tagged_rows:
            raise RuntimeError(
                f"Created {simulation['updates_created']} labels for "
                f"{self.window.tagged_rows} tagged rows"
            )
        updater = GroundTruthUpdater(
            athena_client=self.athena,
            monitoring_run_id=self.window.monitoring_run_id,
        )
        update = updater.update_ground_truth_batch()
        coverage = updater.get_coverage_statistics()
        if int(coverage["with_ground_truth"]) != self.window.tagged_rows:
            raise RuntimeError(
                f"Only {coverage['with_ground_truth']}/{self.window.tagged_rows} run rows were labeled"
            )
        return {"simulation": simulation, "update": update, "coverage": coverage}

    def _baseline_from(self, table_key: str, snapshot_key: str, default: str) -> str:
        table = self.baseline.get(table_key) or default
        snapshot = self.baseline.get(snapshot_key)
        source = f"{ATHENA_DATABASE}.{table}"
        return f"{source} FOR VERSION AS OF {snapshot}" if snapshot else source

    def run_data_drift(self, baseline_limit: int = 5000) -> Dict[str, Any]:
        """Compare the pinned training baseline with this run's tagged rows."""
        if self.window is None or not self.window.is_closed:
            raise RuntimeError("Close capture before calculating data drift")
        from src.drift_monitoring.evidently_reports import run_data_drift_report

        baseline_source = self._baseline_from(
            "training_table", "training_snapshot_id", ATHENA_TRAINING_TABLE
        )
        baseline_sql = f"""
            SELECT {', '.join(self.features)}
            FROM {baseline_source}
            WHERE {self.target_column} IS NOT NULL
            ORDER BY {schema.identifier_column()}
            LIMIT {int(baseline_limit)}
        """
        baseline_df = self.athena.execute_query(baseline_sql)
        raw = self.athena.execute_query(
            f"""
            SELECT input_features
            FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            WHERE monitoring_run_id = {_sql_string(self.window.monitoring_run_id)}
            ORDER BY request_timestamp, inference_id
            """
        )
        current_rows = []
        for payload in raw["input_features"]:
            parsed = json.loads(payload)
            current_rows.append({feature: parsed.get(feature) for feature in self.features})
        current_df = pd.DataFrame(current_rows, columns=self.features)
        for feature in self.features:
            baseline_df[feature] = pd.to_numeric(baseline_df[feature], errors="coerce")
            current_df[feature] = pd.to_numeric(current_df[feature], errors="coerce")

        self.data_drift_results = run_data_drift_report(
            baseline_df=baseline_df,
            current_df=current_df,
            min_samples=self.min_samples,
        )
        return self.data_drift_results

    def run_model_drift(self, prediction_threshold: float = 0.5) -> Dict[str, Any]:
        """Score paired labels/predictions/probabilities for this run only."""
        if self.window is None or not self.window.is_closed:
            raise RuntimeError("Close capture before calculating model drift")
        from src.drift_monitoring.baseline import score_evaluation_baseline
        from src.drift_monitoring.evidently_reports import run_classification_report
        from src.drift_monitoring.monitor_model_performance import (
            ModelPerformanceMonitor,
        )

        current_rows = self.athena.execute_query(
            f"""
            SELECT ground_truth, {PREDICTION_COLUMN}, {PROBABILITY_COLUMN}
            FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            WHERE monitoring_run_id = {_sql_string(self.window.monitoring_run_id)}
              AND ground_truth IS NOT NULL
            ORDER BY request_timestamp, inference_id
            """
        )
        complete_current = current_rows[
            ["ground_truth", PREDICTION_COLUMN, PROBABILITY_COLUMN]
        ].apply(pd.to_numeric, errors="coerce").dropna()
        expected_labels = (
            complete_current[PROBABILITY_COLUMN] > prediction_threshold
        ).astype(int)
        mismatch_count = int(
            (complete_current[PREDICTION_COLUMN].round().astype(int) != expected_labels).sum()
        )
        if mismatch_count:
            self.model_results = {
                "report": None,
                "metrics": None,
                "skip_reason": (
                    f"{mismatch_count} prediction/probability pairs disagree with "
                    f"threshold {prediction_threshold}"
                ),
                "baseline_roc_auc": self.baseline.get("metrics", {}).get("roc_auc"),
                "model_drift_detected": None,
                "prediction_probability_mismatch_count": mismatch_count,
            }
            return self.model_results

        monitor = ModelPerformanceMonitor(
            athena_client=self.athena,
            alert_threshold=MIN_ROC_AUC_THRESHOLD,
            min_samples=self.min_samples,
        )
        metrics = monitor.calculate_performance_metrics(current_rows)
        result: Dict[str, Any] = {
            "report": None,
            "metrics": None if "error" in metrics else metrics,
            "skip_reason": metrics.get("error"),
            "baseline_roc_auc": self.baseline.get("metrics", {}).get("roc_auc"),
            "model_drift_detected": None,
            "prediction_probability_mismatch_count": 0,
        }
        if "error" in metrics:
            self.model_results = result
            return result
        if not self.baseline.get("model_package_arn"):
            result["skip_reason"] = "baseline_model_unavailable"
            self.model_results = result
            return result

        baseline_scored = score_evaluation_baseline(
            baseline=self.baseline,
            athena_client=self.athena,
            feature_names=self.features,
            target_column=self.target_column,
            threshold=prediction_threshold,
        )
        current = current_rows.rename(
            columns={
                "ground_truth": "target",
                PREDICTION_COLUMN: "prediction",
                PROBABILITY_COLUMN: "probability",
            }
        )
        try:
            classification = run_classification_report(
                baseline_df=baseline_scored[["target", "prediction", "probability"]],
                current_df=current[["target", "prediction", "probability"]],
                target_column="target",
                prediction_column="prediction",
                probability_column="probability",
            )
        except ValueError as exc:
            result["skip_reason"] = str(exc)
            self.model_results = result
            return result

        baseline_auc = result["baseline_roc_auc"]
        current_auc = metrics.get("roc_auc")
        result.update(evaluate_model_drift(baseline_auc, current_auc))
        result["report"] = classification
        result["skip_reason"] = None
        self.model_results = result
        return result

    def persist_results(self, log_to_mlflow: bool = True) -> Dict[str, Any]:
        """Persist one internally consistent row for this tagged run."""
        if self.window is None or not self.window.is_closed:
            raise RuntimeError("A closed capture window is required")
        drift = self.data_drift_results
        model = self.model_results or {}
        metrics = model.get("metrics")

        if log_to_mlflow:
            from src.drift_monitoring.log_monitoring_to_mlflow import (
                log_monitoring_to_mlflow,
            )

            self.mlflow_result = log_monitoring_to_mlflow(
                drift_results=drift,
                model_report=model.get("report"),
                overall_metrics=metrics,
                endpoint_name=self.endpoint_name,
                model_name=MLFLOW_MODEL_NAME,
                region=self.region,
            )
        else:
            self.mlflow_result = {"success": False, "mlflow_run_id": None}

        per_feature = None
        if drift:
            per_feature = {
                column: {
                    "score": values.get("drift_score"),
                    "magnitude": values.get("drift_magnitude"),
                    "method": values.get("method", ""),
                    "threshold": values.get("threshold"),
                    "direction": values.get("direction", "unknown"),
                    "drifted": values.get("drifted"),
                    "comparable": values.get("comparable", False),
                    "unavailable_reason": values.get("unavailable_reason"),
                    "baseline_sample_size": values.get("baseline_sample_size"),
                    "current_sample_size": values.get("current_sample_size"),
                }
                for column, values in drift.get("per_column", {}).items()
            }

        data_verdict = drift.get("drift_detected") if drift else None
        model_verdict = model.get("model_drift_detected")
        known_verdicts = [v for v in (data_verdict, model_verdict) if v is not None]
        alert_sent = any(known_verdicts) if known_verdicts else None
        model_package_arn = self.baseline.get("model_package_arn")
        model_version = (
            model_package_arn.split("/")[-1] if model_package_arn else "unavailable"
        )
        baseline_auc = model.get("baseline_roc_auc")
        current_auc = metrics.get("roc_auc") if metrics else None

        columns = [
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
        values = [
            self.window.monitoring_run_id,
            self.window.ended_at,
            self.endpoint_name,
            model_version,
            model_package_arn,
            self.baseline.get("evaluation_snapshot_id"),
            self.baseline.get("training_snapshot_id"),
            data_verdict,
            drift.get("drifted_columns_count") if drift and drift.get("drifted_columns_share") is not None else None,
            drift.get("drifted_columns_share") if drift else None,
            drift.get("features_analyzed") if drift else None,
            drift.get("sample_size") if drift else None,
            model_verdict,
            baseline_auc,
            current_auc,
            model.get("roc_auc_degradation"),
            model.get("roc_auc_degradation_pct"),
            metrics.get("accuracy") if metrics else None,
            metrics.get("precision") if metrics else None,
            metrics.get("recall") if metrics else None,
            metrics.get("f1_score") if metrics else None,
            metrics.get("sample_count") if metrics else None,
            json.dumps(per_feature, allow_nan=False) if per_feature else None,
            None,
            self.mlflow_result.get("mlflow_run_id") if self.mlflow_result else None,
            alert_sent,
            "evidently",
            self.window.ended_at,
        ]
        sql = (
            f"INSERT INTO {ATHENA_DATABASE}.{ATHENA_MONITORING_RESPONSES_TABLE} "
            f"({', '.join(columns)}) VALUES ({', '.join(_sql_value(v) for v in values)})"
        )
        self.athena.execute_query(sql, return_results=False)
        return self.validate_persisted_run()

    def validate_persisted_run(self) -> Dict[str, Any]:
        """Prove persisted samples and labels refer to the same run key."""
        if self.window is None:
            raise RuntimeError("No run has started")
        run_id = _sql_string(self.window.monitoring_run_id)
        result = self.athena.execute_query(
            f"""
            SELECT m.monitoring_run_id, m.data_sample_size, m.model_sample_size,
                   m.features_analyzed, m.drifted_columns_count,
                   m.drifted_columns_share, m.data_drift_detected,
                   m.model_drift_detected,
                   COUNT(DISTINCT i.inference_id) AS tagged_rows,
                   SUM(CASE WHEN i.ground_truth IS NOT NULL THEN 1 ELSE 0 END) AS labeled_rows,
                   CAST(MIN(i.request_timestamp) AS TIMESTAMP(3)) AS first_seen,
                   CAST(MAX(i.request_timestamp) AS TIMESTAMP(3)) AS last_seen
            FROM {ATHENA_DATABASE}.{ATHENA_MONITORING_RESPONSES_TABLE} m
            LEFT JOIN {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} i
              ON i.monitoring_run_id = m.monitoring_run_id
            WHERE m.monitoring_run_id = {run_id}
            GROUP BY 1,2,3,4,5,6,7,8
            """
        )
        if len(result) != 1:
            raise RuntimeError(
                f"Expected one persisted monitoring row, found {len(result)}"
            )
        evidence = result.iloc[0].to_dict()
        tagged = int(evidence["tagged_rows"])
        if pd.notna(evidence.get("data_sample_size")) and int(evidence["data_sample_size"]) != tagged:
            raise RuntimeError("Persisted data_sample_size does not match tagged rows")
        if pd.notna(evidence.get("model_sample_size")) and int(evidence["model_sample_size"]) != int(evidence["labeled_rows"]):
            raise RuntimeError("Persisted model_sample_size does not match labeled rows")
        return evidence
