#!/usr/bin/env python3
"""
Update inference_responses with ground truth from ground_truth_updates table.

This script simulates the production process where:
1. Model makes predictions (inference_responses created with ground_truth=NULL)
2. Outcomes are confirmed (ground_truth_updates table receives confirmations)
3. Batch job JOINs tables and backfills ground_truth

Usage:
    # Update all pending (dry run)
    python scripts/update_ground_truth.py --mode batch --dry-run

    # Update all pending (execute)
    python scripts/update_ground_truth.py --mode batch

    # Update recent confirmations (last 24 hours)
    python scripts/update_ground_truth.py --mode streaming --window-hours 24

    # Force update (override existing ground truth)
    python scripts/update_ground_truth.py --mode batch --force
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import pandas as pd
import numpy as np

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from src.train_pipeline.athena.athena_client import AthenaClient
from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_INFERENCE_TABLE,
    ATHENA_GROUND_TRUTH_UPDATES_TABLE,
    PROBABILITY_COLUMN,
)
from src.config import schema

# Schema-driven column name for ground truth in ground_truth_updates table.
ACTUAL_TARGET_COL = f'actual_{schema.target_column()}'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GroundTruthUpdater:
    """Update inference_responses table with confirmed ground truth."""

    def __init__(
        self,
        athena_client: Optional[AthenaClient] = None,
        dry_run: bool = False,
        force: bool = False,
        monitoring_run_id: Optional[str] = None,
    ):
        """
        Initialize ground truth updater.

        Args:
            athena_client: Athena client (creates default if None)
            dry_run: If True, only preview changes without executing
            force: If True, override existing ground truth values
            monitoring_run_id: If provided, update only inference rows tagged
                as members of this monitoring run.
        """
        self.client = athena_client or AthenaClient()
        self.dry_run = dry_run
        self.force = force
        self.monitoring_run_id = monitoring_run_id

    def _run_filter(self, alias: str = "ir") -> str:
        """Return an escaped SQL predicate for the selected monitoring run."""
        if not self.monitoring_run_id:
            return ""
        run_id = self.monitoring_run_id.replace("'", "''")
        prefix = f"{alias}." if alias else ""
        return f" AND {prefix}monitoring_run_id = '{run_id}'"

    def get_pending_updates_count(
        self,
        window_hours: Optional[int] = None,
    ) -> int:
        """
        Count inference responses awaiting ground truth updates.

        Args:
            window_hours: Optional time window (recent confirmations only)

        Returns:
            Number of pending updates
        """
        logger.info("Counting pending ground truth updates...")

        # Build query
        query = f"""
        SELECT COUNT(DISTINCT ir.inference_id) as pending_count
        FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} ir
        INNER JOIN {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
            ON ir.inference_id = gtu.inference_id
        WHERE {'ir.ground_truth IS NULL' if not self.force else '1=1'}
        {self._run_filter()}
        """

        if window_hours:
            query += f"""
            AND gtu.confirmation_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{window_hours}' HOUR
            """

        # Execute query
        result = self.client.execute_query(query)
        count = int(result['pending_count'].iloc[0]) if not result.empty else 0

        logger.info(f"Found {count:,} pending updates")
        return count

    def preview_updates(
        self,
        window_hours: Optional[int] = None,
        limit: int = 10,
    ) -> pd.DataFrame:
        """
        Preview updates that will be applied.

        Args:
            window_hours: Optional time window
            limit: Number of examples to show

        Returns:
            DataFrame with preview data
        """
        logger.info(f"Previewing {limit} updates...")

        query = f"""
        SELECT
            ir.inference_id,
            ir.{schema.identifier_column()},
            ir.request_timestamp as prediction_timestamp,
            ir.prediction as current_prediction,
            ir.{PROBABILITY_COLUMN} as predicted_probability,
            ir.ground_truth as current_ground_truth,
            gtu.{ACTUAL_TARGET_COL} as new_ground_truth,
            gtu.confirmation_timestamp,
            gtu.confirmation_source,
            gtu.days_since_prediction,
            CASE
                WHEN ir.prediction = CAST(gtu.{ACTUAL_TARGET_COL} AS INT) THEN 'correct'
                ELSE 'incorrect'
            END as prediction_correctness,
            CASE
                WHEN ir.prediction = 1 AND gtu.{ACTUAL_TARGET_COL} = false THEN 'false_positive'
                WHEN ir.prediction = 0 AND gtu.{ACTUAL_TARGET_COL} = true THEN 'false_negative'
                ELSE 'correct'
            END as error_type
        FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} ir
        INNER JOIN {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
            ON ir.inference_id = gtu.inference_id
        WHERE {'ir.ground_truth IS NULL' if not self.force else '1=1'}
        {self._run_filter()}
        """

        if window_hours:
            query += f"""
            AND gtu.confirmation_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{window_hours}' HOUR
            """

        query += f" LIMIT {limit}"

        # Execute query
        df = self.client.execute_query(query)

        if not df.empty:
            logger.info(f"\nPreview of updates:")
            print(df.to_string(index=False))
            print()

        return df

    def get_update_statistics(
        self,
        window_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Get statistics about updates to be applied.

        Args:
            window_hours: Optional time window

        Returns:
            Dictionary with statistics
        """
        logger.info("Calculating update statistics...")

        query = f"""
        SELECT
            COUNT(*) as total_updates,
            COALESCE(SUM(CAST(gtu.{ACTUAL_TARGET_COL} AS INT)), 0) as positive_cases,
            COALESCE(SUM(CASE WHEN ir.prediction = CAST(gtu.{ACTUAL_TARGET_COL} AS INT) THEN 1 ELSE 0 END), 0) as correct_predictions,
            COALESCE(SUM(CASE WHEN ir.prediction = 1 AND gtu.{ACTUAL_TARGET_COL} = false THEN 1 ELSE 0 END), 0) as false_positives,
            COALESCE(SUM(CASE WHEN ir.prediction = 0 AND gtu.{ACTUAL_TARGET_COL} = true THEN 1 ELSE 0 END), 0) as false_negatives,
            AVG(gtu.days_since_prediction) as avg_days_to_confirmation,
            CAST(MIN(gtu.confirmation_timestamp) AS TIMESTAMP(3)) as earliest_confirmation,
            CAST(MAX(gtu.confirmation_timestamp) AS TIMESTAMP(3)) as latest_confirmation
        FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} ir
        INNER JOIN {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
            ON ir.inference_id = gtu.inference_id
        WHERE {'ir.ground_truth IS NULL' if not self.force else '1=1'}
        {self._run_filter()}
        """

        if window_hours:
            query += f"""
            AND gtu.confirmation_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{window_hours}' HOUR
            """

        # Execute query
        result = self.client.execute_query(query)

        if result.empty:
            return {
                'total_updates': 0,
                'positive_cases': 0,
                'correct_predictions': 0,
                'false_positives': 0,
                'false_negatives': 0,
                'avg_days_to_confirmation': 0.0,
            }

        stats = result.iloc[0].to_dict()

        # Calculate accuracy
        total = stats['total_updates']
        if total > 0:
            stats['accuracy'] = stats['correct_predictions'] / total
            stats['false_positive_rate'] = stats['false_positives'] / total
            stats['false_negative_rate'] = stats['false_negatives'] / total
        else:
            stats['accuracy'] = 0.0
            stats['false_positive_rate'] = 0.0
            stats['false_negative_rate'] = 0.0

        return stats

    def update_ground_truth_batch(
        self,
        window_hours: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Update ground truth for all pending inference responses (batch mode).

        This uses Iceberg MERGE to update existing records atomically.

        Args:
            window_hours: Optional time window for recent confirmations

        Returns:
            Dictionary with update results
        """
        logger.info("=" * 80)
        logger.info("Ground Truth Batch Update")
        logger.info("=" * 80)

        # Get statistics before update
        stats_before = self.get_update_statistics(window_hours)
        pending_count = stats_before['total_updates']

        if pending_count == 0:
            logger.info("No pending updates found")
            return {'updated': 0, 'stats': stats_before}

        logger.info(f"\nUpdate statistics:")
        logger.info(f"  Total updates: {pending_count:,}")
        logger.info(f"  Positive (target=true) cases: {stats_before['positive_cases']:,}")
        logger.info(f"  Correct predictions: {stats_before['correct_predictions']:,} ({stats_before['accuracy']*100:.2f}%)")
        logger.info(f"  False positives: {stats_before['false_positives']:,} ({stats_before['false_positive_rate']*100:.2f}%)")
        logger.info(f"  False negatives: {stats_before['false_negatives']:,} ({stats_before['false_negative_rate']*100:.2f}%)")
        logger.info(f"  Avg days to confirmation: {stats_before['avg_days_to_confirmation']:.2f}")

        if self.dry_run:
            logger.info("\n[DRY RUN] Would execute update but skipping due to --dry-run flag")
            return {'updated': 0, 'stats': stats_before, 'dry_run': True}

        # Build MERGE statement for Iceberg table
        # Deduplicate ground_truth_updates (simulator may have been run multiple times)
        # Pick the latest confirmation for each inference_id using ROW_NUMBER()
        window_filter = ""
        if window_hours:
            window_filter = f"AND gtu.confirmation_timestamp >= CURRENT_TIMESTAMP - INTERVAL '{window_hours}' HOUR"

        ground_truth_filter = "ir.ground_truth IS NULL" if not self.force else "1=1"

        merge_query = f"""
        MERGE INTO {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} AS target
        USING (
            SELECT inference_id, ground_truth, ground_truth_timestamp,
                   ground_truth_source, days_to_ground_truth
            FROM (
                SELECT
                    ir.inference_id,
                    CAST(gtu.{ACTUAL_TARGET_COL} AS INT) as ground_truth,
                    gtu.confirmation_timestamp as ground_truth_timestamp,
                    gtu.confirmation_source as ground_truth_source,
                    gtu.days_since_prediction as days_to_ground_truth,
                    ROW_NUMBER() OVER (PARTITION BY ir.inference_id ORDER BY gtu.confirmation_timestamp DESC) as rn
                FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} ir
                INNER JOIN {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
                    ON ir.inference_id = gtu.inference_id
                WHERE {ground_truth_filter}
                {self._run_filter()}
                {window_filter}
            )
            WHERE rn = 1
        ) AS source
        ON target.inference_id = source.inference_id
        WHEN MATCHED THEN UPDATE SET
            ground_truth = source.ground_truth,
            ground_truth_timestamp = source.ground_truth_timestamp,
            ground_truth_source = source.ground_truth_source,
            days_to_ground_truth = source.days_to_ground_truth
        """

        # Execute update
        logger.info("\nExecuting MERGE statement...")
        try:
            self.client.execute_query(merge_query, return_results=False)
            logger.info(f"✓ Successfully updated {pending_count:,} records")

            result = {
                'updated': pending_count,
                'stats': stats_before,
                'dry_run': False,
            }

            return result

        except Exception as e:
            logger.error(f"Error executing MERGE: {e}")
            logger.info("\nFalling back to UPDATE statement...")

            # Fallback: Athena UPDATE with subquery (no FROM clause)
            update_query = f"""
            UPDATE {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE}
            SET ground_truth = (
                    SELECT CAST(gtu.{ACTUAL_TARGET_COL} AS INT)
                    FROM {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
                    WHERE gtu.inference_id = {ATHENA_INFERENCE_TABLE}.inference_id
                    ORDER BY gtu.confirmation_timestamp DESC
                    LIMIT 1
                ),
                ground_truth_timestamp = (
                    SELECT gtu.confirmation_timestamp
                    FROM {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
                    WHERE gtu.inference_id = {ATHENA_INFERENCE_TABLE}.inference_id
                    ORDER BY gtu.confirmation_timestamp DESC
                    LIMIT 1
                ),
                ground_truth_source = (
                    SELECT gtu.confirmation_source
                    FROM {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
                    WHERE gtu.inference_id = {ATHENA_INFERENCE_TABLE}.inference_id
                    ORDER BY gtu.confirmation_timestamp DESC
                    LIMIT 1
                ),
                days_to_ground_truth = (
                    SELECT gtu.days_since_prediction
                    FROM {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} gtu
                    WHERE gtu.inference_id = {ATHENA_INFERENCE_TABLE}.inference_id
                    ORDER BY gtu.confirmation_timestamp DESC
                    LIMIT 1
                )
            WHERE {ground_truth_filter}
                {self._run_filter(alias="")}
                AND inference_id IN (
                    SELECT DISTINCT inference_id
                    FROM {ATHENA_DATABASE}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE}
                )
            """

            self.client.execute_query(update_query, return_results=False)
            logger.info(f"✓ Successfully updated {pending_count:,} records")

            result = {
                'updated': pending_count,
                'stats': stats_before,
                'dry_run': False,
            }

            return result

    def update_ground_truth_streaming(
        self,
        window_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Update ground truth for recent confirmations (streaming mode).

        Args:
            window_hours: Time window in hours (default: 24)

        Returns:
            Dictionary with update results
        """
        logger.info("=" * 80)
        logger.info(f"Ground Truth Streaming Update (last {window_hours} hours)")
        logger.info("=" * 80)

        return self.update_ground_truth_batch(window_hours=window_hours)

    def get_coverage_statistics(self) -> Dict[str, Any]:
        """
        Get ground truth coverage statistics.

        Returns:
            Dictionary with coverage stats
        """
        logger.info("Calculating ground truth coverage...")

        query = f"""
        SELECT
            COUNT(*) as total_predictions,
            COALESCE(SUM(CASE WHEN ground_truth IS NOT NULL THEN 1 ELSE 0 END), 0) as with_ground_truth,
            COALESCE(SUM(CASE WHEN ground_truth IS NULL THEN 1 ELSE 0 END), 0) as without_ground_truth,
            CAST(MIN(request_timestamp) AS TIMESTAMP(3)) as earliest_prediction,
            CAST(MAX(request_timestamp) AS TIMESTAMP(3)) as latest_prediction,
            CAST(MIN(ground_truth_timestamp) AS TIMESTAMP(3)) as earliest_ground_truth,
            CAST(MAX(ground_truth_timestamp) AS TIMESTAMP(3)) as latest_ground_truth
        FROM {ATHENA_DATABASE}.{ATHENA_INFERENCE_TABLE} ir
        WHERE 1=1
        {self._run_filter()}
        """

        result = self.client.execute_query(query)

        if result.empty:
            return {'total_predictions': 0, 'coverage': 0.0}

        stats = result.iloc[0].to_dict()
        total = stats['total_predictions']
        with_gt = stats['with_ground_truth']

        stats['coverage'] = with_gt / total if total > 0 else 0.0
        stats['coverage_pct'] = stats['coverage'] * 100

        return stats


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Update inference_responses with ground truth from investigations'
    )
    parser.add_argument(
        '--mode',
        choices=['batch', 'streaming'],
        default='batch',
        help='Update mode: batch (all pending) or streaming (recent only)'
    )
    parser.add_argument(
        '--window-hours',
        type=int,
        default=24,
        help='Time window in hours for streaming mode (default: 24)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview changes without executing'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force update (override existing ground truth)'
    )
    parser.add_argument(
        '--preview-limit',
        type=int,
        default=10,
        help='Number of examples to preview (default: 10)'
    )

    args = parser.parse_args()

    # Create updater
    updater = GroundTruthUpdater(
        dry_run=args.dry_run,
        force=args.force,
    )

    try:
        # Get initial coverage
        coverage = updater.get_coverage_statistics()
        logger.info(f"\nCurrent ground truth coverage:")
        logger.info(f"  Total predictions: {coverage['total_predictions']:,}")
        logger.info(f"  With ground truth: {coverage['with_ground_truth']:,} ({coverage['coverage_pct']:.2f}%)")
        logger.info(f"  Without ground truth: {coverage['without_ground_truth']:,}")

        # Preview updates
        if args.mode == 'batch':
            updater.preview_updates(limit=args.preview_limit)
        else:
            updater.preview_updates(window_hours=args.window_hours, limit=args.preview_limit)

        # Execute updates
        if args.mode == 'batch':
            result = updater.update_ground_truth_batch()
        else:
            result = updater.update_ground_truth_streaming(window_hours=args.window_hours)

        # Get updated coverage
        if not result.get('dry_run', False):
            coverage_after = updater.get_coverage_statistics()
            logger.info(f"\nUpdated ground truth coverage:")
            logger.info(f"  Total predictions: {coverage_after['total_predictions']:,}")
            logger.info(f"  With ground truth: {coverage_after['with_ground_truth']:,} ({coverage_after['coverage_pct']:.2f}%)")
            logger.info(f"  Coverage improvement: +{coverage_after['coverage_pct'] - coverage['coverage_pct']:.2f}%")

        # Print summary
        print("\n" + "=" * 80)
        print("Update Summary")
        print("=" * 80)
        print(f"Mode: {args.mode}")
        if args.mode == 'streaming':
            print(f"Window: Last {args.window_hours} hours")
        print(f"Dry run: {args.dry_run}")
        print(f"Records updated: {result['updated']:,}")
        if result['updated'] > 0:
            stats = result['stats']
            print(f"Accuracy: {stats['accuracy']*100:.2f}%")
            print(f"False positives: {stats['false_positives']:,}")
            print(f"False negatives: {stats['false_negatives']:,}")
        print("=" * 80)

        return 0

    except Exception as e:
        logger.error(f"Error updating ground truth: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
