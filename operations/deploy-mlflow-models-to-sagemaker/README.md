# Deploying MLflow models to Amazon SageMaker AI Hosting

Companion code for the blog post *"Deploying MLflow models to Amazon SageMaker AI
Hosting"* (draft in [`blog/blog-draft.md`](blog/blog-draft.md)).

There are three distinct ways to take a model from **managed MLflow on Amazon
SageMaker AI** to a real-time SageMaker AI endpoint. These notebooks demonstrate all
three with the **same scikit-learn model**, so the differences you see are purely about
the deployment mechanism.

| Pattern | Notebook | One-liner |
|---|---|---|
| 1. MLflow-native deployment | [`01_deploy_mlflow_native.ipynb`](01_deploy_mlflow_native.ipynb) | Deploy straight from the MLflow Model Registry with `mlflow.deployments` — the SageMaker Model Registry is not used (though sync may still create a metadata-only entry) |
| 2. Registry sync + `ModelBuilder` repack | [`02_deploy_modelbuilder_repack.ipynb`](02_deploy_modelbuilder_repack.ipynb) | Auto-sync creates the Model Package; `ModelBuilder` generates inference code and repacks the model to make it deployable |
| 3. Registry sync + inference spec logging | [`03_deploy_inference_spec_logging.ipynb`](03_deploy_inference_spec_logging.ipynb) | Log an inference specification with `sagemaker-mlflow >= 0.5.0` *before* registering — the synced Model Package is born deployable, serving directly from the MLflow artifact store |

## Which pattern should I use?

- **Single data science team, single MLflow app, no formal approval process** →
  Pattern 1. Simple and native to MLflow.
- **Multiple teams and/or model governance requirements** → Pattern 2 or 3. The
  SageMaker Model Registry adds IAM-gated lifecycle stages, approval status, lineage,
  cross-account sharing, and EventBridge-driven CI/CD.
- **Pattern 2 vs 3:** `ModelBuilder` writes the inference code for you but copies the
  model out of MLflow; inference spec logging keeps the MLflow artifact store as the
  single source of truth but the inference code is on you.

## Getting started

### Step 1 — Deploy the infrastructure

Everything the notebooks need — a Studio domain, a user profile, an execution
role, and a managed MLflow app with Model Registry sync enabled
(`AutoModelRegistrationEnabled`) — is provisioned by a single CloudFormation stack:

```bash
aws cloudformation deploy \
  --template-file cfn/sagemaker-studio-mlflow.yaml \
  --stack-name deploy-mlflow-models \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2        # any region with SageMaker AI + managed MLflow
```

If the SageMaker default bucket (`sagemaker-<region>-<account>`) already exists in
your account, add `--parameter-overrides CreateArtifactBucket=false`.

The stack takes ~15 minutes (the MLflow app is the slow part). Its outputs are
everything you need later:

| Output | Used for |
|---|---|
| `StudioUrl` | Opening Studio (browser) |
| `SageMakerExecutionRoleArn` | `EXECUTION_ROLE` env var when running locally |
| `MLflowAppArn` | Informational — notebook 00 discovers the app by name |

The stack's default MLflow app name (`deploy-mlflow-models-app`) matches what
`00_setup_and_train.ipynb` looks for, so the notebook reuses the stack-provisioned
app instead of creating a new one.

> **Already have a domain?** You can skip the stack if your execution role can run
> training jobs, manage MLflow apps, models, endpoint configs and endpoints, and
> read/write the default SageMaker bucket — and, for pattern 1, push to an ECR
> repository named `mlflow-pyfunc` (note: `AmazonSageMakerFullAccess` alone does
> **not** allow that push — it only allows pushes to `*sagemaker*` repositories).

### Step 2, option A — Run in a SageMaker Studio JupyterLab space

1. Open the `StudioUrl` stack output in a browser (or: SageMaker AI console →
   Domains → `deploy-mlflow-models-domain` → user profile `sagemakeruser` → Open
   Studio).
2. Create a **JupyterLab space** (default instance type is fine) and open it.
3. Clone this repository into the space and open `00_setup_and_train.ipynb` with the
   default Python 3 kernel.
4. For **pattern 1** only: the stack already enables Docker access on the domain,
   but the docker CLI must be installed inside the space — see the
   [SageMaker docker install script](https://docs.aws.amazon.com/sagemaker/latest/dg/studio-updated-jl-docker.html).

### Step 2, option B — Run locally (tested on a MacBook M1)

```bash
git clone <this-repo> && cd deploy-mlflow-models-to-sagemaker
python3.12 -m venv .venv

# torch is a transitive dependency of sagemaker>=3 (via sagemaker-serve).
# requirements.txt adds the PyTorch CPU wheel index so Linux environments
# (Studio spaces, @remote jobs) pull the CPU-only build instead of the
# multi-GB CUDA one; on macOS, pip resolves plain wheels from PyPI. Pinning
# torch==2.4.1 here keeps the local env aligned with what was tested.
./.venv/bin/pip install "torch==2.4.1" "sagemaker>=3,<4" "mlflow>=3.14,<4" \
  "sagemaker-mlflow>=0.5.0,<1" "scikit-learn>=1.4,<1.5" shap matplotlib jupyterlab

# Outside SageMaker the caller is usually an IAM user, not a role — notebook 00
# falls back to the EXECUTION_ROLE env var. Fetch it from the stack outputs:
export AWS_REGION=us-west-2
export EXECUTION_ROLE=$(aws cloudformation describe-stacks \
  --stack-name deploy-mlflow-models --region $AWS_REGION \
  --query "Stacks[0].Outputs[?OutputKey=='SageMakerExecutionRoleArn'].OutputValue" \
  --output text)

./.venv/bin/jupyter lab
```

Local-run notes:

- **Skip the Step 0 install cells** in notebook 00 — the dependencies are already
  in the venv.
- **Pattern 1 needs Docker Desktop running.** The container build works on Apple
  Silicon: `mlflow sagemaker build-and-push-container` produces a `linux/amd64`
  image via emulation (what SageMaker needs) and pushes it to ECR. The build cell
  in notebook 01 detects the environment and only adds `--network sagemaker`
  inside Studio. Expect the first build to take several minutes.
- The push runs under **your** credentials, so your IAM user/role needs ECR push
  permissions on the `mlflow-pyfunc` repository.

### Step 3 — Notebook order

1. `00_setup_and_train.ipynb` — finds the stack-provisioned MLflow app, trains a
   model and logs it to MLflow (training runs inline in the kernel by default;
   uncomment the `@remote` decorator to promote it to a SageMaker Training Job).
   **Run this first**; it `%store`s the shared variables the pattern notebooks read.
2. Any of the pattern notebooks, in any order (independent of each other).
3. `04_cleanup.ipynb` — deletes endpoints, model packages, registered models, and
   (optionally) the MLflow app.

Also supported: **classic SageMaker notebook instances** — the install cell in
`00_setup_and_train.ipynb` falls back to `pip` when `uv` is not available.

### Pinned dependencies

| Package | Pin | Why |
|---|---|---|
| `sagemaker` | `>=3,<4` | SDK v3 API surface (breaking changes vs v2) |
| `mlflow` | `>=3.14,<4` | MLflow 3.x client, matching the managed MLflow app |
| `sagemaker-mlflow` | `>=0.5.0,<1` | `evaluate()` / `log_inference_specification()` |
| `scikit-learn` | `>=1.4,<1.5` | Matches the SKLearn serving container |

### Speeding up dependency installation (optional)

Two places install Python dependencies at runtime; both can be eliminated by baking
a custom image once:

| Hotspot | Default behavior | Prebaked alternative |
|---|---|---|
| `@remote` training job (notebook 00, opt-in) | `dependencies="./requirements.txt"` pip-installs at the start of **every** job | Bake `requirements.txt` into an image based on SageMaker Distribution 4.2 (**Python 3.12**, matching the notebook kernel — required, since `@remote` cloudpickles the function); pass it via `@remote(image_uri=...)` and drop `dependencies=` |
| Pattern 2 endpoint startup | ModelBuilder's `dependencies` list is pip-installed **inside the container at every instance launch** (including scale-out), delaying `/ping` health checks | Bake the pinned list into an image derived from the SKLearn `1.4-2-py312` serving container; pass it as `image_uri` and set `dependencies={"auto": False, "custom": []}` |

Patterns 1 and 3 need nothing: pattern 1's `build-and-push-container` already bakes
everything, and pattern 3 installs nothing at startup (the container ships sklearn,
and `inference.py` only uses the standard library).

> **Cost note:** each pattern notebook creates a real-time endpoint on
> `ml.m5.xlarge`. Run the cleanup notebook when done.

## Related

- [Managed MLflow on Amazon SageMaker AI](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow.html)
- [Automatic model registration (Model Registry sync)](https://docs.aws.amazon.com/sagemaker/latest/dg/mlflow-track-experiments-model-registration.html)
- [Deploy MLflow Model to Amazon SageMaker (MLflow docs)](https://mlflow.org/docs/latest/ml/deployment/deploy-model-to-sagemaker/)
- [sagemaker-mlflow plugin](https://github.com/aws/sagemaker-mlflow)
