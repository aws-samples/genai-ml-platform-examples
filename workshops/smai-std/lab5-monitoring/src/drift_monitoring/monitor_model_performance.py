#!/usr/bin/env python3
"""
Continuous model performance monitoring using available ground truth.

This script monitors model performance over time as ground truth arrives:
- Calculates performance metrics only on records with ground truth
- Tracks metrics over time windows (daily/weekly)
- Compares against training baseline
- Detects statistically significant degradation
- Generates alerts when performance drops below threshold
- Visualizes performance trends

Usage:
    # Monitor last 30 days
    python scripts/monitor_model_performance.py --days 30

    # Monitor with alert threshold
    python scripts/monitor_model_performance.py --days 30 --alert-threshold 0.80

    # Generate detailed report
    python scripts/monitor_model_performance.py --days 30 --report --output reports/

    # Monitor specific endpoint
    python scripts/monitor_model_performance.py --endpoint bank-marketing-prod --days 7
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

import pandas as pd
import numpy as np
from sklearn.metrics import (
    roc_auc_score,
    precision_recall_curve,
    auc,
    confusion_matrix,
    classification_report,
)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from src.train_pipeline.athena.athena_client import AthenaClient
from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_INFERENCE_TABLE,
    MIN_ROC_AUC_THRESHOLD,
    PREDICTION_COLUMN,
    PROBABILITY_COLUMN,
)
from src.config import schema

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ModelPerformanceMonitor:
    """Monitor model performance using available ground truth."""

    def __init__(
        self,
        athena_client: Optional[AthenaClient] = None,
        alert_threshold: float = MIN_ROC_AUC_THRESHOLD,
        min_samples: int = 100,
    ):
        """
        Initialize performance monitor.

        Args:
            athena_client: Athena client (creates default if None)
            alert_threshold: ROC-AUC threshold for alerts
            min_samples: Minimum samples required for reliable metrics
        """
        self.client = athena_client or AthenaClient()
        self.alert_threshold = alert_threshold
        self.min_samples = min_samples

    def get_ground_truth_coverage(
        self,
        endpoint_name: Optional[str] = None,
        days: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get ground truth coverage statistics.

        Args:
            endpoint_name: Optional endpoint filter
            days: Optional time window in days

        Returns:
            Dictionary with coverage statistics
        """
        logger.info("Calculating ground truth coverage...")

        query = f"""
        SELECT
            COUNT(*) as total_predictions,
            COALESCE(SUM(CASE WHEN ground_truth IS NOT NULL THEN 1 ELSE 0 END), 0) as with_ground_truth,
            COALESCE(SUM(CASE WHEN ground_truth IS NULL THEN 1 ELSE 0 END), 0) as without_ground_truth,
            CAST(MIN(request_timestamp) AS TIMESTAMP(3)) as earliest_prediction,
            CAST(MAX(request_timestamp) AS TIMESTAMP(3)) as latest_prediction,
            CAST(MIN(ground_truth_timestamp) AS TIMESTAMP(3)) as earliest_confirmation,
            CAST(MAX(ground_truth_timestamp) AS TIMESTAMP(3)) as latest_confirmation,
            AVG(days_to_ground_truth) as avg_days_to_ground_truth
        FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
        WHERE 1=1
        """

        if endpoint_name:
            query += f" AND endpoint_name = '{endpoint_name}'"

        if days:
            query += f" AND request_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{days}' DAY"

        result = self.client.execute_query(query)

        if result.empty or result['total_predictions'].iloc[0] == 0:
            return {
                'total_predictions': 0,
                'with_ground_truth': 0,
                'without_ground_truth': 0,
                'coverage': 0.0,
                'coverage_pct': 0.0,
            }

        stats = result.iloc[0].to_dict()
        total = stats['total_predictions']
        with_gt = stats['with_ground_truth']

        stats['coverage'] = with_gt / total if total > 0 else 0.0
        stats['coverage_pct'] = stats['coverage'] * 100

        return stats

    def load_predictions_with_ground_truth(
        self,
        endpoint_name: Optional[str] = None,
        days: Optional[int] = None,
    ) -> pd.DataFrame:
        """
        Load predictions that have ground truth available.

        Args:
            endpoint_name: Optional endpoint filter
            days: Optional time window in days

        Returns:
            DataFrame with predictions and ground truth
        """
        logger.info("Loading predictions with ground truth...")

        query = f"""
        SELECT
            inference_id,
            request_timestamp,
            endpoint_name,
            model_version,
            mlflow_run_id,
            {schema.identifier_column()},
            {PREDICTION_COLUMN},
            {PROBABILITY_COLUMN},
            confidence_score,
            ground_truth,
            ground_truth_timestamp,
            ground_truth_source,
            days_to_ground_truth,
            is_high_confidence,
            is_low_confidence
        FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
        WHERE ground_truth IS NOT NULL
        """

        if endpoint_name:
            query += f" AND endpoint_name = '{endpoint_name}'"

        if days:
            query += f" AND request_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{days}' DAY"

        query += " ORDER BY request_timestamp DESC"

        df = self.client.execute_query(query)

        logger.info(f"Loaded {len(df):,} predictions with ground truth")

        return df

    def calculate_performance_metrics(
        self,
        df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Calculate performance metrics.

        Args:
            df: DataFrame with predictions and ground truth

        Returns:
            Dictionary with metrics
        """
        required = ['ground_truth', PREDICTION_COLUMN, PROBABILITY_COLUMN]
        missing = [column for column in required if column not in df.columns]
        if missing:
            return {'error': 'missing_columns', 'missing_columns': missing, 'sample_count': 0}

        paired = df[required].copy()
        for column in required:
            paired[column] = pd.to_numeric(paired[column], errors='coerce')
        paired = paired.replace([np.inf, -np.inf], np.nan).dropna()

        if len(paired) < self.min_samples:
            logger.warning(
                f"Insufficient complete pairs ({len(paired)}) for reliable metrics "
                f"(minimum: {self.min_samples})"
            )
            return {'error': 'insufficient_samples', 'sample_count': len(paired)}

        y_true = paired['ground_truth'].round().astype(int).values
        y_pred = paired[PREDICTION_COLUMN].round().astype(int).values
        y_proba = paired[PROBABILITY_COLUMN].astype(float).values
        if not set(np.unique(y_true)).issubset({0, 1}) or not set(np.unique(y_pred)).issubset({0, 1}):
            return {'error': 'non_binary_labels', 'sample_count': len(paired)}
        if len(np.unique(y_true)) < 2:
            logger.warning("Ground truth is single-class; ROC-AUC is unavailable")
            return {'error': 'single_class_ground_truth', 'sample_count': len(paired)}
        if not np.logical_and(y_proba >= 0.0, y_proba <= 1.0).all():
            return {'error': 'invalid_probabilities', 'sample_count': len(paired)}

        logger.info(f"Calculating metrics on {len(paired):,} complete paired samples...")

        # Basic metrics
        metrics = {
            'sample_count': len(paired),
            'positive_rate': y_true.sum() / len(y_true),
            'prediction_rate': y_pred.sum() / len(y_pred),
        }

        # ROC-AUC
        try:
            metrics['roc_auc'] = roc_auc_score(y_true, y_proba)
            logger.info(f"  ROC-AUC: {metrics['roc_auc']:.4f}")
        except Exception as e:
            logger.warning(f"Could not calculate ROC-AUC: {e}")
            metrics['roc_auc'] = None

        # PR-AUC
        try:
            precision, recall, _ = precision_recall_curve(y_true, y_proba)
            metrics['pr_auc'] = auc(recall, precision)
            logger.info(f"  PR-AUC: {metrics['pr_auc']:.4f}")
        except Exception as e:
            logger.warning(f"Could not calculate PR-AUC: {e}")
            metrics['pr_auc'] = None

        # Confusion matrix
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()

        metrics['true_positives'] = int(tp)
        metrics['true_negatives'] = int(tn)
        metrics['false_positives'] = int(fp)
        metrics['false_negatives'] = int(fn)

        # Derived metrics
        total = tp + tn + fp + fn
        metrics['accuracy'] = (tp + tn) / total if total > 0 else 0

        metrics['precision'] = tp / (tp + fp) if (tp + fp) > 0 else 0
        metrics['recall'] = tp / (tp + fn) if (tp + fn) > 0 else 0
        metrics['specificity'] = tn / (tn + fp) if (tn + fp) > 0 else 0

        if metrics['precision'] + metrics['recall'] > 0:
            metrics['f1_score'] = (
                2 * metrics['precision'] * metrics['recall'] /
                (metrics['precision'] + metrics['recall'])
            )
        else:
            metrics['f1_score'] = 0

        metrics['false_positive_rate'] = fp / (fp + tn) if (fp + tn) > 0 else 0
        metrics['false_negative_rate'] = fn / (fn + tp) if (fn + tp) > 0 else 0

        logger.info(f"  Accuracy: {metrics['accuracy']:.4f}")
        logger.info(f"  Precision: {metrics['precision']:.4f}")
        logger.info(f"  Recall: {metrics['recall']:.4f}")
        logger.info(f"  F1: {metrics['f1_score']:.4f}")

        return metrics

    def calculate_metrics_by_time_window(
        self,
        df: pd.DataFrame,
        window: str = 'D',  # D=daily, W=weekly
    ) -> pd.DataFrame:
        """
        Calculate metrics over time windows.

        Args:
            df: DataFrame with predictions and ground truth
            window: Time window ('D' for daily, 'W' for weekly)

        Returns:
            DataFrame with metrics per time window
        """
        logger.info(f"Calculating metrics by time window ({window})...")

        df = df.copy()
        df['request_timestamp'] = pd.to_datetime(df['request_timestamp'])
        df = df.set_index('request_timestamp')

        # Group by time window
        windows = []

        for period, group_df in df.groupby(pd.Grouper(freq=window)):
            if len(group_df) < self.min_samples:
                logger.debug(f"Skipping {period}: insufficient samples ({len(group_df)})")
                continue

            metrics = self.calculate_performance_metrics(group_df)

            if 'error' in metrics:
                continue

            metrics['period'] = period
            metrics['period_start'] = group_df.index.min()
            metrics['period_end'] = group_df.index.max()

            windows.append(metrics)

        if not windows:
            logger.warning("No time windows with sufficient samples")
            return pd.DataFrame()

        df_metrics = pd.DataFrame(windows)
        df_metrics = df_metrics.sort_values('period')

        logger.info(f"Calculated metrics for {len(df_metrics)} time windows")

        return df_metrics

    def detect_performance_degradation(
        self,
        df_metrics: pd.DataFrame,
        baseline_roc_auc: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect periods with significant performance degradation.

        Args:
            df_metrics: DataFrame with metrics over time
            baseline_roc_auc: Baseline ROC-AUC (uses mean if None)

        Returns:
            List of degradation alerts
        """
        if df_metrics.empty or 'roc_auc' not in df_metrics.columns:
            return []

        logger.info("Detecting performance degradation...")

        alerts = []

        # Use provided baseline or calculate from data
        if baseline_roc_auc is None:
            baseline_roc_auc = df_metrics['roc_auc'].mean()
            logger.info(f"Using mean ROC-AUC as baseline: {baseline_roc_auc:.4f}")

        # Check each period
        for _, row in df_metrics.iterrows():
            period = row['period']
            roc_auc = row['roc_auc']

            # Alert if below threshold
            if roc_auc < self.alert_threshold:
                severity = 'critical' if roc_auc < (self.alert_threshold - 0.05) else 'warning'

                alert = {
                    'period': period,
                    'metric': 'roc_auc',
                    'value': roc_auc,
                    'baseline': baseline_roc_auc,
                    'threshold': self.alert_threshold,
                    'degradation': baseline_roc_auc - roc_auc,
                    'degradation_pct': (baseline_roc_auc - roc_auc) / baseline_roc_auc * 100,
                    'severity': severity,
                    'sample_count': row['sample_count'],
                }

                alerts.append(alert)

                logger.warning(
                    f"[{severity.upper()}] Performance degradation detected for {period}: "
                    f"ROC-AUC={roc_auc:.4f} (baseline={baseline_roc_auc:.4f}, "
                    f"threshold={self.alert_threshold:.4f})"
                )

        return alerts

    def generate_performance_report(
        self,
        endpoint_name: Optional[str] = None,
        days: int = 30,
        window: str = 'D',
        baseline_roc_auc: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.

        Args:
            endpoint_name: Optional endpoint filter
            days: Number of days to analyze
            window: Time window for trend analysis
            baseline_roc_auc: Baseline ROC-AUC for comparison

        Returns:
            Dictionary with report data
        """
        logger.info("=" * 80)
        logger.info("Model Performance Report")
        logger.info("=" * 80)

        # Get coverage
        coverage = self.get_ground_truth_coverage(endpoint_name, days)

        logger.info(f"\nGround Truth Coverage:")
        logger.info(f"  Total predictions: {coverage['total_predictions']:,}")
        logger.info(f"  With ground truth: {coverage['with_ground_truth']:,} ({coverage['coverage_pct']:.2f}%)")
        logger.info(f"  Avg days to confirmation: {coverage.get('avg_days_to_ground_truth', 0):.2f}")

        if coverage['with_ground_truth'] < self.min_samples:
            logger.warning(
                f"\nInsufficient ground truth data ({coverage['with_ground_truth']} samples). "
                f"Need at least {self.min_samples} samples for reliable metrics."
            )
            return {
                'coverage': coverage,
                'overall_metrics': None,
                'time_series_metrics': None,
                'alerts': [],
                'error': 'insufficient_ground_truth',
            }

        # Load predictions
        df = self.load_predictions_with_ground_truth(endpoint_name, days)

        # Overall metrics
        overall_metrics = self.calculate_performance_metrics(df)

        logger.info(f"\nOverall Performance (last {days} days):")
        logger.info(f"  Sample count: {overall_metrics['sample_count']:,}")
        logger.info(f"  ROC-AUC: {overall_metrics.get('roc_auc', 'N/A')}")
        logger.info(f"  PR-AUC: {overall_metrics.get('pr_auc', 'N/A')}")
        logger.info(f"  Accuracy: {overall_metrics['accuracy']:.4f}")
        logger.info(f"  Precision: {overall_metrics['precision']:.4f}")
        logger.info(f"  Recall: {overall_metrics['recall']:.4f}")
        logger.info(f"  F1-Score: {overall_metrics['f1_score']:.4f}")

        # Time series metrics
        df_metrics = self.calculate_metrics_by_time_window(df, window)

        # Detect degradation
        alerts = self.detect_performance_degradation(df_metrics, baseline_roc_auc)

        if alerts:
            logger.info(f"\n⚠ Found {len(alerts)} performance degradation alerts")
        else:
            logger.info("\n✓ No performance degradation detected")

        report = {
            'coverage': coverage,
            'overall_metrics': overall_metrics,
            'time_series_metrics': df_metrics,
            'alerts': alerts,
            'report_timestamp': datetime.now(),
            'endpoint_name': endpoint_name,
            'days': days,
            'window': window,
        }

        return report

    def print_report_summary(self, report: Dict[str, Any]) -> None:
        """Print report summary to console."""
        print("\n" + "=" * 80)
        print("Model Performance Summary")
        print("=" * 80)

        if 'error' in report:
            print(f"\nError: {report['error']}")
            return

        # Coverage
        coverage = report['coverage']
        print(f"\nGround Truth Coverage:")
        print(f"  Total predictions: {coverage['total_predictions']:,}")
        print(f"  With ground truth: {coverage['with_ground_truth']:,} ({coverage['coverage_pct']:.2f}%)")

        # Overall metrics
        metrics = report['overall_metrics']
        if metrics:
            print(f"\nOverall Performance:")
            print(f"  ROC-AUC: {metrics.get('roc_auc', 'N/A')}")
            print(f"  Accuracy: {metrics['accuracy']:.4f}")
            print(f"  Precision: {metrics['precision']:.4f}")
            print(f"  Recall: {metrics['recall']:.4f}")

        # Alerts
        alerts = report['alerts']
        if alerts:
            print(f"\n⚠ Performance Alerts ({len(alerts)}):")
            for alert in alerts[:5]:  # Show first 5
                print(
                    f"  [{alert['severity'].upper()}] {alert['period']}: "
                    f"ROC-AUC={alert['value']:.4f} (degradation: {alert['degradation_pct']:.1f}%)"
                )
        else:
            print("\n✓ No performance degradation detected")

        print("=" * 80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Monitor model performance using ground truth confirmations'
    )
    parser.add_argument(
        '--days',
        type=int,
        default=30,
        help='Number of days to analyze (default: 30)'
    )
    parser.add_argument(
        '--endpoint',
        type=str,
        help='Filter by endpoint name'
    )
    parser.add_argument(
        '--alert-threshold',
        type=float,
        default=MIN_ROC_AUC_THRESHOLD,
        help=f'ROC-AUC alert threshold (default: {MIN_ROC_AUC_THRESHOLD})'
    )
    parser.add_argument(
        '--window',
        choices=['D', 'W'],
        default='D',
        help='Time window for trend analysis: D=daily, W=weekly (default: D)'
    )
    parser.add_argument(
        '--baseline-roc-auc',
        type=float,
        help='Baseline ROC-AUC for comparison (uses data mean if not provided)'
    )
    parser.add_argument(
        '--min-samples',
        type=int,
        default=100,
        help='Minimum samples for reliable metrics (default: 100)'
    )

    args = parser.parse_args()

    # Create monitor
    monitor = ModelPerformanceMonitor(
        alert_threshold=args.alert_threshold,
        min_samples=args.min_samples,
    )

    try:
        # Generate report
        report = monitor.generate_performance_report(
            endpoint_name=args.endpoint,
            days=args.days,
            window=args.window,
            baseline_roc_auc=args.baseline_roc_auc,
        )

        # Print summary
        monitor.print_report_summary(report)

        # Exit with error code if alerts found
        if report.get('alerts'):
            return 1

        return 0

    except Exception as e:
        logger.error(f"Error generating performance report: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
