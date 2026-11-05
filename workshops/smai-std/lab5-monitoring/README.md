# Lab 5 monitoring

This package contains the importable implementation used by the SMAI standard
workshop's Lab 5 monitoring notebooks.

Lab 5D uses `src.drift_monitoring.monitoring_session.MonitoringSession` to:

1. generate configured drift traffic;
2. capture and tag one fresh endpoint-inference window;
3. apply simulated ground truth to that run;
4. calculate data and model drift; and
5. persist one monitoring row for MLflow, Athena, and the Lab 5E QuickSight dashboard.

### Monitoring-run membership

Each Lab 5D run covers all endpoint traffic since the previous run. Closing
capture tags every `inference_responses` row for the endpoint that has no
`monitoring_run_id` and a `request_timestamp` between the lookback start and an
Athena-timed cutoff. Rows that land after the cutoff stay untagged for the next
run, so each row belongs to exactly one run. The rows the notebook sends only
decide how long closing waits for asynchronous captures; they do not decide
membership.

The lookback defaults to 24 hours so a first run does not sweep the whole table
history. Configure it with `monitoring_capture.lookback_hours` in
`src/config/config.yaml` or override it with
`MONITORING_CAPTURE_LOOKBACK_HOURS`. If fewer than 300 rows qualify, nothing is
tagged and closing can be retried.

Lab 5E uses `src.governance.create_governance_dashboard` to create or refresh the QuickSight governance assets. Before any asset write, it verifies the account's QuickSight service role and idempotently attaches only the two current-project managed policies created by `templates/2-iam.yaml`. It also adds newly discovered QuickSight users to existing assets without revoking other principals.

Install the package and notebook dependencies from this directory with:

```bash
python -m pip install -e .
```
