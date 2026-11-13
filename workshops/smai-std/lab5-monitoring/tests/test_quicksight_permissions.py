from __future__ import annotations

import ast
import copy
import sys
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
import yaml
from botocore.exceptions import ClientError


class _OfflineClient:
    def __getattr__(self, name):
        raise RuntimeError(f'AWS access is disabled during unit-test import: {name}')


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

with patch.object(boto3, 'client', return_value=_OfflineClient()):
    import src.governance.create_governance_dashboard as gov


ACCOUNT_ID = '111122223333'
PROJECT_NAME = 'test-project'
ROLE_NAME = 'aws-quicksight-service-role-v0'
ROLE_ARN = f'arn:aws:iam::{ACCOUNT_ID}:role/service-role/{ROLE_NAME}'
S3_POLICY_ARN = (
    f'arn:aws:iam::{ACCOUNT_ID}:policy/'
    f'{PROJECT_NAME}-QuickSightS3DataLakeAccess'
)
ATHENA_POLICY_ARN = (
    f'arn:aws:iam::{ACCOUNT_ID}:policy/'
    f'{PROJECT_NAME}-QuickSightAthenaAccess'
)
POLICY_ARNS = {S3_POLICY_ARN, ATHENA_POLICY_ARN}
USER_A = f'arn:aws:quicksight:us-east-1:{ACCOUNT_ID}:user/default/user-a'
USER_B = f'arn:aws:quicksight:us-east-1:{ACCOUNT_ID}:user/default/user-b'
UNRELATED_USER = f'arn:aws:quicksight:us-east-1:{ACCOUNT_ID}:user/default/other'


def _client_error(code: str, operation: str) -> ClientError:
    return ClientError(
        {'Error': {'Code': code, 'Message': f'{code} from fake client'}},
        operation,
    )


class FakeIamClient:
    def __init__(
        self,
        attachments=(),
        *,
        role_exists: bool = True,
        missing_policy_arn: str | None = None,
        policy_overrides: dict[str, dict] | None = None,
        visibility_lag: int = 0,
    ):
        self.attachments = set(attachments)
        self.role_exists = role_exists
        self.missing_policy_arn = missing_policy_arn
        self.policy_overrides = policy_overrides or {}
        self.visibility_lag = visibility_lag
        self.pending_attachments: set[str] = set()
        self.attach_calls: list[dict] = []
        self.list_calls = 0

    def get_role(self, RoleName):
        if not self.role_exists:
            raise _client_error('NoSuchEntity', 'GetRole')
        assert RoleName == ROLE_NAME
        return {'Role': {'RoleName': RoleName, 'Arn': ROLE_ARN}}

    def get_policy(self, PolicyArn):
        if PolicyArn == self.missing_policy_arn:
            raise _client_error('NoSuchEntity', 'GetPolicy')
        policy = {
            'Arn': PolicyArn,
            'PolicyName': PolicyArn.rsplit('/', 1)[-1],
            'Path': '/',
            'IsAttachable': True,
        }
        policy.update(self.policy_overrides.get(PolicyArn, {}))
        return {'Policy': policy}

    def list_attached_role_policies(self, RoleName, Marker=None):
        assert RoleName == ROLE_NAME
        assert Marker is None
        self.list_calls += 1
        if self.pending_attachments:
            if self.visibility_lag:
                self.visibility_lag -= 1
            else:
                self.attachments.update(self.pending_attachments)
                self.pending_attachments.clear()
        return {
            'AttachedPolicies': [
                {'PolicyName': arn.rsplit('/', 1)[-1], 'PolicyArn': arn}
                for arn in sorted(self.attachments)
            ],
            'IsTruncated': False,
        }

    def attach_role_policy(self, RoleName, PolicyArn):
        assert RoleName == ROLE_NAME
        self.attach_calls.append({'RoleName': RoleName, 'PolicyArn': PolicyArn})
        if self.visibility_lag:
            self.pending_attachments.add(PolicyArn)
        else:
            self.attachments.add(PolicyArn)


@pytest.mark.parametrize(
    ('initial', 'expected_attached'),
    [
        (set(), POLICY_ARNS),
        ({S3_POLICY_ARN}, {ATHENA_POLICY_ARN}),
        (POLICY_ARNS, set()),
    ],
)
def test_service_role_preflight_attaches_only_missing_project_policies(
    initial,
    expected_attached,
):
    client = FakeIamClient(initial)

    result = gov.ensure_quicksight_service_role_policies(
        account_id=ACCOUNT_ID,
        project_name=PROJECT_NAME,
        iam_client=client,
        retry_delay=0,
    )

    assert {call['PolicyArn'] for call in client.attach_calls} == expected_attached
    assert set(result['attached_now']) == expected_attached
    assert client.attachments == POLICY_ARNS


def test_service_role_preflight_is_no_op_when_repeated():
    client = FakeIamClient()

    first = gov.ensure_quicksight_service_role_policies(
        account_id=ACCOUNT_ID,
        project_name=PROJECT_NAME,
        iam_client=client,
        retry_delay=0,
    )
    second = gov.ensure_quicksight_service_role_policies(
        account_id=ACCOUNT_ID,
        project_name=PROJECT_NAME,
        iam_client=client,
        retry_delay=0,
    )

    assert set(first['attached_now']) == POLICY_ARNS
    assert second['attached_now'] == []
    assert len(client.attach_calls) == 2


@pytest.mark.parametrize(
    'overrides',
    [
        {S3_POLICY_ARN: {'Arn': S3_POLICY_ARN.replace(ACCOUNT_ID, '999900001111')}},
        {S3_POLICY_ARN: {'PolicyName': 'other-project-QuickSightS3DataLakeAccess'}},
    ],
)
def test_service_role_preflight_rejects_wrong_account_or_project_policy(overrides):
    client = FakeIamClient(policy_overrides=overrides)

    with pytest.raises(gov.QuickSightAccessPreflightError, match='Refusing to attach policy'):
        gov.ensure_quicksight_service_role_policies(
            account_id=ACCOUNT_ID,
            project_name=PROJECT_NAME,
            iam_client=client,
            retry_delay=0,
        )

    assert client.attach_calls == []


@pytest.mark.parametrize(
    ('client', 'message'),
    [
        (FakeIamClient(role_exists=False), 'service role.*does not exist'),
        (
            FakeIamClient(missing_policy_arn=ATHENA_POLICY_ARN),
            'Required project managed policy.*does not exist',
        ),
    ],
)
def test_service_role_preflight_fails_clearly_for_missing_prerequisites(client, message):
    with pytest.raises(gov.QuickSightAccessPreflightError, match=message):
        gov.ensure_quicksight_service_role_policies(
            account_id=ACCOUNT_ID,
            project_name=PROJECT_NAME,
            iam_client=client,
            retry_delay=0,
        )


def test_service_role_preflight_retries_attachment_visibility():
    client = FakeIamClient(visibility_lag=2)

    result = gov.ensure_quicksight_service_role_policies(
        account_id=ACCOUNT_ID,
        project_name=PROJECT_NAME,
        iam_client=client,
        max_attempts=4,
        retry_delay=0,
    )

    assert set(result['attached_now']) == POLICY_ARNS
    assert client.attachments == POLICY_ARNS
    assert client.list_calls == 4


def test_principal_discovery_paginates_all_users():
    class PagedQuickSightClient:
        def list_users(self, **kwargs):
            if 'NextToken' not in kwargs:
                return {'UserList': [{'Arn': USER_A}], 'NextToken': 'page-2'}
            assert kwargs['NextToken'] == 'page-2'
            return {'UserList': [{'Arn': USER_B}]}

    assert gov.get_quicksight_principals(
        account_id=ACCOUNT_ID,
        quicksight_admin_client=PagedQuickSightClient(),
        identity_region=gov.AWS_DEFAULT_REGION,
    ) == [USER_A, USER_B]


def test_principal_discovery_fails_closed_without_wildcard():
    class EmptyQuickSightClient:
        def list_users(self, **kwargs):
            return {'UserList': []}

    with pytest.raises(gov.QuickSightUnavailable, match='No QuickSight users'):
        gov.get_quicksight_principals(
            account_id=ACCOUNT_ID,
            quicksight_admin_client=EmptyQuickSightClient(),
            identity_region=gov.AWS_DEFAULT_REGION,
        )


class FakePermissionClient:
    def __init__(
        self,
        resource_type: str,
        permissions: list[dict],
        *,
        describe_failures: int = 0,
        visibility_lag: int = 0,
    ):
        self.resource_type = resource_type
        self.permissions = copy.deepcopy(permissions)
        self.describe_failures = describe_failures
        self.visibility_lag = visibility_lag
        self.pending_grants: list[dict] = []
        self.describe_calls = 0
        self.update_calls: list[dict] = []

    def _describe_permissions(self, resource_type: str):
        assert resource_type == self.resource_type
        self.describe_calls += 1
        if self.describe_failures:
            self.describe_failures -= 1
            raise _client_error('ResourceNotFoundException', 'DescribePermissions')
        if self.pending_grants:
            if self.visibility_lag:
                self.visibility_lag -= 1
            else:
                self._apply_grants(self.pending_grants)
                self.pending_grants = []
        return {'Permissions': copy.deepcopy(self.permissions)}

    def _update_permissions(self, resource_type: str, kwargs: dict):
        assert resource_type == self.resource_type
        assert 'RevokePermissions' not in kwargs
        self.update_calls.append(copy.deepcopy(kwargs))
        grants = copy.deepcopy(kwargs['GrantPermissions'])
        if self.visibility_lag:
            self.pending_grants = grants
        else:
            self._apply_grants(grants)
        return {'Status': 200}

    def _apply_grants(self, grants: list[dict]):
        by_principal = {item['Principal']: item for item in self.permissions}
        for grant in grants:
            by_principal[grant['Principal']] = copy.deepcopy(grant)
        self.permissions = list(by_principal.values())

    def describe_data_source_permissions(self, **kwargs):
        return self._describe_permissions('data_source')

    def update_data_source_permissions(self, **kwargs):
        return self._update_permissions('data_source', kwargs)

    def describe_data_set_permissions(self, **kwargs):
        return self._describe_permissions('data_set')

    def update_data_set_permissions(self, **kwargs):
        return self._update_permissions('data_set', kwargs)

    def describe_analysis_permissions(self, **kwargs):
        return self._describe_permissions('analysis')

    def update_analysis_permissions(self, **kwargs):
        return self._update_permissions('analysis', kwargs)

    def describe_dashboard_permissions(self, **kwargs):
        return self._describe_permissions('dashboard')

    def update_dashboard_permissions(self, **kwargs):
        return self._update_permissions('dashboard', kwargs)


@pytest.mark.parametrize(
    ('resource_type', 'actions'),
    [
        ('data_source', gov._DATASOURCE_ACTIONS),
        ('data_set', gov._DATASET_ACTIONS),
        ('analysis', gov._ANALYSIS_ACTIONS),
        ('dashboard', gov._DASHBOARD_ACTIONS),
    ],
)
def test_resource_permission_reconciliation_adds_users_without_revocation(
    resource_type,
    actions,
):
    unrelated_actions = ['quicksight:DescribeDashboard']
    client = FakePermissionClient(
        resource_type,
        [
            {'Principal': USER_A, 'Actions': actions},
            {'Principal': UNRELATED_USER, 'Actions': unrelated_actions},
        ],
    )

    result = gov.ensure_quicksight_resource_permissions(
        account_id=ACCOUNT_ID,
        resource_type=resource_type,
        resource_id='resource-id',
        quicksight_principals=[USER_A, USER_B, USER_B],
        quicksight_client=client,
        retry_delay=0,
    )

    assert result['granted_principals'] == [USER_B]
    assert len(client.update_calls) == 1
    assert client.update_calls[0]['GrantPermissions'] == [
        {'Principal': USER_B, 'Actions': actions}
    ]
    unrelated = next(
        item for item in client.permissions if item['Principal'] == UNRELATED_USER
    )
    assert unrelated['Actions'] == unrelated_actions


def test_resource_permission_reconciliation_retries_eventual_consistency():
    client = FakePermissionClient(
        'analysis',
        [],
        describe_failures=1,
        visibility_lag=2,
    )

    result = gov.ensure_quicksight_resource_permissions(
        account_id=ACCOUNT_ID,
        resource_type='analysis',
        resource_id='analysis-id',
        quicksight_principals=[USER_A, USER_B],
        quicksight_client=client,
        max_attempts=6,
        retry_delay=0,
    )

    assert result['granted_principals'] == [USER_A, USER_B]
    assert client.describe_calls == 5
    assert len(client.update_calls) == 1


class FakeDataSourceClient(FakePermissionClient):
    def __init__(self):
        super().__init__('data_source', [])
        self.exists = False
        self.create_calls: list[dict] = []

    def describe_data_source(self, **kwargs):
        if not self.exists:
            raise _client_error('ResourceNotFoundException', 'DescribeDataSource')
        return {'DataSource': {'Arn': 'arn:fake:data-source'}}

    def create_data_source(self, **kwargs):
        self.exists = True
        self.create_calls.append(copy.deepcopy(kwargs))
        # Simulate a newly discovered second user not appearing in the create grant.
        self.permissions = copy.deepcopy(kwargs['Permissions'][:1])
        return {'Arn': 'arn:fake:data-source'}


class FakeDataSetClient(FakePermissionClient):
    def __init__(self):
        super().__init__(
            'data_set',
            [
                {'Principal': USER_A, 'Actions': gov._DATASET_ACTIONS},
                {'Principal': UNRELATED_USER, 'Actions': ['quicksight:DescribeDataSet']},
            ],
        )
        self.update_data_set_calls: list[dict] = []

    def describe_data_set(self, **kwargs):
        return {'DataSet': {'Arn': 'arn:fake:data-set'}}

    def update_data_set(self, **kwargs):
        self.update_data_set_calls.append(copy.deepcopy(kwargs))
        return {'Arn': 'arn:fake:data-set'}



def test_create_path_reconciles_permissions_after_data_source_creation(monkeypatch):
    monkeypatch.setattr(gov.time, 'sleep', lambda _: None)
    client = FakeDataSourceClient()

    arn = gov.create_or_update_datasource(
        account_id=ACCOUNT_ID,
        quicksight_principals=[USER_A, USER_B],
        quicksight_client=client,
        datasource_id='data-source-id',
    )

    assert arn == 'arn:fake:data-source'
    assert len(client.create_calls) == 1
    assert client.update_calls[0]['GrantPermissions'] == [
        {'Principal': USER_B, 'Actions': gov._DATASOURCE_ACTIONS}
    ]


def test_existing_dataset_update_reconciles_permissions_and_preserves_others(monkeypatch):
    monkeypatch.setattr(gov.time, 'sleep', lambda _: None)
    client = FakeDataSetClient()

    arn = gov.create_inference_dataset(
        datasource_arn='arn:fake:data-source',
        account_id=ACCOUNT_ID,
        quicksight_principals=[USER_A, USER_B],
        quicksight_client=client,
        dataset_id='data-set-id',
    )

    assert arn == 'arn:fake:data-set'
    assert len(client.update_data_set_calls) == 1
    assert client.update_calls[0]['GrantPermissions'] == [
        {'Principal': USER_B, 'Actions': gov._DATASET_ACTIONS}
    ]
    assert any(
        item['Principal'] == UNRELATED_USER for item in client.permissions
    )


def _record(monkeypatch, events: list[str], name: str, result=None, error=None):
    def recorder(*args, **kwargs):
        events.append(name)
        if error:
            raise error
        return result

    monkeypatch.setattr(gov, name, recorder)


class _StsClient:
    def get_caller_identity(self):
        return {'Account': ACCOUNT_ID}


class _UnusedClient:
    pass


def _stub_dashboard_dependencies(monkeypatch, events, *, view_error=None, run_as_role=None):
    monkeypatch.setattr(
        gov.boto3,
        'client',
        lambda service, **kwargs: _StsClient() if service == 'sts' else _UnusedClient(),
    )
    _record(
        monkeypatch,
        events,
        'check_quicksight_subscription',
        {'subscribed': True, 'edition': 'ENTERPRISE', 'reason': None},
    )
    _record(monkeypatch, events, 'resolve_datasource_role', run_as_role)
    _record(
        monkeypatch,
        events,
        'ensure_quicksight_service_role_policies',
        {'attached_now': []},
    )
    _record(monkeypatch, events, 'grant_datasource_role_lake_formation', {'lake_formation_managed': False})
    _record(
        monkeypatch,
        events,
        'verify_athena_data',
        {'has_drift_data': True},
    )
    _record(monkeypatch, events, 'get_quicksight_principals', [USER_A, USER_B])
    _record(monkeypatch, events, 'create_or_update_datasource', 'arn:datasource')
    _record(monkeypatch, events, 'grant_governance_permissions', {'lake_formation': 'done'})
    _record(
        monkeypatch,
        events,
        'create_feature_drift_detail_view',
        {'total_rows': 1},
        view_error,
    )
    _record(monkeypatch, events, 'grant_feature_drift_view_permissions', {'granted': True})
    _record(monkeypatch, events, 'create_inference_dataset', 'arn:inference')
    _record(monkeypatch, events, 'create_drift_dataset', 'arn:drift')
    _record(monkeypatch, events, 'create_feature_drift_dataset', 'arn:feature-drift')
    _record(monkeypatch, events, 'create_feature_level_dataset', 'arn:feature-level')
    _record(monkeypatch, events, 'create_accuracy_dataset', 'arn:accuracy')
    _record(monkeypatch, events, 'create_or_update_analysis', 'arn:analysis')
    _record(
        monkeypatch,
        events,
        'publish_dashboard',
        {
            'dashboard_url': 'https://example.invalid/dashboard',
            'dashboard_arn': 'arn:dashboard',
            'version': '1',
        },
    )
    _record(monkeypatch, events, 'get_dashboard_embed_url', None)


def test_dashboard_operation_order_runs_preflight_and_verified_view_first(monkeypatch):
    events: list[str] = []
    _stub_dashboard_dependencies(monkeypatch, events)

    gov.create_dashboard(region='us-east-1')

    assert events == [
        'check_quicksight_subscription',
        'resolve_datasource_role',
        'ensure_quicksight_service_role_policies',
        'verify_athena_data',
        'get_quicksight_principals',
        'create_or_update_datasource',
        'grant_governance_permissions',
        'create_feature_drift_detail_view',
        'grant_feature_drift_view_permissions',
        'create_inference_dataset',
        'create_drift_dataset',
        'create_feature_drift_dataset',
        'create_feature_level_dataset',
        'create_accuracy_dataset',
        'create_or_update_analysis',
        'publish_dashboard',
        'get_dashboard_embed_url',
    ]


def test_missing_view_fails_before_any_dataset_creation(monkeypatch):
    events: list[str] = []
    _stub_dashboard_dependencies(
        monkeypatch,
        events,
        view_error=RuntimeError('view verification failed'),
    )

    with pytest.raises(RuntimeError, match='view verification failed'):
        gov.create_dashboard(region='us-east-1')

    assert 'create_inference_dataset' not in events
    assert 'create_feature_level_dataset' not in events
    assert events[-1] == 'create_feature_drift_detail_view'


def test_feature_view_uses_configured_table_and_tolerates_malformed_json(monkeypatch):
    queries: list[str] = []

    def fake_query(sql, *args, **kwargs):
        queries.append(sql)
        return {'ResultSet': {'Rows': [{'Data': []}]}}

    monkeypatch.setattr(gov, '_run_athena_query', fake_query)

    gov.create_feature_drift_detail_view(
        database='db_name',
        monitoring_table='fresh_monitoring_rows',
        athena_client=object(),
        output_s3='s3://example/results/',
    )

    assert len(queries) == 2
    assert 'FROM db_name.fresh_monitoring_rows' in queries[0]
    assert 'TRY(CAST(json_parse(per_feature_drift_scores)' in queries[0]
    assert 'FROM db_name.feature_drift_detail' in queries[1]


class CloudFormationLoader(yaml.SafeLoader):
    pass


def _construct_tag(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    return {f'!{tag_suffix}': value}


CloudFormationLoader.add_multi_constructor('!', _construct_tag)


def _find_statement(value, sid):
    if isinstance(value, dict):
        if value.get('Sid') == sid:
            return value
        for child in value.values():
            found = _find_statement(child, sid)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_statement(child, sid)
            if found:
                return found
    return None


def test_iam_template_has_exact_reconciliation_scope_and_managed_policies():
    template_path = Path(__file__).resolve().parents[2] / 'templates' / '2-iam.yaml'
    template = yaml.load(template_path.read_text(), Loader=CloudFormationLoader)
    resources = template['Resources']

    for logical_id, suffix in (
        ('QuickSightServiceRoleS3Policy', 'QuickSightS3DataLakeAccess'),
        ('QuickSightServiceRoleAthenaPolicy', 'QuickSightAthenaAccess'),
    ):
        policy = resources[logical_id]
        assert policy['Type'] == 'AWS::IAM::ManagedPolicy'
        assert 'Condition' not in policy
        assert policy['Properties']['ManagedPolicyName'] == {
            '!Sub': f'${{ProjectName}}-{suffix}'
        }
        assert policy['Properties']['Roles'] == {
            '!If': [
                'ShouldAttachQuickSightServiceRolePolicy',
                ['aws-quicksight-service-role-v0'],
                {'!Ref': 'AWS::NoValue'},
            ]
        }

    s3_policy = resources['QuickSightServiceRoleS3Policy']['Properties']['PolicyDocument']
    source_bucket = _find_statement(s3_policy, 'ReadProjectDataBucket')
    assert set(source_bucket['Action']) == {
        's3:GetObject', 's3:ListBucket', 's3:GetBucketLocation'
    }
    assert {item['!Sub'] for item in source_bucket['Resource']} == {
        'arn:${AWS::Partition}:s3:::${ProjectName}-data-${AWS::AccountId}-${AWS::Region}',
        'arn:${AWS::Partition}:s3:::${ProjectName}-data-${AWS::AccountId}-${AWS::Region}/*',
    }
    results_bucket = _find_statement(s3_policy, 'AthenaQueryResults')
    assert {item['!Sub'] for item in results_bucket['Resource']} == {
        'arn:${AWS::Partition}:s3:::aws-athena-query-results-${AWS::Region}-${AWS::AccountId}',
        'arn:${AWS::Partition}:s3:::aws-athena-query-results-${AWS::Region}-${AWS::AccountId}/*',
    }

    role_arn = (
        'arn:${AWS::Partition}:iam::${AWS::AccountId}:'
        'role/service-role/aws-quicksight-service-role-v0'
    )
    policy_arns = {
        'arn:${AWS::Partition}:iam::${AWS::AccountId}:'
        'policy/${ProjectName}-QuickSightS3DataLakeAccess',
        'arn:${AWS::Partition}:iam::${AWS::AccountId}:'
        'policy/${ProjectName}-QuickSightAthenaAccess',
    }

    inspect = _find_statement(template, 'QuickSightServiceRoleInspect')
    assert set(inspect['Action']) == {'iam:GetRole', 'iam:ListAttachedRolePolicies'}
    assert inspect['Resource'] == [{'!Sub': role_arn}]

    policy_inspect = _find_statement(template, 'QuickSightProjectPolicyInspect')
    assert policy_inspect['Action'] == ['iam:GetPolicy']
    assert {item['!Sub'] for item in policy_inspect['Resource']} == policy_arns

    attach = _find_statement(template, 'QuickSightProjectPolicyAttach')
    assert attach['Action'] == ['iam:AttachRolePolicy']
    # AttachRolePolicy authorizes against the role only; the iam:PolicyARN
    # condition is what limits which policies can be attached.
    assert {item['!Sub'] for item in attach['Resource']} == {role_arn}
    assert {
        item['!Sub'] for item in attach['Condition']['ArnEquals']['iam:PolicyARN']
    } == policy_arns

    quicksight_policy = resources['CloudWatchLogsPolicy']['Properties']['PolicyDocument']
    quicksight_statements = {
        statement['Sid']: statement
        for statement in quicksight_policy['Statement']
        if any(
            action.startswith('quicksight:')
            for action in statement['Action']
        )
    }
    assert set(quicksight_statements) == {
        'QuickSightGovernanceAccountSettings',
        'QuickSightGovernanceUserDiscovery',
        'QuickSightGovernanceDataSourceCreate',
        'QuickSightGovernanceDataSource',
        'QuickSightGovernanceDataSetCreate',
        'QuickSightGovernanceDataSetUpdate',
        'QuickSightGovernanceDataSets',
        'QuickSightGovernanceAnalysis',
        'QuickSightGovernanceDashboard',
    }

    def assert_statement(sid, actions, resources):
        statement = quicksight_statements[sid]
        assert set(statement['Action']) == set(actions)
        assert statement['Resource'] == resources

    datasource_arn = {
        '!Sub': (
            'arn:${AWS::Partition}:quicksight:${AWS::Region}:${AWS::AccountId}:'
            'datasource/bank-marketing-governance-athena-datasource'
        )
    }
    dataset_arns = [
        {
            '!Sub': (
                'arn:${AWS::Partition}:quicksight:${AWS::Region}:${AWS::AccountId}:'
                f'dataset/{dataset_id}'
            )
        }
        for dataset_id in (
            'bank-marketing-governance-inference-dataset',
            'bank-marketing-governance-drift-dataset',
            'bank-marketing-governance-feature-drift-dataset',
            'bank-marketing-governance-feature-level-dataset',
            'bank-marketing-governance-inference-dataset-accuracy',
        )
    ]
    analysis_arn = {
        '!Sub': (
            'arn:${AWS::Partition}:quicksight:${AWS::Region}:${AWS::AccountId}:'
            'analysis/bank-marketing-governance-analysis'
        )
    }
    dashboard_arn = {
        '!Sub': (
            'arn:${AWS::Partition}:quicksight:${AWS::Region}:${AWS::AccountId}:'
            'dashboard/bank-marketing-governance-dashboard'
        )
    }

    assert_statement(
        'QuickSightGovernanceAccountSettings',
        ['quicksight:DescribeAccountSettings'],
        '*',
    )
    assert_statement(
        'QuickSightGovernanceUserDiscovery',
        ['quicksight:ListUsers'],
        [{
            '!Sub': (
                'arn:${AWS::Partition}:quicksight:*:${AWS::AccountId}:'
                'user/default/*'
            )
        }],
    )
    assert_statement(
        'QuickSightGovernanceDataSourceCreate',
        ['quicksight:CreateDataSource'],
        '*',
    )
    assert_statement(
        'QuickSightGovernanceDataSource',
        [
            'quicksight:DescribeDataSource',
            'quicksight:UpdateDataSource',
            'quicksight:DeleteDataSource',
            'quicksight:PassDataSource',
            'quicksight:DescribeDataSourcePermissions',
            'quicksight:UpdateDataSourcePermissions',
        ],
        [datasource_arn],
    )
    assert_statement(
        'QuickSightGovernanceDataSetCreate',
        ['quicksight:CreateDataSet'],
        [datasource_arn],
    )
    assert_statement(
        'QuickSightGovernanceDataSetUpdate',
        ['quicksight:UpdateDataSet'],
        [datasource_arn, *dataset_arns],
    )
    assert_statement(
        'QuickSightGovernanceDataSets',
        [
            'quicksight:DescribeDataSet',
            'quicksight:DeleteDataSet',
            'quicksight:PassDataSet',
            'quicksight:DescribeDataSetPermissions',
            'quicksight:UpdateDataSetPermissions',
        ],
        dataset_arns,
    )
    assert_statement(
        'QuickSightGovernanceAnalysis',
        [
            'quicksight:CreateAnalysis',
            'quicksight:DescribeAnalysis',
            'quicksight:UpdateAnalysis',
            'quicksight:DeleteAnalysis',
            'quicksight:DescribeAnalysisPermissions',
            'quicksight:UpdateAnalysisPermissions',
        ],
        [analysis_arn],
    )
    dashboard_actions = {
        'quicksight:CreateDashboard',
        'quicksight:DescribeDashboard',
        'quicksight:UpdateDashboard',
        'quicksight:UpdateDashboardPublishedVersion',
        'quicksight:DeleteDashboard',
        'quicksight:GetDashboardEmbedUrl',
        'quicksight:DescribeDashboardPermissions',
        'quicksight:UpdateDashboardPermissions',
    }
    assert_statement(
        'QuickSightGovernanceDashboard',
        dashboard_actions,
        [dashboard_arn],
    )

    wildcard_statements = [
        statement
        for statement in quicksight_statements.values()
        if statement['Resource'] == '*'
    ]
    assert {
        tuple(statement['Action'])
        for statement in wildcard_statements
    } == {
        ('quicksight:DescribeAccountSettings',),
        ('quicksight:CreateDataSource',),
    }
    assert all(
        'quicksight:UpdateDashboardPermissions' not in statement['Action']
        and 'quicksight:DescribeDashboardPermissions' not in statement['Action']
        for statement in wildcard_statements
    )

    assert template['Outputs']['QuickSightS3DataLakeAccessPolicyArn']['Value'] == {
        '!Ref': 'QuickSightServiceRoleS3Policy'
    }
    assert template['Outputs']['QuickSightAthenaAccessPolicyArn']['Value'] == {
        '!Ref': 'QuickSightServiceRoleAthenaPolicy'
    }


def test_quicksight_runtime_calls_are_covered_by_iam_template():
    template_path = Path(__file__).resolve().parents[2] / 'templates' / '2-iam.yaml'
    template = yaml.load(template_path.read_text(), Loader=CloudFormationLoader)
    policy = template['Resources']['CloudWatchLogsPolicy']['Properties']['PolicyDocument']
    policy_actions = {
        action
        for statement in policy['Statement']
        for action in statement['Action']
        if action.startswith('quicksight:')
    }

    source_path = PACKAGE_ROOT / 'src' / 'governance' / 'create_governance_dashboard.py'
    source_tree = ast.parse(source_path.read_text())
    method_names = {
        node.func.attr
        for node in ast.walk(source_tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in {'quicksight_client', 'quicksight_admin_client'}
    }
    method_names.add('list_users')
    for describe_method, update_method, _, _ in gov._PERMISSION_APIS.values():
        method_names.update((describe_method, update_method))
    method_names.update(
        {'delete_dashboard', 'delete_analysis', 'delete_data_set', 'delete_data_source'}
    )

    runtime_actions = {
        f"quicksight:{''.join(part.title() for part in method.split('_'))}"
        for method in method_names
    }
    assert runtime_actions <= policy_actions


class FailingDataSourceClient(FakeDataSourceClient):
    def __init__(self, message):
        super().__init__()
        self.message = message
        self.deleted = False
        self.polls = 0

    def describe_data_source(self, **kwargs):
        if not self.exists:
            raise _client_error('ResourceNotFoundException', 'DescribeDataSource')
        self.polls += 1
        if self.polls == 1:
            return {'DataSource': {'Arn': 'arn:fake:data-source', 'Status': 'CREATION_IN_PROGRESS'}}
        return {'DataSource': {
            'Arn': 'arn:fake:data-source', 'Status': 'CREATION_FAILED',
            'ErrorInfo': {'Type': 'GENERIC_SQL_FAILURE', 'Message': self.message},
        }}

    def delete_data_source(self, **kwargs):
        self.deleted = True
        self.exists = False


def test_failed_data_source_without_service_access_stops_with_console_fix(monkeypatch):
    monkeypatch.setattr(gov.time, 'sleep', lambda _: None)
    client = FailingDataSourceClient(
        'The QuickSight service role required to access your AWS resources has not been created yet.'
    )
    with pytest.raises(gov.QuickSightUnavailable, match='QuickSight access to AWS services'):
        gov.create_or_update_datasource(
            account_id=ACCOUNT_ID, quicksight_principals=[USER_A],
            quicksight_client=client, datasource_id='data-source-id',
        )
    assert client.deleted, 'failed creation must be deleted so the next run recreates it'
    assert client.update_calls == [], 'permissions must not be reconciled on a failed source'


def test_failed_data_source_other_errors_are_reported(monkeypatch):
    monkeypatch.setattr(gov.time, 'sleep', lambda _: None)
    client = FailingDataSourceClient('Workgroup primary is not found')
    with pytest.raises(gov.QuickSightUnavailable, match='Workgroup primary is not found'):
        gov.create_or_update_datasource(
            account_id=ACCOUNT_ID, quicksight_principals=[USER_A],
            quicksight_client=client, datasource_id='data-source-id',
        )


RUN_AS_ROLE_ARN = f'arn:aws:iam::{ACCOUNT_ID}:role/test-project-qs-datasource-role'


def test_run_as_role_skips_service_role_preflight_and_grants_before_use(monkeypatch):
    events: list[str] = []
    _stub_dashboard_dependencies(monkeypatch, events, run_as_role=RUN_AS_ROLE_ARN)
    datasource_kwargs = {}

    def record_datasource(*args, **kwargs):
        events.append('create_or_update_datasource')
        datasource_kwargs.update(kwargs)
        return 'arn:datasource'

    monkeypatch.setattr(gov, 'create_or_update_datasource', record_datasource)

    result = gov.create_dashboard(region='us-east-1')

    assert 'ensure_quicksight_service_role_policies' not in events
    assert datasource_kwargs['role_arn'] == RUN_AS_ROLE_ARN
    assert result['quicksight_service_role_permissions'] == {
        'mode': 'run-as-role', 'role_arn': RUN_AS_ROLE_ARN, 'attached_now': [],
    }
    grants = [i for i, e in enumerate(events) if e == 'grant_datasource_role_lake_formation']
    assert len(grants) == 2
    assert grants[0] < events.index('create_or_update_datasource')
    assert events.index('create_feature_drift_detail_view') < grants[1] < events.index('create_inference_dataset')


class _RoleIam:
    def __init__(self, error=None, trust_service='quicksight.amazonaws.com'):
        self.error, self.trust_service = error, trust_service

    def get_role(self, RoleName):
        if self.error:
            raise _client_error(self.error, 'GetRole')
        return {'Role': {'Arn': RUN_AS_ROLE_ARN, 'AssumeRolePolicyDocument': {
            'Statement': [{'Effect': 'Allow', 'Principal': {'Service': self.trust_service},
                           'Action': 'sts:AssumeRole'}]}}}


def test_resolve_datasource_role_returns_arn_or_falls_back():
    assert gov.resolve_datasource_role(iam_client=_RoleIam()) == RUN_AS_ROLE_ARN
    # Older stacks: the role does not exist, or the execution role cannot read it.
    assert gov.resolve_datasource_role(iam_client=_RoleIam('NoSuchEntity')) is None
    assert gov.resolve_datasource_role(iam_client=_RoleIam('AccessDenied')) is None
    with pytest.raises(gov.QuickSightAccessPreflightError, match='does not trust'):
        gov.resolve_datasource_role(iam_client=_RoleIam(trust_service='lambda.amazonaws.com'))


def test_datasource_uses_role_and_project_workgroup_only_with_run_as_role(monkeypatch):
    monkeypatch.setattr(gov.time, 'sleep', lambda _: None)
    with_role = FakeDataSourceClient()
    gov.create_or_update_datasource(
        account_id=ACCOUNT_ID, quicksight_principals=[USER_A],
        quicksight_client=with_role, datasource_id='data-source-id', role_arn=RUN_AS_ROLE_ARN,
    )
    params = with_role.create_calls[0]['DataSourceParameters']['AthenaParameters']
    assert params == {'WorkGroup': gov.QUICKSIGHT_DATASOURCE_WORKGROUP, 'RoleArn': RUN_AS_ROLE_ARN}

    without_role = FakeDataSourceClient()
    gov.create_or_update_datasource(
        account_id=ACCOUNT_ID, quicksight_principals=[USER_A],
        quicksight_client=without_role, datasource_id='data-source-id',
    )
    assert without_role.create_calls[0]['DataSourceParameters']['AthenaParameters'] == {'WorkGroup': 'primary'}


def test_run_as_role_failure_does_not_print_console_fix(monkeypatch):
    monkeypatch.setattr(gov.time, 'sleep', lambda _: None)
    client = FailingDataSourceClient('Unable to assume role')
    with pytest.raises(gov.QuickSightUnavailable, match='run-as role') as exc:
        gov.create_or_update_datasource(
            account_id=ACCOUNT_ID, quicksight_principals=[USER_A],
            quicksight_client=client, datasource_id='data-source-id', role_arn=RUN_AS_ROLE_ARN,
        )
    assert 'Security & permissions' not in str(exc.value)


class _LakeFormation:
    def __init__(self, managed):
        self.managed, self.grants = managed, []

    def get_data_lake_settings(self):
        defaults = [] if self.managed else [{'Principal': {'DataLakePrincipalIdentifier': 'IAM_ALLOWED_PRINCIPALS'}}]
        return {'DataLakeSettings': {'CreateDatabaseDefaultPermissions': defaults}}

    def grant_permissions(self, **kwargs):
        self.grants.append(kwargs)


def test_lake_formation_grants_only_in_managed_mode():
    iam_mode = _LakeFormation(managed=False)
    assert gov.grant_datasource_role_lake_formation(RUN_AS_ROLE_ARN, lf_client=iam_mode)['lake_formation_managed'] is False
    assert iam_mode.grants == []

    managed = _LakeFormation(managed=True)
    gov.grant_datasource_role_lake_formation(RUN_AS_ROLE_ARN, database='db', lf_client=managed)
    granted = {(g['Resource']['Table']['Name'], g['Permissions'][0]) for g in managed.grants}
    assert granted == {
        (t, p)
        for t in (gov.ATHENA_INFERENCE_TABLE, gov.ATHENA_MONITORING_RESPONSES_TABLE, gov.ATHENA_GROUND_TRUTH_UPDATES_TABLE)
        for p in ('SELECT', 'DESCRIBE')
    }
    assert all(g['Principal']['DataLakePrincipalIdentifier'] == RUN_AS_ROLE_ARN for g in managed.grants)


def _iam_statements(template_path):
    template = yaml.load(template_path.read_text(), Loader=CloudFormationLoader)
    return template


@pytest.mark.parametrize('template_path', [
    Path(__file__).resolve().parents[2] / 'templates' / '2-iam.yaml',
])
def test_template_declares_scoped_run_as_role(template_path):
    template = _iam_statements(template_path)
    role = template['Resources']['QuickSightDataSourceRole']['Properties']
    assert role['RoleName'] == {'!Sub': '${ProjectName}-qs-datasource-role'}
    trust = role['AssumeRolePolicyDocument']['Statement']
    assert trust == [{'Effect': 'Allow', 'Principal': {'Service': 'quicksight.amazonaws.com'},
                      'Action': 'sts:AssumeRole'}]
    assert role['ManagedPolicyArns'] == [
        {'!Ref': 'QuickSightServiceRoleS3Policy'}, {'!Ref': 'QuickSightServiceRoleAthenaPolicy'},
    ]
    role_arn = 'arn:${AWS::Partition}:iam::${AWS::AccountId}:role/${ProjectName}-qs-datasource-role'
    passrole = _find_statement(template, 'QuickSightDataSourceRolePass')
    assert passrole['Action'] == ['iam:PassRole']
    assert passrole['Resource'] == [{'!Sub': role_arn}]
    assert passrole['Condition'] == {'StringEquals': {'iam:PassedToService': 'quicksight.amazonaws.com'}}
    inspect = _find_statement(template, 'QuickSightDataSourceRoleInspect')
    assert inspect['Action'] == ['iam:GetRole'] and inspect['Resource'] == [{'!Sub': role_arn}]
    results = _find_statement(template, 'ProjectWorkgroupResults')
    assert 'athena-results/*' in results['Resource'][0]['!Sub']
    assert gov.QUICKSIGHT_DATASOURCE_ROLE_NAME.endswith('-qs-datasource-role')


def test_every_kpi_shows_actual_value_not_comparison():
    # Without explicit options, a KPI with a DAY trend group and 2+ days of
    # runs shows the comparison as its primary value -> "Cannot compare values".
    visuals = gov._build_all_visuals()
    kpis = [v['KPIVisual'] for sheet in visuals.values() for v in sheet if 'KPIVisual' in v]
    assert {k['VisualId'] for k in kpis} == {'m8-latest-auc', 'd7-latest-share', 'f6-highest-score'}
    for kpi in kpis:
        options = kpi['ChartConfiguration']['KPIOptions']
        assert options['PrimaryValueDisplayType'] == 'ACTUAL'
        assert options['Comparison']['ComparisonMethod'] == 'DIFFERENCE'
