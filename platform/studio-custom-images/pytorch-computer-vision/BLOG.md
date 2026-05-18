# How to Create Custom Images for Amazon SageMaker Studio and Unified Studio

## Introduction

Amazon SageMaker Studio provides managed JupyterLab and Code Editor environments for machine learning development. Out of the box, these environments come with the SageMaker Distribution image — a curated set of ML frameworks, data science libraries, and IDEs. But real-world ML teams often need specialized packages, pinned versions, or domain-specific tooling that goes beyond what the default image provides.

A **custom image** is a Docker container that you build, push to Amazon ECR, and register with SageMaker so it appears as a selectable environment in the Studio console. When a user creates a new JupyterLab or Code Editor space, they pick your custom image instead of the default, and their environment launches with everything pre-installed.

### Why customers need custom images

- **Reproducibility** — Pin exact package versions so every team member gets the same environment. No more "works on my machine" caused by `%pip install` pulling different versions on different days.
- **Startup speed** — Pre-installing heavy packages (PyTorch, TensorFlow, CUDA libraries, large model frameworks) eliminates the 3-10 minute `pip install` wait at the start of every session.
- **Governance and compliance** — Lock down which packages are available, ensure only approved versions are used, and scan images for CVEs before deployment.
- **Domain specialization** — Computer vision teams need albumentations and YOLO. NLP teams need transformers and tokenizers. Genomics teams need biopython and pysam. One image doesn't fit all.
- **Consistency across platforms** — A single custom image can work across SageMaker Studio V2 and Unified Studio, on both JupyterLab and Code Editor, giving teams a unified experience regardless of which platform they use.

### Key benefits

| Benefit | Without custom images | With custom images |
|---------|----------------------|-------------------|
| Environment setup time | 3-10 min per session | 0 min (pre-installed) |
| Version consistency | Varies by user/day | Identical for all users |
| Security scanning | Manual, per-user | Centralized, automated |
| Onboarding new team members | Share install scripts | Select image, start working |
| Multi-platform support | Separate configs per platform | One image, multiple configs |

## Solution Overview

The custom image creation process follows a build-once, deploy-everywhere pattern. You build a single Docker image and register it with SageMaker using different configurations for each platform and IDE combination.

### Architecture and Workflow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Custom Image Creation Workflow                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────────────────────────┐
│              │     │              │     │         Amazon ECR               │
│  Dockerfile  │────▶│ Docker Build │────▶│                                  │
│  + requirements    │ (linux/amd64)│     │  pytorch-cv:latest               │
│              │     │              │     │  (single image, all platforms)   │
└──────────────┘     └──────────────┘     └───────────────┬──────────────────┘
                                                          │
                                                          ▼
                                          ┌───────────────────────────────┐
                                          │       SageMaker Image         │
                                          │    (named pointer resource)   │
                                          └───────────────┬───────────────┘
                                                          │
                                                          ▼
                                          ┌───────────────────────────────┐
                                          │       Image Version           │
                                          │  (links ECR digest to Image)  │
                                          └───────────────┬───────────────┘
                                                          │
                              ┌────────────────────────────┼────────────────────────────┐
                              │                            │                            │
                              ▼                            ▼                            ▼
                ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
                │  AppImageConfig     │    │  AppImageConfig     │    │  AppImageConfig     │
                │  (Studio V2 - JL)   │    │  (Code Editor)      │    │  (Unified - JL)     │
                │                     │    │                     │    │                     │
                │  Entry: jupyter-lab │    │  Entry: entrypoint- │    │  Entry: entrypoint- │
                │  + ip, token args   │    │  code-editor        │    │  sagemaker-ui-      │
                │                     │    │                     │    │  jupyter-server     │
                └──────────┬──────────┘    └──────────┬──────────┘    └──────────┬──────────┘
                           │                          │                          │
                           ▼                          ▼                          ▼
                ┌─────────────────────────────────────────────────────────────────────────┐
                │                     SageMaker Domain (update-domain)                    │
                │                                                                         │
                │   ┌─────────────────────┐              ┌─────────────────────┐          │
                │   │   Studio V2 Domain  │              │ UnifiedStudio Domain│          │
                │   │                     │              │                     │          │
                │   │  JupyterLab: -jl    │              │  JupyterLab: -unified-jl       │
                │   │  Code Editor: -ce   │              │  Code Editor: -ce   │          │
                │   └─────────────────────┘              └─────────────────────┘          │
                └─────────────────────────────────────────────────────────────────────────┘
                                                    │
                                                    ▼
                                    ┌───────────────────────────────┐
                                    │     Users select image in     │
                                    │     Studio Space creation     │
                                    └───────────────────────────────┘
```

### Workflow Steps

1. **Author** — Write a Dockerfile extending the SageMaker Distribution base image and a `requirements.txt` with your packages.
2. **Build** — Build the Docker image for `linux/amd64` architecture.
3. **Push** — Push to an Amazon ECR repository in your account.
4. **Register** — Create a SageMaker Image, Image Version, and AppImageConfigs.
5. **Attach** — Update your SageMaker domain(s) to make the image available to users.
6. **Use** — Users select the image when creating a new JupyterLab or Code Editor space.

## Solution Components

### SageMaker Distribution Base Image

The foundation of every custom image. SageMaker Distribution (`public.ecr.aws/sagemaker/sagemaker-distribution`) is a curated Docker image maintained by AWS that includes:

- **Deep learning frameworks**: PyTorch, TensorFlow, Keras
- **Data science libraries**: NumPy, Pandas, scikit-learn, Matplotlib
- **IDE infrastructure**: JupyterLab, Code Editor entrypoints, SageMaker extensions
- **AWS SDKs**: boto3, SageMaker Python SDK, AWS CLI
- **Platform entrypoints**: Scripts that handle authentication and configuration for both Studio V2 and Unified Studio

Using this base image is **required** for Unified Studio compatibility. It ships the `entrypoint-sagemaker-ui-jupyter-server` and `entrypoint-code-editor` scripts that handle Unified Studio's authentication model (MD_IAM).

### Amazon ECR (Elastic Container Registry)

Your private container registry where the built image is stored. SageMaker pulls the image from ECR when launching a space. The SageMaker execution role needs ECR pull permissions (`ecr:GetDownloadUrlForLayer`, `ecr:BatchGetImage`, `ecr:BatchCheckLayerAvailability`).

### SageMaker Image

A named resource that acts as a logical container for image versions. Think of it as a pointer — it doesn't contain the actual Docker image, but references versions that do. You create it once and it persists across image updates.

### Image Version

Links a specific ECR image digest to the SageMaker Image. Each time you rebuild and push your Docker image, you create a new Image Version. SageMaker uses the latest version by default. This provides an audit trail of all image iterations.

### AppImageConfig

The critical configuration that tells SageMaker **how to run** your container. It specifies:

- **ContainerEntrypoint** — Which binary to execute when the container starts
- **ContainerArguments** — Command-line arguments passed to the entrypoint

This is the component that enables a single Docker image to work across multiple platforms and IDEs. You create different AppImageConfigs with different entrypoints:

| AppImageConfig | Entrypoint | Platform + IDE |
|---------------|-----------|----------------|
| `pytorch-cv-jl` | `jupyter-lab` | Studio V2 JupyterLab |
| `pytorch-cv-ce` | `entrypoint-code-editor` | Both platforms, Code Editor |
| `pytorch-cv-unified-jl` | `entrypoint-sagemaker-ui-jupyter-server` | Unified Studio JupyterLab |

### Domain Attachment

An `update-domain` API call that makes your image selectable in the Studio console. You specify which AppImageConfig to use for JupyterLab and Code Editor within the domain's default user settings. Different domains (Studio V2 vs Unified Studio) reference different AppImageConfigs for JupyterLab but share the same one for Code Editor.

## Custom Image Example: PyTorch Computer Vision

This walkthrough creates a custom image with PyTorch computer vision libraries (albumentations, timm, ultralytics) that works on both SageMaker Studio V2 and Unified Studio.

### Prerequisites

- AWS CLI v2 installed and configured
- Docker installed and running
- A SageMaker execution role with ECR pull permissions
- A SageMaker domain (Studio V2, Unified Studio, or both)

### Step 1: Create the project structure

```
pytorch-computer-vision/
├── Dockerfile
├── requirements.txt
└── verify_image.ipynb
```

### Step 2: Define your dependencies

Create `requirements.txt` with the packages your team needs:

```text
albumentations==1.4.3
timm==1.0.3
ultralytics==8.3.40

# Pin numpy to the version in the base image to avoid breaking
# sagemaker SDK, autogluon, catboost, and other pre-installed packages
numpy==1.26.4
```

**Important constraints:**
- Always pin `numpy` to match the base image version (1.26.4 for sagemaker-distribution 3.5.1). Many pre-installed packages have `numpy<2` upper bounds.
- Do not include `boto3`, `botocore`, or `sagemaker` — use the base image versions.
- Pin all packages to exact versions for reproducibility.

### Step 3: Write the Dockerfile

```dockerfile
# PyTorch Computer Vision Custom Image for SageMaker
# Works with: Studio V2 and Unified Studio (JupyterLab & Code Editor)
#
# Single image for all platforms -- entrypoint is configured via AppImageConfig:
#   Studio V2 JupyterLab:       ["jupyter-lab"]
#   Unified Studio JupyterLab:  ["entrypoint-sagemaker-ui-jupyter-server"]
#   Code Editor (both):         ["entrypoint-code-editor"]

FROM public.ecr.aws/sagemaker/sagemaker-distribution:3.5.1-cpu

ARG NB_USER="sagemaker-user"
ARG NB_UID=1000
ARG NB_GID=100

USER root

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

USER $NB_USER

# Do NOT add ENTRYPOINT -- configured via AppImageConfig at attach time
```

Key design decisions:
- **No ENTRYPOINT** — The entrypoint varies by platform. Leaving it unset allows each AppImageConfig to specify the correct one.
- **USER root → USER $NB_USER** — Root is needed for package installation, but SageMaker expects the container to run as non-root.
- **`--no-cache-dir`** — Reduces image size by not caching pip downloads.

### Step 4: Set environment variables

```bash
export AWS_REGION=us-west-2
export ECR_REPO=sagemaker-custom-images/pytorch-cv
export IMAGE_NAME=pytorch-cv
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "Account: $AWS_ACCOUNT_ID  Region: $AWS_REGION  Repo: $ECR_REPO"
```

### Step 5: Build and push to ECR

```bash
# Create ECR repository
aws ecr create-repository --repository-name $ECR_REPO --region $AWS_REGION || true

# Authenticate to public ECR (for pulling the base image)
aws ecr-public get-login-password --region us-east-1 | \
    docker login --username AWS --password-stdin public.ecr.aws

# Build the image (--platform linux/amd64 is required on Apple Silicon)
docker build --platform linux/amd64 -t $IMAGE_NAME .

# Authenticate to your private ECR
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push
docker tag $IMAGE_NAME \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest
docker push \
    $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest
```

### Step 6: Register with SageMaker

```bash
export ROLE_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:role/YourSageMakerRole"

# Create the SageMaker Image (a named pointer resource)
aws sagemaker create-image \
    --image-name $IMAGE_NAME \
    --role-arn $ROLE_ARN \
    --region $AWS_REGION

# Create an Image Version (links ECR digest to the SageMaker Image)
aws sagemaker create-image-version \
    --image-name $IMAGE_NAME \
    --base-image $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest \
    --region $AWS_REGION
```

### Step 7: Create AppImageConfigs

Each AppImageConfig defines how to launch the container for a specific platform and IDE combination.

**Studio V2 — JupyterLab:**

```bash
aws sagemaker create-app-image-config \
    --app-image-config-name ${IMAGE_NAME}-jl \
    --jupyter-lab-app-image-config '{
        "ContainerConfig": {
            "ContainerEntrypoint": ["jupyter-lab"],
            "ContainerArguments": [
                "--ServerApp.base_url=/jupyterlab/default",
                "--ServerApp.ip=0.0.0.0",
                "--ServerApp.token=",
                "--no-browser"
            ]
        }
    }' \
    --region $AWS_REGION
```

Why these arguments:
- `--ServerApp.ip=0.0.0.0` — SageMaker's health check connects over the network, not localhost
- `--ServerApp.token=` — Health check doesn't pass authentication tokens
- `--no-browser` — Container has no display

**Code Editor (works on both platforms):**

```bash
aws sagemaker create-app-image-config \
    --app-image-config-name ${IMAGE_NAME}-ce \
    --code-editor-app-image-config '{
        "ContainerConfig": {
            "ContainerEntrypoint": ["entrypoint-code-editor"]
        }
    }' \
    --region $AWS_REGION
```

**Unified Studio — JupyterLab:**

```bash
aws sagemaker create-app-image-config \
    --app-image-config-name ${IMAGE_NAME}-unified-jl \
    --jupyter-lab-app-image-config '{
        "ContainerConfig": {
            "ContainerEntrypoint": ["entrypoint-sagemaker-ui-jupyter-server"]
        }
    }' \
    --region $AWS_REGION
```

This entrypoint handles Unified Studio's authentication model (MD_IAM). Using `jupyter-lab` directly on Unified Studio causes `InternalFailure`.

### Step 8: Attach to your domain(s)

**For Studio V2:**

```bash
export STUDIO_DOMAIN_ID=d-xxxxxxxxxxxx   # your Studio V2 domain ID

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

**For Unified Studio:**

First, find the SageMaker AI domain ID that corresponds to your Unified Studio project. Unified Studio automatically provisions a SageMaker domain when you create a project. The domain name follows the pattern `SageMakerUnifiedStudio-<project-id>-xxxx`:

```bash
aws sagemaker list-domains --output table
```

Then attach:

```bash
export UNIFIED_DOMAIN_ID=d-xxxxxxxxxxxx   # your Unified Studio domain ID

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

### Step 9: Verify the image

After launching a space with your custom image, run the verification notebook to confirm all packages are installed correctly:

```python
import torch
import torchvision
import albumentations
import timm
import ultralytics
import numpy as np
import sagemaker

print(f"PyTorch: {torch.__version__}")
print(f"Torchvision: {torchvision.__version__}")
print(f"Albumentations: {albumentations.__version__}")
print(f"TIMM: {timm.__version__}")
print(f"Ultralytics: {ultralytics.__version__}")
print(f"NumPy: {np.__version__}")
print(f"SageMaker SDK: {sagemaker.__version__}")

# Quick functional test
model = timm.create_model("resnet18", pretrained=False, num_classes=10)
model.eval()
dummy_input = torch.randn(1, 3, 224, 224)
with torch.no_grad():
    output = model(dummy_input)
print(f"\nResNet18 inference test: input {dummy_input.shape} → output {output.shape}")
print("✅ Custom image verified successfully")
```

### Updating your image

When you need to add packages or update versions, the workflow is simple:

```bash
# Edit requirements.txt, then:
docker build --platform linux/amd64 -t $IMAGE_NAME .
docker tag $IMAGE_NAME $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest
docker push $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest

aws sagemaker create-image-version \
    --image-name $IMAGE_NAME \
    --base-image $AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com/${ECR_REPO}:latest \
    --region $AWS_REGION
```

No need to re-create AppImageConfigs or re-attach to domains. Just restart running spaces to pick up the new version.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `InternalFailure` with no detail | Image built on ARM without `--platform linux/amd64` | Rebuild with the platform flag |
| `InternalFailure` on Studio V2 JupyterLab | Missing `--ServerApp.ip=0.0.0.0` or `--ServerApp.token=` | Add both args to the `-jl` AppImageConfig |
| `InternalFailure` on Unified Studio JupyterLab | Used `jupyter-lab` entrypoint instead of `entrypoint-sagemaker-ui-jupyter-server` | Use the correct entrypoint in the `-unified-jl` config |
| App stuck in "Pending" then fails (Unified Studio) | Missing VPC interface endpoints | Create endpoints for `sagemaker.api`, `sts`, `sagemaker.runtime`, `logs` |
| `ImportError` for numpy or SageMaker SDK | numpy upgraded to 2.x by a transitive dependency | Pin `numpy==1.26.4` |
| `UnpicklingError` loading model weights | PyTorch 2.6+ defaults to `weights_only=True` | Upgrade ultralytics to 8.3+ or the affected library |

### Reading container logs

When debugging failures, check CloudWatch Logs:
- **Log group**: `/aws/sagemaker/studio`
- **Log stream**: `<domain-id>/<space-name>/<app-type>/default`

## Conclusion

Custom images for SageMaker Studio and Unified Studio solve the fundamental tension between standardization and specialization in ML teams. By building a single Docker image and configuring it with platform-specific AppImageConfigs, you get:

1. **One image, four platforms** — Studio V2 JupyterLab, Studio V2 Code Editor, Unified Studio JupyterLab, and Unified Studio Code Editor all served by the same Docker image.
2. **Zero-friction environments** — Team members select the image and start working immediately. No install scripts, no version mismatches, no wasted session time.
3. **Simple update path** — Rebuild, push, create a new version. Running spaces pick up changes on restart without any reconfiguration.

### Key insights

- The **AppImageConfig** is the critical differentiator between platforms — not the Docker image itself. This is the design insight that enables the single-image approach.
- **Never set ENTRYPOINT in the Dockerfile.** Let AppImageConfig control it.
- **Pin numpy** to the base image version. This single constraint prevents the most common class of runtime failures.
- **Authenticate to public ECR** before building. The `403 Forbidden` error on the base image pull is the most common first-time stumbling block.

### Next steps

1. **Build your first image** using this example as a template. Start with your team's most-requested packages.
2. **Automate with CI/CD** — Add a CodePipeline or GitHub Actions workflow that rebuilds and pushes on every merge to main.
3. **Scan for vulnerabilities** — Enable ECR image scanning and set up notifications for critical CVEs.
4. **Create domain-specific images** — As your team grows, create specialized images (NLP, computer vision, tabular ML) rather than one monolithic image.

### Related resources

- [Custom image specifications for Studio V2](https://docs.aws.amazon.com/sagemaker/latest/dg/studio-updated-byoi-specs.html)
- [Dockerfile specifications for Unified Studio](https://docs.aws.amazon.com/sagemaker-unified-studio/latest/userguide/byoi-specifications.html)
- [SageMaker Distribution on GitHub](https://github.com/aws/sagemaker-distribution)
- [Source code for this example](https://github.com/aws-samples/genai-ml-platform-examples/tree/main/platform/studio-custom-images/pytorch-computer-vision)
