"""
Generate a drifted dataset for testing inference monitoring.

This script creates a new dataset with intentional feature drift to test
the MLflow inference monitoring system's ability to detect distribution changes.

All drift parameters (factor, noise, shift) are read from src/config/config.yaml
under the 'drift_generation.default_drift' section. No values are hardcoded.

To adjust drift amounts:
1. Edit src/config/config.yaml
2. Run this script to regenerate the drifted CSV
3. Test with the new drift levels

Example:
    python src/drift_monitoring/generate_drift_dataset.py
"""

import pandas as pd
import numpy as np
import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.config import (
    CSV_TRAINING_DATA,
    CSV_DRIFTED_DATA,
    S3_CSV_TRAINING_DATA,
    S3_CSV_DRIFTED_DATA,
    DRIFT_GEN_DEFAULT_CONFIG,
    DRIFT_GEN_NUM_SAMPLES,
    DRIFT_GEN_RANDOM_STATE,
)


def load_original_dataset():
    """Load the dataset to perturb, and return (dataframe, source description).

    Three sources, tried in order of how cheap they are to read:

    1. The local CSV under data/ — present only if someone exported it.
    2. The same CSV in S3 — present only if someone uploaded it.
    3. The `training_data` Iceberg table in Athena.

    (3) is the one that always exists: Lab 2 writes it, Lab 3A trains from the
    pinned snapshot of it, and it already carries the post-preprocessing column
    names this module drifts. The CSV paths above predate that table and are
    kept only so an offline checkout with an exported CSV still works.
    """
    if CSV_TRAINING_DATA and Path(CSV_TRAINING_DATA).exists():
        print(f"\nLoading original dataset from: {CSV_TRAINING_DATA}")
        return pd.read_csv(CSV_TRAINING_DATA), str(CSV_TRAINING_DATA)

    if S3_CSV_TRAINING_DATA:
        try:
            print(f"\nLoading original dataset from: {S3_CSV_TRAINING_DATA}")
            return pd.read_csv(S3_CSV_TRAINING_DATA), S3_CSV_TRAINING_DATA
        except Exception as exc:
            print(f"  Not available ({type(exc).__name__}), falling back to Athena.")

    from src.config.config import ATHENA_TRAINING_TABLE
    from src.train_pipeline.athena.athena_client import AthenaClient

    print(f"\nLoading original dataset from Athena: {ATHENA_TRAINING_TABLE}")
    df = AthenaClient().read_table(ATHENA_TRAINING_TABLE, limit=ATHENA_SOURCE_LIMIT)
    return df, f"athena:{ATHENA_TRAINING_TABLE}"


DRIFTED_DATA_PATH = CSV_DRIFTED_DATA
NUM_SAMPLES = DRIFT_GEN_NUM_SAMPLES

# Pull several times NUM_SAMPLES from Athena so the sample below actually samples;
# reading the whole table would work too (it is ~33k rows) but this keeps the scan
# bounded if someone points the config at a much larger table.
ATHENA_SOURCE_LIMIT = NUM_SAMPLES * 4
RANDOM_STATE = DRIFT_GEN_RANDOM_STATE

# Drift parameters for key features (read from config.yaml drift_generation.default_drift)
DRIFT_CONFIG = DRIFT_GEN_DEFAULT_CONFIG


def scale_drift_config(drift_config: dict, intensity: float) -> dict:
    """Return a copy of drift_config with every feature's drift scaled by intensity.

    0 = no drift, 1 = drift_config as written, >1 = stronger. Additive drift
    scales shift and noise; multiplicative drift scales the factor's distance
    from 1 (so 1.3 at intensity 0.5 becomes 1.15) and the noise.
    """
    scaled = {}
    for feature, config in drift_config.items():
        config = dict(config)
        if "factor" in config:
            config["factor"] = 1.0 + (config["factor"] - 1.0) * intensity
        if "shift" in config:
            config["shift"] = config["shift"] * intensity
        if "noise" in config:
            config["noise"] = config["noise"] * intensity
        scaled[feature] = config
    return scaled


def build_drifted_sample(
    df_source: pd.DataFrame,
    num_samples: int,
    intensity: float = 1.0,
    seed: int = RANDOM_STATE,
    verbose: bool = False,
) -> pd.DataFrame:
    """Sample num_samples rows of df_source and apply DRIFT_CONFIG scaled by intensity.

    In-memory counterpart of generate_drifted_dataset(), used by the multi-batch
    simulation so each batch gets its own rows and its own drift level.
    """
    np.random.seed(seed)
    n = min(num_samples, len(df_source))
    df = df_source.sample(n=n, random_state=seed).copy()
    if intensity > 0:
        for feature, config in scale_drift_config(DRIFT_CONFIG, intensity).items():
            df = apply_drift(df, feature, config, verbose=verbose)
    return df.reset_index(drop=True)


def apply_drift(df: pd.DataFrame, feature: str, config: dict, verbose: bool = True) -> pd.DataFrame:
    """Apply drift to a specific feature based on configuration."""
    if feature not in df.columns:
        print(f"  Warning: Feature '{feature}' not found in dataset, skipping")
        return df

    original_values = df[feature].values

    drift_type = config.get("type", "")

    # Determine drift type from config keys if not explicitly set
    if not drift_type:
        if "factor" in config:
            drift_type = "multiplicative"
        elif "shift" in config:
            drift_type = "additive"
        else:
            print(f"  Warning: No drift type or factor/shift found for {feature}, skipping")
            return df

    if drift_type == "multiplicative":
        # Multiplicative drift: value = original * (factor ± noise)
        factor = config.get("factor", 1.0)
        noise = config.get("noise", 0)
        random_factors = np.random.uniform(
            factor - noise * factor,
            factor + noise * factor,
            size=len(df)
        )
        drifted_values = original_values * random_factors

    elif drift_type == "additive":
        # Additive drift: value = original + (shift ± noise)
        shift = config.get("shift", 0)
        noise = config.get("noise", 0)
        random_shifts = np.random.uniform(
            shift - noise,
            shift + noise,
            size=len(df)
        )
        drifted_values = original_values + random_shifts

    else:
        raise ValueError(f"Unknown drift type: {drift_type}")

    # Clip to zero: preserve non-negativity for any feature that was originally non-negative
    if (original_values >= 0).all():
        drifted_values = np.maximum(drifted_values, 0)

    # Preserve integer dtype if the original feature was integer-valued
    if np.issubdtype(df[feature].dtype, np.integer) or (original_values == np.floor(original_values)).all():
        drifted_values = np.round(drifted_values).astype(int)

    df[feature] = drifted_values

    if not verbose:
        return df

    # Print drift statistics
    original_mean = original_values.mean()
    drifted_mean = drifted_values.mean()
    pct_change = ((drifted_mean - original_mean) / original_mean) * 100 if original_mean != 0 else 0

    print(f"  {feature}:")
    print(f"    Original mean: {original_mean:.4f}")
    print(f"    Drifted mean: {drifted_mean:.4f}")
    print(f"    Change: {pct_change:+.2f}%")
    description = config.get("description", feature)
    print(f"    Description: {description}")

    return df


def generate_drifted_dataset():
    """Generate a drifted dataset for testing inference monitoring."""

    print("=" * 80)
    print("GENERATING DRIFTED DATASET")
    print("=" * 80)

    # Load original dataset
    df_original, original_source = load_original_dataset()
    print(f"Original dataset shape: {df_original.shape}")

    # Sample random rows
    print(f"\nSampling {NUM_SAMPLES} random rows...")
    np.random.seed(RANDOM_STATE)
    df_drifted = df_original.sample(n=NUM_SAMPLES, random_state=RANDOM_STATE).copy()
    print(f"Sampled dataset shape: {df_drifted.shape}")

    # Apply drift to key features
    print("\nApplying feature drift:")
    print("-" * 80)
    for feature, config in DRIFT_CONFIG.items():
        df_drifted = apply_drift(df_drifted, feature, config)

    # Reset index
    df_drifted = df_drifted.reset_index(drop=True)

    # Save drifted dataset
    print("\n" + "-" * 80)
    print(f"Saving drifted dataset to: {DRIFTED_DATA_PATH}")
    df_drifted.to_csv(DRIFTED_DATA_PATH, index=False)
    print(f"Saved {len(df_drifted)} rows")

    # Summary statistics
    print("\n" + "=" * 80)
    print("DRIFT SUMMARY")
    print("=" * 80)
    print(f"Original dataset: {original_source}")
    print(f"Drifted dataset: {DRIFTED_DATA_PATH}")
    print(f"Number of samples: {NUM_SAMPLES}")
    print(f"\nClass distribution in drifted dataset:")
    try:
        from src.config import schema
        _target = schema.target_column()
    except Exception:
        _target = None
    if _target and _target in df_drifted.columns:
        counts = df_drifted[_target].value_counts()
        print(f"  {_target} = negative: {counts.get(False, counts.get(0, 0))}")
        print(f"  {_target} = positive: {counts.get(True, counts.get(1, 0))}")

    print("\nKey feature comparison:")
    print("-" * 80)
    for feature in DRIFT_CONFIG.keys():
        if feature in df_drifted.columns and feature in df_original.columns:
            original_mean = df_original[feature].mean()
            drifted_mean = df_drifted[feature].mean()
            pct_change = ((drifted_mean - original_mean) / original_mean) * 100
            print(f"{feature:30s} Original: {original_mean:10.2f}  Drifted: {drifted_mean:10.2f}  Change: {pct_change:+6.1f}%")

    print("\n" + "=" * 80)
    print("DRIFTED DATASET GENERATION COMPLETED")
    print("=" * 80)
    print(f"\nLab 5D Section 3 reads {DRIFTED_DATA_PATH} and sends those rows to the")
    print(f"endpoint, so the drift above is what the monitors will see.")
    print("=" * 80)


if __name__ == "__main__":
    generate_drifted_dataset()
