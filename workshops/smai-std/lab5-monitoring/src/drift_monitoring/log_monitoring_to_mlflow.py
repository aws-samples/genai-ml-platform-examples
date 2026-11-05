#!/usr/bin/env python3
"""
Log monitoring results (Evidently reports) to MLflow.

This script logs:
- Overall performance metrics
- Data drift metrics and HTML report
- Classification metrics and HTML report
- Drift summary JSON artifact
"""

import sys
import os
import json
import tempfile
import re
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv


def log_monitoring_to_mlflow(
    drift_results=None,
    model_report=None,
    overall_metrics=None,
    endpoint_name=None,
    model_name=None,
    region='us-east-1'
):
    """
    Log monitoring results to MLflow.

    Args:
        drift_results: Dictionary with data drift results from Evidently
        model_report: Dictionary with classification report from Evidently
        overall_metrics: Dictionary with overall performance metrics
        endpoint_name: Name of the SageMaker endpoint
        model_name: MLflow model name for version lookup
        region: AWS region

    Returns:
        dict: Result with status and MLflow run info
    """

    # Load .env if available
    env_path = Path(__file__).parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)

    # Get MLflow configuration
    mlflow_uri = os.getenv('MLFLOW_TRACKING_URI')
    experiment_name = os.getenv('MLFLOW_EXPERIMENT_NAME', 'bank-marketing-prediction')
    if model_name is None:
        model_name = os.getenv('MLFLOW_MODEL_NAME', 'bank-prediction-XGBoostModel')

    if not mlflow_uri:
        return {
            'success': False,
            'error': 'MLFLOW_TRACKING_URI not set. Set it in .env to enable MLflow logging.',
            'mlflow_run_id': None
        }

    try:
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(mlflow_uri)
        mlflow.set_experiment(experiment_name)

        print("╔════════════════════════════════════════════════════════════════════╗")
        print("║  Logging Monitoring Results to MLflow                             ║")
        print("╚════════════════════════════════════════════════════════════════════╝")
        print("")
        print(f"  Tracking URI: {mlflow_uri}")
        print(f"  Experiment: {experiment_name}")
        print(f"  Model: {model_name}")
        print("")

        with mlflow.start_run(run_name=f'monitoring-{datetime.utcnow().strftime("%Y%m%d-%H%M")}') as mlflow_run:
            mlflow_run_id = mlflow_run.info.run_id
            print(f"[1/5] Started MLflow run: {mlflow_run_id}")

            # Look up latest model version from registry
            model_version = 'unknown'
            try:
                client = MlflowClient()
                versions = client.search_model_versions(f"name='{model_name}'")
                if versions:
                    model_version = max(versions, key=lambda v: int(v.version)).version
                    print(f"  ✓ Found model version: {model_version}")
            except Exception as e:
                print(f"  ⚠ Could not lookup model version: {e}")

            mlflow.log_param('model_version', model_version)
            mlflow.log_param('detection_engine', 'evidently')
            mlflow.log_param('endpoint_name', endpoint_name)

            # --- Log overall performance metrics ---
            print("\n[2/5] Logging overall performance metrics...")
            if overall_metrics and isinstance(overall_metrics, dict) and 'error' not in overall_metrics:
                logged_count = 0
                for k, v in overall_metrics.items():
                    if isinstance(v, (int, float)) and v is not None:
                        mlflow.log_metric(f'monitor_{k}', v)
                        logged_count += 1
                print(f"  ✓ Logged {logged_count} performance metrics")
            else:
                print("  ⚠ No overall metrics to log")

            # --- Log Evidently data drift metrics + HTML report ---
            print("\n[3/5] Logging data drift results...")
            if drift_results and isinstance(drift_results, dict):
                detected = drift_results.get('drift_detected')
                if detected is not None:
                    mlflow.log_metric('drift_detected', 1 if detected else 0)
                drifted_count = drift_results.get('drifted_columns_count')
                if isinstance(drifted_count, (int, float)):
                    mlflow.log_metric('drifted_columns_count', drifted_count)
                drifted_share = drift_results.get('drifted_columns_share')
                if isinstance(drifted_share, (int, float)):
                    mlflow.log_metric('drifted_columns_share', drifted_share)

                # Log only available finite values. Missing feature evidence stays
                # absent in MLflow, matching the NULL persisted for Athena/QuickSight.
                per_column_count = 0
                for col, info in drift_results.get('per_column', {}).items():
                    raw_score = info.get('drift_score')
                    magnitude = info.get('drift_magnitude')
                    if isinstance(raw_score, (int, float)):
                        mlflow.log_metric(f'drift_score_{col}', raw_score)
                    if isinstance(magnitude, (int, float)):
                        mlflow.log_metric(f'drift_magnitude_{col}', magnitude)
                    if raw_score is not None or magnitude is not None:
                        per_column_count += 1

                print(f"  ✓ Logged drift metrics (drifted: {drift_results.get('drifted_columns_count', 0)})")
                print(f"  ✓ Logged {per_column_count} per-column drift scores")

                # Save Evidently data drift HTML report as artifact
                snapshot = drift_results.get('snapshot')
                if snapshot:
                    tmp = tempfile.NamedTemporaryFile(suffix='.html', prefix='data_drift_', delete=False)
                    try:
                        snapshot.save_html(tmp.name)
                        tmp.close()
                        mlflow.log_artifact(tmp.name, 'evidently_reports')
                        print(f"  ✓ Logged Evidently data drift HTML report")
                    finally:
                        if os.path.exists(tmp.name):
                            os.unlink(tmp.name)
            else:
                print("  ⚠ No data drift results to log")

            # --- Log Evidently classification report + model drift metrics ---
            print("\n[4/5] Logging classification/model drift report...")
            if model_report and isinstance(model_report, dict):
                # Log classification metrics from Evidently
                metric_count = 0
                for m in model_report.get('metrics', []):
                    name = m.get('metric_name', '')
                    value = m.get('value')
                    if isinstance(value, (int, float)):
                        # Strip parenthesized args and sanitize for MLflow
                        safe_name = re.sub(r'\([^)]*\)', '', name)
                        safe_name = safe_name.replace('::', '_').replace(' ', '_').lower().strip('_')
                        safe_name = re.sub(r'[^a-z0-9_\-\. /:]', '', safe_name)
                        if safe_name:
                            mlflow.log_metric(f'evidently_{safe_name}', value)
                            metric_count += 1

                print(f"  ✓ Logged {metric_count} classification metrics")

                # Save Evidently classification HTML report as artifact
                snapshot = model_report.get('snapshot')
                if snapshot:
                    tmp = tempfile.NamedTemporaryFile(suffix='.html', prefix='classification_', delete=False)
                    try:
                        snapshot.save_html(tmp.name)
                        tmp.close()
                        mlflow.log_artifact(tmp.name, 'evidently_reports')
                        print(f"  ✓ Logged Evidently classification HTML report")
                    finally:
                        if os.path.exists(tmp.name):
                            os.unlink(tmp.name)
            else:
                print("  ⚠ No classification report to log")

            # --- Log drift summary JSON artifact ---
            print("\n[5/5] Logging drift summary JSON...")
            summary = {
                'timestamp': datetime.utcnow().isoformat(),
                'detection_engine': 'evidently',
                'endpoint_name': endpoint_name,
                'model_version': model_version,
                'data_drift': {
                    'detected': drift_results.get('drift_detected') if drift_results else None,
                    'drifted_columns_count': drift_results.get('drifted_columns_count', 0) if drift_results else 0,
                    'drifted_columns_share': drift_results.get('drifted_columns_share', 0) if drift_results else 0,
                },
                'has_classification_report': bool(model_report),
                'has_overall_metrics': bool(overall_metrics),
            }

            tmp_json = tempfile.NamedTemporaryFile(mode='w', suffix='.json', prefix='drift_summary_', delete=False)
            try:
                json.dump(summary, tmp_json, indent=2, default=str)
                tmp_json.close()
                mlflow.log_artifact(tmp_json.name, 'drift_reports')
                print(f"  ✓ Logged drift summary JSON")
            finally:
                if os.path.exists(tmp_json.name):
                    os.unlink(tmp_json.name)

            # Tags
            mlflow.set_tags({
                'pipeline_step': 'monitoring',
                'endpoint_name': endpoint_name,
                'detection_engine': 'evidently',
                'model_name': model_name,
            })

            print("")
            print("╔════════════════════════════════════════════════════════════════════╗")
            print("║  ✅ MLFLOW LOGGING COMPLETE                                        ║")
            print("╚════════════════════════════════════════════════════════════════════╝")
            print("")
            print(f"  MLflow Run ID: {mlflow_run_id}")
            print(f"  View in MLflow UI: {mlflow_uri}")
            print("")

            return {
                'success': True,
                'mlflow_run_id': mlflow_run_id,
                'mlflow_tracking_uri': mlflow_uri,
                'experiment_name': experiment_name
            }

    except ImportError:
        return {
            'success': False,
            'error': 'MLflow not installed. Install with: pip install mlflow',
            'mlflow_run_id': None
        }
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"\n❌ Error logging to MLflow: {e}")
        print(error_details)
        return {
            'success': False,
            'error': str(e),
            'error_details': error_details,
            'mlflow_run_id': None
        }


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Log monitoring results to MLflow')
    parser.add_argument('--drift-json', help='Path to drift results JSON file')
    parser.add_argument('--model-json', help='Path to model report JSON file')
    parser.add_argument('--metrics-json', help='Path to overall metrics JSON file')
    parser.add_argument('--endpoint', default='bank-marketing-endpoint', help='Endpoint name')
    parser.add_argument('--model-name', help='MLflow model name')
    parser.add_argument('--region', default='us-east-1', help='AWS region')

    args = parser.parse_args()

    # Load JSON files if provided
    drift_results = None
    if args.drift_json and os.path.exists(args.drift_json):
        with open(args.drift_json, 'r') as f:
            drift_results = json.load(f)

    model_report = None
    if args.model_json and os.path.exists(args.model_json):
        with open(args.model_json, 'r') as f:
            model_report = json.load(f)

    overall_metrics = None
    if args.metrics_json and os.path.exists(args.metrics_json):
        with open(args.metrics_json, 'r') as f:
            overall_metrics = json.load(f)

    if not any([drift_results, model_report, overall_metrics]):
        print("❌ No monitoring data provided. Use --drift-json, --model-json, or --metrics-json")
        sys.exit(1)

    result = log_monitoring_to_mlflow(
        drift_results=drift_results,
        model_report=model_report,
        overall_metrics=overall_metrics,
        endpoint_name=args.endpoint,
        model_name=args.model_name,
        region=args.region
    )

    sys.exit(0 if result['success'] else 1)
