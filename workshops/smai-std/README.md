# GenAI & ML Standardization

A hands-on workshop and reference implementation for standardizing the end-to-end machine learning lifecycle on AWS. It combines guided lab notebooks with production-ready MLOps seed code and infrastructure templates, covering both **traditional ML** (XGBoost classification) and **generative AI** (foundation-model fine-tuning) workflows.

The workshop is built on **Amazon SageMaker AI (SMAI)** — the core ML service for training, tuning, JumpStart foundation models, the Model Registry, and real-time endpoints.

The labs are organized around the personas who operate an ML platform — **platform admins**, **data engineers**, **data scientists**, and **ML/Ops engineers** — walking each role through their part of the lifecycle, from platform setup and data preparation to model build, automated deployment, and monitoring.

The material emphasizes **governance at scale**: experiment tracking, model lineage, model registry approval workflows, and automated CI/CD from project creation through production deployment.

## What's Inside

The repository is organized as a sequence of persona-oriented labs that follow the ML platform lifecycle — from platform setup, to data prep, model build, deployment automation, and monitoring — plus reusable seed code and infrastructure assets.

| Lab | Persona | Purpose |
|-----|---------|---------|
| `lab1-onboarding/` | Platform Admin | Set up the platform infrastructure and onboard users. |
| `lab2-data-prep/` | Data Engineer | Prepare data using multiple options: low-code/no-code, SageMaker processing jobs, EMR Serverless, and EMR on EC2. |
| `lab3-model-build/` | Data Scientist | Use the platform tools to experiment with and build both traditional ML and LLM models. |
| `lab4-model-deploy/` | ML Engineer | Integrate with CI/CD tools to automate model build and deployment. |
| `lab5-monitoring/` | ML / Ops Engineer | Monitor operational metrics, model metrics, and logs. |
| `seed-code/` | — | Production-ready MLOps seed repositories (model build + model deploy). |
| `templates/` | — | CloudFormation templates for SageMaker domain, VPC, and MLOps toolchain setup. |
| `scripts/` | — | Utility scripts (e.g., SageMaker domain cleanup). |
| `images/` | — | Screenshots and architecture diagrams used in the labs. |

### Lab Details

**Lab 1 – Onboarding** (`lab1-onboarding/`) · _Platform Admin_
Guides administrators through setting up the **SMAI** platform infrastructure (SageMaker domain, VPC, and supporting resources) and onboarding users, with governed access to datasets in Amazon S3.

**Lab 2 – Data Prep** (`lab2-data-prep/`) · _Data Engineer_
Guides data engineers through preparing data using several approaches so they can pick the right tool for the job:
- Low-code / no-code visual data preparation
- SageMaker processing jobs
- EMR Serverless
- EMR on EC2

**Lab 3 – Model Build** (`lab3-model-build/`) · _Data Scientist_
Guides data scientists in using the **SMAI** platform tools (training, JumpStart, and the Model Registry) to experiment with and build both traditional ML and LLM models.
- `lab3a_traditional_ml_experimenation.ipynb` – Traditional ML with SageMaker AI. Trains a binary classifier on the UCI Bank Marketing dataset to predict term-deposit subscriptions, using managed SageMaker training.
- `lab-3b-fine-tuning.ipynb` – Fine-tune **Llama 3.2 3B** for text summarization using SageMaker JumpStart, with full experiment tracking (parameters, metrics, and base-to-fine-tuned lineage) for auditability and reproducibility.
- `lab-3c-model-evaluation-registration.ipynb` – Evaluate the fine-tuned model against the base model, create model cards with governance metadata, and register versions in the **SageMaker Model Registry** with approval workflows.
- `metrics.py` – Shared evaluation metric helpers.

**Lab 4 – Model Deploy** (`lab4-model-deploy/`) · _ML Engineer_
Guides ML engineers in integrating with CI/CD tools to automate model build and deployment onto **SMAI** endpoints, then validating them (see `lab4x-endpoint-testing.ipynb` for testing an `InService` endpoint with sample payloads). The automation blueprint lives in `seed-code/` (see below).

**Lab 5 – Monitoring** (`lab5-monitoring/`) · _ML / Ops Engineer_
Guides engineers in monitoring operational metrics, model metrics, and logs for models deployed on **SMAI**.

## Seed Code (MLOps Automation)

`seed-code/classification/` contains the MLOps automation blueprint — an event-driven, GitHub-Actions-driven architecture that connects model build to production deployment on **SMAI**.

- **`model_build/`** — SageMaker Pipeline definitions (preprocessing, XGBoost training, evaluation, registration) orchestrated via GitHub Actions. See `seed-code/classification/model_build/README.md` for full setup.
- **`model-build-repo.zip` / `model-deploy-repo.zip`** — Packaged seed repositories.
- **`model_deploy`** (in the deploy zip) — AWS CDK stack that retrieves the approved model from the registry and provisions/updates a SageMaker endpoint with validation and rollback.

### End-to-end automated flow

1. Deploy the supporting AWS infrastructure (EventBridge rules, Step Functions, Lambda) and configure the build and deploy repositories with seed code.
2. Code pushes trigger the GitHub Actions build pipeline.
3. The SageMaker pipeline runs preprocessing → training → evaluation.
4. Experiment tracking captures metrics and lineage (when a tracking server is configured).
5. The trained model is registered in the SMAI Model Registry as `PendingManualApproval`.
6. A reviewer approves the model, flipping its status to `Approved`.
7. The approval event triggers the GitHub Actions deployment workflow.
8. CDK deploys/updates the SageMaker endpoint.
9. The endpoint serves real-time predictions with full traceability.

## Prerequisites

- An AWS account with permissions for Amazon SageMaker, S3, AWS Glue, IAM, and CloudFormation.
- Access to **Amazon SageMaker AI (SMAI)**.
- Python 3.10+ (Miniconda recommended for local pipeline runs).
- AWS CLI configured with appropriate credentials.
- For the seed-code CI/CD flow: a GitHub organization with OIDC-based access to AWS.

## Getting Started

### 1. Deploy Infrastructure

The platform infrastructure is split into five nested CloudFormation stacks orchestrated by a single parent template. This allows independent updates to networking, IAM, or SageMaker resources and makes it easy to add more services later.

**Stack structure:**

| Template | Purpose |
|----------|---------|
| `templates/main.yaml` | Parent stack — orchestrates all nested stacks |
| `templates/1-networking.yaml` | VPC, subnets, NAT Gateway, VPC endpoints, security groups |
| `templates/2-iam.yaml` | IAM roles and policies for SageMaker, Lambda, MLflow, Access Grants, QuickSight |
| `templates/3-sagemaker.yaml` | SageMaker domain, user profiles, MLflow, S3 buckets, Glue catalog, Lambdas |
| `templates/4-inference-capture.yaml` | Inference-capture plane: SQS queue + logger Lambda, and the `inference_responses` / `monitoring_responses` / `ground_truth_updates` Iceberg tables in the `bank_marketing` database (Labs 5D/5E) |
| `templates/5-data-prep.yaml` | EMR Serverless application and EMR on EC2 roles (Labs 2C/2D) |

**Deploy (recommended):** use the deploy script rather than raw `aws cloudformation` calls. It creates the template bucket, uploads all five child templates under a content-hashed prefix, resolves the Service Catalog role collision, prepares Lake Formation for the Iceberg tables, and waits for completion. It runs as-is in AWS CloudShell.

```bash
./scripts/deploy-workshop.sh
```

Common overrides are environment variables; `scripts/deploy-workshop.sh` documents all of them in its header comment:

```bash
PROJECT_NAME=my-workshop AWS_REGION=us-west-2 SEED_CODE_TYPE=classification \
  ./scripts/deploy-workshop.sh
```

Deployment takes **20–40 minutes**, most of it the SageMaker domain and the MLflow tracking server. The script prints the stack outputs when it finishes.

> The template key prefix is versioned with a hash of the template contents. A fixed prefix would make child-template edits invisible to CloudFormation, which caches child templates by URL.

**Manual deploy:** if you deploy by hand, note that the child templates must be uploaded under the `S3TemplateKeyPrefix` that `main.yaml` builds its child URLs from — not the bucket root — and that all five are required:

```bash
BUCKET=<YOUR_PROJECT_NAME>-cfn-templates
PREFIX=genai-ml-std-assets

aws s3 mb s3://${BUCKET} --region <REGION>
for t in 1-networking 2-iam 3-sagemaker 4-inference-capture 5-data-prep; do
  aws s3 cp templates/${t}.yaml s3://${BUCKET}/${PREFIX}/ --region <REGION>
done

aws cloudformation create-stack \
  --stack-name <YOUR_PROJECT_NAME>-workshop \
  --template-body file://templates/main.yaml \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --parameters \
    ParameterKey=ProjectName,ParameterValue=<YOUR_PROJECT_NAME> \
    ParameterKey=S3TemplateBucket,ParameterValue=${BUCKET} \
    ParameterKey=S3TemplateKeyPrefix,ParameterValue=${PREFIX} \
    ParameterKey=SeedCodeType,ParameterValue=classification \
  --region <REGION>
```

Replace `<YOUR_PROJECT_NAME>` with a lowercase, hyphenated name (e.g., `bank-marketing-prediction`, the default) and `<REGION>` with your target region (e.g., `us-east-1`).

**Available parameters** (`templates/main.yaml`):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `ProjectName` | `bank-marketing-prediction` | Used to name all resources; lowercase letters, digits, hyphens only |
| `S3TemplateBucket` | *(required)* | Bucket holding the five child templates |
| `S3TemplateKeyPrefix` | `genai-ml-std-assets` | Key prefix the child templates live under |
| `SeedCodeType` | `llm-fine-tuning` | `classification` or `llm-fine-tuning` |
| `VpcCIDR` | `10.1.0.0/16` | VPC CIDR block |
| `PrivateSubnetCIDR` | `10.1.1.0/24` | Private subnet 1 |
| `PrivateSubnet2CIDR` | `10.1.2.0/24` | Private subnet 2 |
| `PublicSubnetCIDR` | `10.1.3.0/24` | Public subnet (NAT Gateway) |
| `JupyterLabAppInstance` | `ml.m5.2xlarge` | Instance type for JupyterLab |
| `UserAProfileName` | `userA` | Name for first user profile |
| `UserBProfileName` | `userB` | Name for second user profile |
| `EMRReleaseLabel` | `emr-7.5.0` | EMR release for the Lab 2 data-prep stack |
| `CreateServiceCatalogRoles` | `true` | Create the SageMaker Projects / Service Catalog roles. Their names are account-global, so only one stack per account may own them — `deploy-workshop.sh` detects existing roles and passes `false` |
| `AttachQuickSightServiceRolePolicy` | `false` | Attach the data-access policies to QuickSight's service role. Only valid once the account is subscribed to QuickSight — see below |

**Monitor deployment:**

```bash
aws cloudformation describe-stacks \
  --stack-name <YOUR_PROJECT_NAME>-workshop \
  --query "Stacks[0].StackStatus" --output text \
  --region <REGION>
```

### QuickSight prerequisites (one-time per account)

Only **Lab 5E** (`lab5-monitoring/lab5e-governance-dashboard.ipynb`) needs QuickSight. Every other lab runs without it. There is no CloudFormation resource for a QuickSight subscription, so it is a separate, opt-in step — and it has two halves either way:

1. subscribe the account to **Enterprise** edition (billable, one-time, account-global);
2. deploy the stack with `AttachQuickSightServiceRolePolicy=true` so the data-access policies land on `aws-quicksight-service-role-v0`.

The ordering is not optional: an IAM policy resource fails outright if the role it targets does not exist, and that role is created by the subscription. That is why `AttachQuickSightServiceRolePolicy` defaults to `false` — a stack deployed before the subscription would otherwise roll back entirely. And skipping half 2 is the usual cause of a dashboard that publishes but whose panels all fail to load, because QuickSight reads Athena and S3 as its own service role, *not* as the notebook's execution role.

**The default path is the console**, during Lab 5E. The workshop docs
(`model-governance-at-scale-with-sagemaker-ai`, `content/lab/lab-5/lab-5e/`) walk it with
screenshots, and are the canonical version; the summary here is for anyone working from this
repo alone.

*Half 1 — subscribe.* Search the console for `quick`: you'll get two entries, **Amazon Quick**
(the suite the BI product now lives in) and **QuickSight** (the classic entry). Either works. On
the form, set a globally unique account name and a notification email, and leave
**Authentication method** on its default (*Password-based or Single-Sign On*, the equivalent of
`IAM_AND_QUICKSIGHT`) and **Encryption** on the AWS-managed key. The form's **Default region** is
where QuickSight stores its own data — *not* the identity region. It has no edition selector, so
verify afterwards:

```bash
ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

aws quicksight describe-account-settings --aws-account-id "${ACCOUNT_ID}" \
  --region us-east-1 --query 'AccountSettings.Edition' --output text
```

*Half 2 — grant the service role access.* Now that `aws-quicksight-service-role-v0` exists, flip
the stack parameter. Only the IAM nested stack changes, so this is minutes, not the 20-40 of a
full deploy:

```bash
STACK_NAME="${PROJECT_NAME:-bank-marketing-prediction}-workshop"

OVERRIDES=""
for k in $(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
             --query 'Stacks[0].Parameters[].ParameterKey' --output text); do
  if [ "${k}" = "AttachQuickSightServiceRolePolicy" ]; then
    OVERRIDES="${OVERRIDES} ParameterKey=${k},ParameterValue=true"
  else
    OVERRIDES="${OVERRIDES} ParameterKey=${k},UsePreviousValue=true"
  fi
done

aws cloudformation update-stack --stack-name "${STACK_NAME}" \
  --use-previous-template \
  --capabilities CAPABILITY_NAMED_IAM CAPABILITY_AUTO_EXPAND \
  --parameters ${OVERRIDES}
```

Re-running `./scripts/deploy-workshop.sh` does the same thing — it detects the service role
regardless of how the subscription happened and sets the parameter itself — but it redeploys
every nested stack, so prefer the targeted update once the workshop is running. Where you cannot
update the stack at all, attach the two `PolicyDocument` blocks from `templates/2-iam.yaml`
directly with `aws iam put-role-policy`, using the project-scoped names
`${ProjectName}-QuickSightS3DataLakeAccess` and `${ProjectName}-QuickSightAthenaAccess` — these are
project-scoped so multiple projects can share the account-global QuickSight service role, and
`create_governance_dashboard.py` matches them by name (via `config.QUICKSIGHT_S3_POLICY_NAME` /
`QUICKSIGHT_ATHENA_POLICY_NAME`).

**Automating both halves instead.** For provisioning accounts in bulk rather than teaching from
them, the deploy script folds the whole thing into one run:

```bash
SUBSCRIBE_QUICKSIGHT=true QUICKSIGHT_NOTIFICATION_EMAIL=you@example.com \
  ./scripts/deploy-workshop.sh
```

Subscribes, waits for provisioning, confirms the service role, then deploys with the parameter
set. Already-subscribed accounts are detected and left alone. The flag defaults to `false`
because the subscription is billable and permanent, and should not be a side effect of a deploy
nobody read.

| Variable | Default | Notes |
|---|---|---|
| `SUBSCRIBE_QUICKSIGHT` | `false` | **Billable.** Creates the subscription |
| `QUICKSIGHT_NOTIFICATION_EMAIL` | — | Required when subscribing |
| `QUICKSIGHT_IDENTITY_REGION` | `us-east-1` | One per account, **permanent**. Must match `QUICKSIGHT_IDENTITY_REGION` in `.env` for Lab 5E |
| `QUICKSIGHT_EDITION` | `ENTERPRISE` | Lab 5E uses the Definition API, which requires Enterprise |
| `QUICKSIGHT_ACCOUNT_NAME` | `<PROJECT_NAME>-<account>` | **Permanent**; must be globally unique |
| `VERIFY_QUICKSIGHT_IAM` | `true` | Post-deploy check that the execution roles carry the Lab 5E actions |

**Why the edition needs verifying.** The sign-up form asks only for an account name, notification email, default data region, authentication method, and encryption key — nothing about editions — so a console signup gives you no way to tell which one you got. An account that landed on Standard upgrades from *Manage QuickSight → Account settings*; the downgrade is not supported.

**To open the dashboard in the QuickSight UI yourself** (the notebook does not need this): create a QuickSight **Author** or **Admin** user for your identity under *Manage QuickSight → Manage users*.

**Troubleshooting:**

| Symptom | Cause |
|---|---|
| Notebook reports "QuickSight not subscribed" | No subscription, or the caller lacks `quicksight:DescribeAccountSettings` — the notebook cannot tell these apart and says so |
| Dashboard created, panels show an error | QuickSight's service role has no access to the data bucket or Athena — redeploy with `AttachQuickSightServiceRolePolicy=true` |
| `AccessDeniedException` partway through the build | The execution role has some QuickSight permissions but not all — apply the `QuickSightGovernanceDashboard` statement from `templates/2-iam.yaml` |
| Subscription call fails with an account-name or region error | The account is already subscribed in a different region (set `QUICKSIGHT_IDENTITY_REGION`), or the name is taken (set `QUICKSIGHT_ACCOUNT_NAME`) |

### 2. Work Through the Labs

Open the notebooks under `lab1-onboarding/` through `lab5-monitoring/` in SageMaker AI Studio and follow the instructions in each.

### 3. Run the MLOps Seed Code (Optional)

Follow `seed-code/classification/model_build/README.md` to configure GitHub secrets/variables and run the SageMaker pipeline locally or via GitHub Actions.

### Run the build pipeline locally

```bash
cd seed-code/classification/model_build
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python ./ml_pipelines/run_pipeline.py \
  --module-name training.pipeline \
  --role-arn <SAGEMAKER_PIPELINE_ROLE_ARN> \
  --tags '[{"Key":"sagemaker:project-name","Value":"<PROJECT_NAME>"},{"Key":"sagemaker:project-id","Value":"<PROJECT_ID>"}]' \
  --kwargs '{"region":"<REGION>","role":"<ROLE_ARN>","default_bucket":"<BUCKET>","pipeline_name":"local-test-pipeline","model_package_group_name":"<MODEL_GROUP>","glue_database_name":"<GLUE_DB>","glue_table_name":"<GLUE_TABLE>"}'
```

## Datasets

- **Bank Marketing Dataset** (UCI Machine Learning Repository) — used for the traditional ML classification labs.
- **Dolly dataset** — used for the Llama 3.2 fine-tuning lab.

## Clean Up

To avoid ongoing charges after completing the labs:

- Delete SageMaker endpoints, pipelines, and model packages you created.
- Remove S3 artifacts that are no longer needed.
- Delete the CloudFormation stack (this tears down all nested stacks):
  ```bash
  aws cloudformation delete-stack --stack-name <YOUR_PROJECT_NAME> --region <REGION>
  ```
  **Note:** If S3 buckets contain objects, empty them first (`aws s3 rm s3://<bucket> --recursive`) before deleting the stack.
- Use `scripts/delete_sagemaker_domain.py` to remove a SageMaker domain if needed outside of CloudFormation.

## Repository Layout

```
genai-ml-standardization/
├── lab1-onboarding/        # Platform Admin  – platform setup & user onboarding
├── lab2-data-prep/         # Data Engineer   – data prep (low-code, processing jobs, EMR)
├── lab3-model-build/       # Data Scientist  – experimentation & model build (traditional + LLM)
├── lab4-model-deploy/      # ML Engineer     – CI/CD automation for build & deploy
├── lab5-monitoring/        # ML/Ops Engineer – operational metrics, model metrics & logs
├── seed-code/              # MLOps seed repos (build + deploy)
├── templates/              # CloudFormation infrastructure templates
├── scripts/                # Utility scripts
└── images/                 # Diagrams and screenshots
```
