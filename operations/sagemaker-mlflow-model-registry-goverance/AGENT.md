# AGENT.md

Samples for governing ML models with managed MLflow on Amazon SageMaker AI and
the SageMaker Model Registry sync (`AutoModelRegistrationEnabled`). Three
runnable topologies, each a folder with numbered step scripts:

- `topology-1-single-account/` — governance boundary = IAM role
- `topology-2-hub-spoke-central/` — hub-owned MLflow app + registry, RAM sharing
- `topology-3-hub-spoke-hybrid/` — spoke-local everything; approval-triggered
  copy into the hub as a governance record; deployment stays in the spoke

This file is the validated testing guide (profiles, provisioning, env vars, run
order, expected outputs, pitfalls, teardown) for both humans and agents.

## Working conventions

- Ask the user for the two profile names (spoke + hub) before provisioning;
  never guess. Confirm before creating billable infrastructure (MLflow apps,
  Studio domains, `ml.m5.xlarge` endpoints).
- Run step scripts from their topology directory with the repo venv
  (`../.venv/bin/python scripts/NN_*.py`); steps share state via
  `scripts/.sample_state.json` and must run in order.
- Long steps (training ~5 min, endpoint ~4 min) should run in the background
  with output redirected to a log file, then polled.
- After any deploy step succeeds, run the topology's cleanup step promptly —
  endpoints bill per instance-hour.

## Accounts and profiles

Two AWS CLI profiles are required (any names; the scripts read them from env):

- **Spoke / development** — where data scientists work. Topology 1 needs only this.
- **Hub / governance** — owns the central registry. Needed for topologies 2 and 3.

Verify both resolve before doing anything:

```bash
aws sts get-caller-identity --profile <spoke-profile>
aws sts get-caller-identity --profile <hub-profile>
```

Region: validated in `us-west-2`. Managed MLflow apps + Model Registry sync are
not available in every region.

## Provision (CloudFormation, per account)

Each participating account needs one stack from `cfn/sagemaker-studio-mlflow.yaml`
(Studio domain, execution role, S3 artifact bucket `sagemaker-<region>-<acct>`,
managed MLflow app with `AutoModelRegistrationEnabled`). No required parameters.

Workflow:

1. Verify each profile resolves with `aws sts get-caller-identity --profile <p>`
   and report the account IDs.
2. Check whether a `mlflow-governance` stack already exists in each account; if
   so, skip creation and just read the outputs.
3. Confirm with the user before creating anything (managed MLflow apps and
   Studio domains bill while they exist), then deploy per account. Prefer
   `create-stack` + polling over a blocking wait — the MLflow app takes
   ~10 minutes per stack.

```bash
# Spoke (needed for all topologies)
aws cloudformation deploy --template-file cfn/sagemaker-studio-mlflow.yaml \
  --stack-name mlflow-governance --capabilities CAPABILITY_IAM \
  --parameter-overrides DomainName=mlops-dev-domain MLflowAppName=mlflow-dev \
  --profile <spoke-profile> --region us-west-2

# Hub (needed for topologies 2 and 3)
aws cloudformation deploy --template-file cfn/sagemaker-studio-mlflow.yaml \
  --stack-name mlflow-governance --capabilities CAPABILITY_IAM \
  --parameter-overrides DomainName=mlops-hub-domain MLflowAppName=mlflow-hub \
  --profile <hub-profile> --region us-west-2
```

- If the bucket `sagemaker-<region>-<acct>` already exists, stack creation
  fails — delete or adapt first; surface this instead of retrying.
- When `CREATE_COMPLETE`, read the outputs you need (`MLflowAppArn`,
  `SageMakerExecutionRoleArn`):

```bash
aws cloudformation describe-stacks --stack-name mlflow-governance \
  --query "Stacks[0].Outputs[?OutputKey=='MLflowAppArn' || OutputKey=='SageMakerExecutionRoleArn'].[OutputKey,OutputValue]" \
  --output table --profile <profile> --region us-west-2
```

## Python environment

Use **Python 3.12** (matches the `py312` scikit-learn container used for training
and serving). All three topologies share the same pinned `requirements.txt`
(`sagemaker>=3,<4`, `mlflow<4`, `sagemaker-mlflow>=0.5`, `scikit-learn 1.4.x`):

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Run every step script **from its topology directory** so relative paths resolve.
Each topology persists progress in `scripts/.sample_state.json` — steps must run
in order, and a stale state file from a previous run should be deleted before
step 1.

## Run order and env vars per topology

### Topology 1 — single account (spoke only)

```bash
export AWS_PROFILE=<spoke-profile> AWS_DEFAULT_REGION=us-west-2
export MLFLOW_APP_ARN=<spoke MLflowAppArn>
export EXECUTION_ROLE=<spoke SageMakerExecutionRoleArn>
cd topology-1-single-account
python scripts/01_train_and_register.py   # ~5 min: real SageMaker Training Job
python scripts/02_govern_lifecycle.py     # staging OK, production explicitDeny, officer approves
python scripts/03_deploy_and_invoke.py    # ~4 min: real ml.m5.xlarge endpoint
python scripts/04_cleanup.py
```

### Topology 2 — hub-and-spoke central

```bash
export HUB_PROFILE=<hub-profile> SPOKE_PROFILE=<spoke-profile> AWS_DEFAULT_REGION=us-west-2
export HUB_MLFLOW_APP_ARN=<hub MLflowAppArn>
export SPOKE_EXECUTION_ROLE=<spoke SageMakerExecutionRoleArn>
cd topology-2-hub-spoke-central
python scripts/01_share_mlflow_app.py     # RAM share + hub bucket policy
python scripts/02_register_from_spoke.py  # trains locally, syncs into the HUB
python scripts/03_govern_in_hub.py
python scripts/04_deploy_from_spoke.py    # endpoint in the SPOKE
python scripts/05_cleanup.py
```

### Topology 3 — hub-and-spoke hybrid (deploy is spoke-local)

Deployment happens **in the spoke** from its own locally-approved package; the
hub copy is a governance record only (no cross-account artifact access).

```bash
export HUB_PROFILE=<hub-profile> SPOKE_PROFILE=<spoke-profile> AWS_DEFAULT_REGION=us-west-2
export SPOKE_MLFLOW_APP_ARN=<spoke MLflowAppArn>
export SPOKE_EXECUTION_ROLE=<spoke SageMakerExecutionRoleArn>
cd topology-3-hub-spoke-hybrid
python scripts/01_hub_setup.py            # dest group + resource policy + RAM AllowRegister
python scripts/02_register_in_spoke.py    # spoke's OWN app; local approval
python scripts/03_copy_to_hub.py          # CreateModelPackage into hub (provenance metadata)
python scripts/04_approve_in_hub.py       # independent hub sign-off (record, not gate)
python scripts/05_deploy_from_spoke.py    # endpoint in the SPOKE
python scripts/06_cleanup.py --remove-hub-group
```

## Expected results (validated)

- T1 metrics: `train_rmse ≈ 3.17`, `test_rmse ≈ 6.76`.
- T1 prediction: `[34.59, 20.17]`. T2/T3 prediction: `[34.76, 20.19]` (they train
  locally in-process instead of in the remote job — benign variance).
- T1 step 2 must print `IAM decision: explicitDeny` for the production guardrail.
- T3 step 4 must show `CustomerMetadataProperties` with the source package ARN
  and account.

Deploy steps must reach `InService` and print a prediction. Report a pass/fail
per step with the key evidence (ARNs, prediction values). ALWAYS finish with
the topology's cleanup step (use `--remove-hub-group` for topology 3), even if
a later step failed — endpoints bill per instance-hour.

## Known pitfalls (all hit in real runs)

1. **SDK v3 credential routing.** `sagemaker.core` typed resources (`Model`,
   `Endpoint`...) build their control-plane client from the **ambient
   environment** — the `session=` argument only reaches runtime/metrics clients,
   and the client is a singleton. Cross-account scripts must set
   `os.environ["AWS_PROFILE"]` to the correct profile **before importing
   `sagemaker.core`** (the deploy scripts already do this). Passing a
   `sagemaker.core.helper.session_helper.Session` raises a pydantic
   `ValidationError`; the param is a **boto3** `Session`.
2. **Group name hash suffix.** Automatic registration appends a short hash
   (`<model-name>-<hash>`). Never assume the bare name; discover with
   `list_model_package_groups(NameContains=...)`.
3. **Package deletion is eventually consistent.** Deleting a group right after
   its packages fails with "still contains Model Packages"; the cleanup scripts
   poll — do the same if deleting manually.
4. **Transient `credential_process` failures.** Under bursts of parallel calls
   the credential helper can return empty output (`JSONDecodeError: Expecting
   value`). Warm each profile with `aws sts get-caller-identity` and retry —
   not a code bug.
5. **Endpoint cost.** Deploy steps create a real `ml.m5.xlarge` endpoint
   (billed per instance-hour). Always run the topology's cleanup step promptly.
6. **Teardown order.** Before `aws cloudformation delete-stack`, **empty** the
   `sagemaker-<region>-<acct>` bucket (`aws s3 rm s3://... --recursive`) or the
   stack delete stalls. After deletion, MLflow apps linger as `Deleted`
   tombstones in `list-mlflow-apps` — that is expected and not billable.
7. **Long-running steps.** Training (~5 min) and endpoint creation (~4 min)
   block. When running via an agent, launch them in the background with output
   to a log file and poll.

## Full teardown

This is destructive — list what will be deleted (per account: the
`mlflow-governance` stack with its Studio domain, MLflow app, execution role,
and the `sagemaker-<region>-<acct>` bucket contents) and get explicit user
confirmation first. Order matters:

1. Check for leftover sample endpoints in each account
   (`aws sagemaker list-endpoints`) and delete any the user confirms — they
   bill per instance-hour and are not part of the stack.
2. **Empty** each account's artifact bucket. A non-empty bucket stalls stack
   deletion.
3. Delete the stack per account, then poll until `describe-stacks` reports the
   stack no longer exists (several minutes; the MLflow app and domain are the
   slow parts).
4. Verify: stacks gone, `list-domains` returns 0, `head-bucket` returns 404,
   no endpoints left. MLflow apps remaining in `list-mlflow-apps` with status
   `Deleted` are tombstones — expected, not billable.

```bash
aws s3 rm s3://sagemaker-us-west-2-<spoke-acct> --recursive --profile <spoke-profile>
aws s3 rm s3://sagemaker-us-west-2-<hub-acct>  --recursive --profile <hub-profile>
aws cloudformation delete-stack --stack-name mlflow-governance --profile <spoke-profile> --region us-west-2
aws cloudformation delete-stack --stack-name mlflow-governance --profile <hub-profile>  --region us-west-2
```

If a stack delete stalls on the Studio domain, check for running Studio apps or
spaces in the domain and surface them to the user before retrying.
