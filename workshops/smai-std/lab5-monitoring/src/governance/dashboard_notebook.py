"""
Notebook-facing wrappers for lab5e-governance-dashboard.ipynb.

create_governance_dashboard.py does the work and raises on failure, which is
right for `main.py dashboard create`. In the notebook, the failures that can
happen (QuickSight not subscribed, execution role missing QuickSight actions)
are account / IAM setup the learner cannot fix from a cell, so these wrappers
report them with the fix and let the notebook continue — the drift data is
already in Athena and MLflow either way (Lab 5D).
"""

import os
from typing import Any, Dict, Optional

import boto3
from botocore.exceptions import ClientError

from src.config.config import AWS_DEFAULT_REGION, QUICKSIGHT_IDENTITY_REGION
from src.governance import create_governance_dashboard as gov

DATASET_KEYS = ('inference', 'drift', 'feature_drift', 'feature_level', 'accuracy')


def account_id() -> str:
    return os.environ.get('ACCOUNT_ID') or \
        boto3.client('sts', region_name=AWS_DEFAULT_REGION).get_caller_identity()['Account']


def describe_environment(project_name: str) -> str:
    """Print the identifiers this notebook works with; returns the account id."""
    acct = account_id()
    print(f'  PROJECT_NAME               = {project_name}')
    print(f'  ACCOUNT_ID                 = {acct}')
    print(f'  AWS_DEFAULT_REGION         = {AWS_DEFAULT_REGION}')
    print(f'  QUICKSIGHT_IDENTITY_REGION = {QUICKSIGHT_IDENTITY_REGION}')
    return acct


def report_subscription(acct: Optional[str] = None) -> Dict[str, Any]:
    """Run the subscription check create_dashboard() runs internally, and explain the result.

    Surfaced before anything is created so the two things that can block the
    notebook are named up front. Reports and returns instead of raising.
    """
    quicksight_admin = boto3.client('quicksight', region_name=QUICKSIGHT_IDENTITY_REGION)
    subscription = gov.check_quicksight_subscription(
        account_id=acct or account_id(), quicksight_admin_client=quicksight_admin,
    )
    if subscription['subscribed']:
        print(f"✓ QuickSight active (Edition: {subscription['edition']})")
        if subscription['edition'] == 'STANDARD':
            print('  ⚠ Definition API requires Enterprise edition — upgrade before Section 3.')
    elif subscription['reason'] == 'access-denied':
        print('✗ Cannot check QuickSight: this role lacks quicksight:DescribeAccountSettings.')
        print('  QuickSight may well be subscribed — this is an IAM gap, not a sign-up gap.')
        print('  Fix: run scripts/deploy-workshop.sh to apply the QuickSightGovernanceDashboard')
        print("       statement from templates/2-iam.yaml to this notebook's execution role.")
    else:
        print('✗ QuickSight not subscribed for this account.')
        print('  Subscribe from the console (once per account, billable): search the AWS')
        print('  console for "quick" and sign up. The form has no edition selector, so')
        print('  re-run this cell afterwards to confirm you landed on ENTERPRISE.')
        print('  Then attach the data-access policies to aws-quicksight-service-role-v0 —')
        print('  see the markdown cell above for both halves.')
    return subscription


def build_dashboard(region: str = AWS_DEFAULT_REGION) -> Optional[Dict[str, Any]]:
    """gov.create_dashboard(), with setup failures reported instead of raised.

    Returns the create_dashboard() summary dict, or None if it was not created.
    """
    try:
        result = gov.create_dashboard(region=region)
    except gov.QuickSightUnavailable as exc:
        print(f'✗ Dashboard not created — {exc}')
        return None
    except ClientError as exc:
        if exc.response['Error']['Code'] not in ('AccessDeniedException', 'UnrecognizedClientException'):
            raise
        # Subscription check passed but a later call was denied: the role has
        # some QuickSight permissions but not all of them.
        print('✗ Dashboard not created — QuickSight denied a call this notebook needs:')
        print(f"  {exc.operation_name}: {exc.response['Error']['Message']}")
        print('  Fix: attach the full quicksight:* action list from templates/2-iam.yaml')
        print("       (QuickSightGovernanceDashboard statement) to this notebook's execution role.")
        return None

    print()
    print('=' * 70)
    print('Dashboard build complete')
    print('=' * 70)
    print(f"QuickSight subscribed: {result['quicksight_subscribed']} (edition: {result['quicksight_edition']})")
    print(f"Dashboard URL:  {result['dashboard_url']}")
    print(f"Dashboard ARN:  {result['dashboard_arn']}")
    print(f"Analysis ARN:   {result['analysis_arn']}")
    print()
    print('Datasets:')
    for k in DATASET_KEYS:
        print(f"  {k:14s} {result.get(f'{k}_dataset_arn', 'N/A')}")
    if result.get('embed_url'):
        print(f"\nEmbed URL (valid 10h):\n  {result['embed_url']}")
    return result


def delete_dashboard(region: str = AWS_DEFAULT_REGION) -> Dict[str, Any]:
    """gov.delete_dashboard(), with the outcome printed."""
    outcome = gov.delete_dashboard(region=region)
    print('Deleted:  ', outcome['deleted'])
    print('Not found:', outcome['not_found'])
    print('Errors:   ', outcome['errors'])
    return outcome
