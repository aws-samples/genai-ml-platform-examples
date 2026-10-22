"""
Lab 5F SHAP analysis steps, one function per notebook section.

The low-level SHAP mechanics (model loading, background sampling, TreeExplainer,
additivity check, plot files, MLflow logging) live in src/utils/shap_utils.py.
This module wraps them into the steps the Lab 5F notebook walks through and
prints what a learner should see at each step, so the notebook cells stay
short calls.

Key Functions:
- init_mlflow / find_latest_model_run / load_model: resolve the model
- load_training_sample / build_feature_matrix: the data the model saw
- split_background_and_explain / run_shap / predict_positive / validate: SHAP
- feature_importance / plot_* / explain_prediction / force_plot: interpretation
- save_artifacts / log_to_mlflow / print_summary: persist and recap
"""

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import shap
import xgboost as xgb

from src.config import schema
from src.config.config import (
    AWS_DEFAULT_REGION,
    MLFLOW_EXPERIMENT_NAME,
    MLFLOW_MODEL_NAME,
    MLFLOW_MONITORING_EXPERIMENT_NAME,
    MLFLOW_TRACKING_URI,
)
from src.utils.mlflow_utils import setup_mlflow_tracking
from src.utils.shap_utils import (
    compute_shap_values,
    create_shap_visualizations,
    load_model_from_mlflow,
    prepare_background_data,
    save_shap_artifacts_to_mlflow,
    validate_shap_values,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1-2. MLflow and model
# ---------------------------------------------------------------------------

def init_mlflow() -> None:
    """Point MLflow at the workshop tracking server and print the configuration."""
    setup_mlflow_tracking(MLFLOW_TRACKING_URI)

    print("MLflow Configuration:")
    print(f"  Tracking URI: {MLFLOW_TRACKING_URI}")
    print(f"  Training Experiment: {MLFLOW_EXPERIMENT_NAME}")
    print(f"  Monitoring Experiment: {MLFLOW_MONITORING_EXPERIMENT_NAME}")
    print(f"  Model Registry: {MLFLOW_MODEL_NAME}")
    print(f"  Region: {AWS_DEFAULT_REGION}")


def find_latest_model_run(model_name: str = MLFLOW_MODEL_NAME) -> Optional[str]:
    """Return the run ID of the latest registered version of model_name, or None.

    Uses search_model_versions (MLflow 3 API) instead of the deprecated
    get_latest_versions(stages=...) — MLflow 3 removed `stages` in favor of
    aliases. Other places in this project that resolve versions (train.py,
    test_endpoint.py, log_monitoring_to_mlflow.py) all use
    search_model_versions; this matches them.
    """
    client = mlflow.tracking.MlflowClient()
    try:
        versions = client.search_model_versions(f"name='{model_name}'")
    except Exception as e:
        print(f"Error searching model registry: {e}")
        print("Alternative: set MODEL_RUN_ID manually in the next cell.")
        return None

    if not versions:
        print(f"⚠ No registered versions for model: {model_name}")
        print("  Run 1_training_pipeline.ipynb first to train a model.")
        return None

    latest = max(versions, key=lambda v: int(v.version))
    print(f"Latest registered model:")
    print(f"  Name:    {latest.name}")
    print(f"  Version: {latest.version}")
    print(f"  Run ID:  {latest.run_id}")
    print(f"  Status:  {latest.status}")
    aliases = getattr(latest, 'aliases', []) or []
    if aliases:
        print(f"  Aliases: {', '.join(aliases)}")
    return latest.run_id


def load_model(run_id: Optional[str]) -> Tuple[Any, List[str]]:
    """Load the model and its feature names from run_id, printing the feature list."""
    if not run_id:
        raise RuntimeError("⚠ No model loaded. Please set MODEL_RUN_ID above.")

    print(f"Loading model from run: {run_id}")
    model, feature_names = load_model_from_mlflow(run_id)

    print(f"\n✓ Model loaded successfully")
    print(f"  Type: {type(model).__name__}")
    print(f"  Features: {len(feature_names)}")
    print(f"\nFeature Names:")
    for i, feat in enumerate(feature_names, 1):
        print(f"  {i:2d}. {feat}")
    return model, feature_names


# ---------------------------------------------------------------------------
# 3. Training data
# ---------------------------------------------------------------------------

def load_training_sample(data_source: str = "athena", num_samples: int = 5000) -> pd.DataFrame:
    """Load up to num_samples rows of training data and print the class balance.

    data_source:
        "athena" (recommended) — the `training_data` Iceberg table. It is the
                 POST-preprocessing table, so categorical columns (job, marital,
                 education, ...) are already label-encoded, exactly as the
                 model was trained; no extra encoding is needed.
        "csv"    (legacy) — CSV_TRAINING_DATA, which is no longer auto-generated.
    """
    if data_source == "athena":
        from src.config.config import ATHENA_TRAINING_TABLE
        from src.train_pipeline.athena.athena_client import AthenaClient

        print(f"Loading {num_samples} samples from Athena ({ATHENA_TRAINING_TABLE})...")
        df = AthenaClient().read_table(ATHENA_TRAINING_TABLE, limit=num_samples)
        print(f"✓ Loaded {len(df)} rows from Athena")
        print("  (Data is already preprocessed - every feature is numeric)")

    elif data_source == "csv":
        from src.config.config import CSV_TRAINING_DATA

        if not CSV_TRAINING_DATA.exists():
            raise FileNotFoundError(
                f"CSV not found: {CSV_TRAINING_DATA}\n"
                f"The project no longer auto-generates this CSV (switched to kagglehub).\n"
                f"Use DATA_SOURCE='athena' (recommended) or manually export from Athena."
            )
        print(f"Loading from CSV: {CSV_TRAINING_DATA}")
        df = pd.read_csv(CSV_TRAINING_DATA)
        if len(df) > num_samples:
            df = df.sample(n=num_samples, random_state=42)
        print(f"✓ Loaded {len(df)} rows from CSV")
        print("  ⚠️ CSV may not match current preprocessing - use 'athena' for accuracy")
    else:
        raise ValueError(f"DATA_SOURCE must be 'athena' or 'csv', got: {data_source!r}")

    print(f"\nDataset shape: {df.shape}")
    print(f"Columns: {len(df.columns)}")

    target_column = schema.target_column()
    if target_column in df.columns:
        print(f"\nSubscription rate: {df[target_column].mean():.2%}")
        print(f"  Subscribed:     {int(df[target_column].sum()):,}")
        print(f"  Not subscribed: {int((~df[target_column].astype(bool)).sum()):,}")
    else:
        print(f"⚠ Target column '{target_column}' not found in data")
    return df


def build_feature_matrix(
    df: pd.DataFrame,
    feature_names: List[str],
) -> Tuple[pd.DataFrame, Optional[pd.Series]]:
    """Build (X, y) with X in the model's own feature order.

    The booster expects its features in the exact order it was trained on, so X
    is built from `feature_names` (the model's own list) rather than from the
    table's column order. Anything the model lists but the schema does not is
    not a real predictive feature, so it is zeroed rather than fed noise — if
    that count is not 0, the model and the schema have diverged.
    """
    print("Preparing feature data...")

    schema_features = set(schema.feature_names())
    metadata_cols = [f for f in feature_names if f not in schema_features]
    real_features = [f for f in feature_names if f in schema_features]

    if metadata_cols:
        print(f"  ℹ Model includes {len(metadata_cols)} metadata columns: {metadata_cols}")
        print(f"  ℹ These will be zeroed out for SHAP (not real predictive features)")

    # All model features, in order (XGBoost needs exact column count/order).
    X = pd.DataFrame(index=df.index)
    for col in feature_names:
        if col in df.columns and pd.api.types.is_numeric_dtype(df[col]):
            X[col] = df[col].values
        elif col in df.columns:
            # Coerce non-numeric to numeric (e.g. client_id string -> NaN -> 0)
            X[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).values
        else:
            X[col] = 0
    X = X.fillna(0).astype(np.float64)

    target_column = schema.target_column()
    y = df[target_column].copy() if target_column in df.columns else None

    print(f"\nFeatures shape: {X.shape} (all {len(feature_names)} model features)")
    print(f"  Real features:    {len(real_features)}")
    print(f"  Metadata (zeroed): {len(metadata_cols)}")
    print(f"Target shape:   {y.shape if y is not None else 'N/A'}")
    print("✓ All features are numeric")
    return X, y


# ---------------------------------------------------------------------------
# 4-6. Background data, SHAP values, validation
# ---------------------------------------------------------------------------

def split_background_and_explain(
    X: pd.DataFrame,
    y: Optional[pd.Series],
    background_samples: int = 500,
    explain_samples: int = 200,
    random_state: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, Optional[pd.Series]]:
    """Stratified background set for the explainer, plus the rows to explain.

    Returns (X_background, X_explain, y_explain).
    """
    print(f"Preparing background dataset ({background_samples} samples)...")
    X_background = prepare_background_data(
        X, y,
        n_samples=background_samples,
        stratify=y is not None,
        random_state=random_state,
    )

    print(f"\nPreparing explanation dataset ({explain_samples} samples)...")
    if len(X) > explain_samples:
        if y is not None:
            from sklearn.model_selection import train_test_split
            _, X_explain, _, y_explain = train_test_split(
                X, y, test_size=explain_samples, stratify=y, random_state=random_state
            )
        else:
            X_explain = X.sample(n=explain_samples, random_state=random_state)
            y_explain = None
    else:
        X_explain, y_explain = X, y

    print(f"✓ Background data: {X_background.shape}")
    print(f"✓ Explanation data: {X_explain.shape}")
    if y_explain is not None:
        print(f"\nExplanation Set Subscription Rate: {y_explain.mean():.2%}")
    return X_background, X_explain, y_explain


def run_shap(
    model: Any,
    X_background: pd.DataFrame,
    X_explain: pd.DataFrame,
    check_additivity: bool = False,
) -> Tuple[shap.TreeExplainer, np.ndarray, float]:
    """Compute SHAP values with TreeExplainer. Returns (explainer, shap_values, seconds).

    check_additivity=True is useful for debugging but slower.
    """
    print("Computing SHAP values...\n")
    print("This may take a few minutes depending on:")
    print(f"  - Background samples: {len(X_background)}")
    print(f"  - Explanation samples: {len(X_explain)}")
    print(f"  - Features: {X_explain.shape[1]}")
    print("\nProgress: Starting...")

    start_time = time.time()
    explainer, shap_values = compute_shap_values(
        model, X_background, X_explain, check_additivity=check_additivity
    )
    elapsed_time = time.time() - start_time

    print(f"\n✓ SHAP computation complete!")
    print(f"  Time: {elapsed_time:.2f} seconds")
    print(f"  Rate: {len(X_explain) / elapsed_time:.1f} samples/second")
    print(f"  SHAP values shape: {shap_values.shape}")
    print(f"  Expected value (base): {explainer.expected_value}")
    return explainer, shap_values, elapsed_time


def predict_positive(model: Any, X: pd.DataFrame) -> np.ndarray:
    """P(subscribed) for each row of X, for a raw Booster or an sklearn wrapper."""
    X_numeric = X.copy()
    for col in X_numeric.columns:
        if X_numeric[col].dtype == 'object' or X_numeric[col].dtype.name == 'category':
            X_numeric[col] = pd.to_numeric(X_numeric[col], errors='coerce')
    X_numeric = X_numeric.astype(np.float64)

    if isinstance(model, xgb.Booster):
        predictions = model.predict(xgb.DMatrix(X_numeric))
    else:
        predictions = model.predict_proba(X_numeric)[:, 1]

    print(f"Model Predictions:")
    print(f"  Min: {predictions.min():.4f}")
    print(f"  Max: {predictions.max():.4f}")
    print(f"  Mean: {predictions.mean():.4f}")
    print(f"  Median: {np.median(predictions):.4f}")
    return predictions


def validate(
    explainer: shap.TreeExplainer,
    shap_values: np.ndarray,
    predictions: np.ndarray,
    tolerance: float = 1e-4,
) -> Dict[str, Any]:
    """Check base_value + sum(shap_values) ≈ prediction and print the verdict."""
    print("\nValidating SHAP values...")
    results = validate_shap_values(explainer, shap_values, predictions, tolerance=tolerance)

    if results['passed']:
        print(f"\n✓ SHAP Validation PASSED")
        print(f"  Max error: {results['max_error']:.2e}")
        print(f"  Mean error: {results['mean_error']:.2e}")
    else:
        print(f"\n✗ SHAP Validation FAILED")
        print(f"  Failed samples: {len(results['failed_samples'])}")
        print(f"  Max error: {results['max_error']:.2e}")
        print(f"\nFirst few failures:")
        for sample in results['failed_samples'][:3]:
            print(f"  Sample {sample['index']}: error = {sample['error']:.2e}")
    return results


# ---------------------------------------------------------------------------
# 7-10. Interpretation
# ---------------------------------------------------------------------------

def base_value(explainer: shap.TreeExplainer) -> float:
    """The explainer's expected value for the positive class."""
    ev = explainer.expected_value
    return ev[1] if isinstance(ev, (list, np.ndarray)) else ev


def feature_importance(shap_values: np.ndarray, feature_names: List[str], top_n: int = 15) -> pd.DataFrame:
    """Mean |SHAP| per feature, printed (top 10) and plotted (top top_n)."""
    importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': np.abs(shap_values).mean(axis=0),
    }).sort_values('importance', ascending=False)

    print("Top 10 Features by SHAP Importance:\n")
    print(importance_df.head(10).to_string(index=False))

    top_features = importance_df.head(top_n)
    plt.figure(figsize=(10, 8))
    plt.barh(range(len(top_features)), top_features['importance'])
    plt.yticks(range(len(top_features)), top_features['feature'])
    plt.xlabel('Mean |SHAP Value|', fontsize=12)
    plt.title(f'Top {top_n} Features by SHAP Importance', fontsize=14, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.show()

    print(f"\n💡 Insight: The top feature '{top_features.iloc[0]['feature']}' has "
          f"{top_features.iloc[0]['importance']:.4f} mean absolute SHAP value.")
    return importance_df


def plot_summary_bar(shap_values: np.ndarray, X_explain: pd.DataFrame, max_display: int = 20) -> None:
    """SHAP summary bar plot (mean |SHAP| ranking)."""
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X_explain, plot_type="bar", max_display=max_display, show=False)
    plt.title("SHAP Feature Importance", fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()

    print("\n📊 Interpretation: Features are ranked by their average impact on model output magnitude.")


def plot_summary_beeswarm(shap_values: np.ndarray, X_explain: pd.DataFrame, max_display: int = 20) -> None:
    """SHAP beeswarm plot (impact by feature value)."""
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X_explain, max_display=max_display, show=False)
    plt.title("SHAP Summary Plot (Feature Impact by Value)", fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()

    print("\n📊 Interpretation:")
    print("  - Each dot is a sample")
    print("  - X-axis: SHAP value (left = lowers P(subscribed), right = raises it)")
    print("  - Color: Feature value (pink = high, blue = low)")
    print("  - Vertical spread: Number of samples with that SHAP value")


def explain_prediction(
    explainer: shap.TreeExplainer,
    shap_values: np.ndarray,
    X_explain: pd.DataFrame,
    predictions: np.ndarray,
    y_explain: Optional[pd.Series],
    which: str = "highest",
) -> int:
    """Waterfall plot for the most ("highest") or least ("lowest") likely subscriber.

    Returns the row index (into X_explain) that was explained.
    """
    if which == "highest":
        idx, label = int(np.argmax(predictions)), "Highest Positive-Prediction Case"
    elif which == "lowest":
        idx, label = int(np.argmin(predictions)), "Lowest Negative-Prediction Case"
    else:
        raise ValueError(f"which must be 'highest' or 'lowest', got: {which!r}")
    prob = predictions[idx]

    print(f"Analyzing {which} {'positive' if which == 'highest' else 'negative'}-prediction case:")
    print(f"  Sample index: {idx}")
    print(f"  Positive-class probability: {prob:.4f}")
    if y_explain is not None:
        print(f"  Actual label: {'Subscribed' if y_explain.iloc[idx] else 'Not subscribed'}")

    plt.figure(figsize=(10, 8))
    shap.plots.waterfall(
        shap.Explanation(
            values=shap_values[idx],
            base_values=base_value(explainer),
            data=X_explain.iloc[idx],
            feature_names=list(X_explain.columns),
        ),
        max_display=15,
        show=False,
    )
    plt.title(f"SHAP Waterfall Plot - {label} (prob={prob:.4f})", fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()

    if which == "highest":
        print("\n📊 Interpretation:")
        print("  - Base value (E[f(x)]): Expected P(subscribed) across the background set")
        print("  - Red bars: Features pushing the prediction HIGHER (toward subscribing)")
        print("  - Blue bars: Features pushing it LOWER (toward not subscribing)")
        print("  - Final prediction: Base value + sum of all feature contributions")
    else:
        print("\n💡 Insight: Compare this to the likely-subscriber above to see how the feature contributions differ.")
    return idx


def force_plot(explainer: shap.TreeExplainer, shap_values: np.ndarray, X_explain: pd.DataFrame, idx: int):
    """Interactive force plot for one row. Display the returned object in the notebook."""
    print(f"Creating force plot for sample {idx}...")
    shap.initjs()
    return shap.force_plot(
        base_value(explainer), shap_values[idx], X_explain.iloc[idx], matplotlib=False
    )


def plot_decision(
    explainer: shap.TreeExplainer,
    shap_values: np.ndarray,
    X_explain: pd.DataFrame,
    max_samples: int = 50,
) -> None:
    """Decision plot for a random sample of up to max_samples predictions."""
    sample_size = min(max_samples, len(X_explain))
    sample_indices = np.random.choice(len(X_explain), size=sample_size, replace=False)

    plt.figure(figsize=(12, 8))
    shap.decision_plot(
        base_value(explainer),
        shap_values[sample_indices],
        X_explain.iloc[sample_indices],
        show=False,
    )
    plt.title(f"SHAP Decision Plot ({sample_size} Predictions)", fontsize=14, fontweight='bold')
    plt.tight_layout()
    plt.show()

    print("\n📊 Interpretation:")
    print("  - Each line represents one prediction")
    print("  - Y-axis: Features (ordered by importance)")
    print("  - X-axis: Model output (P(subscribed))")
    print("  - Lines moving right: Features increasing P(subscribed)")
    print("  - Lines moving left: Features decreasing P(subscribed)")


def plot_top_dependence(
    shap_values: np.ndarray,
    X_explain: pd.DataFrame,
    feature_names: List[str],
    importance_df: pd.DataFrame,
    top_k: int = 3,
) -> List[str]:
    """Dependence plots for the top_k most important features. Returns their names."""
    top_features = importance_df.head(top_k)['feature'].tolist()

    print(f"Creating dependence plots for top {top_k} features:")
    for rank, feature in enumerate(top_features, 1):
        print(f"  {rank}. {feature}")

    fig, axes = plt.subplots(1, top_k, figsize=(6 * top_k, 5))
    axes = np.atleast_1d(axes)
    for ax, feature in zip(axes, top_features):
        plt.sca(ax)
        shap.dependence_plot(feature_names.index(feature), shap_values, X_explain, show=False)
        ax.set_title(f"Dependence: {feature}", fontsize=12, fontweight='bold')
    plt.tight_layout()
    plt.show()

    print("\n📊 Interpretation:")
    print("  - X-axis: Feature value")
    print("  - Y-axis: SHAP value (impact on prediction)")
    print("  - Color: Another feature (automatic interaction detection)")
    print("  - Vertical scatter at same X: Interactions with other features")
    return top_features


# ---------------------------------------------------------------------------
# 11-13. Artifacts, MLflow, summary
# ---------------------------------------------------------------------------

def save_artifacts(
    explainer: shap.TreeExplainer,
    shap_values: np.ndarray,
    X_explain: pd.DataFrame,
    feature_names: List[str],
    importance_df: pd.DataFrame,
    output_dir: Union[Path, str] = "shap_output",
    max_display: int = 20,
) -> Tuple[Dict[str, Path], Path]:
    """Write every plot, shap_values.csv and feature_importance.csv to output_dir.

    Returns (plot_paths, shap_csv_path).
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    print(f"Saving SHAP artifacts to: {output_dir}")

    plot_paths = create_shap_visualizations(
        explainer, shap_values, X_explain, output_dir, max_display=max_display
    )
    print(f"\n✓ Saved {len(plot_paths)} visualizations:")
    for plot_path in plot_paths.values():
        print(f"  - {plot_path}")

    shap_csv_path = output_dir / "shap_values.csv"
    pd.DataFrame(shap_values, columns=feature_names).to_csv(shap_csv_path, index=False)
    print(f"✓ Saved SHAP values: {shap_csv_path}")

    importance_csv_path = output_dir / "feature_importance.csv"
    importance_df.to_csv(importance_csv_path, index=False)
    print(f"✓ Saved feature importance: {importance_csv_path}")
    return plot_paths, shap_csv_path


def log_to_mlflow(
    training_run_id: str,
    shap_values: np.ndarray,
    plot_paths: Dict[str, Path],
    feature_names: List[str],
    experiment_name: str = MLFLOW_MONITORING_EXPERIMENT_NAME,
) -> str:
    """Log the SHAP artifacts to a new run linked to the training run. Returns its run ID."""
    print("Logging SHAP artifacts to MLflow...")
    shap_run_id = save_shap_artifacts_to_mlflow(
        training_run_id=training_run_id,
        shap_values=shap_values,
        plot_paths=plot_paths,
        feature_names=feature_names,
        experiment_name=experiment_name,
    )

    print(f"\n✓ SHAP artifacts logged to MLflow")
    print(f"  Run ID: {shap_run_id}")
    print(f"  Experiment: {experiment_name}")
    print(f"  Training Run: {training_run_id}")

    mlflow_browser_url = os.getenv('MLFLOW_TRACKING_BROWSER_URL', '')
    if mlflow_browser_url:
        print(f"\n🔗 View in MLflow UI:")
        print(f"  {mlflow_browser_url}")
    return shap_run_id


def print_summary(
    X_explain: pd.DataFrame,
    X_background: pd.DataFrame,
    feature_names: List[str],
    predictions: np.ndarray,
    validation_results: Dict[str, Any],
    elapsed_time: float,
    importance_df: pd.DataFrame,
    plot_paths: Dict[str, Path],
    shap_csv_path: Path,
    shap_run_id: Optional[str],
) -> None:
    """Recap of the whole analysis."""
    print("=" * 80)
    print("SHAP EXPLAINABILITY ANALYSIS SUMMARY")
    print("=" * 80)

    print(f"\n📊 Dataset Statistics:")
    print(f"  Total samples analyzed: {len(X_explain)}")
    print(f"  Features: {len(feature_names)}")
    print(f"  Background samples: {len(X_background)}")

    print(f"\n🎯 Model Performance:")
    print(f"  Average P(subscribed): {predictions.mean():.4f}")
    print(f"  Min P(subscribed): {predictions.min():.4f}")
    print(f"  Max P(subscribed): {predictions.max():.4f}")

    print(f"\n🔍 SHAP Analysis Results:")
    print(f"  Validation: {validation_results['passed']}")
    print(f"  Max error: {validation_results['max_error']:.2e}")
    print(f"  Computation time: {elapsed_time:.2f} seconds")

    print(f"\n⭐ Top 5 Most Important Features:")
    # enumerate, not iterrows: the DataFrame index is the original feature
    # position, so the index would print positions, not ranks 1-5.
    for rank, (_, row) in enumerate(importance_df.head(5).iterrows(), 1):
        print(f"  {rank}. {row['feature']:30s} (SHAP: {row['importance']:.4f})")

    print(f"\n💾 Artifacts Saved:")
    print(f"  Visualizations: {len(plot_paths)} plots")
    print(f"  SHAP values CSV: {shap_csv_path}")
    print(f"  MLflow run: {shap_run_id}")

    print("\n" + "=" * 80)
    print("✓ SHAP ANALYSIS COMPLETE")
    print("=" * 80)

    print("\n💡 Next Steps:")
    print("  1. Review feature importance to validate model behavior")
    print("  2. Analyze waterfall plots to understand specific predictions")
    print("  3. Examine dependence plots for feature interactions")
    print("  4. Compare SHAP results across model versions in MLflow")
    print("  5. Use insights to improve feature engineering or model architecture")
