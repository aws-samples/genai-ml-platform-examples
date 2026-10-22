"""
One monitoring pass over the live endpoint — the code behind Lab 5D.

`MonitoringSession` holds the endpoint, the AWS clients, and the drift baselines
for a notebook session, and exposes each step of a monitoring pass:

    traffic       invoke() / sanity_check() / send() / send_drifted_csv()
                  wait_for_rows() / prediction_counts()
    ground truth  apply_ground_truth() / coverage()
    drift run     start_run() → data_drift() + model_drift() → finish_run()

Lab 5D Sections 3–5 call these one step at a time; the multi-batch simulation
(batch_simulation.py, Lab 5D Section 6) calls the same methods in a loop, so a
single pass and a loop of passes write identical monitoring_responses rows.

The "current" window of a run comes from config.yaml → drift_window:

    since_last_run  (previous run's monitoring_timestamp, run_ts]
                    first-ever run: the last MONITORING_DATA_DRIFT_LOOKBACK_DAYS
    rolling         (run_ts − minutes, run_ts]

All timestamps are naive UTC, matching request_timestamp (the Lab 3A inference
handler stamps it with datetime.utcnow()).
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

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
    DATA_S3_BUCKET,
    DRIFT_WINDOW_MINUTES,
    DRIFT_WINDOW_MODE,
    MIN_ROC_AUC_THRESHOLD,
    MLFLOW_MODEL_NAME,
    MONITORING_DATA_DRIFT_LOOKBACK_DAYS,
    PROBABILITY_COLUMN,
    resolve_endpoint_name,
)
from src.drift_monitoring.baseline import load_baseline_from_registry, score_evaluation_baseline
from src.drift_monitoring.evidently_reports import run_classification_report, run_data_drift_report
from src.drift_monitoring.log_monitoring_to_mlflow import log_monitoring_to_mlflow
from src.drift_monitoring.monitor_model_performance import ModelPerformanceMonitor
from src.drift_monitoring.simulate_ground_truth_from_athena import GroundTruthSimulator
from src.drift_monitoring.update_ground_truth import GroundTruthUpdater
from src.train_pipeline.athena.athena_client import AthenaClient

logger = logging.getLogger(__name__)

WINDOW_MODES = ('since_last_run', 'rolling')

# Evidently / sample-size limits used by every drift run.
BASELINE_LIMIT = 5000
INFERENCE_LIMIT = 10000
MIN_SAMPLES = 50
PREDICTION_THRESHOLD = 0.5

# Representative Bank Marketing values on the training scale, for the one-row
# sanity check. Swapping datasets? Update these to realistic ranges for your
# schema, or the sanity row inflates drift_magnitude in Section 5.
SANITY_DEFAULTS = {
    'age': 41, 'job': 0, 'marital': 1, 'education': 6, 'credit_default': 0,
    'housing': 2, 'loan': 0, 'contact': 1, 'month': 6, 'day_of_week': 1,
    'duration': 180, 'campaign': 2, 'pdays': 999, 'previous': 0,
    'poutcome': 1, 'emp_var_rate': 1.1, 'cons_price_idx': 93.994,
    'cons_conf_idx': -36.4, 'euribor3m': 4.857, 'nr_employed': 5191.0,
}

# Must match the monitoring_responses DDL in templates/4-inference-capture.yaml
# and the QuickSight dataset in src/governance/create_governance_dashboard.py.
MONITORING_COLUMNS = [
    'monitoring_run_id', 'monitoring_timestamp',
    'endpoint_name', 'model_version', 'model_package_arn',
    'evaluation_snapshot_id', 'training_snapshot_id',
    'data_drift_detected', 'drifted_columns_count', 'drifted_columns_share',
    'features_analyzed', 'data_sample_size', 'model_drift_detected',
    'baseline_roc_auc', 'current_roc_auc',
    'roc_auc_degradation', 'roc_auc_degradation_pct',
    'accuracy', 'precision', 'recall', 'f1_score',
    'model_sample_size', 'per_feature_drift_scores',
    'evidently_report_s3_path', 'mlflow_run_id',
    'alert_sent', 'detection_engine', 'created_at',
]

RULE = '━' * 72


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ts_literal(ts) -> str:
    return f"TIMESTAMP '{pd.Timestamp(ts).strftime('%Y-%m-%d %H:%M:%S')}'"


def sql_val(v) -> str:
    if v is None:
        return 'NULL'
    if isinstance(v, (bool, np.bool_)):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return str(v)


def _source(table: str, snapshot_id: str) -> str:
    return (f'{ATHENA_DATABASE}.{table} FOR VERSION AS OF {snapshot_id}'
            if snapshot_id else f'{ATHENA_DATABASE}.{table}')


def _snap_log(snapshot_id: str) -> str:
    return f'Iceberg snapshot {snapshot_id}' if snapshot_id else 'live table (no snapshot pinned)'


@dataclass
class MonitoringRun:
    """One drift run: its id, when it ran, and the window it measures."""

    monitoring_run_id: str
    run_ts: datetime
    lower: datetime          # exclusive lower bound of the current window
    window_label: str


class MonitoringSession:
    """Endpoint, clients and baselines for a Lab 5D session."""

    def __init__(
        self,
        endpoint_name: Optional[str] = None,
        window_mode: str = DRIFT_WINDOW_MODE,
        window_minutes: int = DRIFT_WINDOW_MINUTES,
        athena_client=None,
        runtime_client=None,
    ):
        if window_mode not in WINDOW_MODES:
            raise ValueError(f'window_mode must be one of {WINDOW_MODES}, got {window_mode!r}')
        self.endpoint_name = endpoint_name or resolve_endpoint_name()
        if not self.endpoint_name:
            raise RuntimeError(
                'No InService bank-marketing endpoint found. Deploy it from '
                'lab3-model-build/lab-3a_traditional_ml_experimenation.ipynb first, '
                'or pin endpoint.name in src/config/config.yaml.'
            )
        self.region = AWS_DEFAULT_REGION
        self.window_mode = window_mode
        self.window_minutes = window_minutes
        self.athena_client = athena_client or AthenaClient()
        self.runtime_client = runtime_client or boto3.client('sagemaker-runtime', region_name=self.region)
        self.feature_names = schema.feature_names()
        self.target_column = schema.target_column()
        self._baseline_meta = None
        self._training_baseline_df = None
        self._evaluation_baseline_df = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def describe(self) -> None:
        print(f'Region            : {self.region}')
        print(f'Endpoint          : {self.endpoint_name}')
        print(f'Athena DB         : {ATHENA_DATABASE}')
        print(f'Target column     : {self.target_column}')
        print(f'Features          : {len(self.feature_names)}')
        print(f'S3 bucket         : {DATA_S3_BUCKET}')
        print(f'MLflow URI        : {os.getenv("MLFLOW_TRACKING_URI", "NOT SET")}')
        print(f'Drift window      : {self.window_label()}')

    def window_label(self) -> str:
        if self.window_mode == 'rolling':
            return f'rolling, last {self.window_minutes} min'
        return (f'since last run (first run: last '
                f'{MONITORING_DATA_DRIFT_LOOKBACK_DAYS} days)')

    def check_tables(self) -> list:
        """Read-only: confirm the workshop stack created the monitoring tables."""
        required = [ATHENA_INFERENCE_TABLE, ATHENA_MONITORING_RESPONSES_TABLE,
                    ATHENA_GROUND_TRUTH_UPDATES_TABLE]
        glue = boto3.client('glue', region_name=self.region)
        missing = []
        print(RULE)
        print(f'MONITORING TABLES (in {ATHENA_DATABASE}, created by the workshop stack)')
        print(RULE)
        for table in required:
            try:
                glue.get_table(DatabaseName=ATHENA_DATABASE, Name=table)
                print(f'  ✓ {ATHENA_DATABASE}.{table}')
            except Exception:
                missing.append(table)
                print(f'  ✗ {ATHENA_DATABASE}.{table}  (MISSING)')
        print(RULE)
        if missing:
            print('Missing table(s):', ', '.join(missing))
            print('Redeploy the workshop stack (scripts/deploy-workshop.sh) — the\n'
                  '4-inference-capture.yaml table-creator provisions all three.\n'
                  'This notebook never creates tables itself.')
        return missing

    # ------------------------------------------------------------------
    # Traffic
    # ------------------------------------------------------------------
    def invoke(self, features: Dict[str, Any]) -> Tuple[Dict[str, Any], float]:
        """Invoke the endpoint with one JSON row. Returns (result, latency_ms).

        Lab 3A's handler returns
        {"predictions": [0/1], "probabilities": {"yes": [...], "no": [...]}};
        other handlers label the positive class "positive" or (legacy) "fraud".
        """
        payload = json.dumps({k: (v.item() if hasattr(v, 'item') else v) for k, v in features.items()})
        start = time.time()
        response = self.runtime_client.invoke_endpoint(
            EndpointName=self.endpoint_name, ContentType='application/json', Body=payload,
        )
        latency_ms = (time.time() - start) * 1000
        result = json.loads(response['Body'].read().decode())

        probs = result.get('probabilities', {})
        for key in ('yes', 'positive', 'fraud'):
            if probs.get(key):
                prob_positive = probs[key][0]
                break
        else:
            raise KeyError(f'No positive-class probability in handler response: {sorted(probs)}')
        return {'prediction': result['predictions'][0], 'probability_positive': prob_positive}, latency_ms

    def sanity_check(self) -> Dict[str, Any]:
        """One non-drifted prediction, to confirm the endpoint is alive."""
        payload = {f: SANITY_DEFAULTS.get(f, 0.0) for f in self.feature_names}
        result, latency_ms = self.invoke(payload)
        print(f"Prediction          : {result['prediction']}")
        print(f"P({self.target_column}=1): {result['probability_positive']:.4f}")
        print(f'Latency             : {latency_ms:.0f} ms')
        print(f'\nLogged to {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} (visible after SQS flush).')
        return result

    def send(self, df: pd.DataFrame, verbose: bool = True) -> Dict[str, Any]:
        """Send every row of df (feature columns only) to the endpoint."""
        predictions, latencies, errors = [], [], []
        for _, row in df[self.feature_names].iterrows():
            try:
                result, lat = self.invoke(row.to_dict())
                predictions.append(result)
                latencies.append(lat)
            except Exception as e:
                errors.append(str(e))
        stats = {
            'sent': len(predictions),
            'errors': len(errors),
            'positive': sum(1 for p in predictions if p['prediction'] == 1),
            'latencies': np.array(latencies) if latencies else np.array([0.0]),
        }
        if verbose:
            lat = stats['latencies']
            print(f"Sent             : {stats['sent']}/{len(df)}  ({stats['errors']} errors)")
            print(f'Latency P50/P95/P99: {np.percentile(lat, 50):.0f} / '
                  f'{np.percentile(lat, 95):.0f} / {np.percentile(lat, 99):.0f} ms')
            print(f"Positive ({self.target_column}=1): {stats['positive']}/{stats['sent']} "
                  f"({stats['positive'] / max(stats['sent'], 1) * 100:.1f}%)")
        return stats

    def send_drifted_csv(self, csv_path: Path, n: int, random_state: int = 123) -> Dict[str, Any]:
        """Send n rows of the drifted CSV (Section 2) and wait until they land."""
        csv_path = Path(csv_path)
        if not csv_path.exists():
            raise FileNotFoundError(f'Drifted CSV not found: {csv_path} — run Section 2 first.')
        df = pd.read_csv(csv_path)
        for col in self.feature_names:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=self.feature_names, how='all')
        sample = df.sample(n=min(n, len(df)), random_state=random_state)

        print(f'Source           : {csv_path.name}')
        print(f'Sending          : {len(sample)} rows to {self.endpoint_name}\n')
        start = utcnow()
        stats = self.send(sample)
        print('\nWaiting for SQS → Lambda → Athena capture...')
        stats['landed'] = self.wait_for_rows(start, expected=stats['sent'])
        print(f"✓ {stats['landed']} of {stats['sent']} rows landed in {ATHENA_INFERENCE_TABLE}.")
        return stats

    def wait_for_rows(
        self,
        since_ts: datetime,
        expected: int,
        timeout_s: int = 300,
        poll_s: int = 15,
        min_fraction: float = 0.95,
    ) -> int:
        """Poll inference_responses until ≥ min_fraction of `expected` rows landed."""
        target = int(expected * min_fraction)
        deadline = time.time() + timeout_s
        while True:
            res = self.athena_client.execute_query(f"""
                SELECT COUNT(*) AS n
                FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
                WHERE endpoint_name = '{self.endpoint_name}'
                  AND request_timestamp >= {ts_literal(since_ts)}
            """)
            landed = int(res['n'].iloc[0]) if not res.empty else 0
            if landed >= target or time.time() >= deadline:
                return landed
            time.sleep(poll_s)

    def prediction_counts(self) -> pd.DataFrame:
        """Total predictions captured for this endpoint, with their time range."""
        result = self.athena_client.execute_query(f"""
            SELECT COUNT(*) AS total,
                   CAST(MIN(request_timestamp) AS TIMESTAMP(3)) AS earliest,
                   CAST(MAX(request_timestamp) AS TIMESTAMP(3)) AS latest
            FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            WHERE endpoint_name = '{self.endpoint_name}'
        """)
        if not result.empty and result['total'].iloc[0] > 0:
            print(f"✓ Found {result['total'].iloc[0]:,} predictions for {self.endpoint_name}")
            print(f"  Time range: {result['earliest'].iloc[0]} → {result['latest'].iloc[0]}")
        else:
            print('⚠ No predictions found yet — wait ~30s for the SQS→Lambda flush, then retry.')
        return result

    # ------------------------------------------------------------------
    # Ground truth
    # ------------------------------------------------------------------
    def apply_ground_truth(
        self,
        accuracy: float,
        feature_drift_impact: float = 0.0,
        model_drift_magnitude: float = 0.0,
        seed: int = 42,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Simulate labels for every unlabelled prediction, then MERGE them in."""
        simulator = GroundTruthSimulator(
            athena_client=self.athena_client,
            endpoint_name=self.endpoint_name,
            accuracy=accuracy,
            positive_confirmation_days=(1, 7),
            negative_confirmation_days=(1, 30),
            feature_drift_impact=feature_drift_impact,
            model_drift_magnitude=model_drift_magnitude,
            seed=seed,
        )
        stats = simulator.simulate_and_write(limit=None)
        if stats['total_predictions'] == 0:
            if verbose:
                print('⚠ No predictions without ground truth — run Section 3 first '
                      '(or every prediction is already labelled).')
            return stats

        updater = GroundTruthUpdater(athena_client=self.athena_client, dry_run=False)
        stats['merged'] = updater.update_ground_truth_batch()['updated']
        if verbose:
            print(f"Predictions labelled : {stats['total_predictions']:,}")
            print(f"Actual positive      : {stats['actual_positive']:,}")
            print(f"False positives      : {stats['false_positives']:,}")
            print(f"False negatives      : {stats['false_negatives']:,}")
            print(f"Merged into {ATHENA_INFERENCE_TABLE}: {stats['merged']:,}")
        return stats

    def coverage(self) -> Dict[str, Any]:
        cov = GroundTruthUpdater(athena_client=self.athena_client, dry_run=False).get_coverage_statistics()
        print('Ground truth coverage:')
        print(f"  Total predictions   : {cov['total_predictions']:,}")
        print(f"  With ground truth   : {cov['with_ground_truth']:,} ({cov['coverage_pct']:.2f}%)")
        print(f"  Without ground truth: {cov['without_ground_truth']:,}")
        return cov

    # ------------------------------------------------------------------
    # Baselines (loaded once, on first use)
    # ------------------------------------------------------------------
    @property
    def baseline_meta(self) -> Dict[str, Any]:
        if self._baseline_meta is None:
            self._baseline_meta = load_baseline_from_registry() or {}
        return self._baseline_meta

    @property
    def baseline_roc_auc(self) -> Optional[float]:
        """ROC-AUC on the held-out set at training time (baseline.json)."""
        return self.baseline_meta.get('metrics', {}).get('roc_auc')

    @property
    def training_source(self) -> str:
        meta = self.baseline_meta
        return _source(meta.get('training_table') or ATHENA_TRAINING_TABLE,
                       meta.get('training_snapshot_id') or '')

    @property
    def training_baseline_df(self) -> pd.DataFrame:
        """Data-drift reference: the pinned training_data snapshot."""
        if self._training_baseline_df is None:
            self._training_baseline_df = self.athena_client.execute_query(f"""
                SELECT {", ".join(self.feature_names)}
                FROM {self.training_source}
                WHERE {self.target_column} IS NOT NULL
                LIMIT {BASELINE_LIMIT}
            """).apply(pd.to_numeric, errors='coerce').dropna(how='all')
        return self._training_baseline_df

    @property
    def evaluation_baseline_df(self) -> Optional[pd.DataFrame]:
        """Model-drift reference: evaluation_data re-scored with the registered model.

        The table's own `prediction` column is NULL (Lab 2 creates it, nothing
        backfills it), so the baseline is computed rather than read.
        """
        if self._evaluation_baseline_df is None and self.baseline_meta.get('model_package_arn'):
            self._evaluation_baseline_df = score_evaluation_baseline(
                baseline=self.baseline_meta,
                athena_client=self.athena_client,
                feature_names=self.feature_names,
                target_column=self.target_column,
                threshold=PREDICTION_THRESHOLD,
            )
        return self._evaluation_baseline_df

    # ------------------------------------------------------------------
    # Drift run
    # ------------------------------------------------------------------
    def resolve_window(self, run_ts: datetime) -> Tuple[datetime, str]:
        """Exclusive lower bound of the current window ending at run_ts, plus a label."""
        if self.window_mode == 'rolling':
            return run_ts - timedelta(minutes=self.window_minutes), f'rolling, last {self.window_minutes} min'
        try:
            prev = self.athena_client.execute_query(f"""
                SELECT MAX(monitoring_timestamp) AS prev_ts
                FROM {ATHENA_DATABASE}.{ATHENA_MONITORING_RESPONSES_TABLE}
                WHERE endpoint_name = '{self.endpoint_name}'
                  AND monitoring_timestamp < {ts_literal(run_ts)}
            """)
            # SQL NULL comes back as pd.NaT, which is not None — treat both as first run.
            prev_ts = None if prev.empty or pd.isna(prev['prev_ts'].iloc[0]) else prev['prev_ts'].iloc[0]
        except Exception:
            prev_ts = None
        if prev_ts is None:
            return (run_ts - timedelta(days=MONITORING_DATA_DRIFT_LOOKBACK_DAYS),
                    f'first run, last {MONITORING_DATA_DRIFT_LOOKBACK_DAYS} days')
        return pd.Timestamp(prev_ts).to_pydatetime(), f'since last run @ {prev_ts}'

    def start_run(self, suffix: str = '', verbose: bool = True) -> MonitoringRun:
        """Allocate a monitoring_run_id and resolve the window it measures."""
        run_ts = utcnow()
        lower, label = self.resolve_window(run_ts)
        run = MonitoringRun(
            monitoring_run_id=f'notebook-drift-{run_ts.strftime("%Y%m%d-%H%M%S")}{suffix}',
            run_ts=run_ts, lower=lower, window_label=label,
        )
        if verbose:
            meta = self.baseline_meta
            evaluation = _source(meta.get('evaluation_table') or ATHENA_EVALUATION_TABLE,
                                 meta.get('evaluation_snapshot_id') or '')
            print(RULE)
            print('MONITORING RUN — LINEAGE')
            print(RULE)
            print(f'  monitoring_run_id   : {run.monitoring_run_id}')
            print(f'  Endpoint            : {self.endpoint_name}')
            print(f"  Model package ARN   : {meta.get('model_package_arn') or '(not pinned)'}")
            print(f"  Training baseline   : {self.training_source}  ({_snap_log(meta.get('training_snapshot_id') or '')})")
            print(f"  Evaluation baseline : {evaluation}  ({_snap_log(meta.get('evaluation_snapshot_id') or '')})")
            print('  Training ROC-AUC    : '
                  + (f'{self.baseline_roc_auc:.4f}' if self.baseline_roc_auc else '(not recorded in baseline.json)'))
            print(f'  Current window      : {run.window_label}')
            print(RULE)
        return run

    def performance_report(self, days: int = 7) -> Dict[str, Any]:
        """ModelPerformanceMonitor's daily report over the last `days` (Section 5.1)."""
        monitor = ModelPerformanceMonitor(
            athena_client=self.athena_client, alert_threshold=MIN_ROC_AUC_THRESHOLD, min_samples=MIN_SAMPLES,
        )
        report = monitor.generate_performance_report(
            endpoint_name=self.endpoint_name, days=days, window='D',
            # Judge each window against training-time ROC-AUC. With None the
            # monitor averages the windows it is judging, so every alert would
            # report "degradation: 0.0%".
            baseline_roc_auc=self.baseline_roc_auc,
        )
        monitor.print_report_summary(report)
        return report

    def data_drift(self, run: MonitoringRun, verbose: bool = True) -> Optional[Dict[str, Any]]:
        """Evidently DataDriftPreset: training baseline vs predictions in the run's window."""
        inf_raw = self.athena_client.execute_query(f"""
            SELECT input_features
            FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            WHERE endpoint_name = '{self.endpoint_name}'
              AND request_timestamp > {ts_literal(run.lower)}
              AND request_timestamp <= {ts_literal(run.run_ts)}
            LIMIT {INFERENCE_LIMIT}
        """)
        if verbose:
            print(f'Baseline : {self.training_source} ({len(self.training_baseline_df):,} rows)')
            print(f'Current  : {len(inf_raw):,} rows — {run.window_label}')
        if len(inf_raw) < MIN_SAMPLES:
            print(f'⚠ Data drift skipped — {len(inf_raw)} rows in window (need ≥ {MIN_SAMPLES}). '
                  'Send more predictions, then start a new run.')
            return None

        current_df = pd.DataFrame([
            {f: float(d.get(f, float('nan'))) for f in self.feature_names}
            for d in (json.loads(r) for r in inf_raw['input_features'])
        ]).dropna(how='all')
        baseline_df = self.training_baseline_df
        valid = [c for c in self.feature_names
                 if c in baseline_df.columns and baseline_df[c].notna().any()
                 and current_df[c].notna().any()]
        if verbose and len(valid) < len(self.feature_names):
            print(f'  ⚠ Dropping all-NaN columns: {sorted(set(self.feature_names) - set(valid))}')

        results = run_data_drift_report(baseline_df=baseline_df[valid], current_df=current_df[valid])
        results['features_analyzed'] = len(valid)
        results['sample_size'] = len(current_df)
        if verbose:
            print_data_drift_result(results)
        return results

    def _labelled(self, lower: datetime, upper: datetime) -> pd.DataFrame:
        return self.athena_client.execute_query(f"""
            SELECT prediction, {PROBABILITY_COLUMN}, ground_truth
            FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            WHERE endpoint_name = '{self.endpoint_name}'
              AND ground_truth IS NOT NULL
              AND request_timestamp > {ts_literal(lower)}
              AND request_timestamp <= {ts_literal(upper)}
        """)

    @staticmethod
    def _model_drift_usable(df: pd.DataFrame) -> Tuple[bool, str]:
        """Evidently needs both classes in target AND prediction."""
        if len(df) < MIN_SAMPLES:
            return False, f'only {len(df)} labelled rows (need ≥ {MIN_SAMPLES})'
        if df['ground_truth'].nunique() < 2:
            return False, 'ground truth is single-class'
        if (df[PROBABILITY_COLUMN] >= PREDICTION_THRESHOLD).nunique() < 2:
            return False, f'predictions are single-class at threshold {PREDICTION_THRESHOLD}'
        return True, ''

    def model_drift(
        self,
        run: MonitoringRun,
        widen_days: Optional[int] = None,
        verbose: bool = True,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """Classification metrics on the run's labelled predictions, plus an Evidently report.

        Metrics cover the run's window only, so consecutive runs are independent
        points on the model-drift trend. With widen_days set, a window too small
        to score is widened to the last widen_days instead of being skipped.

        Returns (metrics, model_report); either may be None if skipped.
        """
        gt_df = self._labelled(run.lower, run.run_ts)
        label = run.window_label
        usable, why = self._model_drift_usable(gt_df)
        if not usable and widen_days:
            print(f'⚠ Window unusable for model drift ({why}); widening to the last {widen_days} days.')
            gt_df = self._labelled(run.run_ts - timedelta(days=widen_days), run.run_ts)
            label = f'widened to last {widen_days} days'
            usable, why = self._model_drift_usable(gt_df)
        if verbose:
            print(f'Current  : {len(gt_df):,} labelled predictions — {label}')
        if not usable:
            print(f'⚠ Model drift skipped — {why}. Send more predictions and apply ground truth.')
            return None, None

        monitor = ModelPerformanceMonitor(
            athena_client=self.athena_client, alert_threshold=MIN_ROC_AUC_THRESHOLD, min_samples=MIN_SAMPLES,
        )
        metrics = monitor.calculate_performance_metrics(gt_df)

        model_report = None
        base = self.evaluation_baseline_df
        current_df = pd.DataFrame({
            'target': gt_df['ground_truth'].astype(int).values,
            'prediction': (gt_df[PROBABILITY_COLUMN] >= PREDICTION_THRESHOLD).astype(int).values,
        })
        if base is None:
            print('⚠ No baseline.json resolved — skipping the Evidently classification report.')
        elif all(col.nunique() >= 2 for col in (base['target'], base['prediction'],
                                                current_df['target'], current_df['prediction'])):
            # Only the two label columns — Evidently profiles every column it is given.
            model_report = run_classification_report(
                baseline_df=base[['target', 'prediction']], current_df=current_df,
                target_column='target', prediction_column='prediction',
            )

        if verbose:
            auc = metrics.get('roc_auc')
            print(f"  ROC-AUC   : {'n/a' if auc is None else f'{auc:.4f}'}"
                  + (f'  (training baseline {self.baseline_roc_auc:.4f})' if self.baseline_roc_auc else ''))
            print(f"  Precision : {metrics['precision']:.4f}   Recall: {metrics['recall']:.4f}   "
                  f"F1: {metrics['f1_score']:.4f}   Accuracy: {metrics['accuracy']:.4f}")
            print(f"  Confusion : TP={metrics['true_positives']}  FP={metrics['false_positives']}  "
                  f"FN={metrics['false_negatives']}  TN={metrics['true_negatives']}")
        return metrics, model_report

    def finish_run(
        self,
        run: MonitoringRun,
        drift_results: Optional[Dict[str, Any]],
        metrics: Optional[Dict[str, Any]],
        model_report: Optional[Dict[str, Any]] = None,
        log_to_mlflow: bool = True,
        verbose: bool = True,
    ) -> Dict[str, Any]:
        """Log the run to MLflow, write it to monitoring_responses, tag its inference rows."""
        mlflow_run_id = None
        if log_to_mlflow:
            result = log_monitoring_to_mlflow(
                drift_results=drift_results, model_report=model_report, overall_metrics=metrics,
                endpoint_name=self.endpoint_name, model_name=MLFLOW_MODEL_NAME, region=self.region,
            )
            mlflow_run_id = result.get('mlflow_run_id')
            if not result.get('success'):
                print(f"⚠ MLflow logging failed: {result.get('error', 'unknown')}")

        row = self._monitoring_row(run, drift_results, metrics, mlflow_run_id)
        values = [sql_val(row[c]) for c in MONITORING_COLUMNS]
        # Timestamps go in as TIMESTAMP literals, not strings.
        for col in ('monitoring_timestamp', 'created_at'):
            values[MONITORING_COLUMNS.index(col)] = ts_literal(run.run_ts)
        self.athena_client.execute_query(
            f"INSERT INTO {ATHENA_DATABASE}.{ATHENA_MONITORING_RESPONSES_TABLE} "
            f"({', '.join(MONITORING_COLUMNS)}) VALUES ({', '.join(values)})",
            return_results=False,
        )

        # Tag the predictions this run measured. Only untagged rows, so re-runs
        # are idempotent and, with a rolling window, overlapping rows keep the
        # id of the first run that measured them.
        self.athena_client.execute_query(f"""
            UPDATE {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            SET monitoring_run_id = '{run.monitoring_run_id}'
            WHERE endpoint_name = '{self.endpoint_name}'
              AND monitoring_run_id IS NULL
              AND request_timestamp > {ts_literal(run.lower)}
              AND request_timestamp <= {ts_literal(run.run_ts)}
        """, return_results=False)

        if verbose:
            print(f'✓ Wrote {run.monitoring_run_id} to {ATHENA_DATABASE}.{ATHENA_MONITORING_RESPONSES_TABLE}')
            print(f"  Data drift detected   : {row['data_drift_detected']}")
            print(f"  Model drift detected  : {row['model_drift_detected']}")
            print(f"  MLflow run            : {mlflow_run_id or '(not logged)'}")
        return row

    def _monitoring_row(
        self,
        run: MonitoringRun,
        drift_results: Optional[Dict[str, Any]],
        metrics: Optional[Dict[str, Any]],
        mlflow_run_id: Optional[str],
    ) -> Dict[str, Any]:
        """The monitoring_responses row for a run, keyed by column name."""
        drift_results = drift_results or {}
        # Persist magnitude as well as the raw score: Evidently picks the test
        # per column, so raw drift_score has opposite drift directions depending
        # on the test. Dashboards compare magnitude (test-agnostic, ≥ 1.0 = drift).
        per_feature = {
            col: {
                'score':     info.get('drift_score', 0),
                'magnitude': info.get('drift_magnitude', 0),
                'method':    info.get('method', ''),
                'threshold': info.get('threshold', 0),
            }
            for col, info in drift_results.get('per_column', {}).items()
        }

        current_auc = degrad = degrad_pct = mdrift = None
        baseline_auc = None
        metrics = metrics if metrics and 'error' not in metrics else {}
        if metrics:
            current_auc = metrics.get('roc_auc')
            baseline_auc = self.baseline_roc_auc
            if baseline_auc and current_auc is not None:
                degrad = baseline_auc - current_auc
                degrad_pct = degrad / baseline_auc * 100
            # Same verdict as ModelPerformanceMonitor's alert.
            mdrift = bool(current_auc is not None and current_auc < MIN_ROC_AUC_THRESHOLD)

        data_detected = bool(drift_results.get('drift_detected', False))
        mp_arn = self.baseline_meta.get('model_package_arn')
        return {
            'monitoring_run_id': run.monitoring_run_id,
            'monitoring_timestamp': run.run_ts,
            'endpoint_name': self.endpoint_name,
            'model_version': mp_arn.split('/')[-1] if mp_arn else 'latest',
            'model_package_arn': mp_arn,
            'evaluation_snapshot_id': self.baseline_meta.get('evaluation_snapshot_id') or None,
            'training_snapshot_id': self.baseline_meta.get('training_snapshot_id') or None,
            'data_drift_detected': data_detected,
            'drifted_columns_count': drift_results.get('drifted_columns_count', 0),
            'drifted_columns_share': drift_results.get('drifted_columns_share', 0.0),
            'features_analyzed': drift_results.get('features_analyzed', 0),
            'data_sample_size': drift_results.get('sample_size', 0),
            'model_drift_detected': mdrift,
            'baseline_roc_auc': baseline_auc,
            'current_roc_auc': current_auc,
            'roc_auc_degradation': degrad,
            'roc_auc_degradation_pct': degrad_pct,
            'accuracy': metrics.get('accuracy'),
            'precision': metrics.get('precision'),
            'recall': metrics.get('recall'),
            'f1_score': metrics.get('f1_score'),
            'model_sample_size': metrics.get('sample_count'),
            'per_feature_drift_scores': json.dumps(per_feature) if per_feature else None,
            'evidently_report_s3_path': None,
            'mlflow_run_id': mlflow_run_id,
            'alert_sent': bool(data_detected or mdrift),
            'detection_engine': 'evidently',
            'created_at': run.run_ts,
        }


def print_data_drift_result(drift_results: Dict[str, Any], top_n: int = 5) -> None:
    """Dataset verdict plus the top drifted features by drift_magnitude."""
    print(RULE)
    # The dataset verdict is a SHARE rule, not "any column drifted": a run can
    # show several drifted features and still report False.
    print(f"  Drift detected     : {drift_results['drift_detected']}"
          f"  (dataset drifts when the drifted share reaches {drift_results['drift_share_threshold']:.0%})")
    print(f"  Drifted features   : {drift_results['drifted_columns_count']} / {drift_results['features_analyzed']}"
          f" ({drift_results['drifted_columns_share']:.1%})")
    top = sorted(
        [(c, i) for c, i in drift_results.get('per_column', {}).items() if i.get('drifted')],
        key=lambda x: x[1].get('drift_magnitude', 0), reverse=True,
    )[:top_n]
    if top:
        print(f'  Top {len(top)} drifted      :')
        for c, info in top:
            print(f"    - {c:32s}  magnitude=×{info.get('drift_magnitude', 0):.1f}  "
                  f"(score={info.get('drift_score', 0):.4f}, method={info.get('method', '?')})")
    print(RULE)


def print_per_column_drift(drift_results: Dict[str, Any]) -> None:
    """Every feature, sorted by drift_magnitude (1.0 = at threshold, higher = more drifted)."""
    for c, info in sorted(drift_results.get('per_column', {}).items(),
                          key=lambda x: x[1].get('drift_magnitude', 0), reverse=True):
        status = '⚠ DRIFT' if info.get('drifted', False) else '✓ OK'
        print(f"    - {c:32s}  magnitude=×{info.get('drift_magnitude', 0):.1f}  "
              f"(score={info.get('drift_score', 0):.4f}, method={info.get('method', '?')})  [{status}]")
