#!/usr/bin/env python3
"""
Simulate ground truth updates for inference predictions stored in Athena.

This script:
1. Queries inference_responses table for predictions without ground truth
2. Randomly assigns ground truth (with realistic correlation to predictions)
3. Writes ground truth updates to ground_truth_updates table in Athena

Usage:
    # Simulate ground truth for all predictions without ground truth
    python scripts/simulate_ground_truth_from_athena.py

    # Simulate for specific endpoint
    python scripts/simulate_ground_truth_from_athena.py --endpoint-name bank-marketing-endpoint

    # Control accuracy (how often predictions match ground truth)
    python scripts/simulate_ground_truth_from_athena.py --accuracy 0.90

    # Limit number of updates
    python scripts/simulate_ground_truth_from_athena.py --limit 100
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import uuid

import pandas as pd
import numpy as np

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from src.config import schema
from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_INFERENCE_TABLE,
    ATHENA_GROUND_TRUTH_UPDATES_TABLE,
    PROBABILITY_COLUMN,
)
from src.train_pipeline.athena.athena_client import AthenaClient

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Schema-driven column name for ground truth.
# Derived from dataset_schema.yaml: actual_{target_column}
# e.g. "actual_subscribed" for Bank Marketing, "actual_fraud" for fraud detection.
ACTUAL_TARGET_COL = f'actual_{schema.target_column()}'


class GroundTruthSimulator:
    """Simulate ground truth for Athena inference predictions."""

    def __init__(
        self,
        athena_client: AthenaClient,
        endpoint_name: str = None,
        accuracy: float = 0.85,
        positive_confirmation_days: tuple = (1, 7),
        negative_confirmation_days: tuple = (1, 30),
        feature_drift_impact: float = 0.0,
        model_drift_magnitude: float = 0.0,
        seed: int = 42,
        monitoring_run_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ):
        """
        Initialize ground truth simulator.

        Args:
            athena_client: Athena client for queries
            endpoint_name: Optional filter for specific endpoint
            accuracy: Base model accuracy (0.0-1.0)
            positive_confirmation_days: (min, max) days for positive class confirmation
            negative_confirmation_days: (min, max) days for negative class confirmation
            feature_drift_impact: Accuracy reduction due to feature drift (0.0-1.0)
            model_drift_magnitude: Direct model accuracy degradation (0.0-1.0)
            seed: Random seed for reproducibility
            monitoring_run_id: If provided, label only inference rows already
                tagged as members of this monitoring run.
            batch_id: Stable identifier persisted on every generated update.
                Defaults to ``monitoring_run_id`` when one is provided.

        Effective accuracy = max(0.5, accuracy - feature_drift_impact - model_drift_magnitude).
        """
        self.client = athena_client
        self.endpoint_name = endpoint_name
        self.monitoring_run_id = monitoring_run_id
        self.batch_id = batch_id or monitoring_run_id
        self.accuracy = accuracy
        self.positive_confirmation_days = positive_confirmation_days
        self.negative_confirmation_days = negative_confirmation_days
        self.feature_drift_impact = feature_drift_impact
        self.model_drift_magnitude = model_drift_magnitude

        # Effective accuracy: base minus both drift impacts, floored at 50%.
        self.effective_accuracy = max(0.5, accuracy - feature_drift_impact - model_drift_magnitude)

        self.rng = np.random.default_rng(seed)

        logger.info("Initialized GroundTruthSimulator:")
        logger.info(f"  Base accuracy        : {accuracy:.2f}")
        if feature_drift_impact > 0:
            logger.info(f"  Feature drift impact : -{feature_drift_impact:.2f}")
        if model_drift_magnitude > 0:
            logger.info(f"  Model drift magnitude: -{model_drift_magnitude:.2f}")
        logger.info(f"  Effective accuracy   : {self.effective_accuracy:.2f}")

    def load_predictions_without_ground_truth(self, limit: int = None) -> pd.DataFrame:
        """Load inference predictions that don't have ground truth yet."""
        logger.info("Loading predictions without ground truth from Athena...")

        id_col = schema.identifier_column()
        query = f"""
        SELECT
            inference_id,
            {id_col},
            CAST(request_timestamp AS TIMESTAMP(3)) as request_timestamp,
            endpoint_name,
            prediction,
            {PROBABILITY_COLUMN},
            confidence_score
        FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
        WHERE ground_truth IS NULL
        """

        if self.endpoint_name:
            endpoint = self.endpoint_name.replace("'", "''")
            query += f" AND endpoint_name = '{endpoint}'"

        if self.monitoring_run_id:
            run_id = self.monitoring_run_id.replace("'", "''")
            query += f" AND monitoring_run_id = '{run_id}'"

        query += " ORDER BY request_timestamp DESC"

        if limit:
            query += f" LIMIT {limit}"

        df = self.client.execute_query(query)

        if df.empty:
            logger.warning("No predictions found without ground truth")
            return df

        logger.info(f"Loaded {len(df):,} predictions without ground truth")
        logger.info(f"  Predicted positive class: {(df['prediction'] == 1).sum():,}")
        logger.info(f"  Predicted negative class: {(df['prediction'] == 0).sum():,}")

        return df

    def simulate_ground_truth(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Simulate ground truth with realistic correlation to predictions.
        Applies accuracy degradation from feature drift and model drift.

        The accuracy parameter controls how often predictions match ground truth:
        - accuracy = 0.85 means 85% of predictions are correct
        - Remaining 15% are split between false positives and false negatives
        """
        logger.info(f"Simulating ground truth with {self.effective_accuracy*100:.1f}% effective accuracy...")

        if self.effective_accuracy < self.accuracy:
            logger.info(f"  Accuracy degradation: {self.accuracy:.2f} → {self.effective_accuracy:.2f}")
            if self.feature_drift_impact > 0:
                logger.info(f"    Feature drift impact: -{self.feature_drift_impact:.2f}")
            if self.model_drift_magnitude > 0:
                logger.info(f"    Model drift: -{self.model_drift_magnitude:.2f}")

        df = df.copy()

        # Start with predictions as ground truth (perfect accuracy)
        df[ACTUAL_TARGET_COL] = df['prediction'].astype(bool)

        # Introduce errors to reach target effective accuracy
        error_rate = 1.0 - self.effective_accuracy
        num_errors = int(len(df) * error_rate)

        if num_errors > 0:
            # Randomly select which predictions to flip
            error_indices = self.rng.choice(df.index, size=num_errors, replace=False)

            # Flip the ground truth for these errors
            df.loc[error_indices, ACTUAL_TARGET_COL] = ~df.loc[error_indices, ACTUAL_TARGET_COL]

            # Calculate error types
            false_positives = ((df['prediction'] == 1) & (~df[ACTUAL_TARGET_COL])).sum()
            false_negatives = ((df['prediction'] == 0) & (df[ACTUAL_TARGET_COL])).sum()

            logger.info(f"  Introduced {num_errors:,} errors:")
            logger.info(f"    False positives: {false_positives:,}")
            logger.info(f"    False negatives: {false_negatives:,}")

        # Calculate flags
        df['false_positive'] = (df['prediction'] == 1) & (~df[ACTUAL_TARGET_COL])
        df['false_negative'] = (df['prediction'] == 0) & (df[ACTUAL_TARGET_COL])

        # Log statistics
        actual_positive_count = df[ACTUAL_TARGET_COL].sum()
        logger.info(f"\nSimulated ground truth statistics:")
        logger.info(f"  Total: {len(df):,}")
        logger.info(f"  Actual positive class: {actual_positive_count:,} ({actual_positive_count/len(df)*100:.2f}%)")
        logger.info(f"  Actual negative class: {(~df[ACTUAL_TARGET_COL]).sum():,}")

        return df

    def assign_confirmation_timestamps(self, df: pd.DataFrame) -> pd.DataFrame:
        """Assign realistic confirmation timestamps based on class label."""
        logger.info("Assigning confirmation timestamps...")

        df = df.copy()

        # Positive class cases: faster confirmation (1-7 days)
        positive_mask = df[ACTUAL_TARGET_COL]
        if positive_mask.any():
            positive_delays = self.rng.uniform(
                self.positive_confirmation_days[0],
                self.positive_confirmation_days[1],
                size=positive_mask.sum()
            )
            df.loc[positive_mask, 'days_since_prediction'] = positive_delays

        # Negative class cases: slower confirmation (1-30 days)
        negative_mask = ~positive_mask
        if negative_mask.any():
            negative_delays = self.rng.uniform(
                self.negative_confirmation_days[0],
                self.negative_confirmation_days[1],
                size=negative_mask.sum()
            )
            df.loc[negative_mask, 'days_since_prediction'] = negative_delays

        # Calculate confirmation timestamp
        df['confirmation_timestamp'] = pd.to_datetime(df['request_timestamp']) + pd.to_timedelta(
            df['days_since_prediction'], unit='D'
        )

        logger.info(f"  Positive class confirmation delay: {positive_delays.mean():.1f} days (avg)" if positive_mask.any() else "  No positive class cases")
        logger.info(f"  Negative class confirmation delay: {negative_delays.mean():.1f} days (avg)" if negative_mask.any() else "  No negative class cases")

        return df

    def assign_confirmation_sources(self, df: pd.DataFrame) -> pd.DataFrame:
        """Assign confirmation sources based on class label."""
        logger.info("Assigning confirmation sources...")

        df = df.copy()

        # How a term-deposit subscription gets confirmed either way. These are
        # simulated: in production they would be the real back-office systems
        # that report the campaign outcome.
        positive_sources = [
            'deposit_opened',
            'contract_signed',
            'callback_confirmed',
            'branch_visit',
        ]

        negative_sources = [
            'declined_on_call',
            'no_response',
            'unreachable',
        ]

        positive_mask = df[ACTUAL_TARGET_COL]
        df.loc[positive_mask, 'confirmation_source'] = self.rng.choice(
            positive_sources,
            size=positive_mask.sum()
        )

        negative_mask = ~positive_mask
        df.loc[negative_mask, 'confirmation_source'] = self.rng.choice(
            negative_sources,
            size=negative_mask.sum()
        )

        return df

    def create_ground_truth_updates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create ground truth updates dataframe for Athena."""
        logger.info("Creating ground truth updates...")

        # Assign confirmation timestamps
        df = self.assign_confirmation_timestamps(df)

        # Assign confirmation sources
        df = self.assign_confirmation_sources(df)

        # Create updates dataframe with Athena schema
        id_col = schema.identifier_column()
        created_at = datetime.now()
        batch_id = self.batch_id or f'simulated_{created_at.strftime("%Y%m%d_%H%M%S")}'
        updates = pd.DataFrame({
            id_col: df[id_col],
            'inference_id': df['inference_id'],
            ACTUAL_TARGET_COL: df[ACTUAL_TARGET_COL],
            'confirmation_timestamp': df['confirmation_timestamp'],
            'confirmation_source': df['confirmation_source'],
            'transaction_timestamp': pd.to_datetime(df['request_timestamp']),
            'prediction_timestamp': pd.to_datetime(df['request_timestamp']),
            'days_since_transaction': df['days_since_prediction'],  # Same as prediction in this case
            'days_since_prediction': df['days_since_prediction'],
            'investigation_notes': df.apply(self._generate_note, axis=1),
            'investigation_priority': df[ACTUAL_TARGET_COL].apply(lambda x: 'high' if x else 'low'),
            'false_positive': df['false_positive'],
            'false_negative': df['false_negative'],
            'window_id': np.int32(1),  # Default window
            'batch_id': batch_id,
            'created_at': created_at,
            'updated_at': created_at,
        })

        logger.info(f"Created {len(updates):,} ground truth updates")

        return updates

    def _generate_note(self, row) -> str:
        """Generate investigation note based on confirmation source."""
        notes_by_source = {
            'deposit_opened': 'Term deposit account opened',
            'contract_signed': 'Customer signed the deposit agreement',
            'callback_confirmed': 'Customer confirmed the subscription on callback',
            'branch_visit': 'Subscription completed in branch',
            'declined_on_call': 'Customer declined during the call',
            'no_response': 'Campaign window closed with no response',
            'unreachable': 'Customer could not be reached',
        }

        source = row.get('confirmation_source', 'unknown')
        return notes_by_source.get(source, 'No additional details')

    def write_updates_to_athena(self, updates: pd.DataFrame) -> None:
        """Write ground truth updates to Athena table."""
        logger.info(f"Writing {len(updates):,} updates to Athena table: {ATHENA_GROUND_TRUTH_UPDATES_TABLE}...")

        # Write to Athena using Iceberg append
        self.client.write_dataframe(
            df=updates,
            table_name=ATHENA_GROUND_TRUTH_UPDATES_TABLE,
            mode='append'
        )

        logger.info("✓ Ground truth updates written to Athena")

    def simulate_and_write(self, limit: int = None) -> Dict[str, Any]:
        """
        Complete workflow: load predictions, simulate ground truth, write updates.

        Returns:
            Dictionary with statistics
        """
        logger.info("=" * 80)
        logger.info("Starting Ground Truth Simulation")
        logger.info("=" * 80)

        # Load predictions without ground truth
        df = self.load_predictions_without_ground_truth(limit=limit)

        if df.empty:
            logger.warning("No predictions to process")
            return {
                'total_predictions': 0,
                'updates_created': 0,
                'actual_positive': 0,
                'false_positives': 0,
                'false_negatives': 0,
                'accuracy': self.effective_accuracy,
                'monitoring_run_id': self.monitoring_run_id,
                'batch_id': self.batch_id,
            }

        # Simulate ground truth
        df = self.simulate_ground_truth(df)

        # Create updates dataframe
        updates = self.create_ground_truth_updates(df)

        # Write to Athena
        self.write_updates_to_athena(updates)

        # Return statistics
        stats = {
            'total_predictions': len(df),
            'updates_created': len(updates),
            'actual_positive': int(df[ACTUAL_TARGET_COL].sum()),
            'false_positives': int(df['false_positive'].sum()),
            'false_negatives': int(df['false_negative'].sum()),
            'accuracy': float(
                (df['prediction'].astype(bool) == df[ACTUAL_TARGET_COL]).mean()
            ),
            'configured_accuracy': self.effective_accuracy,
            'monitoring_run_id': self.monitoring_run_id,
            'batch_id': updates['batch_id'].iloc[0] if not updates.empty else None,
        }

        logger.info("=" * 80)
        logger.info("Simulation Complete")
        logger.info("=" * 80)
        logger.info(f"  Total predictions processed: {stats['total_predictions']:,}")
        logger.info(f"  Ground truth updates created: {stats['updates_created']:,}")
        logger.info(f"  Actual positive class: {stats['actual_positive']:,} ({stats['actual_positive']/stats['total_predictions']*100:.2f}%)")
        logger.info(f"  False positives: {stats['false_positives']:,}")
        logger.info(f"  False negatives: {stats['false_negatives']:,}")
        logger.info(f"  Model accuracy: {stats['accuracy']*100:.1f}%")
        logger.info("=" * 80)

        return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Simulate ground truth for Athena inference predictions'
    )
    parser.add_argument(
        '--endpoint-name',
        type=str,
        help='Filter predictions by endpoint name'
    )
    parser.add_argument(
        '--accuracy',
        type=float,
        default=0.85,
        help='Model accuracy (0.0-1.0, default: 0.85)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of predictions to process'
    )
    parser.add_argument(
        '--positive-days',
        type=str,
        default='1,7',
        help='Positive class confirmation delay range in days (min,max, default: 1,7)'
    )
    parser.add_argument(
        '--negative-days',
        type=str,
        default='1,30',
        help='Negative class confirmation delay range in days (min,max, default: 1,30)'
    )
    parser.add_argument(
        '--seed',
        type=int,
        default=42,
        help='Random seed for reproducibility (default: 42)'
    )

    args = parser.parse_args()

    # Parse day ranges
    positive_days = tuple(map(int, args.positive_days.split(',')))
    negative_days = tuple(map(int, args.negative_days.split(',')))

    # Initialize Athena client
    athena_client = AthenaClient()

    # Create simulator
    simulator = GroundTruthSimulator(
        athena_client=athena_client,
        endpoint_name=args.endpoint_name,
        accuracy=args.accuracy,
        positive_confirmation_days=positive_days,
        negative_confirmation_days=negative_days,
        seed=args.seed,
    )

    # Run simulation
    try:
        stats = simulator.simulate_and_write(limit=args.limit)

        if stats['updates_created'] > 0:
            print("\n✅ Ground truth simulation complete!")
            print(f"\nNext steps:")
            print(f"  1. Run update_ground_truth.py to merge updates into inference_responses:")
            print(f"     python scripts/update_ground_truth.py --mode batch")
            print(f"\n  2. Check coverage in inference monitoring notebook (Cell 16)")
            print(f"\n  3. Run monitoring to detect drift (Cells 21-34)")

        return 0

    except Exception as e:
        logger.error(f"Error during simulation: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
