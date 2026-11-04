# Lab 5 monitoring

This package contains the importable implementation used by the SMAI standard
workshop's Lab 5 monitoring notebooks.

Lab 5D uses `src.drift_monitoring.monitoring_session.MonitoringSession` to:

1. generate configured drift traffic;
2. capture and tag one fresh endpoint-inference window;
3. apply simulated ground truth to that run;
4. calculate data and model drift; and
5. persist one monitoring row for MLflow, Athena, and the Lab 5E QuickSight dashboard.

Lab 5E uses `src.governance.create_governance_dashboard` to create or refresh the QuickSight governance assets. Before any asset write, it verifies the account's QuickSight service role and idempotently attaches only the two current-project managed policies created by `templates/2-iam.yaml`. It also adds newly discovered QuickSight users to existing assets without revoking other principals.

Install the package and notebook dependencies from this directory with:

```bash
python -m pip install -e .
```
