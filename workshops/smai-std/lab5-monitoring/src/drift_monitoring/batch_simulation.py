"""
Multi-batch drift simulation: one monitoring run per batch of traffic.

Lab 5D Sections 2-5 walk through a single monitoring pass. This module repeats
that pass in a loop (Lab 5D Section 6) using the same MonitoringSession methods,
so every batch writes exactly the row a single pass writes. Each batch:

  1. builds a drifted sample at the batch's intensity
     (drift_simulation.batches[i].intensity × drift_generation.default_drift)
  2. sends it to the endpoint and waits until the rows land in
     inference_responses (SQS → Lambda → Athena)
  3. simulates ground truth at the batch's gt_accuracy and merges it
  4. computes data drift and model drift over the configured drift window
  5. logs to MLflow, INSERTs one row into monitoring_responses, and tags the
     measured inference rows with the run's monitoring_run_id

N batches → N rows in monitoring_responses → N points on every trend visual of
the Lab 5E governance dashboard. No table or column is added or renamed.
"""

import json
from typing import Any, Dict, List, Optional

import pandas as pd

from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_INFERENCE_TABLE,
    ATHENA_MONITORING_RESPONSES_TABLE,
    DRIFT_SIM_ROWS_PER_BATCH,
)
from src.drift_monitoring.generate_drift_dataset import build_drifted_sample, load_original_dataset
from src.drift_monitoring.monitoring_run import MonitoringSession, utcnow

# Batch i samples with seed DRIFT_SEED_BASE + i and labels with GT_SEED_BASE + i,
# so every batch gets different rows and label flips, and reruns are repeatable.
DRIFT_SEED_BASE = 1000
GT_SEED_BASE = 42


class BatchSimulation:
    """Run drift_simulation.batches against a MonitoringSession."""

    def __init__(self, session: MonitoringSession, rows_per_batch: int = DRIFT_SIM_ROWS_PER_BATCH):
        self.session = session
        self.rows_per_batch = rows_per_batch
        self.results: List[Dict[str, Any]] = []
        self._source_df: Optional[pd.DataFrame] = None

    @property
    def source_df(self) -> pd.DataFrame:
        """Rows the drifted samples are drawn from (training_data, loaded once)."""
        if self._source_df is None:
            df, source = load_original_dataset()
            features = self.session.feature_names
            df = df.copy()
            for col in features:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            self._source_df = df.dropna(subset=features, how='any')
            print(f'Drift source rows   : {len(self._source_df):,} from {source}')
        return self._source_df

    def run_batch(
        self,
        batch_index: int,
        intensity: float,
        gt_accuracy: float,
        log_to_mlflow: bool = True,
    ) -> Dict[str, Any]:
        """Send one batch, label it, measure drift over the window, write the run."""
        s = self.session
        print(f'\n━━ Batch {batch_index}: intensity={intensity}, gt_accuracy={gt_accuracy} ━━')

        batch_start = utcnow()
        sample = build_drifted_sample(
            self.source_df, self.rows_per_batch, intensity=intensity,
            seed=DRIFT_SEED_BASE + batch_index,
        )
        sent = s.send(sample, verbose=False)
        landed = s.wait_for_rows(batch_start, expected=sent['sent'])
        print(f"    Sent {sent['sent']}/{len(sample)} ({sent['errors']} errors), "
              f'{landed} landed in {ATHENA_INFERENCE_TABLE}')

        gt = s.apply_ground_truth(gt_accuracy, seed=GT_SEED_BASE + batch_index, verbose=False)
        print(f"    Labelled {gt['total_predictions']} predictions")

        run = s.start_run(suffix=f'-b{batch_index}', verbose=False)
        print(f'    Window: {run.window_label}')
        drift_results = s.data_drift(run, verbose=False)
        metrics, model_report = s.model_drift(run, verbose=False)
        row = s.finish_run(run, drift_results, metrics, model_report,
                           log_to_mlflow=log_to_mlflow, verbose=False)

        per_feature = json.loads(row['per_feature_drift_scores'] or '{}')
        top = max(per_feature.items(), key=lambda kv: kv[1]['magnitude'], default=(None, {}))
        summary = {
            'batch_index': batch_index,
            'intensity': intensity,
            'gt_accuracy': gt_accuracy,
            'monitoring_run_id': row['monitoring_run_id'],
            'monitoring_timestamp': row['monitoring_timestamp'],
            'window': run.window_label,
            'data_sample_size': row['data_sample_size'],
            'drifted_columns_share': row['drifted_columns_share'],
            'data_drift_detected': row['data_drift_detected'],
            'top_feature': top[0],
            'top_feature_magnitude': top[1].get('magnitude'),
            'model_sample_size': row['model_sample_size'],
            'current_roc_auc': row['current_roc_auc'],
            'roc_auc_degradation_pct': row['roc_auc_degradation_pct'],
            'model_drift_detected': row['model_drift_detected'],
        }
        self.results.append(summary)

        auc = summary['current_roc_auc']
        print(f"    ✓ {row['monitoring_run_id']}: drift share={summary['drifted_columns_share']:.0%}, "
              f"top feature={summary['top_feature']} ×{summary['top_feature_magnitude'] or 0:.1f}, "
              f"ROC-AUC={'n/a' if auc is None else f'{auc:.3f}'}")
        return summary

    def run(self, batches: List[Dict[str, Any]], log_to_mlflow: bool = True) -> pd.DataFrame:
        """Run every batch in order and return one summary row per monitoring run."""
        for i, batch in enumerate(batches):
            self.run_batch(
                i,
                intensity=float(batch.get('intensity', 1.0)),
                gt_accuracy=float(batch.get('gt_accuracy', 0.85)),
                log_to_mlflow=log_to_mlflow,
            )
        return pd.DataFrame(self.results)


def print_schedule(batches: List[Dict[str, Any]]) -> None:
    print('Batch schedule:')
    for i, b in enumerate(batches):
        print(f"  {i}: intensity={b['intensity']:<5}  gt_accuracy={b['gt_accuracy']}")


def load_trend(session: MonitoringSession) -> Dict[str, pd.DataFrame]:
    """Every monitoring run for the endpoint, plus per-feature magnitudes per run.

    Unpacks per_feature_drift_scores the same way the feature_drift_detail
    Athena view does, so these are the values the Lab 5E dashboard charts.
    """
    runs = session.athena_client.execute_query(f"""
        SELECT monitoring_run_id, monitoring_timestamp, drifted_columns_share,
               current_roc_auc, baseline_roc_auc, per_feature_drift_scores
        FROM {ATHENA_DATABASE}.{ATHENA_MONITORING_RESPONSES_TABLE}
        WHERE endpoint_name = '{session.endpoint_name}'
        ORDER BY monitoring_timestamp
    """)
    runs['monitoring_timestamp'] = pd.to_datetime(runs['monitoring_timestamp'])

    feat_rows = []
    for _, r in runs.dropna(subset=['per_feature_drift_scores']).iterrows():
        for feat, info in json.loads(r['per_feature_drift_scores']).items():
            mag = info.get('magnitude') if isinstance(info, dict) else info
            feat_rows.append({'monitoring_timestamp': r['monitoring_timestamp'],
                              'feature': feat, 'magnitude': mag})
    return {'runs': runs, 'features': pd.DataFrame(feat_rows)}


def plot_trend(session: MonitoringSession, top_features: int = 6) -> pd.DataFrame:
    """Plot data-, feature- and model-drift trends across every run for the endpoint."""
    import matplotlib.pyplot as plt

    trend = load_trend(session)
    runs, feat_df = trend['runs'], trend['features']

    fig, axes = plt.subplots(1, 3, figsize=(18, 4.5))

    axes[0].plot(runs['monitoring_timestamp'], runs['drifted_columns_share'], marker='o')
    axes[0].set_title('Data drift — drifted feature share')
    axes[0].set_ylim(0, 1)

    if not feat_df.empty:
        for feat in feat_df.groupby('feature')['magnitude'].max().nlargest(top_features).index:
            f = feat_df[feat_df['feature'] == feat]
            axes[1].plot(f['monitoring_timestamp'], f['magnitude'], marker='o', label=feat)
        axes[1].axhline(1.0, color='grey', linestyle='--', linewidth=1)
        axes[1].legend(fontsize=8)
    axes[1].set_title('Feature drift — magnitude (≥ 1 = drifted)')

    axes[2].plot(runs['monitoring_timestamp'], runs['current_roc_auc'], marker='o', label='current')
    axes[2].plot(runs['monitoring_timestamp'], runs['baseline_roc_auc'], linestyle='--', label='baseline')
    axes[2].set_title('Model drift — ROC-AUC')
    axes[2].legend(fontsize=8)

    for ax in axes:
        ax.tick_params(axis='x', rotation=30)
    plt.tight_layout()
    plt.show()
    print(f'{len(runs)} monitoring runs for {session.endpoint_name}. '
          'Open / refresh the Lab 5E dashboard to see them.')
    return runs
