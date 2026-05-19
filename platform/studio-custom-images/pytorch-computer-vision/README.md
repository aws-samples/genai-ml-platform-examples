# PyTorch Computer Vision Custom Image

A single custom image with PyTorch and computer vision libraries that works across SageMaker Studio V2 and Unified Studio — JupyterLab and Code Editor on both platforms.

## What's included

The base image ([SageMaker Distribution](https://github.com/aws/sagemaker-distribution) 3.5.1) already includes PyTorch, OpenCV, NumPy, and Pandas. This example adds:

- **albumentations** - Image augmentation library
- **timm** - Pre-trained vision models (ViT, EfficientNet, ConvNeXt, etc.)
- **ultralytics** - YOLOv8 for object detection and segmentation

## How custom images work

SageMaker uses a chain of resources to go from a Docker image to a selectable environment in the Studio console:

```
Dockerfile → ECR image → SageMaker Image → Image Version → AppImageConfig → Domain attachment
```

- **ECR image**: Your Docker image, pushed to Amazon ECR.
- **SageMaker Image**: A named resource that acts as a pointer. It can have multiple versions.
- **Image Version**: Links a specific ECR image digest to the SageMaker Image. When you rebuild and push, you create a new version.
- **AppImageConfig**: Tells SageMaker how to _run_ the container — which entrypoint to use, what arguments to pass. This is where you configure the IDE (JupyterLab vs Code Editor) and the platform (Studio V2 vs Unified Studio).
- **Domain attachment**: An `update-domain` call that makes the image available to users when they create a new space.

You create the SageMaker Image and AppImageConfig once. After that, updating your image is just: rebuild, push, create a new Image Version, restart your space.

## Dockerfile rules

The Dockerfile in this example is minimal by design. Here are the constraints that matter:

**Use the `sagemaker-distribution` base image.** This is required for Unified Studio — it ships the `entrypoint-sagemaker-ui-jupyter-server` and `entrypoint-code-editor` scripts. For Studio V2 only, other base images work, but `sagemaker-distribution` is the only one that covers all platforms.

**Do NOT set ENTRYPOINT.** The entrypoint varies by platform and IDE. By leaving it unset in the Dockerfile, each `AppImageConfig` specifies the right one at launch time. This is what allows a single image to work across all four combinations.

**Pin numpy to match the base image.** The base image ships with `numpy==1.26.4`. Many pre-installed packages (the SageMaker Python SDK, autogluon, catboost) have `numpy<2` upper bounds. If one of your dependencies pulls in numpy 2.x as a transitive dependency, the build will succeed but imports will fail at runtime with cryptic errors. Always pin:

```
numpy==1.26.4   # must match base image
```

**Don't override AWS SDK packages.** Do not include `boto3`, `botocore`, or `sagemaker` in your `requirements.txt`. They come from the base image with specific version constraints. Overriding them can break the SageMaker SDK and extension loading.

**Switch to root for installs, then back.** The base image runs as `sagemaker-user` (UID 1000). You need `USER root` to install packages, then `USER $NB_USER` at the end. SageMaker expects the container to run as a non-root user.

## Key design: single image, multiple platforms

A single Docker image works across all four platform-IDE combinations. The only difference is the `AppImageConfig`, which sets the entrypoint:

| Platform | IDE | Entrypoint | Why this one |
|----------|-----|-----------|-------------|
| Studio V2 | JupyterLab | `jupyter-lab` | Raw JupyterLab binary. Needs explicit `--ServerApp.ip=0.0.0.0` and `--ServerApp.token=` because the SageMaker health check connects over the network without authentication. |
| Studio V2 | Code Editor | `entrypoint-code-editor` | Wrapper script from the base image. Handles configuration automatically. |
| Unified Studio | JupyterLab | `entrypoint-sagemaker-ui-jupyter-server` | Wrapper that configures Unified Studio's auth model (`MD_IAM`). Using `jupyter-lab` here causes `InternalFailure`. |
| Unified Studio | Code Editor | `entrypoint-code-editor` | Same wrapper as Studio V2 — it detects the environment and adapts. |

All three entrypoints ship with the `sagemaker-distribution` base image. Code Editor uses the same config on both platforms. JupyterLab does not — this is the detail most likely to cause a failed deployment.

## Prerequisites

- **AWS CLI v2** installed and configured
- **Docker** installed and running locally
- **A SageMaker execution role** — needs permissions to pull from ECR (`ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`). To find your existing role: SageMaker console → Domains → select your domain → Domain settings → the "Execution role" field. It looks like `arn:aws:iam::<account>:role/service-role/AmazonSageMaker-ExecutionRole-...`
- **A SageMaker domain** (Studio V2, Unified Studio, or both)

## Setup

Run this block first. The `aws sts` call is last because it is slow and can cause shells to drop pasted lines that follow it:

```bash
export AWS_REGION=us-west-2          # change to your region
export ECR_REPO=sagemaker-custom-images/pytorch-cv
export IMAGE_NAME=pytorch-cv
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account: $AWS_ACCOUNT_ID  Region: $AWS_REGION  Repo: $ECR_REPO"
```

Verify the output shows the correct values before proceeding.

## Build and push

Run from the `examples/pytorch-computer-vision/` directory:

```bash
# Create ECR repository (skip if it already exists)
aws ecr create-repository --repository-name $ECR_REPO --region $AWS_REGION || true

# Login to public ECR
aws ecr-public get-login-password --region us-east-1 | docker login --username AWS --password-stdin public.ecr.aws

# Build (--platform linux/amd64 is required when building on Apple Silicon)
docker build --platform linux/amd64 -t $IMAGE_NAME .

# Login to ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push
docker tag $IMAGE_NAME $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest
```

## Register with SageMaker

This creates the SageMaker Image, an Image Version pointing to your ECR image, and three AppImageConfigs (one per entrypoint):

```bash
export ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/YourSageMakerRole"  # change to your execution role

# Create SageMaker Image — a named resource that holds versions
aws sagemaker create-image \
    --image-name $IMAGE_NAME \
    --role-arn $ROLE_ARN \
    --region $AWS_REGION

# Create Image Version — links the ECR digest to the SageMaker Image
aws sagemaker create-image-version \
    --image-name $IMAGE_NAME \
    --base-image $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest \
    --region $AWS_REGION

# AppImageConfig for Studio V2 JupyterLab
# ip=0.0.0.0: health check connects over the network, not localhost
# token=: health check doesn't pass auth tokens
# no-browser: container has no display
aws sagemaker create-app-image-config \
    --app-image-config-name ${IMAGE_NAME}-jl \
    --jupyter-lab-app-image-config '{
        "ContainerConfig": {
            "ContainerEntrypoint": ["jupyter-lab"],
            "ContainerArguments": ["--ServerApp.base_url=/jupyterlab/default", "--ServerApp.ip=0.0.0.0", "--ServerApp.token=", "--no-browser"]
        }
    }' \
    --region $AWS_REGION

# AppImageConfig for Code Editor (works on both Studio V2 and Unified Studio)
aws sagemaker create-app-image-config \
    --app-image-config-name ${IMAGE_NAME}-ce \
    --code-editor-app-image-config '{
        "ContainerConfig": {
            "ContainerEntrypoint": ["entrypoint-code-editor"]
        }
    }' \
    --region $AWS_REGION

# AppImageConfig for Unified Studio JupyterLab
# Uses a different entrypoint that handles Unified Studio's auth model (MD_IAM)
aws sagemaker create-app-image-config \
    --app-image-config-name ${IMAGE_NAME}-unified-jl \
    --jupyter-lab-app-image-config '{
        "ContainerConfig": {
            "ContainerEntrypoint": ["entrypoint-sagemaker-ui-jupyter-server"]
        }
    }' \
    --region $AWS_REGION
```

## Attach to a domain

These `update-domain` calls make the image selectable when users create a new space. Note: `CustomImages` replaces the existing list — if you have other custom images, include them all.

### Studio V2

To find your domain ID: SageMaker console → Domains → select your domain → the `d-xxxxxxxxxxxx` in the URL or the "Domain ID" field.

```bash
export STUDIO_DOMAIN_ID=d-xxxxxxxxxxxx   # change to your Studio domain ID

aws sagemaker update-domain \
    --domain-id $STUDIO_DOMAIN_ID \
    --region $AWS_REGION \
    --default-user-settings '{
        "JupyterLabAppSettings": {
            "CustomImages": [{
                "ImageName": "'"$IMAGE_NAME"'",
                "AppImageConfigName": "'"${IMAGE_NAME}-jl"'"
            }]
        },
        "CodeEditorAppSettings": {
            "CustomImages": [{
                "ImageName": "'"$IMAGE_NAME"'",
                "AppImageConfigName": "'"${IMAGE_NAME}-ce"'"
            }]
        }
    }'
```

### Unified Studio

The SageMaker AI(SMAI) domain is provisioned automatically when you create SageMaker Unified Studio(SMUS) Project.  To identify the matching SMAI domain id to your SMUS Project,  run this command:

```bash
aws sagemaker list-domains --output table
```
Unified Studio created SMAI domain have SMUS ProjectId as second level qualifier as shown below:
SageMakerUnifiedStudio-<smus-project-id>-xxxx

```bash
export UNIFIED_DOMAIN_ID=d-xxxxxxxxxxxx    # change to your Unified Studio domain ID

aws sagemaker update-domain \
    --domain-id $UNIFIED_DOMAIN_ID \
    --region $AWS_REGION \
    --default-user-settings '{
        "JupyterLabAppSettings": {
            "CustomImages": [{
                "ImageName": "'"$IMAGE_NAME"'",
                "AppImageConfigName": "'"${IMAGE_NAME}-unified-jl"'"
            }]
        },
        "CodeEditorAppSettings": {
            "CustomImages": [{
                "ImageName": "'"$IMAGE_NAME"'",
                "AppImageConfigName": "'"${IMAGE_NAME}-ce"'"
            }]
        }
    }'
```

## Updating your image

After changing `requirements.txt` or the Dockerfile, rebuild and push a new version:

```bash
docker build --platform linux/amd64 -t $IMAGE_NAME .
docker tag $IMAGE_NAME $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest

aws sagemaker create-image-version \
    --image-name $IMAGE_NAME \
    --base-image $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest \
    --region $AWS_REGION
```

You do not need to re-create the AppImageConfig or re-attach to the domain. Restart any running spaces to pick up the new version.

## Validate

After launching a space with your custom image:

```bash
python validate.py
```

## Troubleshooting

### Common failures

| Symptom | Cause | Fix |
|---------|-------|-----|
| `InternalFailure`, no further detail | Image built on ARM (Apple Silicon) without `--platform linux/amd64` | Rebuild with `docker build --platform linux/amd64` |
| `InternalFailure` on Studio V2 JupyterLab | Missing `--ServerApp.ip=0.0.0.0` or `--ServerApp.token=` in ContainerArguments | Add both args to the `-jl` AppImageConfig |
| `InternalFailure` on Unified Studio JupyterLab | Used `jupyter-lab` entrypoint instead of `entrypoint-sagemaker-ui-jupyter-server` | Create a separate AppImageConfig with the correct entrypoint |
| App stuck in "Pending" on Unified Studio, then fails | Missing VPC interface endpoints (Unified Studio domains are VpcOnly) | Create endpoints for `sagemaker.api`, `sts`, `sagemaker.runtime`, and `logs` in the domain's VPC with its security group |
| `ImportError` at runtime for numpy, catboost, or sagemaker SDK | numpy upgraded to 2.x by a transitive dependency | Pin `numpy==1.26.4` in `requirements.txt` |
| Image builds but packages fail to import | Overriding AWS SDK packages (boto3, botocore, sagemaker) | Remove them from `requirements.txt` — use the base image versions |
| `docker push` goes to wrong ECR repo in zsh | zsh interprets `$VAR:latest` as history modifier `:l` + literal `atest` | Use `${VAR}:latest` (curly braces) |

### Reading container logs

When an app fails, check CloudWatch:

- **Log group**: `/aws/sagemaker/studio`
- **Log stream**: `<domain-id>/<space-name>/<app-type>/default`

What to look for:
- `Environment is Environment.STUDIO_IAM` — confirms Studio V2 detected correctly
- `Environment is Environment.MD_IAM` — confirms Unified Studio detected correctly
- `Serving notebooks from local directory` — JupyterLab started successfully
- `received signal 15` — SageMaker killed the container after health check timeout

## Clean up

Delete resources in reverse order to avoid dependency errors:

```bash
# 1. Delete any running apps and spaces first (via the Studio console or CLI)

# 2. Remove the image from domain(s)
aws sagemaker update-domain \
    --domain-id $STUDIO_DOMAIN_ID \
    --region $AWS_REGION \
    --default-user-settings '{
        "JupyterLabAppSettings": { "CustomImages": [] },
        "CodeEditorAppSettings": { "CustomImages": [] }
    }'

# 3. Delete AppImageConfigs
aws sagemaker delete-app-image-config --app-image-config-name ${IMAGE_NAME}-jl --region $AWS_REGION
aws sagemaker delete-app-image-config --app-image-config-name ${IMAGE_NAME}-ce --region $AWS_REGION
aws sagemaker delete-app-image-config --app-image-config-name ${IMAGE_NAME}-unified-jl --region $AWS_REGION

# 4. Delete image version and image
aws sagemaker delete-image-version --image-name $IMAGE_NAME --version-number 1 --region $AWS_REGION
aws sagemaker delete-image --image-name $IMAGE_NAME --region $AWS_REGION

# 5. Delete the ECR repository if no longer needed
aws ecr delete-repository --repository-name $ECR_REPO --region $AWS_REGION --force
```

## Related resources

- [Custom image specs for Studio V2](https://docs.aws.amazon.com/sagemaker/latest/dg/studio-updated-byoi-specs.html)
- [Dockerfile specs for Unified Studio](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/byoi-specifications.html)
- [SageMaker Distribution on GitHub](https://github.com/aws/sagemaker-distribution)
