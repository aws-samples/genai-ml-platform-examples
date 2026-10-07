"""
Library of QuickSight governance dashboard operations.

Functions:
- check_quicksight_subscription   — verify QuickSight is active for the account
- verify_athena_data               — check inference/monitoring row counts in Athena
- get_quicksight_principals        — list QuickSight user ARNs to grant permissions to
- create_or_update_datasource      — create/update the Athena data source
- grant_governance_permissions     — Lake Formation table grants (+ QuickSight service-role check)
- create_inference_dataset         — inference_responses dataset (+ calculated columns)
- create_drift_dataset             — monitoring_responses dataset (+ calculated columns)
- create_feature_drift_dataset     — CustomSql join of monitoring_responses + inference_responses
- create_feature_drift_detail_view — Athena view unpacking per-feature drift scores
- grant_feature_drift_view_permissions — Lake Formation grant on the view
- create_feature_level_dataset     — dataset backed by the feature_drift_detail view
- create_accuracy_dataset          — CustomSql join of inference_responses + ground_truth_updates
- build_model_drift_visuals / build_data_drift_visuals / build_feature_drift_visuals
                                    — pure-data visual definitions for the 3 sheets
                                      (Model Drift 11, Data Drift 10, Feature Drift 11 = 32 total)
- create_or_update_analysis        — QuickSight analysis via the Definition API
- publish_dashboard                — QuickSight dashboard via the Definition API
- get_dashboard_embed_url          — best-effort embed URL generation
- delete_governance_resources      — tear down dashboard/analysis/datasets/datasource
- create_dashboard                 — top-level orchestrator (build everything)
- delete_dashboard                 — top-level orchestrator (tear everything down)

Ported from `lab5e-governance-dashboard.ipynb` so this dashboard-build
logic is importable and testable outside a notebook; that notebook is a thin
driver over `create_dashboard()` / `delete_dashboard()`. This module
is intentionally library-only — no `__main__` block — matching
`deploy_endpoint.py` / `manage_drift_lambda.py`.

Every PhysicalTableMap / LogicalTableMap / CustomSql / visual dict below is
ported byte-for-byte from the notebook — these are exact AWS API request
shapes, not reimplementations.

Lake Formation reconciliation (notebook Section 5):
The notebook defines an inline `grant_lakeformation_permissions()` that
shells out to `aws lakeformation grant-permissions` via `subprocess` to
grant `IAM_ALLOWED_PRINCIPALS` on the database + 3 tables (inference_responses,
monitoring_responses, ground_truth_updates). `src/setup/grant_lake_formation_permissions.py`
already does the equivalent job via boto3 (no subprocess) against the
caller's resolved IAM identity across a superset of tables (all 7 project
tables — harmless/idempotent to grant on all of them), so
`grant_governance_permissions()` below calls that existing module directly
for the table-level grants instead of reimplementing the notebook's
subprocess-based loop. QuickSight's own data access (inline policies on its
service role) is declared in templates/2-iam.yaml so that CloudFormation owns
every IAM grant in the workshop; `_check_s3_permissions()` only reports whether
those policies are in place. The `feature_drift_detail` Athena VIEW needs
its own Lake Formation grant since it isn't one of the 7 tables the reused
module covers — issued directly via boto3 in
`grant_feature_drift_view_permissions()` (the notebook used a subprocess
`aws lakeformation grant-permissions` CLI call for this one grant; boto3's
`lakeformation.grant_permissions()` API takes an identical
`Resource={'Table': {...}}` shape for both tables and views, so there is no
functional reason to shell out here — using boto3 directly keeps this
module consistent with every other AWS call it makes).
"""

import logging
import time
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from src.config import config, schema
from src.config.config import (
    ATHENA_DATABASE,
    ATHENA_GROUND_TRUTH_UPDATES_TABLE,
    ATHENA_INFERENCE_TABLE,
    ATHENA_MONITORING_RESPONSES_TABLE,
    ATHENA_OUTPUT_S3,
    AWS_DEFAULT_REGION,
    LAMBDA_EXEC_ROLE,
    PREDICTION_COLUMN,
    PROBABILITY_ALT_COLUMN,
    PROBABILITY_COLUMN,
    QUICKSIGHT_ACCURACY_DATASET_ID,
    QUICKSIGHT_ACCURACY_DATASET_NAME,
    QUICKSIGHT_ANALYSIS_ID,
    QUICKSIGHT_ANALYSIS_NAME,
    QUICKSIGHT_DASHBOARD_ID,
    QUICKSIGHT_DASHBOARD_NAME,
    QUICKSIGHT_DATASOURCE_ID,
    QUICKSIGHT_DATASOURCE_NAME,
    QUICKSIGHT_DRIFT_DATASET_ID,
    QUICKSIGHT_DRIFT_DATASET_NAME,
    QUICKSIGHT_FEATURE_DRIFT_DATASET_ID,
    QUICKSIGHT_FEATURE_DRIFT_DATASET_NAME,
    QUICKSIGHT_FEATURE_LEVEL_DATASET_ID,
    QUICKSIGHT_FEATURE_LEVEL_DATASET_NAME,
    QUICKSIGHT_IDENTITY_REGION,
    QUICKSIGHT_INFERENCE_DATASET_ID,
    QUICKSIGHT_INFERENCE_DATASET_NAME,
    QUICKSIGHT_SERVICE_ROLE_NAME,
    QUICKSIGHT_S3_POLICY_NAME,
    QUICKSIGHT_ATHENA_POLICY_NAME,
)
from src.setup.grant_lake_formation_permissions import (
    grant_lake_formation_permissions,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Name of the Athena view created by create_feature_drift_detail_view(),
# unpacking the JSON per_feature_drift_scores column into one row per
# (monitoring_run_id, feature).
FEATURE_DRIFT_DETAIL_VIEW = 'feature_drift_detail'

# Dataset identifiers used in the Definition API's DataSetIdentifierDeclarations
# (bound to real dataset ARNs at analysis/dashboard-build time). Matches the
# notebook's local identifiers exactly so the ported visual JSON needs no changes.
DS_IDENT_INFERENCE = 'inference-ds'
DS_IDENT_DRIFT = 'drift-ds'
DS_IDENT_FEATURE_DRIFT = 'feature-drift-ds'
DS_IDENT_FEATURE_LEVEL = 'feature-level-ds'
DS_IDENT_ACCURACY = 'accuracy-ds'

# Standard QuickSight action sets granted to every principal on each resource
# type — copied verbatim from the notebook's DS_ACTIONS / DSET_ACTIONS /
# ANALYSIS_ACTIONS / DASHBOARD_ACTIONS.
_DATASOURCE_ACTIONS = [
    'quicksight:DescribeDataSource', 'quicksight:DescribeDataSourcePermissions',
    'quicksight:PassDataSource', 'quicksight:UpdateDataSource',
    'quicksight:DeleteDataSource', 'quicksight:UpdateDataSourcePermissions',
]
_DATASET_ACTIONS = [
    'quicksight:DescribeDataSet', 'quicksight:DescribeDataSetPermissions',
    'quicksight:PassDataSet', 'quicksight:DescribeIngestion',
    'quicksight:ListIngestions', 'quicksight:UpdateDataSet',
    'quicksight:DeleteDataSet', 'quicksight:CreateIngestion',
    'quicksight:CancelIngestion', 'quicksight:UpdateDataSetPermissions',
]
_ANALYSIS_ACTIONS = [
    'quicksight:RestoreAnalysis', 'quicksight:UpdateAnalysisPermissions',
    'quicksight:DeleteAnalysis', 'quicksight:DescribeAnalysisPermissions',
    'quicksight:QueryAnalysis', 'quicksight:DescribeAnalysis', 'quicksight:UpdateAnalysis',
]
_DASHBOARD_ACTIONS = [
    'quicksight:DescribeDashboard', 'quicksight:ListDashboardVersions',
    'quicksight:UpdateDashboardPermissions', 'quicksight:QueryDashboard',
    'quicksight:UpdateDashboard', 'quicksight:DeleteDashboard',
    'quicksight:DescribeDashboardPermissions', 'quicksight:UpdateDashboardPublishedVersion',
]


class QuickSightUnavailable(RuntimeError):
    """QuickSight cannot be used from here — not subscribed, or IAM denies it.

    Raised instead of letting the first QuickSight call fail with a bare
    ClientError, so the message names the one thing that has to change (an
    account sign-up, or a policy on the execution role). Neither is fixable
    from inside the notebook, which is why the notebook catches this and
    reports it rather than dying on it.
    """


# ---------------------------------------------------------------------------
# Section 2/3 — read-only verification checks
# ---------------------------------------------------------------------------


def check_quicksight_subscription(
    account_id: Optional[str] = None,
    quicksight_admin_client: Optional[Any] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Check whether QuickSight is subscribed/active for this account.

    Mirrors the notebook's Section 2 check: `describe_account_settings`
    against the identity-region client. Any edition (including STANDARD)
    counts as "subscribed" — the notebook only warns (doesn't raise) when
    the edition is STANDARD, since the Definition API requires Enterprise.

    Args:
        account_id: AWS account ID. Resolved via STS if not provided.
        quicksight_admin_client: Optional boto3 QuickSight client bound to
            QUICKSIGHT_IDENTITY_REGION (constructed if not provided).
        region: QuickSight identity region for client construction.
            Defaults to config.QUICKSIGHT_IDENTITY_REGION.

    Returns:
        Dict with keys 'subscribed' (bool), 'edition' (str or None) and
        'reason' (str or None — why the check could not confirm).
        Returns subscribed=False rather than raising for the two conditions a
        workshop account actually hits: QuickSight never signed up for
        (``ResourceNotFoundException``) and the execution role lacking
        ``quicksight:DescribeAccountSettings`` (``AccessDeniedException``).
        Those are different fixes — sign-up vs IAM — so they are reported
        separately instead of as one "not subscribed".
    """
    resolved_region = region or QUICKSIGHT_IDENTITY_REGION

    if quicksight_admin_client is None:
        quicksight_admin_client = boto3.client('quicksight', region_name=resolved_region)

    resolved_account_id = account_id
    if resolved_account_id is None:
        sts_client = boto3.client('sts', region_name=resolved_region)
        resolved_account_id = sts_client.get_caller_identity()['Account']

    try:
        settings = quicksight_admin_client.describe_account_settings(AwsAccountId=resolved_account_id)
        edition = settings.get('AccountSettings', {}).get('Edition', 'Unknown')
        logger.info(f"✓ QuickSight active (Edition: {edition})")
        if edition == 'STANDARD':
            logger.warning("Definition API requires Enterprise edition")
        return {'subscribed': True, 'edition': edition, 'reason': None}
    except ClientError as e:
        code = e.response['Error']['Code']
        if code == 'ResourceNotFoundException':
            logger.error(
                "QuickSight not subscribed for this account — sign up once from the "
                "console (search for 'quick'), confirm the edition is ENTERPRISE, then "
                "attach the data-access policies to aws-quicksight-service-role-v0 by "
                "deploying with AttachQuickSightServiceRolePolicy=true. For bulk "
                "provisioning, SUBSCRIBE_QUICKSIGHT=true "
                "QUICKSIGHT_NOTIFICATION_EMAIL=<address> scripts/deploy-workshop.sh "
                "does both."
            )
            return {'subscribed': False, 'edition': None, 'reason': 'not-subscribed'}
        if code in ('AccessDeniedException', 'UnrecognizedClientException'):
            logger.error(
                "Cannot check QuickSight: this role lacks quicksight:DescribeAccountSettings. "
                "QuickSight may well be subscribed — this is an IAM gap, not a sign-up gap. "
                "Grant the quicksight:* actions listed in templates/2-iam.yaml "
                "(QuickSightGovernanceDashboard statement) to the lab role, then re-run."
            )
            return {'subscribed': False, 'edition': None, 'reason': 'access-denied'}
        raise


def _run_athena_query(
    sql: str,
    athena_client: Any,
    database: str,
    output_s3: str,
    poll_interval: int = 1,
) -> Dict[str, Any]:
    """
    Run an Athena query synchronously and return its results.

    Direct port of the notebook's `run_athena_query()` helper (Section 3).

    Args:
        sql: SQL query string
        athena_client: boto3 Athena client
        database: Athena database name
        output_s3: S3 location for query results
        poll_interval: Seconds between status polls

    Returns:
        The `get_query_results` response dict.

    Raises:
        RuntimeError: If the query does not SUCCEED.
    """
    start = athena_client.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={'Database': database},
        ResultConfiguration={'OutputLocation': output_s3},
    )
    execution_id = start['QueryExecutionId']
    while True:
        status_resp = athena_client.get_query_execution(QueryExecutionId=execution_id)
        state = status_resp['QueryExecution']['Status']['State']
        if state in ('SUCCEEDED', 'FAILED', 'CANCELLED'):
            break
        time.sleep(poll_interval)

    if state != 'SUCCEEDED':
        reason = status_resp['QueryExecution']['Status'].get('StateChangeReason', '')
        raise RuntimeError(f'Query {state}: {reason}')

    return athena_client.get_query_results(QueryExecutionId=execution_id)


def verify_athena_data(
    database: Optional[str] = None,
    inference_table: Optional[str] = None,
    monitoring_table: Optional[str] = None,
    athena_client: Optional[Any] = None,
    output_s3: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Verify inference + monitoring data exists in Athena (Section 3).

    Mirrors the notebook's graceful-degradation behavior: a missing/empty
    `monitoring_responses` table is caught and logged as a warning (not
    raised) so dashboard creation can proceed with drift trend visuals
    simply showing no data yet.

    Args:
        database: Athena database name. Defaults to config.ATHENA_DATABASE.
        inference_table: Name of the inference_responses table. Defaults to
            config.ATHENA_INFERENCE_TABLE.
        monitoring_table: Name of the monitoring_responses table. Defaults
            to config.ATHENA_MONITORING_RESPONSES_TABLE.
        athena_client: Optional boto3 Athena client (constructed if not provided)
        output_s3: S3 location for query results. Defaults to config.ATHENA_OUTPUT_S3.

    Returns:
        Dict with keys: 'inference_records' (int), 'inference_with_ground_truth'
        (int), 'monitoring_runs' (int), 'has_drift_data' (bool).
    """
    resolved_database = database or ATHENA_DATABASE
    resolved_inference_table = inference_table or ATHENA_INFERENCE_TABLE
    resolved_monitoring_table = monitoring_table or ATHENA_MONITORING_RESPONSES_TABLE
    resolved_output_s3 = output_s3 or ATHENA_OUTPUT_S3

    if athena_client is None:
        athena_client = boto3.client('athena', region_name=AWS_DEFAULT_REGION)

    logger.info(f"Checking {resolved_inference_table} table...")
    result = _run_athena_query(
        f'SELECT COUNT(*) FROM {resolved_inference_table}',
        athena_client, resolved_database, resolved_output_s3,
    )
    inference_records = int(result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue'])
    logger.info(f"  Total records: {inference_records}")

    result = _run_athena_query(
        f'SELECT COUNT(*) FROM {resolved_inference_table} WHERE ground_truth IS NOT NULL',
        athena_client, resolved_database, resolved_output_s3,
    )
    inference_with_ground_truth = int(result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue'])
    logger.info(f"  With ground truth: {inference_with_ground_truth}")

    monitoring_runs = 0
    has_drift_data = False
    logger.info(f"Checking {resolved_monitoring_table} table...")
    try:
        result = _run_athena_query(
            f'SELECT COUNT(*) FROM {resolved_monitoring_table}',
            athena_client, resolved_database, resolved_output_s3,
        )
        monitoring_runs = int(result['ResultSet']['Rows'][1]['Data'][0]['VarCharValue'])
        has_drift_data = monitoring_runs > 0
        if has_drift_data:
            logger.info(f"  Total monitoring runs: {monitoring_runs}")
            logger.info("✓ Drift data available")
        else:
            logger.warning(
                f"{resolved_monitoring_table} has zero rows — drift trend visuals "
                "will be empty until monitoring runs complete."
            )
    except Exception as e:
        logger.warning(
            f"  ⚠ {resolved_monitoring_table} not available: {e}. "
            "Drift trend visuals will be empty until monitoring runs complete."
        )
        monitoring_runs = 0
        has_drift_data = False

    return {
        'inference_records': inference_records,
        'inference_with_ground_truth': inference_with_ground_truth,
        'monitoring_runs': monitoring_runs,
        'has_drift_data': has_drift_data,
    }


# ---------------------------------------------------------------------------
# Section 4 — Athena data source
# ---------------------------------------------------------------------------


def get_quicksight_principals(
    account_id: str,
    quicksight_admin_client: Optional[Any] = None,
    identity_region: Optional[str] = None,
) -> List[str]:
    """
    Return ARNs for all QuickSight users in the account's default namespace.

    Direct port of the notebook's `get_quicksight_principals()`. Falls back
    to a wildcard Admin-group ARN if `list_users` fails or returns nothing
    (e.g. the caller lacks quicksight:ListUsers) so dashboard resources are
    still created with a usable (if broader) permission grant.

    Args:
        account_id: AWS account ID
        quicksight_admin_client: Optional boto3 QuickSight client bound to
            the identity region (constructed if not provided)
        identity_region: QuickSight identity region. Defaults to
            config.QUICKSIGHT_IDENTITY_REGION. Used both for client
            construction and the fallback ARN.

    Returns:
        List of QuickSight user ARNs (at least one entry).
    """
    resolved_identity_region = identity_region or QUICKSIGHT_IDENTITY_REGION

    if quicksight_admin_client is None:
        quicksight_admin_client = boto3.client('quicksight', region_name=resolved_identity_region)

    try:
        users = quicksight_admin_client.list_users(AwsAccountId=account_id, Namespace='default')
        arns = [u['Arn'] for u in users.get('UserList', [])]
        if arns:
            return arns
    except Exception:
        pass
    return [f'arn:aws:quicksight:{resolved_identity_region}:{account_id}:user/default/Admin/*']


def create_or_update_datasource(
    account_id: str,
    quicksight_principals: List[str],
    quicksight_client: Optional[Any] = None,
    datasource_id: Optional[str] = None,
    datasource_name: Optional[str] = None,
) -> str:
    """
    Create or update the Athena data source in QuickSight (Section 4).

    Idempotent describe/create-or-update pattern: describe_data_source
    succeeds -> update_data_source; ResourceNotFoundException -> create
    with Permissions attached (update calls don't take Permissions —
    matches the notebook, which only sets Permissions on create).

    Args:
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        datasource_id: Data source ID. Defaults to config.QUICKSIGHT_DATASOURCE_ID.
        datasource_name: Data source display name. Defaults to
            config.QUICKSIGHT_DATASOURCE_NAME.

    Returns:
        The data source ARN.
    """
    resolved_datasource_id = datasource_id or QUICKSIGHT_DATASOURCE_ID
    resolved_datasource_name = datasource_name or QUICKSIGHT_DATASOURCE_NAME

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    common = dict(
        AwsAccountId=account_id,
        DataSourceId=resolved_datasource_id,
        Name=resolved_datasource_name,
        DataSourceParameters={'AthenaParameters': {'WorkGroup': 'primary'}},
    )
    try:
        quicksight_client.describe_data_source(AwsAccountId=account_id, DataSourceId=resolved_datasource_id)
        logger.info("Updating existing data source...")
        resp = quicksight_client.update_data_source(**common)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info("Creating new data source...")
            resp = quicksight_client.create_data_source(
                **common,
                Type='ATHENA',
                Permissions=[{'Principal': p, 'Actions': _DATASOURCE_ACTIONS} for p in quicksight_principals],
            )
        else:
            raise

    logger.info(f"✓ Data source: {resp['Arn']}")
    return resp['Arn']


# ---------------------------------------------------------------------------
# Section 5 — Lake Formation + S3 permissions
# ---------------------------------------------------------------------------


def _check_s3_permissions(
    role_name: str,
    iam_client: Any,
) -> Dict[str, bool]:
    """
    Report whether the QuickSight service role has the access the dashboard needs.

    QuickSight queries the data as its own service role, and those permissions
    are declared in templates/2-iam.yaml (QuickSightServiceRoleS3Policy,
    QuickSightServiceRoleAthenaPolicy) so that CloudFormation owns every IAM
    grant in the workshop. Those two resources are conditional: they can only
    attach once the account is subscribed to QuickSight and the service role
    exists. An account that subscribed after its last deploy therefore needs the
    gap named here, rather than getting a dashboard whose panels fail to load.

    Args:
        role_name: QuickSight service role name (e.g. QUICKSIGHT_SERVICE_ROLE_NAME)
        iam_client: boto3 IAM client

    Returns:
        Dict with keys 'data_lake' and 'athena_access', True when that policy
        is present on the role. An unreadable role (no iam:ListRolePolicies,
        role absent) reports False with a warning rather than raising — every
        other Lab 5 notebook works without QuickSight.
    """
    results = {'data_lake': False, 'athena_access': False}

    try:
        attached = iam_client.list_role_policies(RoleName=role_name)['PolicyNames']
    except Exception as e:
        logger.warning(f"  ✗ Cannot read policies on {role_name}: {e}")
        logger.warning(
            "    Run scripts/deploy-workshop.sh once the account is subscribed to "
            "QuickSight: the deploy is what grants QuickSight access to the data "
            "bucket and Athena."
        )
        return results

    # Policy names are project-scoped in templates/2-iam.yaml and mirrored by
    # config.QUICKSIGHT_S3_POLICY_NAME / QUICKSIGHT_ATHENA_POLICY_NAME.
    results['data_lake'] = QUICKSIGHT_S3_POLICY_NAME in attached
    results['athena_access'] = QUICKSIGHT_ATHENA_POLICY_NAME in attached

    for label, present in (
        (QUICKSIGHT_S3_POLICY_NAME, results['data_lake']),
        (QUICKSIGHT_ATHENA_POLICY_NAME, results['athena_access']),
    ):
        if present:
            logger.info(f"  ✓ Policy: {label}")
        else:
            logger.warning(
                f"  ✗ Policy {label} missing on {role_name} — the dashboard will be "
                "created but its panels will fail to load data. Run "
                "scripts/deploy-workshop.sh to attach it."
            )

    return results


def grant_governance_permissions(
    database: Optional[str] = None,
    region: Optional[str] = None,
    lambda_role_arn: Optional[str] = None,
    quicksight_service_role_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Grant the Lake Formation table access the dashboard needs (Section 5).

    Reuses the existing
    `src.setup.grant_lake_formation_permissions.grant_lake_formation_permissions()`
    (covers all 7 project tables — a harmless/idempotent superset of the 3
    tables this dashboard actually needs — via boto3, no subprocess shell-outs)
    rather than reimplementing the notebook's inline subprocess-based grant loop.

    QuickSight's own data access is declared in templates/2-iam.yaml, so this
    function only calls `_check_s3_permissions()` to report whether those
    CloudFormation-owned policies are attached to the QuickSight service role.

    Args:
        database: Athena/Glue database name. Defaults to config.ATHENA_DATABASE.
        region: AWS region. Defaults to config.AWS_DEFAULT_REGION.
        lambda_role_arn: Drift-monitor Lambda's exec role ARN, passed through
            to grant_lake_formation_permissions for the monitoring_responses
            grant. Defaults to config.LAMBDA_EXEC_ROLE.
        quicksight_service_role_name: QuickSight service role name. Defaults
            to config.QUICKSIGHT_SERVICE_ROLE_NAME.

    Returns:
        Dict with keys: 'lake_formation' ('done'), 's3_permissions' (the
        `_check_s3_permissions()` result dict, reporting what CloudFormation
        has attached to the QuickSight service role).
    """
    resolved_database = database or ATHENA_DATABASE
    resolved_region = region or AWS_DEFAULT_REGION
    resolved_lambda_role_arn = lambda_role_arn if lambda_role_arn is not None else LAMBDA_EXEC_ROLE
    resolved_quicksight_service_role_name = quicksight_service_role_name or QUICKSIGHT_SERVICE_ROLE_NAME

    iam_client = boto3.client('iam', region_name=resolved_region)

    grant_lake_formation_permissions(
        database=resolved_database,
        region=resolved_region,
        lambda_role_arn=resolved_lambda_role_arn,
    )

    s3_results = _check_s3_permissions(
        role_name=resolved_quicksight_service_role_name,
        iam_client=iam_client,
    )

    return {'lake_formation': 'done', 's3_permissions': s3_results}


# ---------------------------------------------------------------------------
# Section 6 — datasets
# ---------------------------------------------------------------------------


def create_inference_dataset(
    datasource_arn: str,
    account_id: str,
    quicksight_principals: List[str],
    quicksight_client: Optional[Any] = None,
    dataset_id: Optional[str] = None,
    dataset_name: Optional[str] = None,
    database: Optional[str] = None,
    inference_table: Optional[str] = None,
) -> str:
    """
    Create/update the `inference_responses` dataset (Section 6a).

    RelationalTable with calculated columns `prediction_accuracy` and
    `risk_tier` added via LogicalTableMap.

    Args:
        datasource_arn: ARN of the Athena data source
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        dataset_id: Dataset ID. Defaults to config.QUICKSIGHT_INFERENCE_DATASET_ID.
        dataset_name: Dataset display name. Defaults to
            config.QUICKSIGHT_INFERENCE_DATASET_NAME.
        database: Athena database name. Defaults to config.ATHENA_DATABASE.
        inference_table: Name of the inference_responses table. Defaults to
            config.ATHENA_INFERENCE_TABLE.

    Returns:
        The dataset ARN.
    """
    resolved_dataset_id = dataset_id or QUICKSIGHT_INFERENCE_DATASET_ID
    resolved_dataset_name = dataset_name or QUICKSIGHT_INFERENCE_DATASET_NAME
    resolved_database = database or ATHENA_DATABASE
    resolved_inference_table = inference_table or ATHENA_INFERENCE_TABLE

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    # RelationalTable — no column list needed, QuickSight auto-discovers from Athena.
    physical_table_map = {
        'inference-responses': {
            'RelationalTable': {
                'DataSourceArn': datasource_arn,
                'Catalog': 'AwsDataCatalog',
                'Schema': resolved_database,
                'Name': resolved_inference_table,
                'InputColumns': [
                    {'Name': 'inference_id', 'Type': 'STRING'},
                    {'Name': 'request_timestamp', 'Type': 'DATETIME'},
                    {'Name': 'endpoint_name', 'Type': 'STRING'},
                    {'Name': 'model_version', 'Type': 'STRING'},
                    {'Name': 'mlflow_run_id', 'Type': 'STRING'},
                    {'Name': 'input_features', 'Type': 'STRING'},
                    # Prediction + probability column names come from config
                    # (PREDICTION_COLUMN / PROBABILITY_COLUMN / PROBABILITY_ALT_COLUMN)
                    # so BYO users whose inference handler emits differently
                    # named columns don't have to edit this file. Defaults
                    # match the reference implementation.
                    {'Name': PREDICTION_COLUMN, 'Type': 'INTEGER'},
                    {'Name': PROBABILITY_COLUMN, 'Type': 'DECIMAL'},
                    *([{'Name': PROBABILITY_ALT_COLUMN, 'Type': 'DECIMAL'}]
                       if PROBABILITY_ALT_COLUMN else []),
                    {'Name': 'confidence_score', 'Type': 'DECIMAL'},
                    {'Name': 'ground_truth', 'Type': 'INTEGER'},
                    {'Name': 'ground_truth_timestamp', 'Type': 'DATETIME'},
                    {'Name': 'ground_truth_source', 'Type': 'STRING'},
                    {'Name': 'days_to_ground_truth', 'Type': 'DECIMAL'},
                    {'Name': 'inference_latency_ms', 'Type': 'DECIMAL'},
                    {'Name': 'model_load_time_ms', 'Type': 'DECIMAL'},
                    {'Name': 'preprocessing_time_ms', 'Type': 'DECIMAL'},
                    {'Name': schema.identifier_column(), 'Type': 'STRING'},
                    {'Name': 'is_high_confidence', 'Type': 'BIT'},
                    {'Name': 'is_low_confidence', 'Type': 'BIT'},
                    {'Name': 'prediction_bucket', 'Type': 'STRING'},
                    {'Name': 'request_id', 'Type': 'STRING'},
                    {'Name': 'response_time', 'Type': 'DATETIME'},
                    {'Name': 'error_message', 'Type': 'STRING'},
                    {'Name': 'inference_mode', 'Type': 'STRING'},
                    # monitoring_run_id back-fills here when a drift run scores this row.
                    # NULL until Lab 5D's UPDATE statement tags it. Joins to
                    # monitoring_responses.monitoring_run_id 1:N for "which inferences
                    # contributed to this drift run?" lookups.
                    {'Name': 'monitoring_run_id', 'Type': 'STRING'},
                ],
            }
        }
    }

    # Calculated fields via LogicalTableMap
    logical_table_map = {
        'inference-responses-logical': {
            'Alias': 'Inference Responses',
            'Source': {'PhysicalTableId': 'inference-responses'},
            'DataTransforms': [
                {
                    'CreateColumnsOperation': {
                        'Columns': [
                            {
                                'ColumnName': 'prediction_accuracy',
                                'ColumnId': 'prediction-accuracy',
                                'Expression': (
                                    "ifelse("
                                    "isNull({ground_truth}), 'Pending', "
                                    "ifelse({" + PREDICTION_COLUMN + "} = {ground_truth}, "
                                    "'Correct', 'Incorrect'))"
                                ),
                            },
                            # `risk_tier` bucketing thresholds (0.2/0.5/0.8) are
                            # calibrated for a binary-classification score. For
                            # non-binary targets, replace this expression via
                            # `dashboard update` or edit the module locally.
                            {
                                'ColumnName': 'risk_tier',
                                'ColumnId': 'risk-tier',
                                'Expression': (
                                    "ifelse("
                                    "{" + PROBABILITY_COLUMN + "} > 0.8, 'High Risk', "
                                    "ifelse({" + PROBABILITY_COLUMN + "} > 0.5, 'Medium Risk', "
                                    "ifelse({" + PROBABILITY_COLUMN + "} > 0.2, 'Low Risk', "
                                    "'Minimal Risk')))"
                                ),
                            },
                        ]
                    }
                }
            ],
        }
    }

    common = dict(
        AwsAccountId=account_id, DataSetId=resolved_dataset_id,
        Name=resolved_dataset_name,
        PhysicalTableMap=physical_table_map,
        LogicalTableMap=logical_table_map,
        ImportMode='DIRECT_QUERY',
    )
    try:
        quicksight_client.describe_data_set(AwsAccountId=account_id, DataSetId=resolved_dataset_id)
        logger.info("Updating existing dataset...")
        resp = quicksight_client.update_data_set(**common)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info("Creating new dataset...")
            resp = quicksight_client.create_data_set(
                **common,
                Permissions=[{'Principal': p, 'Actions': _DATASET_ACTIONS} for p in quicksight_principals],
            )
        else:
            raise

    logger.info(f"✓ Inference dataset: {resp['Arn']}")
    return resp['Arn']


def create_drift_dataset(
    datasource_arn: str,
    account_id: str,
    quicksight_principals: List[str],
    quicksight_client: Optional[Any] = None,
    dataset_id: Optional[str] = None,
    dataset_name: Optional[str] = None,
    database: Optional[str] = None,
    monitoring_table: Optional[str] = None,
) -> str:
    """
    Create/update the `monitoring_responses` dataset (Section 6b).

    RelationalTable with calculated columns `drift_severity` and
    `performance_status` added via LogicalTableMap.

    Args:
        datasource_arn: ARN of the Athena data source
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        dataset_id: Dataset ID. Defaults to config.QUICKSIGHT_DRIFT_DATASET_ID.
        dataset_name: Dataset display name. Defaults to
            config.QUICKSIGHT_DRIFT_DATASET_NAME.
        database: Athena database name. Defaults to config.ATHENA_DATABASE.
        monitoring_table: Name of the monitoring_responses table. Defaults
            to config.ATHENA_MONITORING_RESPONSES_TABLE.

    Returns:
        The dataset ARN.
    """
    resolved_dataset_id = dataset_id or QUICKSIGHT_DRIFT_DATASET_ID
    resolved_dataset_name = dataset_name or QUICKSIGHT_DRIFT_DATASET_NAME
    resolved_database = database or ATHENA_DATABASE
    resolved_monitoring_table = monitoring_table or ATHENA_MONITORING_RESPONSES_TABLE

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    # monitoring_responses dataset — drift metrics from Evidently runs
    drift_physical_table_map = {
        'monitoring-responses': {
            'RelationalTable': {
                'DataSourceArn': datasource_arn,
                'Catalog': 'AwsDataCatalog',
                'Schema': resolved_database,
                'Name': resolved_monitoring_table,
                'InputColumns': [
                    {'Name': 'monitoring_run_id', 'Type': 'STRING'},
                    {'Name': 'monitoring_timestamp', 'Type': 'DATETIME'},
                    {'Name': 'endpoint_name', 'Type': 'STRING'},
                    {'Name': 'model_version', 'Type': 'STRING'},
                    {'Name': 'model_package_arn', 'Type': 'STRING'},
                    {'Name': 'evaluation_snapshot_id', 'Type': 'STRING'},
                    {'Name': 'training_snapshot_id', 'Type': 'STRING'},
                    {'Name': 'data_drift_detected', 'Type': 'BIT'},
                    {'Name': 'drifted_columns_count', 'Type': 'INTEGER'},
                    {'Name': 'drifted_columns_share', 'Type': 'DECIMAL'},
                    {'Name': 'features_analyzed', 'Type': 'INTEGER'},
                    {'Name': 'data_sample_size', 'Type': 'INTEGER'},
                    {'Name': 'model_drift_detected', 'Type': 'BIT'},
                    {'Name': 'baseline_roc_auc', 'Type': 'DECIMAL'},
                    {'Name': 'current_roc_auc', 'Type': 'DECIMAL'},
                    {'Name': 'roc_auc_degradation', 'Type': 'DECIMAL'},
                    {'Name': 'roc_auc_degradation_pct', 'Type': 'DECIMAL'},
                    {'Name': 'accuracy', 'Type': 'DECIMAL'},
                    {'Name': 'precision', 'Type': 'DECIMAL'},
                    {'Name': 'recall', 'Type': 'DECIMAL'},
                    {'Name': 'f1_score', 'Type': 'DECIMAL'},
                    {'Name': 'model_sample_size', 'Type': 'INTEGER'},
                    {'Name': 'per_feature_drift_scores', 'Type': 'STRING'},
                    {'Name': 'evidently_report_s3_path', 'Type': 'STRING'},
                    {'Name': 'mlflow_run_id', 'Type': 'STRING'},
                    {'Name': 'alert_sent', 'Type': 'BIT'},
                    {'Name': 'detection_engine', 'Type': 'STRING'},
                    {'Name': 'created_at', 'Type': 'DATETIME'},
                ],
            }
        }
    }

    drift_logical_table_map = {
        'monitoring-responses-logical': {
            'Alias': 'Monitoring Responses',
            'Source': {'PhysicalTableId': 'monitoring-responses'},
            'DataTransforms': [
                {
                    'CreateColumnsOperation': {
                        'Columns': [
                            {
                                'ColumnName': 'drift_severity',
                                'ColumnId': 'drift-severity',
                                'Expression': (
                                    "ifelse("
                                    "{drifted_columns_share} > 0.3, 'HIGH', "
                                    "ifelse({drifted_columns_share} > 0.15, 'MEDIUM', 'LOW'))"
                                ),
                            },
                            {
                                'ColumnName': 'performance_status',
                                'ColumnId': 'performance-status',
                                'Expression': (
                                    "ifelse("
                                    "{current_roc_auc} >= 0.95, 'GOOD', "
                                    "ifelse({current_roc_auc} >= 0.90, 'WARNING', 'CRITICAL'))"
                                ),
                            },
                        ]
                    }
                }
            ],
        }
    }

    drift_dset_common = dict(
        AwsAccountId=account_id, DataSetId=resolved_dataset_id,
        Name=resolved_dataset_name,
        PhysicalTableMap=drift_physical_table_map,
        LogicalTableMap=drift_logical_table_map,
        ImportMode='DIRECT_QUERY',
    )
    try:
        quicksight_client.describe_data_set(AwsAccountId=account_id, DataSetId=resolved_dataset_id)
        logger.info("Updating existing drift dataset...")
        resp = quicksight_client.update_data_set(**drift_dset_common)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info("Creating new drift dataset...")
            resp = quicksight_client.create_data_set(
                **drift_dset_common,
                Permissions=[{'Principal': p, 'Actions': _DATASET_ACTIONS} for p in quicksight_principals],
            )
        else:
            raise

    logger.info(f"✓ Drift dataset: {resp['Arn']}")
    return resp['Arn']


def create_feature_drift_dataset(
    datasource_arn: str,
    account_id: str,
    quicksight_principals: List[str],
    quicksight_client: Optional[Any] = None,
    dataset_id: Optional[str] = None,
    dataset_name: Optional[str] = None,
    database: Optional[str] = None,
    monitoring_table: Optional[str] = None,
    inference_table: Optional[str] = None,
) -> str:
    """
    Create/update the feature-drift-by-model-version joined dataset (Section 6c, dataset 1).

    CustomSql joining `monitoring_responses` to `inference_responses` on
    the exact foreign key `monitoring_run_id` (back-filled by the drift
    Lambda on every inference row it scored) to aggregate inference counts
    + avg positive-class probability alongside per-run drift metrics.

    Args:
        datasource_arn: ARN of the Athena data source
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        dataset_id: Dataset ID. Defaults to config.QUICKSIGHT_FEATURE_DRIFT_DATASET_ID.
        dataset_name: Dataset display name. Defaults to
            config.QUICKSIGHT_FEATURE_DRIFT_DATASET_NAME.
        database: Athena database name. Defaults to config.ATHENA_DATABASE.
        monitoring_table: Name of the monitoring_responses table. Defaults
            to config.ATHENA_MONITORING_RESPONSES_TABLE.
        inference_table: Name of the inference_responses table. Defaults to
            config.ATHENA_INFERENCE_TABLE.

    Returns:
        The dataset ARN.
    """
    resolved_dataset_id = dataset_id or QUICKSIGHT_FEATURE_DRIFT_DATASET_ID
    resolved_dataset_name = dataset_name or QUICKSIGHT_FEATURE_DRIFT_DATASET_NAME
    resolved_database = database or ATHENA_DATABASE
    resolved_monitoring_table = monitoring_table or ATHENA_MONITORING_RESPONSES_TABLE
    resolved_inference_table = inference_table or ATHENA_INFERENCE_TABLE

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    # Feature drift dataset — joins monitoring_responses to inference_responses
    # by monitoring_run_id (foreign key Lab 5D back-fills on each inference
    # row it scored). Aggregates inference counts + avg positive prob
    # alongside the per-run drift metrics so dashboards can slice both sides
    # of the drift <-> inference relationship in a single dataset.
    custom_sql = f'''
SELECT 
    m.monitoring_run_id,
    m.monitoring_timestamp,
    m.model_version,
    m.model_package_arn,
    m.evaluation_snapshot_id,
    m.training_snapshot_id,
    m.drifted_columns_count,
    m.drifted_columns_share,
    m.features_analyzed,
    m.baseline_roc_auc,
    m.current_roc_auc,
    m.data_drift_detected,
    m.accuracy,
    m.precision,
    m.recall,
    m.f1_score,
    COUNT(DISTINCT i.inference_id) as inference_count,
    -- avg_score = AVG of the probability/score column. Aliased so the
    -- dashboard doesn't have to know the physical column name.
    AVG(i.{PROBABILITY_COLUMN}) as avg_positive_prob,
    COUNT(CASE WHEN i.ground_truth IS NOT NULL THEN 1 END) as gt_count,
    MIN(i.request_timestamp) as window_start,
    MAX(i.request_timestamp) as window_end
FROM {resolved_database}.{resolved_monitoring_table} m
LEFT JOIN {resolved_database}.{resolved_inference_table} i
    -- Join on the run tag, not on time. Lab 5D stamps monitoring_run_id onto
    -- every inference row it scored, so run membership is recorded at scoring
    -- time rather than inferred here. That makes the join exact at any cadence:
    -- a run whose window opened weeks ago still matches its own rows, because
    -- the tag does not expire, and back-to-back runs minutes apart cannot
    -- double-count, because each row carries exactly one run's tag no matter
    -- how much the runs' time ranges overlap.
    ON i.monitoring_run_id = m.monitoring_run_id
GROUP BY 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16
ORDER BY m.monitoring_timestamp DESC
'''

    feature_drift_physical_table_map = {
        'feature-drift-joined': {
            'CustomSql': {
                'DataSourceArn': datasource_arn,
                'Name': 'FeatureDriftJoin',
                'SqlQuery': custom_sql,
                'Columns': [
                    {'Name': 'monitoring_run_id', 'Type': 'STRING'},
                    {'Name': 'monitoring_timestamp', 'Type': 'DATETIME'},
                    {'Name': 'model_version', 'Type': 'STRING'},
                    {'Name': 'model_package_arn', 'Type': 'STRING'},
                    {'Name': 'evaluation_snapshot_id', 'Type': 'STRING'},
                    {'Name': 'training_snapshot_id', 'Type': 'STRING'},
                    {'Name': 'drifted_columns_count', 'Type': 'INTEGER'},
                    {'Name': 'drifted_columns_share', 'Type': 'DECIMAL'},
                    {'Name': 'features_analyzed', 'Type': 'INTEGER'},
                    {'Name': 'baseline_roc_auc', 'Type': 'DECIMAL'},
                    {'Name': 'current_roc_auc', 'Type': 'DECIMAL'},
                    {'Name': 'data_drift_detected', 'Type': 'BIT'},
                    {'Name': 'accuracy', 'Type': 'DECIMAL'},
                    {'Name': 'precision', 'Type': 'DECIMAL'},
                    {'Name': 'recall', 'Type': 'DECIMAL'},
                    {'Name': 'f1_score', 'Type': 'DECIMAL'},
                    {'Name': 'inference_count', 'Type': 'INTEGER'},
                    {'Name': 'avg_positive_prob', 'Type': 'DECIMAL'},
                    {'Name': 'gt_count', 'Type': 'INTEGER'},
                    # Earliest / latest request_timestamp seen for this drift run.
                    # Lets visuals show "this run scored inferences from <start> to <end>".
                    {'Name': 'window_start', 'Type': 'DATETIME'},
                    {'Name': 'window_end', 'Type': 'DATETIME'},
                ],
            }
        }
    }

    feature_drift_logical_table_map = {
        'feature-drift-logical': {
            'Alias': 'Feature Drift Analysis',
            'Source': {'PhysicalTableId': 'feature-drift-joined'},
        }
    }

    feature_drift_dset_common = dict(
        AwsAccountId=account_id, DataSetId=resolved_dataset_id,
        Name=resolved_dataset_name,
        PhysicalTableMap=feature_drift_physical_table_map,
        LogicalTableMap=feature_drift_logical_table_map,
        ImportMode='DIRECT_QUERY',
    )

    try:
        quicksight_client.describe_data_set(AwsAccountId=account_id, DataSetId=resolved_dataset_id)
        logger.info("Updating existing feature drift dataset...")
        resp = quicksight_client.update_data_set(**feature_drift_dset_common)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info("Creating new feature drift dataset...")
            resp = quicksight_client.create_data_set(
                **feature_drift_dset_common,
                Permissions=[{'Principal': p, 'Actions': _DATASET_ACTIONS} for p in quicksight_principals],
            )
        else:
            raise

    logger.info(f"✓ Feature drift dataset: {resp['Arn']}")
    return resp['Arn']


def create_feature_drift_detail_view(
    database: Optional[str] = None,
    athena_client: Optional[Any] = None,
    output_s3: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create/replace the `feature_drift_detail` Athena view (Section 6c) and test it.

    Unpacks the JSON `per_feature_drift_scores` column on
    `monitoring_responses` into one row per (monitoring_run_id, feature_name)
    via `CROSS JOIN UNNEST`, adding a computed `drift_severity` /
    `drift_detected` pair. This view backs `create_feature_level_dataset()`.
    After creating the view, runs a test query against it and returns its
    summary stats — matches the notebook's own post-creation test query.

    Args:
        database: Athena database name. Defaults to config.ATHENA_DATABASE.
        athena_client: Optional boto3 Athena client (constructed if not provided)
        output_s3: S3 location for query results. Defaults to config.ATHENA_OUTPUT_S3.

    Returns:
        Dict with keys: 'total_rows', 'features', 'runs', 'first_run', 'last_run'.

    Raises:
        RuntimeError: If the CREATE VIEW query (or the test query) fails.
    """
    resolved_database = database or ATHENA_DATABASE
    resolved_output_s3 = output_s3 or ATHENA_OUTPUT_S3

    if athena_client is None:
        athena_client = boto3.client('athena', region_name=AWS_DEFAULT_REGION)

    logger.info("Creating feature_drift_detail view...")

    create_view_sql = f"""
CREATE OR REPLACE VIEW {resolved_database}.{FEATURE_DRIFT_DETAIL_VIEW} AS
SELECT
    monitoring_run_id,
    monitoring_timestamp,
    model_version,
    model_package_arn,
    evaluation_snapshot_id,
    training_snapshot_id,
    endpoint_name,
    data_drift_detected,
    drifted_columns_count,
    drifted_columns_share,
    baseline_roc_auc,
    current_roc_auc,
    feature_name,
    COALESCE(
        TRY(CAST(json_format(feature_value) AS DOUBLE)),
        TRY(CAST(json_extract_scalar(json_format(feature_value), '$.score') AS DOUBLE))
    ) as drift_score,
    COALESCE(
        TRY(CAST(json_extract_scalar(json_format(feature_value), '$.magnitude') AS DOUBLE)),
        TRY(CAST(json_format(feature_value) AS DOUBLE))
    ) as drift_magnitude,
    TRY(json_extract_scalar(json_format(feature_value), '$.method')) as drift_method,
    TRY(CAST(json_extract_scalar(json_format(feature_value), '$.threshold') AS DOUBLE)) as drift_threshold,
    CASE
        WHEN COALESCE(
            TRY(CAST(json_extract_scalar(json_format(feature_value), '$.magnitude') AS DOUBLE)),
            TRY(CAST(json_format(feature_value) AS DOUBLE))
        ) > 2.5 THEN 'Significant'
        WHEN COALESCE(
            TRY(CAST(json_extract_scalar(json_format(feature_value), '$.magnitude') AS DOUBLE)),
            TRY(CAST(json_format(feature_value) AS DOUBLE))
        ) > 1.0 THEN 'Moderate'
        ELSE 'Low'
    END as drift_severity,
    CASE WHEN COALESCE(
        TRY(CAST(json_extract_scalar(json_format(feature_value), '$.magnitude') AS DOUBLE)),
        TRY(CAST(json_format(feature_value) AS DOUBLE))
    ) > 1.0 THEN true ELSE false END as drift_detected
FROM {resolved_database}.monitoring_responses
CROSS JOIN UNNEST(
    CAST(json_parse(per_feature_drift_scores) AS MAP(VARCHAR, JSON))
) AS t(feature_name, feature_value)
WHERE per_feature_drift_scores IS NOT NULL
    AND per_feature_drift_scores != 'null'
    AND per_feature_drift_scores != '{{}}'
"""

    try:
        _run_athena_query(create_view_sql, athena_client, resolved_database, resolved_output_s3)
    except RuntimeError as e:
        logger.error(f"✗ View creation failed: {e}")
        raise RuntimeError(f"feature_drift_detail view creation failed: {e}") from e
    logger.info("✓ View created successfully!")

    logger.info("Testing view with sample query...")
    test_query = f"""
SELECT
    COUNT(*) as total_rows,
    COUNT(DISTINCT feature_name) as features,
    COUNT(DISTINCT monitoring_run_id) as runs,
    MIN(monitoring_timestamp) as first_run,
    MAX(monitoring_timestamp) as last_run
FROM {resolved_database}.{FEATURE_DRIFT_DETAIL_VIEW}
"""
    try:
        result = _run_athena_query(test_query, athena_client, resolved_database, resolved_output_s3)
    except RuntimeError as e:
        logger.error(f"✗ Test query failed: {e}")
        raise RuntimeError(f"feature_drift_detail view test query failed: {e}") from e

    rows = result['ResultSet']['Rows']
    if len(rows) > 1:
        data = rows[1]['Data']
        stats = {
            'total_rows': int(data[0].get('VarCharValue', '0')),
            'features': int(data[1].get('VarCharValue', '0')),
            'runs': int(data[2].get('VarCharValue', '0')),
            'first_run': data[3].get('VarCharValue', 'N/A'),
            'last_run': data[4].get('VarCharValue', 'N/A'),
        }
    else:
        stats = {'total_rows': 0, 'features': 0, 'runs': 0, 'first_run': 'N/A', 'last_run': 'N/A'}

    logger.info(f"✓ View test successful! Total rows: {stats['total_rows']}")
    logger.info("✓ View is ready for QuickSight dataset!")
    return stats


def grant_feature_drift_view_permissions(
    database: Optional[str] = None,
    region: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Grant Lake Formation SELECT/DESCRIBE on the `feature_drift_detail` view (Section 6c).

    Views require their own Lake Formation grant separate from the
    underlying table's grant, since the view doesn't exist until
    `create_feature_drift_detail_view()` has run — it can't be covered by
    the upfront `grant_governance_permissions()` call.

    Implementation note: the notebook issues this specific grant via a
    `subprocess` call to the `aws lakeformation grant-permissions` CLI
    (unlike every other Lake Formation grant in this project, which uses
    boto3 directly). boto3's `lakeformation.grant_permissions()` takes an
    identical `Resource={'Table': {'DatabaseName': ..., 'Name': ...}}`
    shape for both tables and views — Lake Formation itself doesn't
    distinguish them at the API level — so there's no functional reason to
    shell out here. This function uses boto3 directly for consistency with
    the rest of this module (grant_governance_permissions, etc.), and
    handles the "already granted" case gracefully like the notebook does.

    Args:
        database: Athena/Glue database name. Defaults to config.ATHENA_DATABASE.
        region: AWS region. Defaults to config.AWS_DEFAULT_REGION.

    Returns:
        Dict with keys: 'granted' (bool), 'principal', 'resource', 'permissions'.
    """
    resolved_database = database or ATHENA_DATABASE
    resolved_region = region or AWS_DEFAULT_REGION

    lf_client = boto3.client('lakeformation', region_name=resolved_region)

    logger.info("Granting Lake Formation permissions on feature_drift_detail view...")
    try:
        lf_client.grant_permissions(
            Principal={'DataLakePrincipalIdentifier': 'IAM_ALLOWED_PRINCIPALS'},
            Resource={'Table': {'DatabaseName': resolved_database, 'Name': FEATURE_DRIFT_DETAIL_VIEW}},
            Permissions=['SELECT', 'DESCRIBE'],
        )
        logger.info("✓ Lake Formation permissions granted on view")
        granted = True
    except Exception as e:
        msg = str(e).lower()
        if 'alreadyexists' in type(e).__name__.lower() or 'already' in msg:
            logger.info("✓ Permissions already exist (no change needed)")
            granted = True
        else:
            logger.warning(f"⚠ Warning: {e}. This might be OK if permissions were granted previously.")
            granted = False

    return {
        'granted': granted,
        'principal': 'IAM_ALLOWED_PRINCIPALS',
        'resource': f'{resolved_database}.{FEATURE_DRIFT_DETAIL_VIEW}',
        'permissions': ['SELECT', 'DESCRIBE'],
    }


def create_feature_level_dataset(
    datasource_arn: str,
    account_id: str,
    quicksight_principals: List[str],
    quicksight_client: Optional[Any] = None,
    dataset_id: Optional[str] = None,
    dataset_name: Optional[str] = None,
    database: Optional[str] = None,
) -> str:
    """
    Create/update the feature-level drift dataset (Section 6c, dataset 2).

    RelationalTable backed by the `feature_drift_detail` Athena view (must
    already exist — call `create_feature_drift_detail_view()` first). Shows
    individual feature drift scores across monitoring runs.

    Args:
        datasource_arn: ARN of the Athena data source
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        dataset_id: Dataset ID. Defaults to config.QUICKSIGHT_FEATURE_LEVEL_DATASET_ID.
        dataset_name: Dataset display name. Defaults to
            config.QUICKSIGHT_FEATURE_LEVEL_DATASET_NAME.
        database: Athena database name. Defaults to config.ATHENA_DATABASE.

    Returns:
        The dataset ARN.
    """
    resolved_dataset_id = dataset_id or QUICKSIGHT_FEATURE_LEVEL_DATASET_ID
    resolved_dataset_name = dataset_name or QUICKSIGHT_FEATURE_LEVEL_DATASET_NAME
    resolved_database = database or ATHENA_DATABASE

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    feature_level_physical_table = {
        'feature-level-view': {
            'RelationalTable': {
                'DataSourceArn': datasource_arn,
                'Catalog': 'AwsDataCatalog',
                'Schema': resolved_database,
                'Name': FEATURE_DRIFT_DETAIL_VIEW,
                'InputColumns': [
                    {'Name': 'monitoring_run_id', 'Type': 'STRING'},
                    {'Name': 'monitoring_timestamp', 'Type': 'DATETIME'},
                    {'Name': 'model_version', 'Type': 'STRING'},
                    {'Name': 'model_package_arn', 'Type': 'STRING'},
                    {'Name': 'evaluation_snapshot_id', 'Type': 'STRING'},
                    {'Name': 'training_snapshot_id', 'Type': 'STRING'},
                    {'Name': 'endpoint_name', 'Type': 'STRING'},
                    {'Name': 'data_drift_detected', 'Type': 'BIT'},
                    {'Name': 'drifted_columns_count', 'Type': 'INTEGER'},
                    {'Name': 'drifted_columns_share', 'Type': 'DECIMAL'},
                    {'Name': 'baseline_roc_auc', 'Type': 'DECIMAL'},
                    {'Name': 'current_roc_auc', 'Type': 'DECIMAL'},
                    {'Name': 'feature_name', 'Type': 'STRING'},
                    {'Name': 'drift_score', 'Type': 'DECIMAL'},
                    {'Name': 'drift_severity', 'Type': 'STRING'},
                    {'Name': 'drift_detected', 'Type': 'BIT'},
                ],
            }
        }
    }

    feature_level_logical_table = {
        'feature-level-logical': {
            'Alias': 'Feature Level Drift',
            'Source': {'PhysicalTableId': 'feature-level-view'},
        }
    }

    feature_level_dset_common = dict(
        AwsAccountId=account_id,
        DataSetId=resolved_dataset_id,
        Name=resolved_dataset_name,
        PhysicalTableMap=feature_level_physical_table,
        LogicalTableMap=feature_level_logical_table,
        ImportMode='DIRECT_QUERY',
    )

    try:
        quicksight_client.describe_data_set(AwsAccountId=account_id, DataSetId=resolved_dataset_id)
        logger.info("Updating existing feature-level dataset...")
        resp = quicksight_client.update_data_set(**feature_level_dset_common)
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info("Creating new feature-level dataset...")
            resp = quicksight_client.create_data_set(
                **feature_level_dset_common,
                Permissions=[{'Principal': p, 'Actions': _DATASET_ACTIONS} for p in quicksight_principals],
            )
        else:
            raise

    logger.info(f"✓ Feature-level dataset: {resp['Arn']}")
    return resp['Arn']


def create_accuracy_dataset(
    datasource_arn: str,
    account_id: str,
    quicksight_principals: List[str],
    quicksight_client: Optional[Any] = None,
    dataset_id: Optional[str] = None,
    dataset_name: Optional[str] = None,
    database: Optional[str] = None,
) -> str:
    """
    Create/update the prediction-accuracy timeline dataset (Section 6d).

    CustomSql inner-joining `inference_responses` with
    `ground_truth_updates` on `inference_id`, restricted to the last 30
    days, with calculated columns `accuracy_pct` and `is_correct`.

    Args:
        datasource_arn: ARN of the Athena data source
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        dataset_id: Dataset ID. Defaults to config.QUICKSIGHT_ACCURACY_DATASET_ID.
        dataset_name: Dataset display name. Defaults to
            config.QUICKSIGHT_ACCURACY_DATASET_NAME.
        database: Athena database name. Defaults to config.ATHENA_DATABASE.

    Returns:
        The dataset ARN.
    """
    resolved_dataset_id = dataset_id or QUICKSIGHT_ACCURACY_DATASET_ID
    resolved_dataset_name = dataset_name or QUICKSIGHT_ACCURACY_DATASET_NAME
    resolved_database = database or ATHENA_DATABASE

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    # Use CustomSQL to join inference_responses with ground_truth_updates.
    #
    # The ground-truth column is schema-derived, not fixed: the simulator writes
    # `actual_{target_column}` (src/drift_monitoring/simulate_ground_truth_from_athena.py),
    # so it is `actual_subscribed` for bank marketing and `actual_fraud` for a
    # fraud dataset. Resolve it the same way here rather than hardcoding a name
    # that only holds for one dataset. It is aliased back to `actual_target` so
    # the QuickSight column names below and the visuals stay dataset-agnostic.
    actual_col = f'actual_{schema.target_column()}'
    accuracy_custom_sql = f"""
SELECT
    DATE(i.request_timestamp) as inference_date,
    i.inference_id,
    i.endpoint_name,
    i.model_version,
    i.{PREDICTION_COLUMN} as predicted_positive,
    CAST(g.{actual_col} AS INT) as actual_target,
    CASE
        WHEN i.{PREDICTION_COLUMN} = CAST(g.{actual_col} AS INT) THEN 1
        ELSE 0
    END as prediction_match,
    CASE
        WHEN i.{PREDICTION_COLUMN} = 1 AND CAST(g.{actual_col} AS INT) = 1 THEN 'True Positive'
        WHEN i.{PREDICTION_COLUMN} = 0 AND CAST(g.{actual_col} AS INT) = 0 THEN 'True Negative'
        WHEN i.{PREDICTION_COLUMN} = 1 AND CAST(g.{actual_col} AS INT) = 0 THEN 'False Positive'
        WHEN i.{PREDICTION_COLUMN} = 0 AND CAST(g.{actual_col} AS INT) = 1 THEN 'False Negative'
        ELSE 'Unknown'
    END as prediction_category,
    i.request_timestamp as prediction_time,
    g.confirmation_timestamp as ground_truth_time,
    g.days_since_prediction
FROM {resolved_database}.{ATHENA_INFERENCE_TABLE} i
INNER JOIN {resolved_database}.{ATHENA_GROUND_TRUTH_UPDATES_TABLE} g
    ON i.inference_id = g.inference_id
WHERE i.request_timestamp >= CURRENT_DATE - INTERVAL '30' DAY
    AND g.{actual_col} IS NOT NULL
ORDER BY i.request_timestamp DESC
"""

    accuracy_physical_table = {
        'accuracy-join': {
            'CustomSql': {
                'DataSourceArn': datasource_arn,
                'Name': 'accuracy-join',
                'SqlQuery': accuracy_custom_sql,
                'Columns': [
                    {'Name': 'inference_date', 'Type': 'DATETIME'},
                    {'Name': 'inference_id', 'Type': 'STRING'},
                    {'Name': 'endpoint_name', 'Type': 'STRING'},
                    {'Name': 'model_version', 'Type': 'STRING'},
                    {'Name': 'predicted_positive', 'Type': 'INTEGER'},
                    {'Name': 'actual_target', 'Type': 'INTEGER'},
                    {'Name': 'prediction_match', 'Type': 'INTEGER'},
                    {'Name': 'prediction_category', 'Type': 'STRING'},
                    {'Name': 'prediction_time', 'Type': 'DATETIME'},
                    {'Name': 'ground_truth_time', 'Type': 'DATETIME'},
                    {'Name': 'days_since_prediction', 'Type': 'DECIMAL'},
                ]
            }
        }
    }

    # Calculated field for accuracy percentage
    accuracy_logical_table = {
        'accuracy-logical': {
            'Alias': 'Prediction Accuracy',
            'Source': {'PhysicalTableId': 'accuracy-join'},
            'DataTransforms': [
                {
                    'CreateColumnsOperation': {
                        'Columns': [
                            {
                                'ColumnName': 'accuracy_pct',
                                'ColumnId': 'accuracy-pct',
                                'Expression': 'sum({prediction_match}) / count({inference_id}) * 100'
                            },
                            {
                                'ColumnName': 'is_correct',
                                'ColumnId': 'is-correct',
                                'Expression': 'ifelse({prediction_match} = 1, "Correct", "Incorrect")'
                            }
                        ]
                    }
                }
            ]
        }
    }

    try:
        quicksight_client.describe_data_set(AwsAccountId=account_id, DataSetId=resolved_dataset_id)
        logger.info(f"Dataset {resolved_dataset_id} already exists, updating...")
        resp = quicksight_client.update_data_set(
            AwsAccountId=account_id,
            DataSetId=resolved_dataset_id,
            Name=resolved_dataset_name,
            PhysicalTableMap=accuracy_physical_table,
            LogicalTableMap=accuracy_logical_table,
            ImportMode='DIRECT_QUERY',
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info(f"Creating new dataset {resolved_dataset_id}...")
            resp = quicksight_client.create_data_set(
                AwsAccountId=account_id,
                DataSetId=resolved_dataset_id,
                Name=resolved_dataset_name,
                PhysicalTableMap=accuracy_physical_table,
                LogicalTableMap=accuracy_logical_table,
                ImportMode='DIRECT_QUERY',
                Permissions=[{'Principal': p, 'Actions': _DATASET_ACTIONS} for p in quicksight_principals],
            )
            logger.info("✓ Dataset created")
        else:
            raise

    logger.info(f"✓ Accuracy dataset ARN: {resp['Arn']}")
    return resp['Arn']


# ---------------------------------------------------------------------------
# Section 7 — visual definitions (pure data construction, no AWS calls)
# ---------------------------------------------------------------------------


def build_model_drift_visuals() -> List[Dict[str, Any]]:
    """
    Build the "Model Drift Trends" tab (Sheet 1).

    Each visual answers "how is model performance trending, and by which
    granularity?" — plain time trend, or sliced by model version, model
    package ARN, endpoint, or training snapshot ID. Ends with a lineage
    audit table (row per monitoring_run_id with every immutable reference)
    so auditors can screenshot the trail without leaving QuickSight.

    Bound to `DS_IDENT_DRIFT` (monitoring_responses) throughout — that's
    the single durable table containing every drift verdict + its lineage.

    Visuals:
        M1  ROC-AUC Baseline vs Current Over Time    (line, 2 series)
        M2  Model Performance Metrics Over Time      (line, 4 series)
        M3  ROC-AUC Trend by Model Version           (line, colored)
        M4  Drift Verdict Rate by Model Package ARN  (bar)
        M5  Drift Verdict Rate by Endpoint           (bar)
        M6  Performance by Training Snapshot         (table)
        M7  Model Lineage Audit                      (table)
        M8  Latest Current ROC-AUC                   (KPI)
    """
    def dcol(name):
        return {'DataSetIdentifier': DS_IDENT_DRIFT, 'ColumnName': name}

    m1_roc_auc_over_time = {
        'LineChartVisual': {
            'VisualId': 'm1-roc-auc-over-time',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'ROC-AUC: Baseline vs Current Over Time'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'm1-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [
                            {'NumericalMeasureField': {'FieldId': 'm1-baseline', 'Column': dcol('baseline_roc_auc'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'm1-current', 'Column': dcol('current_roc_auc'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                        ],
                    }
                }
            }
        }
    }

    m2_perf_metrics_over_time = {
        'LineChartVisual': {
            'VisualId': 'm2-perf-metrics',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Model Performance Metrics Over Time'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'm2-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [
                            {'NumericalMeasureField': {'FieldId': 'm2-acc',  'Column': dcol('accuracy'),  'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'm2-prec', 'Column': dcol('precision'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'm2-rec',  'Column': dcol('recall'),    'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'm2-f1',   'Column': dcol('f1_score'),  'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                        ],
                    }
                }
            }
        }
    }

    m3_roc_auc_by_version = {
        'LineChartVisual': {
            'VisualId': 'm3-roc-auc-by-version',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'ROC-AUC Trend by Model Version'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'm3-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'm3-auc', 'Column': dcol('current_roc_auc'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors': [{'CategoricalDimensionField': {'FieldId': 'm3-version', 'Column': dcol('model_version')}}],
                    }
                }
            }
        }
    }

    # Drift-detection RATE = mean of the BIT column `model_drift_detected`,
    # aggregated per group. QuickSight aggregates a BIT column as 0/1 so
    # the AVG gives the fraction of runs that flagged drift.
    m4_verdict_rate_by_arn = {
        'BarChartVisual': {
            'VisualId': 'm4-verdict-rate-by-arn',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Model-Drift Verdict Rate by Model Package ARN'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'CategoricalDimensionField': {'FieldId': 'm4-arn', 'Column': dcol('model_package_arn')}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'm4-rate', 'Column': dcol('model_drift_detected'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                },
                'Orientation': 'HORIZONTAL',
            }
        }
    }

    m5_verdict_rate_by_endpoint = {
        'BarChartVisual': {
            'VisualId': 'm5-verdict-rate-by-endpoint',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Model-Drift Verdict Rate by Endpoint'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'CategoricalDimensionField': {'FieldId': 'm5-ep', 'Column': dcol('endpoint_name')}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'm5-rate', 'Column': dcol('model_drift_detected'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                },
                'Orientation': 'HORIZONTAL',
            }
        }
    }

    # M6 groups by training_snapshot_id — the immutable Iceberg snapshot
    # the model was trained on. Answers "does retraining on newer data
    # actually improve production performance?"
    m6_perf_by_train_snapshot = {
        'TableVisual': {
            'VisualId': 'm6-perf-by-train-snapshot',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Performance by Training Snapshot'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'TableAggregatedFieldWells': {
                        'GroupBy': [
                            {'CategoricalDimensionField': {'FieldId': 'm6-tsnap', 'Column': dcol('training_snapshot_id')}},
                        ],
                        'Values': [
                            {'NumericalMeasureField': {'FieldId': 'm6-avg-auc', 'Column': dcol('current_roc_auc'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'm6-avg-acc', 'Column': dcol('accuracy'),        'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'm6-drate',   'Column': dcol('model_drift_detected'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'CategoricalMeasureField': {'FieldId': 'm6-runs',    'Column': dcol('monitoring_run_id'),    'AggregationFunction': 'COUNT'}},
                        ],
                    }
                }
            }
        }
    }

    # M7 — the auditor's screenshot table. Every immutable reference on
    # every drift run.
    m7_lineage_audit = {
        'TableVisual': {
            'VisualId': 'm7-lineage-audit',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Model Lineage Audit (per monitoring run)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'TableAggregatedFieldWells': {
                        'GroupBy': [
                            {'DateDimensionField':        {'FieldId': 'm7-ts',    'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'MINUTE'}},
                            {'CategoricalDimensionField': {'FieldId': 'm7-run',   'Column': dcol('monitoring_run_id')}},
                            {'CategoricalDimensionField': {'FieldId': 'm7-ep',    'Column': dcol('endpoint_name')}},
                            {'CategoricalDimensionField': {'FieldId': 'm7-mv',    'Column': dcol('model_version')}},
                            {'CategoricalDimensionField': {'FieldId': 'm7-arn',   'Column': dcol('model_package_arn')}},
                            {'CategoricalDimensionField': {'FieldId': 'm7-tsnap', 'Column': dcol('training_snapshot_id')}},
                            {'CategoricalDimensionField': {'FieldId': 'm7-esnap', 'Column': dcol('evaluation_snapshot_id')}},
                            {'NumericalDimensionField': {'FieldId': 'm7-ddd',   'Column': dcol('data_drift_detected')}},
                            {'NumericalDimensionField': {'FieldId': 'm7-mdd',   'Column': dcol('model_drift_detected')}},
                        ],
                        'Values': [
                            {'NumericalMeasureField': {'FieldId': 'm7-auc', 'Column': dcol('current_roc_auc'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                        ],
                    }
                }
            }
        }
    }

    m8_latest_auc = {
        'KPIVisual': {
            'VisualId': 'm8-latest-auc',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Latest Current ROC-AUC'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{'NumericalMeasureField': {'FieldId': 'm8-val', 'Column': dcol('current_roc_auc'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    'TrendGroups': [{'DateDimensionField': {'FieldId': 'm8-trend', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                }
            }
        }
    }

    # M9 — Confusion Matrix Over Time. Aggregate accuracy-join records
    # by day and prediction_category (TP/FP/TN/FN). Reveals *which* class
    # of error is trending: e.g. accuracy dips but only because false-negatives
    # spiked, which for classification tasks matters far more than an accuracy
    # bump from more true-negatives. Bound to the accuracy-join dataset
    # since that's where the confusion-category breakdown lives.
    def acol(name):
        return {'DataSetIdentifier': DS_IDENT_ACCURACY, 'ColumnName': name}

    m9_confusion_matrix_trend = {
        'BarChartVisual': {
            'VisualId': 'm9-confusion-matrix-trend',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Confusion Matrix Over Time (TP/FP/TN/FN)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'm9-date', 'Column': acol('inference_date'), 'DateGranularity': 'DAY'}}],
                        'Values':   [{'CategoricalMeasureField': {'FieldId': 'm9-cnt', 'Column': acol('inference_id'), 'AggregationFunction': 'COUNT'}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'm9-cat', 'Column': acol('prediction_category')}}],
                    }
                },
                'Orientation': 'VERTICAL',
                'BarsArrangement': 'STACKED',
            }
        }
    }

    # M10 — Performance Degradation % Trend. Threshold-relative degradation
    # is more actionable than absolute AUC because the alert threshold in
    # config is defined as a % (`model_drift_threshold`). Line stays flat
    # near 0% during healthy runs; every spike over the config threshold
    # was a drift alert. Answers "how badly did each run regress?"
    m10_degradation_pct = {
        'LineChartVisual': {
            'VisualId': 'm10-degradation-pct',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'ROC-AUC Degradation % Over Time'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'm10-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':   [{'NumericalMeasureField': {'FieldId': 'm10-degpct', 'Column': dcol('roc_auc_degradation_pct'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'm10-mv', 'Column': dcol('model_version')}}],
                    }
                }
            }
        }
    }

    # M11 — Ground Truth Coverage. Every model-drift verdict below is only
    # trustworthy if we have labels for the predictions being scored. This
    # visual = COUNT(gt_count) / COUNT(inference_count) over time — the
    # data comes from the feature_drift join dataset which already carries
    # both counts. Falling coverage is a *precondition* for model-drift
    # metrics becoming unreliable, so this belongs at the top of the tab.
    def fcol(name):
        return {'DataSetIdentifier': DS_IDENT_FEATURE_DRIFT, 'ColumnName': name}

    m11_gt_coverage = {
        'LineChartVisual': {
            'VisualId': 'm11-gt-coverage',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Ground-Truth Coverage Over Time (labels / predictions)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'm11-date', 'Column': fcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [
                            {'NumericalMeasureField': {'FieldId': 'm11-gt',  'Column': fcol('gt_count'),        'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
                            {'NumericalMeasureField': {'FieldId': 'm11-inf', 'Column': fcol('inference_count'), 'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}},
                        ],
                    }
                }
            }
        }
    }

    return [
        m1_roc_auc_over_time,
        m2_perf_metrics_over_time,
        m3_roc_auc_by_version,
        m4_verdict_rate_by_arn,
        m5_verdict_rate_by_endpoint,
        m6_perf_by_train_snapshot,
        m7_lineage_audit,
        m8_latest_auc,
        m9_confusion_matrix_trend,
        m10_degradation_pct,
        m11_gt_coverage,
    ]


def build_data_drift_visuals() -> List[Dict[str, Any]]:
    """
    Build the "Data Drift Trends" tab (Sheet 2).

    Answers "is production traffic drifting away from training data, and
    at what rate — by model version, endpoint, or in aggregate?"

    Bound to `DS_IDENT_DRIFT` (monitoring_responses) for D1-D5, D7 and
    `DS_IDENT_FEATURE_DRIFT` (join of monitoring + inference) for D6.

    Visuals:
        D1  Data Drift Share Over Time                       (line)
        D2  Drifted Features Count Over Time                 (line)
        D3  Drift Alerts Timeline (severity colored)         (bar)
        D4  Data Drift Share by Model Version                (line, colored)
        D5  Data Drift Share by Endpoint                     (line, colored)
        D6  Inference Volume vs Drift Share Correlation      (combo)
        D7  Latest Data Drift Share                          (KPI)
    """
    def dcol(name):
        return {'DataSetIdentifier': DS_IDENT_DRIFT, 'ColumnName': name}

    def fcol(name):
        return {'DataSetIdentifier': DS_IDENT_FEATURE_DRIFT, 'ColumnName': name}

    d1_share_over_time = {
        'LineChartVisual': {
            'VisualId': 'd1-drift-share-trend',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Data Drift Share Over Time'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'd1-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'd1-share', 'Column': dcol('drifted_columns_share'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                }
            }
        }
    }

    d2_count_over_time = {
        'LineChartVisual': {
            'VisualId': 'd2-drift-count-trend',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Drifted Features Count Over Time'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'd2-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'd2-count', 'Column': dcol('drifted_columns_count'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                }
            }
        }
    }

    d3_alerts_timeline = {
        'BarChartVisual': {
            'VisualId': 'd3-alerts-timeline',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Drift Alerts Timeline'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'd3-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'd3-alerts', 'Column': dcol('alert_sent'), 'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}}],
                        'Colors': [{'CategoricalDimensionField': {'FieldId': 'd3-sev', 'Column': dcol('drift_severity')}}],
                    }
                },
                'Orientation': 'VERTICAL',
            }
        }
    }

    d4_share_by_version = {
        'LineChartVisual': {
            'VisualId': 'd4-share-by-version',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Data Drift Share by Model Version'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'd4-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'd4-share', 'Column': dcol('drifted_columns_share'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors': [{'CategoricalDimensionField': {'FieldId': 'd4-version', 'Column': dcol('model_version')}}],
                    }
                }
            }
        }
    }

    d5_share_by_endpoint = {
        'LineChartVisual': {
            'VisualId': 'd5-share-by-endpoint',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Data Drift Share by Endpoint'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'd5-date', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values': [{'NumericalMeasureField': {'FieldId': 'd5-share', 'Column': dcol('drifted_columns_share'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors': [{'CategoricalDimensionField': {'FieldId': 'd5-ep', 'Column': dcol('endpoint_name')}}],
                    }
                }
            }
        }
    }

    # D6 uses the CustomSql feature-drift dataset that joins monitoring +
    # inference — this is the only visual that needs inference_count.
    d6_volume_vs_drift = {
        'ComboChartVisual': {
            'VisualId': 'd6-volume-vs-drift',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Inference Volume vs Drift Share Correlation'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'ComboChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'd6-date', 'Column': fcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'BarValues':  [{'NumericalMeasureField': {'FieldId': 'd6-vol',   'Column': fcol('inference_count'),        'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}}],
                        'LineValues': [{'NumericalMeasureField': {'FieldId': 'd6-drift', 'Column': fcol('drifted_columns_share'),  'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                }
            }
        }
    }

    d7_latest_share = {
        'KPIVisual': {
            'VisualId': 'd7-latest-share',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Latest Data Drift Share'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{'NumericalMeasureField': {'FieldId': 'd7-val', 'Column': dcol('drifted_columns_share'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    'TrendGroups': [{'DateDimensionField': {'FieldId': 'd7-trend', 'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                }
            }
        }
    }

    # D8 — raw source-data table. Every `monitoring_responses` row with the
    # exact numeric fields that power D1-D7 above. Lets users inspect the
    # underlying data behind every chart on this sheet without pivoting to
    # Athena.
    d8_source_data = {
        'TableVisual': {
            'VisualId': 'd8-source-data',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Source Data — monitoring_responses'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'TableAggregatedFieldWells': {
                        'GroupBy': [
                            {'DateDimensionField':        {'FieldId': 'd8-ts',    'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'MINUTE'}},
                            {'CategoricalDimensionField': {'FieldId': 'd8-run',   'Column': dcol('monitoring_run_id')}},
                            {'CategoricalDimensionField': {'FieldId': 'd8-ep',    'Column': dcol('endpoint_name')}},
                            {'CategoricalDimensionField': {'FieldId': 'd8-mv',    'Column': dcol('model_version')}},
                            {'CategoricalDimensionField': {'FieldId': 'd8-sev',   'Column': dcol('drift_severity')}},
                            {'NumericalDimensionField': {'FieldId': 'd8-ddd',   'Column': dcol('data_drift_detected')}},
                        ],
                        'Values': [
                            {'NumericalMeasureField': {'FieldId': 'd8-share', 'Column': dcol('drifted_columns_share'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'd8-count', 'Column': dcol('drifted_columns_count'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'd8-analz', 'Column': dcol('features_analyzed'),     'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                            {'NumericalMeasureField': {'FieldId': 'd8-samp',  'Column': dcol('data_sample_size'),      'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                        ],
                    }
                }
            }
        }
    }

    # D9 — Prediction Score Distribution Over Time. Box plot per day of the
    # continuous probability output. This is the *leading* indicator of drift:
    # data drift + concept drift both surface as a shift in the score
    # distribution BEFORE ground truth is collected and BEFORE ROC-AUC dips.
    # A shift from bimodal (0 and 1 clusters) toward the middle = the model
    # is losing certainty. Bound to the inference dataset because the
    # underlying probability column lives there.
    def icol(name):
        return {'DataSetIdentifier': DS_IDENT_INFERENCE, 'ColumnName': name}

    d9_score_distribution = {
        'BoxPlotVisual': {
            'VisualId': 'd9-score-distribution',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Prediction Score Distribution Over Time (leading indicator)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BoxPlotAggregatedFieldWells': {
                        'GroupBy': [{'DateDimensionField': {'FieldId': 'd9-date',  'Column': icol('request_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':  [{'NumericalMeasureField': {'FieldId': 'd9-score', 'Column': icol(PROBABILITY_COLUMN)}}],
                    }
                }
            }
        }
    }

    # D10 — Sample Size Reliability. KS-test drift verdicts on small samples
    # are unreliable — Evidently's own docs recommend ≥ 1000 rows for stable
    # p-values. This visual makes the "how much data actually powered each
    # drift verdict?" question visible. Bars below a horizontal reference
    # line (users can add via QuickSight console) signal shaky runs.
    d10_sample_size = {
        'BarChartVisual': {
            'VisualId': 'd10-sample-size',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Drift Verdict Sample Size Per Run'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField':    {'FieldId': 'd10-date',  'Column': dcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':   [{'NumericalMeasureField': {'FieldId': 'd10-samp',  'Column': dcol('data_sample_size'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'd10-mv',  'Column': dcol('model_version')}}],
                    }
                },
                'Orientation': 'VERTICAL',
            }
        }
    }

    return [
        d1_share_over_time,
        d2_count_over_time,
        d3_alerts_timeline,
        d4_share_by_version,
        d5_share_by_endpoint,
        d6_volume_vs_drift,
        d7_latest_share,
        d8_source_data,
        d9_score_distribution,
        d10_sample_size,
    ]


def build_feature_drift_visuals() -> List[Dict[str, Any]]:
    """
    Build the "Feature Drift Trends" tab (Sheet 3).

    Answers "which specific features are drifting, over what time, and is
    the drift consistent across model versions?" Bound to
    `DS_IDENT_FEATURE_LEVEL` (the CustomSql view that unpacks the JSON
    per_feature_drift_scores).

    Visuals:
        F1  Feature Drift Score Timeline               (line, per-feature)
        F2  Top 15 Most-Drifting Features (all time)   (horizontal bar)
        F3  Drift Severity by Feature (Top 15)         (stacked bar)
        F4  Feature Drift Heatmap (Features × Time)    (pivot)
        F5  Feature Drift Details                      (lookup table)
        F6  Highest Current Drift Score                (KPI)
        F7  Feature Drift Heatmap (Features × Version) (pivot — cross-model consistency)
    """
    def flcol(name):
        return {'DataSetIdentifier': DS_IDENT_FEATURE_LEVEL, 'ColumnName': name}

    # Reference line at magnitude = 1.0 (drifted threshold: magnitude >= 1.0 means drifted)
    magnitude_ref_line_1 = [{
        'Status': 'ENABLED',
        'DataConfiguration': {'StaticConfiguration': {'Value': 1.0}, 'AxisBinding': 'PRIMARY_YAXIS'},
        'StyleConfiguration': {'Pattern': 'DASHED', 'Color': '#C00000'},
        'LabelConfiguration': {
            'CustomLabelConfiguration': {'CustomLabel': 'magnitude = 1.0 (above = drifted)'},
            'FontConfiguration': {'FontSize': {'Relative': 'SMALL'}},
        },
    }]

    f1_score_timeline = {
        'LineChartVisual': {
            'VisualId': 'f1-feature-drift-timeline',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Feature Drift Score Timeline'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'f1-date', 'Column': flcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':   [{'NumericalMeasureField': {'FieldId': 'f1-score', 'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'f1-feat', 'Column': flcol('feature_name')}}],
                    }
                },
                'ReferenceLines': magnitude_ref_line_1,
                # Y-axis title goes in PrimaryYAxisLabelOptions (a
                # ChartAxisLabelOptions), NOT PrimaryYAxisDisplayOptions.AxisOptions
                # — the latter has no AxisLabel field and botocore rejects the
                # whole CreateDashboard call with a ParamValidationError.
                'PrimaryYAxisLabelOptions': {'Visibility': 'VISIBLE', 'AxisLabelOptions': [{'CustomLabel': 'drift_magnitude (x threshold)'}]},
            }
        }
    }

    f2_top_features = {
        'BarChartVisual': {
            'VisualId': 'f2-top-features',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Top 15 Most-Drifting Features (All Time)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'CategoricalDimensionField': {'FieldId': 'f2-feat', 'Column': flcol('feature_name')}}],
                        'Values':   [{'NumericalMeasureField':    {'FieldId': 'f2-avg',  'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                },
                'Orientation': 'HORIZONTAL',
                'CategoryLabelOptions': {'Visibility': 'VISIBLE'},
            }
        }
    }

    f3_severity_by_feature = {
        'BarChartVisual': {
            'VisualId': 'f3-severity-by-feature',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Drift Severity Distribution by Feature (Top 15)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'CategoricalDimensionField': {'FieldId': 'f3-feat', 'Column': flcol('feature_name')}}],
                        'Values':   [{'NumericalMeasureField':    {'FieldId': 'f3-cnt',  'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'COUNT'}}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'f3-sev', 'Column': flcol('drift_severity')}}],
                    }
                },
                'Orientation': 'HORIZONTAL',
                'BarsArrangement': 'STACKED',
            }
        }
    }

    f4_heatmap_time = {
        'PivotTableVisual': {
            'VisualId': 'f4-heatmap-time',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Feature Drift Heatmap (Features × Time)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'PivotTableAggregatedFieldWells': {
                        'Rows':    [{'CategoricalDimensionField': {'FieldId': 'f4-feat', 'Column': flcol('feature_name')}}],
                        'Columns': [{'DateDimensionField':        {'FieldId': 'f4-date', 'Column': flcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':  [{'NumericalMeasureField':    {'FieldId': 'f4-val',  'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                }
            }
        }
    }

    f5_details_table = {
        'TableVisual': {
            'VisualId': 'f5-details-table',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Feature Drift Details (per run × feature)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'TableAggregatedFieldWells': {
                        'GroupBy': [
                            {'DateDimensionField':        {'FieldId': 'f5-ts',    'Column': flcol('monitoring_timestamp'), 'DateGranularity': 'MINUTE'}},
                            {'CategoricalDimensionField': {'FieldId': 'f5-feat',  'Column': flcol('feature_name')}},
                            {'CategoricalDimensionField': {'FieldId': 'f5-sev',   'Column': flcol('drift_severity')}},
                            {'CategoricalDimensionField': {'FieldId': 'f5-mv',    'Column': flcol('model_version')}},
                        ],
                        'Values': [
                            {'NumericalMeasureField': {'FieldId': 'f5-score', 'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}},
                        ],
                    }
                }
            }
        }
    }

    f6_highest_score = {
        'KPIVisual': {
            'VisualId': 'f6-highest-score',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Highest Current Drift Score'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'Values': [{'NumericalMeasureField': {'FieldId': 'f6-val', 'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}}}],
                    'TrendGroups': [{'DateDimensionField': {'FieldId': 'f6-trend', 'Column': flcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                }
            }
        }
    }

    # F7 — new. Cross-model-version heatmap. Row = feature, column =
    # model_version, cell = AVG drift score. Answers "is this feature
    # drifting consistently across our retrained models, or is it a
    # symptom of one specific version's training data?"
    f7_heatmap_version = {
        'PivotTableVisual': {
            'VisualId': 'f7-heatmap-version',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Feature Drift Heatmap (Features × Model Version)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'PivotTableAggregatedFieldWells': {
                        'Rows':    [{'CategoricalDimensionField': {'FieldId': 'f7-feat', 'Column': flcol('feature_name')}}],
                        'Columns': [{'CategoricalDimensionField': {'FieldId': 'f7-mv',   'Column': flcol('model_version')}}],
                        'Values':  [{'NumericalMeasureField':    {'FieldId': 'f7-val',  'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                    }
                }
            }
        }
    }

    # F8 — Max Feature Drift Score Per Run. The *worst* feature per run is
    # more actionable than the AVG shown on Sheet 2 (D1): a moderate average
    # drift can hide a single feature that shifted catastrophically. This
    # visual highlights the peak — the feature that would trigger the
    # loudest alert — and its trend over monitoring runs.
    f8_max_drift_per_run = {
        'LineChartVisual': {
            'VisualId': 'f8-max-drift-per-run',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Max Feature Drift Score Per Run (worst-feature signal)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'f8-date', 'Column': flcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':   [{'NumericalMeasureField': {'FieldId': 'f8-max', 'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'MAX'}}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'f8-mv', 'Column': flcol('model_version')}}],
                    }
                }
            }
        }
    }

    # F9 — Repeat-Offender Features. COUNT of runs where each feature was
    # flagged as drifted (drift_detected = TRUE). Answers "which features
    # drift chronically vs. one-off spikes?" — chronic drifters are usually
    # retraining candidates; one-off spikes are usually data-quality issues.
    # Different granularity than F2 (which averages the score); this one
    # counts flagged occurrences.
    f9_repeat_offenders = {
        'BarChartVisual': {
            'VisualId': 'f9-repeat-offenders',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText': 'Repeat-Offender Features (# of runs where drift_detected=TRUE)'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'BarChartAggregatedFieldWells': {
                        'Category': [{'CategoricalDimensionField': {'FieldId': 'f9-feat', 'Column': flcol('feature_name')}}],
                        'Values':   [{'NumericalMeasureField':    {'FieldId': 'f9-cnt',  'Column': flcol('drift_detected'), 'AggregationFunction': {'SimpleNumericalAggregation': 'SUM'}}}],
                    }
                },
                'Orientation': 'HORIZONTAL',
            }
        }
    }

    # ─── Raw drift_score - split by test-family so direction is unambiguous ─

    # F10 — Raw p-value scores. Filter to KS / Chi-square rows only via a
    # DataSet-scoped filter in QuickSight (drift_method LIKE '%p_value%').
    # For p-values, LOWER = more drift. Reference line at 0.05 marks the
    # significance threshold — anything BELOW is drifted.
    f10_raw_pvalue_timeline = {
        'LineChartVisual': {
            'VisualId': 'f10-raw-pvalue-timeline',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText':
                'Raw drift_score - p-value tests (KS / Chi-square) - LOWER = more drift. Below red 0.05 line = drifted. FILTER: drift_method contains "p_value".'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'f10-date', 'Column': flcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':   [{'NumericalMeasureField': {'FieldId': 'f10-score', 'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'f10-feat', 'Column': flcol('feature_name')}}],
                    }
                },
                'ReferenceLines': [{
                    'Status': 'ENABLED',
                    'DataConfiguration': {'StaticConfiguration': {'Value': 0.05}, 'AxisBinding': 'PRIMARY_YAXIS'},
                    'StyleConfiguration': {'Pattern': 'DASHED', 'Color': '#C00000'},
                    'LabelConfiguration': {
                        'CustomLabelConfiguration': {'CustomLabel': 'p = 0.05 (below = drifted)'},
                        'FontConfiguration': {'FontSize': {'Relative': 'SMALL'}},
                    },
                }],
                'PrimaryYAxisLabelOptions': {'Visibility': 'VISIBLE', 'AxisLabelOptions': [{'CustomLabel': 'p-value (LOWER = more drift)'}]},
            }
        }
    }

    # F11 — Raw distance scores. Filter to Wasserstein / Jensen-Shannon / PSI
    # rows only via a DataSet-scoped filter (drift_method contains "distance"
    # or "PSI"). For distances, HIGHER = more drift. Reference line at 0.1
    # (Evidently's default distance threshold).
    f11_raw_distance_timeline = {
        'LineChartVisual': {
            'VisualId': 'f11-raw-distance-timeline',
            'Title': {'Visibility': 'VISIBLE', 'FormatText': {'PlainText':
                'Raw drift_score - distance tests (Wasserstein / Jensen-Shannon / PSI) - HIGHER = more drift. Above red 0.1 line = drifted. FILTER: drift_method contains "distance".'}},
            'ChartConfiguration': {
                'FieldWells': {
                    'LineChartAggregatedFieldWells': {
                        'Category': [{'DateDimensionField': {'FieldId': 'f11-date', 'Column': flcol('monitoring_timestamp'), 'DateGranularity': 'DAY'}}],
                        'Values':   [{'NumericalMeasureField': {'FieldId': 'f11-score', 'Column': flcol('drift_score'), 'AggregationFunction': {'SimpleNumericalAggregation': 'AVERAGE'}}}],
                        'Colors':   [{'CategoricalDimensionField': {'FieldId': 'f11-feat', 'Column': flcol('feature_name')}}],
                    }
                },
                'ReferenceLines': [{
                    'Status': 'ENABLED',
                    'DataConfiguration': {'StaticConfiguration': {'Value': 0.1}, 'AxisBinding': 'PRIMARY_YAXIS'},
                    'StyleConfiguration': {'Pattern': 'DASHED', 'Color': '#C00000'},
                    'LabelConfiguration': {
                        'CustomLabelConfiguration': {'CustomLabel': 'distance = 0.1 (above = drifted)'},
                        'FontConfiguration': {'FontSize': {'Relative': 'SMALL'}},
                    },
                }],
                'PrimaryYAxisLabelOptions': {'Visibility': 'VISIBLE', 'AxisLabelOptions': [{'CustomLabel': 'distance (HIGHER = more drift)'}]},
            }
        }
    }

    return [
        f1_score_timeline,
        f2_top_features,
        f3_severity_by_feature,
        f4_heatmap_time,
        f5_details_table,
        f6_highest_score,
        f7_heatmap_version,
        f8_max_drift_per_run,
        f9_repeat_offenders,
    ]




def _build_all_visuals() -> Dict[str, List[Dict[str, Any]]]:
    """
    Build all visual definitions for the redesigned 3-tab dashboard.

    The dashboard was consolidated from an earlier 4-tab layout (which
    duplicated coverage across an "Inference Monitoring" sheet and
    drift-analysis sheets, and carried domain-specific visuals
    irrelevant to drift). Each of the three tabs answers a single
    organizing question:

      - Model Drift Trends   — "how is model performance degrading, and
                              for which model version / package ARN /
                              endpoint / training snapshot?"
      - Data Drift Trends    — "is production input distribution shifting,
                              at which granularity?"
      - Feature Drift Trends — "which specific features are drifting,
                              and is it consistent across model versions?"

    Every sheet ends with a raw source-data table so users can inspect
    the exact rows powering the charts above without pivoting to Athena.

    Returns:
        Dict with keys 'sheet1'-'sheet3', each a list of visual dicts.
        Total: 8 + 8 + 7 = 23 visuals across three sheets.
    """
    return {
        'sheet1': build_model_drift_visuals(),
        'sheet2': build_data_drift_visuals(),
        'sheet3': build_feature_drift_visuals(),
    }


def _build_definition(
    dataset_arns: Dict[str, str],
    visuals: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Build the shared Definition-API payload used by both analysis and dashboard.

    Args:
        dataset_arns: Dict with keys 'inference', 'drift', 'feature_drift',
            'feature_level', 'accuracy' mapping to dataset ARNs. All five
            datasets stay declared even after the 4→3 tab consolidation:
            the drift-monitor Lambda still writes to `monitoring_responses`
            and the CustomSql feature-drift join is still used by D6.
            Keeping every declaration makes it a no-op to re-add ad-hoc
            visuals from the QuickSight console against any of them.
        visuals: Dict from `_build_all_visuals()` with keys 'sheet1'..'sheet3'.

    Returns:
        A Definition dict with DataSetIdentifierDeclarations + 3 Sheets.
    """
    return {
        'DataSetIdentifierDeclarations': [
            {'Identifier': DS_IDENT_INFERENCE, 'DataSetArn': dataset_arns['inference']},
            {'Identifier': DS_IDENT_DRIFT, 'DataSetArn': dataset_arns['drift']},
            {'Identifier': DS_IDENT_FEATURE_DRIFT, 'DataSetArn': dataset_arns['feature_drift']},
            {'Identifier': DS_IDENT_FEATURE_LEVEL, 'DataSetArn': dataset_arns['feature_level']},
            {'Identifier': DS_IDENT_ACCURACY, 'DataSetArn': dataset_arns['accuracy']},
        ],
        'Sheets': [
            {'SheetId': 'governance-sheet-model',   'Name': 'Model Drift Trends',   'Visuals': visuals['sheet1']},
            {'SheetId': 'governance-sheet-data',    'Name': 'Data Drift Trends',    'Visuals': visuals['sheet2']},
            {'SheetId': 'governance-sheet-feature', 'Name': 'Feature Drift Trends', 'Visuals': visuals['sheet3']},
        ],
    }


# ---------------------------------------------------------------------------
# Section 8 — analysis (Definition API)
# ---------------------------------------------------------------------------


def create_or_update_analysis(
    account_id: str,
    quicksight_principals: List[str],
    dataset_arns: Dict[str, str],
    quicksight_client: Optional[Any] = None,
    analysis_id: Optional[str] = None,
    analysis_name: Optional[str] = None,
    poll_interval: int = 2,
    max_poll_attempts: int = 30,
) -> str:
    """
    Create or update the governance analysis via the Definition API (Section 8).

    Idempotent describe/create-or-update pattern, polling
    `describe_analysis` until the (new) version reaches
    'CREATION_SUCCESSFUL' (raising on 'CREATION_FAILED'/'UPDATE_FAILED'/
    'DELETED' — with the `Errors` list included in the raised exception
    message, matching the notebook's error-detail printing — and logging a
    warning on timeout rather than raising, matching the notebook which
    only prints a warning after `max_attempts`).

    Args:
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        dataset_arns: Dict with keys 'inference', 'drift', 'feature_drift',
            'feature_level', 'accuracy' mapping to dataset ARNs
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        analysis_id: Analysis ID. Defaults to config.QUICKSIGHT_ANALYSIS_ID.
        analysis_name: Analysis display name. Defaults to
            config.QUICKSIGHT_ANALYSIS_NAME.
        poll_interval: Seconds between status polls.
        max_poll_attempts: Max number of status polls before giving up.

    Returns:
        The analysis ARN.

    Raises:
        RuntimeError: If the analysis reaches a *_FAILED or DELETED status.
            The exception message includes the `Errors` list from the
            analysis description.
    """
    resolved_analysis_id = analysis_id or QUICKSIGHT_ANALYSIS_ID
    resolved_analysis_name = analysis_name or QUICKSIGHT_ANALYSIS_NAME

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    visuals = _build_all_visuals()
    analysis_definition = _build_definition(dataset_arns, visuals)
    analysis_definition['AnalysisDefaults'] = {
        'DefaultNewSheetConfiguration': {
            'InteractiveLayoutConfiguration': {
                'FreeForm': {'CanvasSizeOptions': {'ScreenCanvasSizeOptions': {'OptimizedViewPortWidth': '1600px'}}}
            }
        }
    }

    try:
        quicksight_client.describe_analysis(AwsAccountId=account_id, AnalysisId=resolved_analysis_id)
        logger.info("Analysis exists, updating...")
        resp = quicksight_client.update_analysis(
            AwsAccountId=account_id, AnalysisId=resolved_analysis_id,
            Name=resolved_analysis_name,
            Definition=analysis_definition,
        )

        logger.info("  Waiting for analysis to complete...")
        status = None
        for _ in range(max_poll_attempts):
            analysis_resp = quicksight_client.describe_analysis(AwsAccountId=account_id, AnalysisId=resolved_analysis_id)
            status = analysis_resp['Analysis']['Status']

            if status == 'CREATION_SUCCESSFUL':
                logger.info("  ✓ Analysis update successful")
                break
            elif status in ('CREATION_FAILED', 'UPDATE_FAILED', 'DELETED'):
                errors = analysis_resp['Analysis'].get('Errors', [])
                logger.error(f"  ✗ Analysis update failed with status: {status}")
                for i, err in enumerate(errors[:5], 1):
                    logger.error(f"    {i}. [{err.get('Type', 'Unknown')}] {err.get('Message', 'No message')}")
                if len(errors) > 5:
                    logger.error(f"    ... and {len(errors) - 5} more errors")
                raise RuntimeError(f"Analysis in {status} state - Errors: {errors}")

            time.sleep(poll_interval)
        else:
            logger.warning(f"  ⚠ Timeout waiting for analysis (status: {status})")

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info("Creating new analysis...")
            resp = quicksight_client.create_analysis(
                AwsAccountId=account_id, AnalysisId=resolved_analysis_id,
                Name=resolved_analysis_name,
                Definition=analysis_definition,
                Permissions=[{'Principal': p, 'Actions': _ANALYSIS_ACTIONS} for p in quicksight_principals],
            )
            logger.info("  ✓ Analysis created")
        else:
            raise

    logger.info(f"✓ Analysis: {resp['Arn']}")
    return resp['Arn']


# ---------------------------------------------------------------------------
# Section 9 — dashboard (Definition API)
# ---------------------------------------------------------------------------


def publish_dashboard(
    account_id: str,
    quicksight_principals: List[str],
    dataset_arns: Dict[str, str],
    quicksight_client: Optional[Any] = None,
    dashboard_id: Optional[str] = None,
    dashboard_name: Optional[str] = None,
    region: Optional[str] = None,
    poll_interval: int = 2,
    max_poll_attempts: int = 30,
) -> Dict[str, Any]:
    """
    Create/update and publish the governance dashboard via the Definition API (Section 9).

    Idempotent describe/create-or-update pattern. On update, polls
    `describe_dashboard` (by version number) until 'CREATION_SUCCESSFUL'
    then calls `update_dashboard_published_version`. On create, the new
    dashboard is published implicitly by `create_dashboard` (no separate
    publish call needed — matches the notebook).

    Args:
        account_id: AWS account ID
        quicksight_principals: QuickSight user ARNs to grant on create
        dataset_arns: Dict with keys 'inference', 'drift', 'feature_drift',
            'feature_level', 'accuracy' mapping to dataset ARNs
        quicksight_client: Optional boto3 QuickSight client bound to the
            asset region (constructed if not provided)
        dashboard_id: Dashboard ID. Defaults to config.QUICKSIGHT_DASHBOARD_ID.
        dashboard_name: Dashboard display name. Defaults to
            config.QUICKSIGHT_DASHBOARD_NAME.
        region: AWS region, used to build the returned console URL and to
            construct the QuickSight client if not provided. Defaults to
            config.AWS_DEFAULT_REGION.
        poll_interval: Seconds between status polls.
        max_poll_attempts: Max number of status polls before giving up.

    Returns:
        Dict with keys: 'dashboard_arn', 'dashboard_url', 'version'.

    Raises:
        RuntimeError: If the dashboard version reaches a *_FAILED or DELETED status.
    """
    resolved_dashboard_id = dashboard_id or QUICKSIGHT_DASHBOARD_ID
    resolved_dashboard_name = dashboard_name or QUICKSIGHT_DASHBOARD_NAME
    resolved_region = region or AWS_DEFAULT_REGION

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=resolved_region)

    visuals = _build_all_visuals()
    dashboard_definition = _build_definition(dataset_arns, visuals)

    publish_options = {
        'AdHocFilteringOption': {'AvailabilityStatus': 'ENABLED'},
        'ExportToCSVOption': {'AvailabilityStatus': 'ENABLED'},
        'SheetControlsOption': {'VisibilityState': 'EXPANDED'},
    }

    version = None
    try:
        quicksight_client.describe_dashboard(AwsAccountId=account_id, DashboardId=resolved_dashboard_id)
        logger.info("Dashboard exists, updating...")
        resp = quicksight_client.update_dashboard(
            AwsAccountId=account_id, DashboardId=resolved_dashboard_id,
            Name=resolved_dashboard_name,
            Definition=dashboard_definition,
            DashboardPublishOptions=publish_options,
        )
        version = resp['VersionArn'].split('/')[-1]

        logger.info(f"  Waiting for dashboard version {version} to complete...")
        status = None
        for _ in range(max_poll_attempts):
            dash_resp = quicksight_client.describe_dashboard(
                AwsAccountId=account_id, DashboardId=resolved_dashboard_id, VersionNumber=int(version)
            )
            status = dash_resp['Dashboard']['Version']['Status']

            if status == 'CREATION_SUCCESSFUL':
                logger.info("  ✓ Dashboard update successful")
                break
            elif status in ('CREATION_FAILED', 'UPDATE_FAILED', 'DELETED'):
                errors = dash_resp['Dashboard']['Version'].get('Errors', [])
                logger.error(f"  ✗ Dashboard update failed with status: {status}")
                for err in errors[:3]:
                    logger.error(f"    - {err.get('Type', 'Unknown')}: {err.get('Message', 'No message')}")
                raise RuntimeError(f"Dashboard in {status} state, cannot publish - Errors: {errors}")

            time.sleep(poll_interval)
        else:
            logger.warning(f"  ⚠ Timeout waiting for dashboard (status: {status})")

        if status == 'CREATION_SUCCESSFUL':
            quicksight_client.update_dashboard_published_version(
                AwsAccountId=account_id, DashboardId=resolved_dashboard_id, VersionNumber=int(version)
            )
            logger.info(f"  ✓ Published version {version}")

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            logger.info("Creating new dashboard...")
            resp = quicksight_client.create_dashboard(
                AwsAccountId=account_id, DashboardId=resolved_dashboard_id,
                Name=resolved_dashboard_name,
                Definition=dashboard_definition,
                DashboardPublishOptions=publish_options,
                Permissions=[{'Principal': p, 'Actions': _DASHBOARD_ACTIONS} for p in quicksight_principals],
            )
            version = resp['VersionArn'].split('/')[-1]
            logger.info(f"  ✓ Created dashboard version {version}")
        else:
            raise

    dashboard_url = f'https://{resolved_region}.quicksight.aws.amazon.com/sn/dashboards/{resolved_dashboard_id}'
    logger.info(f"✓ Dashboard: {dashboard_url}")
    return {
        'dashboard_arn': resp['Arn'],
        'dashboard_url': dashboard_url,
        'version': version,
    }


# ---------------------------------------------------------------------------
# Section 10 — embed URL (optional, best-effort)
# ---------------------------------------------------------------------------


def get_dashboard_embed_url(
    account_id: str,
    dashboard_id: Optional[str] = None,
    quicksight_client: Optional[Any] = None,
    session_lifetime_minutes: int = 600,
) -> Optional[str]:
    """
    Generate a QuickSight embed URL for the governance dashboard (Section 10).

    Optional / best-effort — requires embedding to be enabled in QuickSight
    admin settings for the calling identity type. Matches the notebook: a
    ClientError here is caught and logged, returning None rather than
    raising, since this is a nice-to-have.

    Args:
        account_id: AWS account ID
        dashboard_id: Dashboard ID. Defaults to config.QUICKSIGHT_DASHBOARD_ID.
        quicksight_client: Optional boto3 QuickSight client (constructed if not provided)
        session_lifetime_minutes: Embed session lifetime in minutes.

    Returns:
        The embed URL string, or None if generation failed.
    """
    resolved_dashboard_id = dashboard_id or QUICKSIGHT_DASHBOARD_ID

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    try:
        resp = quicksight_client.get_dashboard_embed_url(
            AwsAccountId=account_id, DashboardId=resolved_dashboard_id,
            IdentityType='QUICKSIGHT', SessionLifetimeInMinutes=session_lifetime_minutes,
            UndoRedoDisabled=False, ResetDisabled=False,
        )
        embed_url = resp['EmbedUrl']
        logger.info(f"Embed URL (valid {session_lifetime_minutes // 60} hours): {embed_url}")
        return embed_url
    except ClientError as e:
        message = e.response['Error']['Message']
        logger.warning(f"Could not generate embed URL: {message}")
        logger.warning("Ensure embedding is enabled in QuickSight admin settings.")
        return None


# ---------------------------------------------------------------------------
# Section 11 — cleanup
# ---------------------------------------------------------------------------


def delete_governance_resources(
    account_id: str,
    quicksight_client: Optional[Any] = None,
    dashboard_id: Optional[str] = None,
    analysis_id: Optional[str] = None,
    dataset_ids: Optional[List[str]] = None,
    datasource_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Delete the QuickSight governance dashboard and all its resources (Section 11).

    Deletes the dashboard, analysis, each dataset in `dataset_ids`, then the
    datasource, in that order. Each resource is deleted independently: a
    ResourceNotFoundException on any one resource is caught and recorded as
    'not_found' rather than aborting the rest of the teardown, so one
    missing resource doesn't leave the others orphaned.

    Args:
        account_id: AWS account ID
        quicksight_client: Optional boto3 QuickSight client (constructed if not provided)
        dashboard_id: Dashboard ID. Defaults to config.QUICKSIGHT_DASHBOARD_ID.
        analysis_id: Analysis ID. Defaults to config.QUICKSIGHT_ANALYSIS_ID.
        dataset_ids: Dataset IDs to delete. Defaults to ALL 5 dataset ID
            config constants if not passed.
        datasource_id: Data source ID. Defaults to config.QUICKSIGHT_DATASOURCE_ID.

    Returns:
        Dict with keys: 'deleted' (list), 'not_found' (list), 'errors'
        (dict mapping resource id -> error string).
    """
    resolved_dashboard_id = dashboard_id or QUICKSIGHT_DASHBOARD_ID
    resolved_analysis_id = analysis_id or QUICKSIGHT_ANALYSIS_ID
    resolved_dataset_ids = dataset_ids if dataset_ids is not None else [
        QUICKSIGHT_INFERENCE_DATASET_ID,
        QUICKSIGHT_DRIFT_DATASET_ID,
        QUICKSIGHT_FEATURE_DRIFT_DATASET_ID,
        QUICKSIGHT_FEATURE_LEVEL_DATASET_ID,
        QUICKSIGHT_ACCURACY_DATASET_ID,
    ]
    resolved_datasource_id = datasource_id or QUICKSIGHT_DATASOURCE_ID

    if quicksight_client is None:
        quicksight_client = boto3.client('quicksight', region_name=AWS_DEFAULT_REGION)

    deleted: List[str] = []
    not_found: List[str] = []
    errors: Dict[str, str] = {}

    resources_to_delete = [('dashboard', resolved_dashboard_id, 'DashboardId'),
                            ('analysis', resolved_analysis_id, 'AnalysisId')]
    resources_to_delete += [('data_set', ds_id, 'DataSetId') for ds_id in resolved_dataset_ids]
    resources_to_delete += [('data_source', resolved_datasource_id, 'DataSourceId')]

    for res_type, res_id, id_key in resources_to_delete:
        try:
            getattr(quicksight_client, f'delete_{res_type}')(AwsAccountId=account_id, **{id_key: res_id})
            logger.info(f"  ✓ Deleted {res_type}: {res_id}")
            deleted.append(res_id)
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                logger.info(f"  {res_type} {res_id} not found, nothing to delete")
                not_found.append(res_id)
            else:
                logger.warning(f"  ⚠ {res_type} {res_id}: {e}")
                errors[res_id] = str(e)

    logger.info("✓ Cleanup complete")
    return {'deleted': deleted, 'not_found': not_found, 'errors': errors}


# ---------------------------------------------------------------------------
# Top-level orchestrators
# ---------------------------------------------------------------------------


def create_dashboard(region: Optional[str] = None) -> Dict[str, Any]:
    """
    Build/refresh the full QuickSight governance dashboard.

    Top-level orchestrator wiring together every section of the notebook in
    order: resolve account -> subscription check -> Athena data check ->
    principals -> data source -> Lake Formation/S3 permissions -> inference
    dataset -> drift dataset -> feature drift dataset -> feature_drift_detail
    view (+ its Lake Formation grant) -> feature-level dataset -> accuracy
    dataset -> analysis -> dashboard -> (best-effort) embed URL.

    This is the entry point `lab5e-governance-dashboard.ipynb` calls.

    Args:
        region: AWS data-plane region (Athena/QuickSight asset region).
            Defaults to config.AWS_DEFAULT_REGION. The QuickSight identity
            region (for admin/user APIs) always comes from
            config.QUICKSIGHT_IDENTITY_REGION — the two are architecturally
            distinct and not both overridable via a single `region` param.

    Returns:
        Dict with keys: 'dashboard_url', 'dashboard_arn', 'analysis_arn',
        'datasource_arn', 'inference_dataset_arn', 'drift_dataset_arn',
        'feature_drift_dataset_arn', 'feature_level_dataset_arn',
        'accuracy_dataset_arn', 'athena_verification' (verify_athena_data()
        result dict), 'embed_url' (str or None), 'quicksight_subscribed'
        (bool), 'quicksight_edition' (str or None).
    """
    resolved_region = region or AWS_DEFAULT_REGION

    quicksight_admin_client = boto3.client('quicksight', region_name=QUICKSIGHT_IDENTITY_REGION)
    quicksight_client = boto3.client('quicksight', region_name=resolved_region)
    athena_client = boto3.client('athena', region_name=resolved_region)
    sts_client = boto3.client('sts', region_name=resolved_region)

    account_id = sts_client.get_caller_identity()['Account']
    logger.info(f"Account:                    {account_id}")
    logger.info(f"Data-plane region (Athena): {resolved_region}")
    logger.info(f"QuickSight identity region: {QUICKSIGHT_IDENTITY_REGION}")

    subscription = check_quicksight_subscription(
        account_id=account_id, quicksight_admin_client=quicksight_admin_client,
    )
    if not subscription['subscribed']:
        # Fail here, with the fix, rather than letting the next QuickSight call
        # (list_users) surface the same problem as a bare ClientError.
        if subscription.get('reason') == 'access-denied':
            raise QuickSightUnavailable(
                f"This role cannot call QuickSight in account {account_id} "
                f"(quicksight:DescribeAccountSettings denied). QuickSight itself may be "
                f"subscribed — the missing piece is IAM. Attach the quicksight:* actions "
                f"from templates/2-iam.yaml (QuickSightGovernanceDashboard statement) to the lab "
                f"execution role, then re-run this notebook."
            )
        raise QuickSightUnavailable(
            f"QuickSight is not subscribed for account {account_id}. Sign up once per "
            f"account at https://quicksight.aws.amazon.com/ (Enterprise edition — the "
            f"Definition API this notebook uses is not in Standard), invite this "
            f"identity as an Author/Admin, and give QuickSight access to S3 + Athena. "
            f"See the markdown cell above for the 5-minute walkthrough."
        )
    elif subscription['edition'] == 'STANDARD':
        logger.warning("Definition API requires Enterprise edition")

    data_check = verify_athena_data(athena_client=athena_client)
    if not data_check['has_drift_data']:
        logger.warning(
            "No drift monitoring data available yet — drift trend visuals "
            "will be empty until monitoring runs complete. Continuing with "
            "dashboard creation."
        )

    quicksight_principals = get_quicksight_principals(
        account_id=account_id, quicksight_admin_client=quicksight_admin_client,
    )

    datasource_arn = create_or_update_datasource(
        account_id=account_id,
        quicksight_principals=quicksight_principals,
        quicksight_client=quicksight_client,
    )

    grant_governance_permissions(region=resolved_region)

    inference_arn = create_inference_dataset(
        datasource_arn, account_id, quicksight_principals, quicksight_client=quicksight_client,
    )
    drift_arn = create_drift_dataset(
        datasource_arn, account_id, quicksight_principals, quicksight_client=quicksight_client,
    )
    feature_drift_arn = create_feature_drift_dataset(
        datasource_arn, account_id, quicksight_principals, quicksight_client=quicksight_client,
    )

    # feature_drift_detail view must exist before the feature-level dataset
    # references it.
    create_feature_drift_detail_view(athena_client=athena_client)
    grant_feature_drift_view_permissions(region=resolved_region)

    feature_level_arn = create_feature_level_dataset(
        datasource_arn, account_id, quicksight_principals, quicksight_client=quicksight_client,
    )
    accuracy_arn = create_accuracy_dataset(
        datasource_arn, account_id, quicksight_principals, quicksight_client=quicksight_client,
    )

    dataset_arns = {
        'inference': inference_arn,
        'drift': drift_arn,
        'feature_drift': feature_drift_arn,
        'feature_level': feature_level_arn,
        'accuracy': accuracy_arn,
    }

    analysis_arn = create_or_update_analysis(
        account_id, quicksight_principals, dataset_arns, quicksight_client=quicksight_client,
    )
    dashboard_result = publish_dashboard(
        account_id, quicksight_principals, dataset_arns,
        quicksight_client=quicksight_client, region=resolved_region,
    )

    embed_url = get_dashboard_embed_url(account_id=account_id, quicksight_client=quicksight_client)

    return {
        'dashboard_url': dashboard_result['dashboard_url'],
        'dashboard_arn': dashboard_result['dashboard_arn'],
        'analysis_arn': analysis_arn,
        'datasource_arn': datasource_arn,
        'inference_dataset_arn': inference_arn,
        'drift_dataset_arn': drift_arn,
        'feature_drift_dataset_arn': feature_drift_arn,
        'feature_level_dataset_arn': feature_level_arn,
        'accuracy_dataset_arn': accuracy_arn,
        'athena_verification': data_check,
        'embed_url': embed_url,
        'quicksight_subscribed': subscription['subscribed'],
        'quicksight_edition': subscription['edition'],
    }


def delete_dashboard(region: Optional[str] = None) -> Dict[str, Any]:
    """
    Delete the QuickSight governance dashboard and all its resources.

    This is the entry point `lab5e-governance-dashboard.ipynb`'s cleanup cell
    calls (guarded by CONFIRM_DELETE). Resolves the
    account ID and delegates to `delete_governance_resources()` with all
    default resource IDs.

    Args:
        region: AWS data-plane / asset region. Defaults to config.AWS_DEFAULT_REGION.

    Returns:
        The `delete_governance_resources()` result dict: keys 'deleted'
        (list), 'not_found' (list), 'errors' (dict).
    """
    resolved_region = region or AWS_DEFAULT_REGION

    quicksight_client = boto3.client('quicksight', region_name=resolved_region)
    sts_client = boto3.client('sts', region_name=resolved_region)
    account_id = sts_client.get_caller_identity()['Account']

    return delete_governance_resources(account_id=account_id, quicksight_client=quicksight_client)
