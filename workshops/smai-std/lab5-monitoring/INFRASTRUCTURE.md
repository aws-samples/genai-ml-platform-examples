# Infrastructure Behind Lab 5D / 5E / 5F

Everything Lab 5 needs is created by **`scripts/deploy-workshop.sh`**, which
deploys six independent CloudFormation stacks. There is no companion stack, no
stack deployed from a notebook, and nothing for you to deploy between labs.
Notebooks only **write rows** and **create QuickSight objects**; they never
create AWS infrastructure.

Drift itself is computed **inline in notebook 5D** — Evidently runs in the
kernel, results are `INSERT`ed into Athena and logged to MLflow, and Lab 5E reads
those tables from QuickSight. No drift Lambda, no EventBridge schedule, no SNS
topic, and no CloudWatch alarm exists anywhere in this repo. (The production form
of that scheduled architecture is a separate AWS blog post; see the Lab 5D
workshop page.)

> **Note on the inference path.** Prediction *capture* is not notebook code — it
> is a real SQS queue plus a logger Lambda in `templates/4-inference-capture.yaml`
> (below). Lab 5D's notebook writes the *drift verdicts*; the endpoint's captured
> predictions arrive through that pipeline.

---

## Stack layout

`scripts/deploy-workshop.sh` deploys six **independent, top-level** stacks in
dependency order, named `<STACK_PREFIX>-<component>` where `STACK_PREFIX`
defaults to `PROJECT_NAME`. Outputs are threaded forward as parameters — the
SageMaker stack's data bucket and the IAM stack's execution-role names become
parameters of the later stacks.

| Stack | Template | Relevance to Lab 5 |
|---|---|---|
| `<prefix>-networking` | `1-networking.yaml` | VPC, two private subnets, public subnet + NAT, security groups, 11 VPC endpoints (S3, SageMaker API/Runtime/Studio, STS, SSM, CloudWatch, Logs, ECR) — the domain runs VpcOnly |
| `<prefix>-iam` | `2-iam.yaml` | Execution roles and every policy Lab 5 needs, including the two QuickSight service-role policies and the MLflow data-plane grants |
| `<prefix>-sagemaker` | `3-sagemaker.yaml` | Domain, user profiles, JupyterLab space, MLflow app, S3 buckets, S3 Access Grants |
| `<prefix>-inference-capture` | `4-inference-capture.yaml` | **The Lab 5 data plane**: `inference_responses`, `monitoring_responses`, `ground_truth_updates` + the SQS→Lambda capture pipeline |
| `<prefix>-data-prep` | `5-data-prep.yaml` | `training_data` and `evaluation_data` (the drift baselines) + the Lab 2C/2D EMR resources |
| `<prefix>-okta-federation` | `6-okta-federation.yaml` | Lab 1D only — not used by Lab 5. Opt-in via `ENABLE_OKTA_FEDERATION=true` |

> **`templates/main.yaml` is deprecated.** It was the parent stack that nested
> the templates above, and it is retained only so a pre-split deployment can
> still be deleted with the template that created it. It is not deployed,
> updated, or tested. `deploy-workshop.sh` detects a surviving parent stack and
> refuses to run alongside it, because the two layouts would collide on every
> fixed-name resource.

Because the stacks are independent, a change to one template touches only that
stack — useful for Lab 5E, where the QuickSight policies live in the IAM stack:

```bash
ONLY_STACKS=iam ./scripts/deploy-workshop.sh      # minutes, not 20-40
```

### Two Glue databases exist — know which is which

| Database | Created by | Who uses it |
|---|---|---|
| **`bank_marketing`** | `4-inference-capture.yaml` (`MonitoringGlueDatabase`, from the `AthenaDatabase` parameter) | **All five Lab 5 tables.** Also Lab 2's data-prep tables |
| `bank-classification-db` | `3-sagemaker.yaml` (`BankClassificationGlueDatabase`, hardcoded) + one Glue table `bank-marketing-data` | The optional MLOps **seed code** only (`seed-code/classification/model_build/config/pipeline_config.json`). No lab notebook reads or writes it |

`5-data-prep.yaml` also declares `bank_marketing`, but it is guarded by
`Condition: ShouldCreateGlueDatabase` and `deploy-workshop.sh` passes
`CreateGlueDatabase=false`, so the two stacks do not collide — Glue database
names are unique per account and region. This is also why the deploy order puts
`inference-capture` before `data-prep`: the former creates the database, the
latter reuses it.

---

## Resources used by Lab 5

### From `3-sagemaker.yaml`

| Resource | Type | Used by |
|---|---|---|
| SageMaker Domain (VpcOnly) | `AWS::SageMaker::Domain` | All — runtime environment |
| User profiles (userA, userB) | `AWS::SageMaker::UserProfile` | All — execution identity |
| JupyterLab space | `AWS::SageMaker::Space` | All — notebook execution |
| MLflow app (serverless) | `AWS::SageMaker::MlflowApp` | 5D (drift metrics + Evidently reports as artifacts), 5F (model registry) |
| Data bucket | `AWS::S3::Bucket` | All — Iceberg data, Athena query results, Evidently HTML |
| MLflow artifacts bucket | `AWS::S3::Bucket` | 5D, 5F |

### From `4-inference-capture.yaml` — the Lab 5 data plane

| Resource | Logical ID | Purpose |
|---|---|---|
| Glue database | `MonitoringGlueDatabase` | `bank_marketing` |
| SQS queue | `InferenceCaptureQueue` | Buffers one message per prediction. Its URL is the endpoint container's `SQS_QUEUE_URL` env var (Lab 3) |
| Dead-letter queue | `InferenceCaptureDLQ` | Capture messages that fail repeatedly |
| Logger Lambda | `InferenceLoggerFunction` | Drains SQS in batches and `INSERT`s into `inference_responses` |
| Event source mapping | `InferenceLoggerEventSource` | Triggers the logger from SQS |
| Table-creator Lambda | `TableCreatorFunction` | Runs the `CREATE TABLE IF NOT EXISTS` DDL through Athena |
| Custom resource | `InferenceTable` | Invokes the table creator. Its `Version` property is the lever that forces the DDL to re-run on a stack update |
| SQS-send policy | `SqsSendPolicy` | Grants the endpoint execution role `sqs:SendMessage`, when `EndpointExecutionRoleNames` is supplied |

**Capture flow:** endpoint inference handler → SQS → logger Lambda → Athena
`INSERT` into `inference_responses`. Decoupling through SQS means a traffic spike
queues instead of backpressuring the endpoint.

### From `5-data-prep.yaml` — the drift baselines

| Resource | Purpose |
|---|---|
| `DataPrepTables` (custom resource) | Creates `training_data` and `evaluation_data` Iceberg tables |
| `DataPrepTableBucket` / `Namespace` / `S3TrainingTable` / `S3EvaluationTable` | `AWS::S3Tables::*` — the managed Iceberg layer used by Lab 2 |
| `LakeFormation::PrincipalPermissions` ×8 | Database and table grants for the table-creator and the three notebook roles. Gated by `EnableLakeFormationGrants` (default `false`; `deploy-workshop.sh` instead ensures Lake Formation's `IAM_ALLOWED_PRINCIPALS` default so plain IAM access works) |
| `EMRServerlessApplication`, `EMRServiceRole`, `EMREC2InstanceProfile` | Labs 2C / 2D only — not used by Lab 5 |

---

## The five Athena Iceberg tables

All in the **`bank_marketing`** database. Created by CloudFormation custom-resource
Lambdas running `CREATE TABLE IF NOT EXISTS`, never by a notebook. They are
**not** dropped when the stack is deleted — captured data is preserved on purpose.

| Table | Created by | Written by | Purpose |
|---|---|---|---|
| `training_data` | `5-data-prep.yaml` | Lab 2 | Frozen training slice — the **data-drift** reference distribution |
| `evaluation_data` | `5-data-prep.yaml` | Lab 2 | Frozen held-out slice — the **model-drift** baseline metrics |
| `inference_responses` | `4-inference-capture.yaml` | Logger Lambda (per prediction); Lab 5D back-fills `monitoring_run_id` | Captured endpoint predictions: `inference_id`, `endpoint_name`, `prediction`, `probability_positive`, `ground_truth`, `monitoring_run_id`, latency fields — 26 columns |
| `monitoring_responses` | `4-inference-capture.yaml` | Lab 5D notebook (`INSERT`) | One row per drift run: `monitoring_run_id`, `data_drift_detected`, `model_drift_detected`, `baseline_roc_auc`, `current_roc_auc`, `drifted_columns_share`, `training_snapshot_id`, `evaluation_snapshot_id` — 28 columns |
| `ground_truth_updates` | `4-inference-capture.yaml` | Lab 5D's ground-truth simulator | Late-arriving labels: `inference_id`, `actual_subscribed`, timestamps, `update_batch_id` |

The label column is `actual_<target>` — `actual_subscribed` for this dataset —
derived from the schema, not hardcoded. Lab 5E's accuracy dataset joins on it.

### Changing a table's columns after deployment

The DDL is `CREATE TABLE IF NOT EXISTS`, so **re-running the stack does not alter
a table that already exists**, and CloudFormation cannot detect that a Glue table
drifted or was dropped — drift detection does not cover custom resources. To apply
a column change to an already-deployed account, either:

```sql
ALTER TABLE bank_marketing.monitoring_responses ADD COLUMN <name> <type>;
```

or drop that one table and redeploy with the custom resource's `Version` property
bumped, which forces the DDL to re-run and create the missing table. Note that
dropping an Iceberg table in Athena **also deletes its data** (Iceberg tables are
managed tables), and each table has its own S3 prefix, so dropping one does not
touch the others.

---

## Notebook → infrastructure dependency map

| Notebook | Needs |
|---|---|
| **5A** CloudWatch metrics | Live endpoint |
| **5B** CloudWatch logs | Live endpoint |
| **5C** CloudTrail | Nothing beyond the domain |
| **5D** Inference monitoring | Domain, MLflow, **live endpoint**, all five Athena tables, capture pipeline |
| **5E** Governance dashboard | The tables 5D wrote to, plus a **QuickSight Enterprise** subscription |
| **5F** SHAP explainability | Domain, MLflow, `training_data` (SHAP background set), approved model package |

Labs 5A–5F all need the endpoint alive. Lab 3A's final cell deletes it — run that
only after finishing Lab 5.

---

## QuickSight prerequisites (notebook 5E only)

The QuickSight **account subscription** has no CloudFormation resource, so it
happens outside the stack — once per AWS account, and billable. The default path
is the **console**, from notebook 5E itself: search the console for `quick` and
sign up. The workshop docs walk it, and doing it by hand is deliberate, because
the subscription and the data-access grant below are two separate events and
watching them happen separately is the governance point of the lab.

The sign-up form has no edition selector, and 5E needs **Enterprise** (the
Definition API it publishes through is an Enterprise feature), so verify rather
than assume:

```bash
aws quicksight describe-account-settings --aws-account-id <account> \
  --region us-east-1 --query 'AccountSettings.Edition' --output text
```

`scripts/deploy-workshop.sh` can subscribe instead, for provisioning accounts in
bulk:

```bash
SUBSCRIBE_QUICKSIGHT=true QUICKSIGHT_NOTIFICATION_EMAIL=you@example.com ./scripts/deploy-workshop.sh
```

That requests Enterprise with `IAM_AND_QUICKSIGHT` authentication in
`QUICKSIGHT_IDENTITY_REGION` (default `us-east-1`) — the console form's default
*Password-based or Single-Sign On* is the same thing. The flag defaults to `false`
because both the identity region and the QuickSight account name are permanent.

**QuickSight's access to the data is CloudFormation-owned.** QuickSight reads
Athena and S3 as its own service role — `aws-quicksight-service-role-v0` — *not*
as the notebook's execution role. `templates/2-iam.yaml` attaches
`QuickSightServiceRoleS3Policy` (data bucket + Athena results) and
`QuickSightServiceRoleAthenaPolicy` (Athena/Glue read) to that role, in place of
the console's *Manage QuickSight → Security & permissions* toggles.

Both are conditional on `AttachQuickSightServiceRolePolicy`, which defaults to
`false`: an IAM policy resource fails outright if its target role does not exist,
and that role is created by the subscription. Subscribing from the console during
5E therefore always leaves the stack a step behind. Re-run the deploy limited to
the IAM stack — the script detects the service role however the subscription
happened and sets the parameter itself:

```bash
ONLY_STACKS=iam ./scripts/deploy-workshop.sh
```

Without those policies the dashboard is created successfully but every panel
fails to load.

Two things notebook 5E does not need, but a human browsing the dashboard does: a
QuickSight **Author/Admin** user for your IAM/SSO identity (*Manage QuickSight →
Manage users*), and `QUICKSIGHT_IDENTITY_REGION` in `.env` if the account's
identity region differs from `AWS_DEFAULT_REGION`.

> **If the deploy reports QuickSight as not subscribed when it is**, the identity
> region is wrong. QuickSight has one identity endpoint per account, fixed when
> the account was first activated, and `deploy-workshop.sh` defaults to
> `us-east-1`. It now detects the real region from the API error and reports it;
> set `QUICKSIGHT_IDENTITY_REGION` here *and* in `.env`, because Lab 5E reads its
> own config rather than the script's.

Full prerequisites and troubleshooting: the repo `README.md`, section
**QuickSight prerequisites (one-time per account)**.

---

## Deployment order

```
1. ./scripts/deploy-workshop.sh          ← six stacks, in order, 20-40 min
2. lab0-setup/setup.ipynb                ← writes the shared .env every lab reads
3. Lab 2      prepare data               → training_data, evaluation_data
4. Lab 3A/3C  train, register, deploy    → live endpoint + baseline.json
5. Lab 5A-5C  infrastructure monitoring
6. Lab 5D     drift monitoring           → monitoring_responses, ground_truth_updates
7. Lab 5E     governance dashboard       ← needs QuickSight Enterprise
8. Lab 5F     explainability
9. Lab 3A final cell                     ← delete the endpoint last
```

### Teardown

```bash
scripts/teardown-workshop.sh          # deletes the six stacks in reverse order
```

It clears the two things that otherwise block deletion — running Studio apps and
objects in the grants/data/mlflow buckets — and, if the networking stack delete
hits the classic VpcOnly blocker, removes the domain's orphaned EFS mount targets
and NFS security groups before retrying.

Two Lab 5–specific points:

- **A lab endpoint deployed with a `VpcConfig` will block teardown.** Its ENIs sit
  in the workshop's private subnets, and the EFS/NFS unblock cannot clear them
  because they belong to a live endpoint. The script detects and names those
  endpoints before it starts; pass `DELETE_LAB_ENDPOINTS=true` to have it delete
  them first.
- **The Athena tables and their S3 data go with the stacks.** Export anything you
  want to keep — drift verdicts in `monitoring_responses`, captured predictions in
  `inference_responses` — before tearing down. `scripts/delete_s3_buckets.py`
  empties and removes the buckets if a stack delete leaves them stranded.

For stacks only, with no bucket or app cleanup:

```bash
TEARDOWN=true ./scripts/deploy-workshop.sh
```
