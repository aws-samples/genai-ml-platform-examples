"""
SHAP explainability utilities for the deployed XGBoost model.

This module provides utilities for generating SHAP (SHapley Additive exPlanations)
values to explain model predictions both globally (feature importance) and locally
(individual prediction explanations).

Key Functions:
- load_model_from_mlflow: Load XGBoost model from MLflow run artifacts
- prepare_background_data: Create stratified background dataset for SHAP
- compute_shap_values: Calculate SHAP values using TreeExplainer
- validate_shap_values: Verify mathematical consistency of SHAP values
- create_shap_visualizations: Generate comprehensive SHAP plots
- save_shap_artifacts_to_mlflow: Log SHAP results to MLflow
"""

import json
import logging
import os
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List, Union

import boto3
import mlflow
import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt
import xgboost as xgb
from xgboost import XGBClassifier

logger = logging.getLogger(__name__)


def load_model_from_mlflow(
    run_id: str,
    model_name: str = "model"
) -> Tuple[Any, List[str]]:
    """
    Load XGBoost model and feature names from MLflow run.

    Handles both sklearn wrapper (XGBClassifier) and native Booster formats.
    Uses MLflow's secure model loading with multiple fallback strategies.

    Note: Model files are loaded only from MLflow, which is a trusted source
    in this MLOps pipeline. MLflow manages model serialization securely.

    Args:
        run_id: MLflow run ID containing the model
        model_name: Model artifact name (default: "model")

    Returns:
        Tuple of (model, feature_names)

    Example:
        >>> model, features = load_model_from_mlflow("abc123def456")
        >>> print(f"Loaded model with {len(features)} features")
    """
    logger.info(f"Loading model from MLflow run: {run_id}")

    # Ensure boto3 is configured with the correct region
    # This is critical for downloading artifacts from S3
    region = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')
    os.environ['AWS_DEFAULT_REGION'] = region
    logger.info(f"Using AWS region: {region}")

    # Try multiple loading strategies
    model = None
    model_uri = f"runs:/{run_id}/{model_name}"

    # Track all errors for better debugging
    errors = []

    # Strategy 1: Try loading from model registry if this looks like a registry URI
    if model_name == "model" and not run_id.startswith("models:/"):
        # Try model registry first
        try:
            logger.info("Attempting to load from model registry...")
            model_registry_name = os.getenv('MLFLOW_MODEL_NAME', 'bank-prediction-XGBoostModel')
            model_uri_registry = f"models:/{model_registry_name}/latest"
            model = mlflow.xgboost.load_model(model_uri_registry)
            logger.info("✓ Successfully loaded from model registry")
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"Model registry loader failed: {error_msg}")
            errors.append(("model_registry", error_msg))

    # Strategy 2: Try XGBoost-specific loader for run ID
    if model is None:
        try:
            logger.info("Attempting to load with mlflow.xgboost.load_model()...")
            model = mlflow.xgboost.load_model(model_uri)
            logger.info("✓ Successfully loaded with XGBoost loader")
        except Exception as e:
            error_msg = str(e)
            logger.warning(f"XGBoost loader failed: {error_msg}")
            errors.append(("xgboost", error_msg))

            # Strategy 3: Try generic PyFunc loader
            try:
                logger.info("Attempting to load with mlflow.pyfunc.load_model()...")
                pyfunc_model = mlflow.pyfunc.load_model(model_uri)

                # Extract underlying model if it's wrapped
                if hasattr(pyfunc_model, '_model_impl'):
                    model = pyfunc_model._model_impl.xgb_model
                    logger.info("✓ Successfully loaded with PyFunc loader (extracted XGBoost model)")
                else:
                    model = pyfunc_model
                    logger.info("✓ Successfully loaded with PyFunc loader")
            except Exception as e2:
                error_msg = str(e2)
                logger.warning(f"PyFunc loader failed: {error_msg}")
                errors.append(("pyfunc", error_msg))

                # Strategy 4: Download and load manually from MLflow artifacts
                try:
                    logger.info("Attempting to download and load manually...")
                    import tempfile
                    from pathlib import Path

                    with tempfile.TemporaryDirectory() as tmpdir:
                        # Download all artifacts from MLflow (trusted source)
                        artifact_path = mlflow.artifacts.download_artifacts(
                            artifact_uri=f"runs:/{run_id}/{model_name}",
                            dst_path=tmpdir
                        )

                        artifact_dir = Path(artifact_path)

                        # Look for XGBoost model files
                        for ext in ['xgboost-model', 'xgboost-model.json', 'model.json', 'model.ubj']:
                            model_file = artifact_dir / ext
                            if model_file.exists():
                                logger.info(f"Found model file: {model_file}")
                                model = xgb.Booster()
                                model.load_model(str(model_file))
                                logger.info(f"✓ Successfully loaded from {ext}")
                                break

                        # Try sklearn format if no native format found
                        if model is None:
                            model_file = artifact_dir / 'model.pkl'
                            if model_file.exists():
                                logger.info(f"Found sklearn model file: {model_file}")
                                # This is safe because it's from MLflow, not untrusted external source
                                import pickle
                                with open(model_file, 'rb') as f:
                                    model = pickle.load(f)
                                logger.info(f"✓ Successfully loaded from model.pkl")

                        if model is None:
                            raise ValueError(f"Could not find model file in downloaded artifacts at {artifact_dir}")

                except Exception as e3:
                    error_msg = str(e3)
                    logger.error(f"Manual loading failed: {error_msg}")
                    errors.append(("manual", error_msg))

                    # Check if this is the XGBoost version incompatibility issue
                    if "binary format has been deprecated" in error_msg or "binary format has been deprecated" in " ".join([e[1] for e in errors]):
                        raise ValueError(
                            f"\n{'='*80}\n"
                            f"❌ XGBOOST VERSION INCOMPATIBILITY\n"
                            f"{'='*80}\n"
                            f"Your model was trained with XGBoost 1.x and saved in the deprecated\n"
                            f"binary format (.xgb). Your current environment has XGBoost 3.2.0,\n"
                            f"which no longer supports this format.\n\n"
                            f"SOLUTION: Retrain the model with current XGBoost version\n"
                            f"{'='*80}\n"
                            f"1. Open: lab5d-1-training-pipeline.ipynb\n"
                            f"2. Run all cells to train a new model\n"
                            f"3. The new model will be in JSON format (compatible)\n"
                            f"4. Then return to this SHAP notebook\n"
                            f"{'='*80}\n"
                            f"\nAlternatively, if you must use the old model, downgrade XGBoost:\n"
                            f"  uv pip install 'xgboost<2.0'\n"
                            f"{'='*80}\n"
                        )
                    else:
                        # Generic error message
                        error_summary = "\n".join([f"  - {name}: {msg[:100]}" for name, msg in errors])
                        raise ValueError(
                            f"Failed to load model from MLflow run {run_id}.\n"
                            f"Tried {len(errors)} strategies:\n{error_summary}"
                        )

    # Download feature metadata
    try:
        feature_metadata_uri = f"runs:/{run_id}/feature_names.json"
        local_path = mlflow.artifacts.download_artifacts(feature_metadata_uri)
        with open(local_path, 'r') as f:
            feature_metadata = json.load(f)
            feature_names = feature_metadata['feature_names']
        logger.info(f"Loaded feature names from feature_names.json")
    except Exception as e:
        logger.warning(f"Could not load feature_names.json: {e}")
        # Extract from model if available
        if hasattr(model, 'feature_names_in_'):
            feature_names = list(model.feature_names_in_)
            logger.info("Extracted feature names from model.feature_names_in_")
        elif isinstance(model, xgb.Booster):
            feature_names = model.feature_names if hasattr(model, 'feature_names') else None
            if feature_names:
                logger.info("Extracted feature names from Booster.feature_names")
            else:
                # Booster trained with header=None has no feature names stored.
                # Fall back to the dataset schema — it defines the canonical
                # feature order, which is the same order the training CSV used.
                logger.warning(
                    "Booster has no feature_names (likely trained with header=None). "
                    "Falling back to dataset schema feature order."
                )
                from src.config import schema as _schema
                feature_names = list(_schema.feature_names())
                logger.info(
                    "Using %d feature names from dataset_schema.yaml", len(feature_names)
                )
                # Stamp the names onto the booster so downstream DMatrix calls
                # (e.g. in compute_shap_values) agree on column order.
                model.feature_names = feature_names
        elif hasattr(model, 'get_booster'):
            # Try to get from underlying booster
            booster = model.get_booster()
            feature_names = booster.feature_names if hasattr(booster, 'feature_names') else None
            if feature_names:
                logger.info("Extracted feature names from underlying Booster")
            else:
                logger.warning(
                    "Underlying Booster has no feature_names. "
                    "Falling back to dataset schema feature order."
                )
                from src.config import schema as _schema
                feature_names = list(_schema.feature_names())
                logger.info(
                    "Using %d feature names from dataset_schema.yaml", len(feature_names)
                )
                booster.feature_names = feature_names
        else:
            raise ValueError("Cannot determine feature names from model or metadata")

    # Lab 3A's train.py reads its training CSV with header=None, so the booster
    # it logs to MLflow carries POSITIONAL feature names — '1', '2', ... '20'.
    # Those are useless as SHAP labels, and worse: a caller matching them against
    # the dataset schema finds zero real features and zeroes the whole matrix,
    # which makes every prediction identical. The CSV's column order is the
    # schema's feature order, so relabel by position.
    if feature_names and all(str(n).isdigit() for n in feature_names):
        from src.config import schema

        schema_features = schema.feature_names()
        if len(schema_features) == len(feature_names):
            logger.info(
                "Model carries positional feature names; relabeling from "
                "dataset_schema.yaml (%d features)", len(schema_features)
            )
            feature_names = list(schema_features)
            if isinstance(model, xgb.Booster):
                # Keep the booster in step, or DMatrix(named DataFrame) is
                # rejected for a feature-name mismatch at predict time.
                model.feature_names = feature_names
        else:
            logger.warning(
                "Model has %d positional feature names but the schema declares %d — "
                "leaving the positional names in place.",
                len(feature_names), len(schema_features),
            )

    logger.info(f"✓ Loaded model with {len(feature_names)} features")
    return model, feature_names


def prepare_background_data(
    X: pd.DataFrame,
    y: Optional[pd.Series] = None,
    n_samples: int = 500,
    stratify: bool = True,
    random_state: int = 42
) -> pd.DataFrame:
    """
    Prepare background dataset for SHAP explainer.

    Uses stratified sampling to maintain class balance when target labels
    are provided. This ensures the background data is representative of
    the training distribution.

    Args:
        X: Feature dataframe
        y: Target labels (required if stratify=True)
        n_samples: Number of background samples
        stratify: Whether to use stratified sampling
        random_state: Random seed for reproducibility

    Returns:
        Background dataset (DataFrame)

    Raises:
        ValueError: If stratify=True but y is None

    Example:
        >>> X_bg = prepare_background_data(X_train, y_train, n_samples=500)
        >>> print(f"Background data: {len(X_bg)} samples")
    """
    n_samples = min(n_samples, len(X))

    if stratify and y is not None:
        # Stratified sampling to maintain class distribution
        from sklearn.model_selection import train_test_split
        X_bg, _, y_bg, _ = train_test_split(
            X, y,
            train_size=n_samples,
            stratify=y,
            random_state=random_state
        )
        positive_rate = y_bg.mean() if hasattr(y_bg, 'mean') else np.mean(y_bg)
        logger.info(f"Background data: {len(X_bg)} samples, positive rate: {positive_rate:.3f}")
        return X_bg
    elif stratify and y is None:
        raise ValueError("stratify=True requires target labels (y)")
    else:
        # Random sampling
        X_bg = X.sample(n=n_samples, random_state=random_state)
        logger.info(f"Background data: {len(X_bg)} samples (random sampling)")
        return X_bg


def compute_shap_values(
    model: Any,
    X_background: pd.DataFrame,
    X_explain: pd.DataFrame,
    check_additivity: bool = False
) -> Tuple[shap.TreeExplainer, np.ndarray]:
    """
    Compute SHAP values using TreeExplainer.

    TreeExplainer is optimized for tree-based models like XGBoost and provides
    exact Shapley values (not approximations). It's 100-1000x faster than
    model-agnostic methods like KernelExplainer.

    Args:
        model: XGBoost model (XGBClassifier or Booster)
        X_background: Background dataset for explainer
        X_explain: Data to explain
        check_additivity: Whether to validate SHAP additivity property (slower)

    Returns:
        Tuple of (explainer, shap_values)
        - explainer: TreeExplainer instance with expected_value
        - shap_values: Array of shape (n_samples, n_features)

    Example:
        >>> explainer, shap_values = compute_shap_values(model, X_bg, X_test[:100])
        >>> print(f"SHAP values shape: {shap_values.shape}")
    """
    logger.info("Creating TreeExplainer...")

    # Convert sklearn wrapper to Booster for TreeExplainer
    if isinstance(model, XGBClassifier):
        booster = model.get_booster()
        logger.info("Converted XGBClassifier to Booster")
    elif isinstance(model, xgb.Booster):
        booster = model
        logger.info("Using native Booster")
    else:
        raise ValueError(f"Unsupported model type: {type(model)}")

    # Ensure all data is numeric (convert object dtypes to float)
    X_background_numeric = X_background.copy()
    X_explain_numeric = X_explain.copy()

    # Convert any object/categorical columns to numeric
    for col in X_background_numeric.columns:
        if X_background_numeric[col].dtype == 'object' or X_background_numeric[col].dtype.name == 'category':
            logger.warning(f"Converting non-numeric column '{col}' to float64")
            X_background_numeric[col] = pd.to_numeric(X_background_numeric[col], errors='coerce')

    for col in X_explain_numeric.columns:
        if X_explain_numeric[col].dtype == 'object' or X_explain_numeric[col].dtype.name == 'category':
            logger.warning(f"Converting non-numeric column '{col}' to float64")
            X_explain_numeric[col] = pd.to_numeric(X_explain_numeric[col], errors='coerce')

    # Ensure float64 dtype for all columns (SHAP requirement)
    X_background_numeric = X_background_numeric.astype(np.float64)
    X_explain_numeric = X_explain_numeric.astype(np.float64)

    logger.info(f"Background data dtype: {X_background_numeric.dtypes.unique()}")
    logger.info(f"Explain data dtype: {X_explain_numeric.dtypes.unique()}")

    # Create explainer WITHOUT background data.
    #
    # feature_perturbation='tree_path_dependent' is the XGBoost-recommended
    # SHAP method: it uses the tree's own training-time leaf weights as the
    # implicit reference distribution. Passing an explicit background sample
    # with this method requires the sample to visit every leaf in every tree
    # \u2014 which almost never happens in practice, and raises:
    #   "The background dataset you provided does not cover all the leaves ..."
    # Solution: data=None. Background samples are still useful for
    # visualizations (dependence plots, summary plots) which consume
    # X_explain / X_background as feature matrices, not as SHAP inputs.
    #
    # If you need SHAP values that account for a specific background
    # distribution (e.g., counterfactual analysis vs a control cohort),
    # switch to feature_perturbation='interventional' and pass data=
    # X_background_numeric \u2014 but note that interventional SHAP assumes
    # feature independence within each perturbation, which is a semantic
    # change, not just a config knob.
    explainer = shap.TreeExplainer(
        booster,
        data=None,
        feature_perturbation='tree_path_dependent'
    )

    logger.info(f"Computing SHAP values for {len(X_explain_numeric)} samples...")
    shap_values = explainer.shap_values(X_explain_numeric, check_additivity=check_additivity)

    logger.info(f"✓ SHAP values shape: {shap_values.shape}")
    return explainer, shap_values


def validate_shap_values(
    explainer: shap.TreeExplainer,
    shap_values: np.ndarray,
    predictions: np.ndarray,
    tolerance: float = 1e-4,
    model_output: str = 'probability'
) -> Dict[str, Any]:
    """
    Validate SHAP values mathematical consistency.

    Verifies the additivity property: base_value + sum(shap_values) ≈ model_prediction
    This is a fundamental property of Shapley values.

    Note: When using tree_path_dependent feature perturbation, SHAP values are in
    log-odds space. We need to apply the logistic function to convert to probabilities.

    Args:
        explainer: SHAP explainer with base_value (expected value)
        shap_values: Computed SHAP values
        predictions: Model predictions (probabilities for binary classification)
        tolerance: Numerical tolerance for validation (default: 1e-4)
        model_output: 'probability' or 'log_odds' - what the predictions represent

    Returns:
        Validation results dictionary with keys:
        - passed: bool, whether all samples passed validation
        - max_error: float, maximum absolute error across samples
        - mean_error: float, mean absolute error
        - failed_samples: list of dicts with error details for failed samples

    Example:
        >>> results = validate_shap_values(explainer, shap_values, predictions)
        >>> if results['passed']:
        ...     print(f"✓ SHAP validation passed (max error: {results['max_error']:.2e})")
    """
    base_value = explainer.expected_value

    # For binary classification, expected_value might be array
    if isinstance(base_value, (list, np.ndarray)):
        base_value = base_value[1] if len(base_value) > 1 else base_value[0]

    validation_results = {
        'passed': True,
        'max_error': 0.0,
        'mean_error': 0.0,
        'failed_samples': []
    }

    errors = []
    for i in range(len(shap_values)):
        shap_sum = base_value + shap_values[i].sum()

        # Convert to probability if needed (SHAP values are in log-odds space)
        # when using tree_path_dependent
        if model_output == 'probability':
            # Apply logistic function: p = 1 / (1 + exp(-log_odds))
            shap_prediction = 1 / (1 + np.exp(-shap_sum))
        else:
            shap_prediction = shap_sum

        error = abs(shap_prediction - predictions[i])
        errors.append(error)

        if error > tolerance:
            validation_results['passed'] = False
            validation_results['failed_samples'].append({
                'index': i,
                'error': float(error),
                'shap_sum': float(shap_sum),
                'shap_prediction': float(shap_prediction),
                'actual_prediction': float(predictions[i])
            })

    validation_results['max_error'] = float(np.max(errors))
    validation_results['mean_error'] = float(np.mean(errors))

    if validation_results['passed']:
        logger.info(f"✓ SHAP validation passed (max error: {validation_results['max_error']:.2e})")
    else:
        logger.warning(f"✗ SHAP validation failed for {len(validation_results['failed_samples'])} samples")
        logger.warning(f"  Max error: {validation_results['max_error']:.2e}, tolerance: {tolerance:.2e}")

    return validation_results


def create_shap_visualizations(
    explainer: shap.TreeExplainer,
    shap_values: np.ndarray,
    X: pd.DataFrame,
    output_dir: Union[Path, str],
    max_display: int = 20
) -> Dict[str, Path]:
    """
    Generate all SHAP visualization plots.

    Creates comprehensive visualizations for both global (model-level) and
    local (prediction-level) interpretability:
    - Summary plots: Feature importance and impact distribution
    - Waterfall plots: Individual prediction explanations
    - Force plots: Interactive visualization
    - Decision plots: Multi-prediction comparison
    - Dependence plots: Feature interactions

    Args:
        explainer: SHAP explainer with expected_value
        shap_values: SHAP values for data
        X: Feature data (DataFrame with feature names)
        output_dir: Directory to save plots
        max_display: Maximum features to display in plots

    Returns:
        Dictionary mapping plot_name -> file_path

    Example:
        >>> plot_paths = create_shap_visualizations(explainer, shap_values, X_test, "shap_output/")
        >>> print(f"Generated {len(plot_paths)} plots")
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    plot_paths = {}

    logger.info("Generating SHAP visualizations...")

    # 1. Summary plot (bar) - Feature importance
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X, plot_type="bar", max_display=max_display, show=False)
    plt.title("SHAP Feature Importance (Mean Absolute SHAP Value)", fontsize=14, fontweight='bold')
    summary_bar_path = output_dir / "shap_summary_bar.png"
    plt.savefig(summary_bar_path, bbox_inches='tight', dpi=150)
    plt.close()
    plot_paths['summary_bar'] = summary_bar_path
    logger.info(f"✓ Summary plot (bar): {summary_bar_path}")

    # 2. Summary plot (beeswarm) - Feature value impact
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, X, max_display=max_display, show=False)
    plt.title("SHAP Summary Plot (Feature Value Impact)", fontsize=14, fontweight='bold')
    summary_beeswarm_path = output_dir / "shap_summary_beeswarm.png"
    plt.savefig(summary_beeswarm_path, bbox_inches='tight', dpi=150)
    plt.close()
    plot_paths['summary_beeswarm'] = summary_beeswarm_path
    logger.info(f"✓ Summary plot (beeswarm): {summary_beeswarm_path}")

    # 3. Waterfall plot (highest positive-prediction case - most positive SHAP sum)
    highest_idx = np.argmax(shap_values.sum(axis=1))
    plt.figure(figsize=(10, 8))
    shap.plots.waterfall(
        shap.Explanation(
            values=shap_values[highest_idx],
            base_values=explainer.expected_value if not isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value[1],
            data=X.iloc[highest_idx],
            feature_names=list(X.columns)
        ),
        max_display=max_display,
        show=False
    )
    plt.title("SHAP Waterfall Plot (Highest Positive-Prediction Case)", fontsize=14, fontweight='bold')
    waterfall_highest_path = output_dir / "shap_waterfall_highest_prediction.png"
    plt.savefig(waterfall_highest_path, bbox_inches='tight', dpi=150)
    plt.close()
    plot_paths['waterfall_highest'] = waterfall_highest_path
    logger.info(f"✓ Waterfall plot (highest prediction): {waterfall_highest_path}")

    # 4. Waterfall plot (lowest negative-prediction case - most negative SHAP sum)
    lowest_idx = np.argmin(shap_values.sum(axis=1))
    plt.figure(figsize=(10, 8))
    shap.plots.waterfall(
        shap.Explanation(
            values=shap_values[lowest_idx],
            base_values=explainer.expected_value if not isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value[1],
            data=X.iloc[lowest_idx],
            feature_names=list(X.columns)
        ),
        max_display=max_display,
        show=False
    )
    plt.title("SHAP Waterfall Plot (Lowest Negative-Prediction Case)", fontsize=14, fontweight='bold')
    waterfall_lowest_path = output_dir / "shap_waterfall_lowest_prediction.png"
    plt.savefig(waterfall_lowest_path, bbox_inches='tight', dpi=150)
    plt.close()
    plot_paths['waterfall_lowest'] = waterfall_lowest_path
    logger.info(f"✓ Waterfall plot (lowest prediction): {waterfall_lowest_path}")

    # 5. Force plot (interactive HTML) - first sample
    base_val = explainer.expected_value if not isinstance(explainer.expected_value, (list, np.ndarray)) else explainer.expected_value[1]
    force_plot_html = shap.force_plot(
        base_val,
        shap_values[0],
        X.iloc[0],
        matplotlib=False
    )
    force_plot_path = output_dir / "shap_force_plot.html"
    shap.save_html(str(force_plot_path), force_plot_html)
    plot_paths['force_plot'] = force_plot_path
    logger.info(f"✓ Force plot (HTML): {force_plot_path}")

    # 6. Decision plot (compare multiple predictions)
    sample_size = min(50, len(X))
    sample_indices = np.random.choice(len(X), size=sample_size, replace=False)
    plt.figure(figsize=(12, 8))
    shap.decision_plot(
        base_val,
        shap_values[sample_indices],
        X.iloc[sample_indices],
        show=False
    )
    plt.title(f"SHAP Decision Plot ({sample_size} Predictions)", fontsize=14, fontweight='bold')
    decision_plot_path = output_dir / "shap_decision_plot.png"
    plt.savefig(decision_plot_path, bbox_inches='tight', dpi=150)
    plt.close()
    plot_paths['decision_plot'] = decision_plot_path
    logger.info(f"✓ Decision plot: {decision_plot_path}")

    # 7. Dependence plots (top 3 features)
    mean_abs_shap = np.abs(shap_values).mean(axis=0)
    top_features_idx = np.argsort(mean_abs_shap)[-3:][::-1]

    for rank, feat_idx in enumerate(top_features_idx):
        feature_name = X.columns[feat_idx]
        plt.figure(figsize=(10, 6))
        shap.dependence_plot(
            feat_idx,
            shap_values,
            X,
            show=False
        )
        plt.title(f"SHAP Dependence Plot: {feature_name}", fontsize=14, fontweight='bold')
        # Clean feature name for filename
        safe_name = feature_name.replace('/', '_').replace(' ', '_')
        dependence_plot_path = output_dir / f"shap_dependence_{rank+1}_{safe_name}.png"
        plt.savefig(dependence_plot_path, bbox_inches='tight', dpi=150)
        plt.close()
        plot_paths[f'dependence_{feature_name}'] = dependence_plot_path
        logger.info(f"✓ Dependence plot ({feature_name}): {dependence_plot_path}")

    logger.info(f"✓ Generated {len(plot_paths)} SHAP visualizations")
    return plot_paths


def save_shap_artifacts_to_mlflow(
    training_run_id: str,
    shap_values: np.ndarray,
    plot_paths: Dict[str, Path],
    feature_names: List[str],
    experiment_name: Optional[str] = None
) -> str:
    """
    Log SHAP artifacts to MLflow.

    Creates a new MLflow run in the monitoring experiment and logs:
    - Feature importance (mean absolute SHAP values) as JSON
    - Top 10 features as metrics and parameters
    - All visualization plots
    - SHAP values as CSV for further analysis
    - Link to original training run via tags

    Args:
        training_run_id: Original training run ID (for reference)
        shap_values: Computed SHAP values
        plot_paths: Dictionary of plot paths
        feature_names: Feature names
        experiment_name: MLflow experiment name (optional, uses default if None)

    Returns:
        MLflow run ID for SHAP analysis

    Example:
        >>> shap_run_id = save_shap_artifacts_to_mlflow(
        ...     "train123", shap_values, plot_paths, feature_names
        ... )
        >>> print(f"SHAP artifacts logged to run: {shap_run_id}")
    """
    from src.utils.mlflow_utils import setup_mlflow_tracking, get_or_create_experiment
    from src.config.config import MLFLOW_TRACKING_URI, MLFLOW_MONITORING_EXPERIMENT_NAME

    setup_mlflow_tracking(MLFLOW_TRACKING_URI)

    exp_name = experiment_name or MLFLOW_MONITORING_EXPERIMENT_NAME
    experiment_id = get_or_create_experiment(exp_name)

    with mlflow.start_run(experiment_id=experiment_id, run_name=f"shap-analysis-{training_run_id[:8]}") as run:
        shap_run_id = run.info.run_id

        # Log reference to original training run
        mlflow.set_tag("training_run_id", training_run_id)
        mlflow.set_tag("analysis_type", "shap_explainability")
        mlflow.set_tag("shap_method", "TreeExplainer")

        # Log parameters
        mlflow.log_param("num_samples_explained", shap_values.shape[0])
        mlflow.log_param("num_features", shap_values.shape[1])

        # Log mean absolute SHAP values (feature importance)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        feature_importance = dict(zip(feature_names, mean_abs_shap.tolist()))
        mlflow.log_dict(feature_importance, "shap_feature_importance.json")

        # Log top 10 features as metrics and parameters
        top_features = sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
        for rank, (feat_name, importance) in enumerate(top_features, 1):
            mlflow.log_metric(f"shap_importance_rank_{rank}", importance)
            mlflow.log_param(f"top_feature_{rank}", feat_name)

        logger.info(f"Top 3 features by SHAP importance:")
        for rank, (feat_name, importance) in enumerate(top_features[:3], 1):
            logger.info(f"  {rank}. {feat_name}: {importance:.4f}")

        # Log visualizations
        for plot_name, plot_path in plot_paths.items():
            mlflow.log_artifact(str(plot_path), artifact_path="shap_plots")
        logger.info(f"Logged {len(plot_paths)} visualization plots")

        # Save SHAP values as CSV for further analysis
        shap_df = pd.DataFrame(shap_values, columns=feature_names)
        shap_csv_path = Path(plot_paths[list(plot_paths.keys())[0]]).parent / "shap_values.csv"
        shap_df.to_csv(shap_csv_path, index=False)
        mlflow.log_artifact(str(shap_csv_path), artifact_path="shap_data")
        logger.info(f"Saved SHAP values CSV: {shap_csv_path}")

        logger.info(f"✓ SHAP artifacts logged to MLflow run: {shap_run_id}")
        logger.info(f"  Experiment: {exp_name}")
        logger.info(f"  Training run reference: {training_run_id}")

    return shap_run_id
