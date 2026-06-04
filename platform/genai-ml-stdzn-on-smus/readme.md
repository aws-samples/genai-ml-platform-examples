# Self-Deployment Guide

Deploy the SageMaker Unified Studio (SMUS) workshop infrastructure into your own AWS account. This guide covers two deployment scripts:

1. **`deploy.sh`** — Deploys the SMUS platform (VPC, IAM, Identity Center, Domain, AI Registry, Code Editor)
2. **`deploy-platform.sh`** — Deploys the MLOps AIOps platform (Lambda functions, Step Functions, EventBridge, GitHub OIDC integration)

## Prerequisites

### Required tools

| Tool | Version | Check command |
|------|---------|---------------|
| AWS CLI | v2+ | `aws --version` |
| Docker | Any | `docker --version` |
| Git | Any | `git --version` |
| zip | Any | `zip --version` |
| jq | Any | `jq --version` |

### AWS account requirements

- **IAM permissions**: AdministratorAccess (or equivalent broad permissions for CloudFormation, IAM, VPC, S3, Lambda, SageMaker, DataZone)
- **Region**: Must be a region where SageMaker Unified Studio is available (us-east-1, us-west-2, eu-west-1, etc.)
- **Service quotas**: Sufficient capacity for VPC, NAT Gateway, EC2, Lambda, DynamoDB
- **Identity Center**: If deploying Identity Center, the account must not already have an instance with the same name

### Configure AWS CLI

```bash
aws configure
# or use SSO:
aws sso login --profile your-profile
```

Verify access:

```bash
aws sts get-caller-identity
```

---

## Part 1: SMUS Platform Deployment (`deploy.sh`)

This script deploys the foundational SMUS infrastructure: VPC, IAM roles, Identity Center (optional), DataZone Domain, AI Registry, and Code Editor IDE.

### Step 1: Clone the repository

```bash
git clone https://github.com/aws-samples/genai-ml-platform-examples.git
cd genai-ml-platform-examples/platform/genai-ml-stdzn-on-smus
```

### Step 2: Make the script executable

```bash
chmod +x deploy.sh
```

### Step 3: Run the deployment

**Simplest deployment (new VPC, all components):**

```bash
./deploy.sh --region us-west-2
```

**Skip Identity Center (if you already have one or don't need it):**

```bash
./deploy.sh --region us-west-2 --skip-identity-center
```

**Use a custom VPC CIDR (avoid conflicts with existing VPCs):**

```bash
./deploy.sh --region us-west-2 --vpc-cidr 10.50.0.0/16 --skip-identity-center
```

**Use an existing VPC:**

```bash
./deploy.sh --region us-west-2 \
    --vpc-id vpc-0abc123 \
    --private-subnets subnet-aaa,subnet-bbb,subnet-ccc \
    --skip-identity-center
```

### Step 4: Wait for completion

The deployment takes **15-30 minutes**. The script provides progress updates and will exit with the Domain Portal URL on success.

### Step 5: Access the Domain

After deployment completes, the script outputs the Domain Portal URL. Open it in your browser to access SageMaker Unified Studio.

---

## Part 2: MLOps Platform Deployment (`deploy-platform.sh`)

This script deploys the AIOps/MLOps automation layer: GitHub integration, CI/CD pipelines, model approval workflows, and Lambda functions.

### Prerequisites (in addition to Part 1)

- **GitHub organization**: You need a GitHub org where deployment repositories will be created
- **GitHub Personal Access Token**: With `repo`, `workflow`, and `admin:org` scopes

### Step 1: Make the script executable

```bash
chmod +x deploy-platform.sh
```

### Step 2: Run the deployment

**Basic deployment:**

```bash
./deploy-platform.sh --region us-west-2 --github-org your-github-org
```

**If your account already has a GitHub OIDC provider:**

```bash
# Find existing OIDC provider ARN
aws iam list-open-id-connect-providers

# Deploy using existing provider
./deploy-platform.sh --region us-west-2 \
    --github-org your-github-org \
    --existing-oidc-arn "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
```

**Skip OIDC provider creation (if you'll set up GitHub integration later):**

```bash
./deploy-platform.sh --region us-west-2 \
    --github-org your-github-org \
    --no-oidc \
    --existing-oidc-arn "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
```

> **Important:** When using `--no-oidc`, you must provide `--existing-oidc-arn`. Omitting it causes an IAM error ("Federated principals must be valid domain names").

### Step 3: Store GitHub Token

After the stack deploys, store your GitHub Personal Access Token:

```bash
# Get the secret name from stack outputs
SECRET_NAME=$(aws cloudformation describe-stacks \
    --stack-name smus-aiops-platform \
    --region us-west-2 \
    --query "Stacks[0].Outputs[?OutputKey=='GitHubTokenSecretName'].OutputValue" \
    --output text)

# Store the token
aws secretsmanager put-secret-value \
    --secret-id "$SECRET_NAME" \
    --secret-string '{"github_token":"ghp_YOUR_TOKEN_HERE"}' \
    --region us-west-2
```

---

## Usage Reference

### `deploy.sh` options

| Option | Description | Default |
|--------|-------------|---------|
| `--region REGION` | AWS region to deploy into | `us-east-1` |
| `--stack-prefix PREFIX` | CloudFormation stack name prefix | `smus-workshop-v1` |
| `--domain-name NAME` | DataZone domain name | `smus-domain-orchestrated-v1` |
| `--vpc-cidr CIDR` | VPC CIDR block (when creating new VPC) | `10.38.0.0/16` |
| `--vpc-id VPC_ID` | Use existing VPC instead of creating one | — |
| `--private-subnets S1,S2,S3` | 3 comma-separated private subnet IDs (required with `--vpc-id`) | — |
| `--skip-identity-center` | Skip IAM Identity Center deployment | `false` |
| `--skip-code-editor` | Skip the Code Editor IDE stack | `false` |
| `--teardown` | Delete all deployed stacks and S3 bucket | — |
| `-h, --help` | Show help message | — |

### `deploy-platform.sh` options

| Option | Description | Default |
|--------|-------------|---------|
| `--region REGION` | AWS region | `us-east-1` |
| `--stack-name NAME` | CloudFormation stack name | `smus-aiops-platform` |
| `--project-prefix PREFIX` | Resource name prefix | `smus-aiops` |
| `--github-org ORG` | Private GitHub org for deployment repos (**required**) | — |
| `--lambda-repo-org ORG` | Public repo org for lambda source | `aws-samples` |
| `--lambda-repo-name NAME` | Public repo name for lambda source | `genai-ml-platform-examples` |
| `--lambda-repo-branch BRANCH` | Branch to pull lambda source from | `main` |
| `--no-oidc` | Don't create GitHub OIDC provider | `false` |
| `--existing-oidc-arn ARN` | Use existing OIDC provider ARN (required with `--no-oidc`) | — |
| `--teardown` | Delete stack and clean up | — |
| `-h, --help` | Show help message | — |

---

## Deployment Examples

### Minimal deployment (testing/evaluation)

```bash
# Deploy SMUS platform without Identity Center
./deploy.sh --region us-west-2 --skip-identity-center --skip-code-editor

# Deploy MLOps platform
./deploy-platform.sh --region us-west-2 --github-org my-org
```

### Full deployment (workshop-ready)

```bash
# Deploy everything
./deploy.sh --region us-west-2

# Deploy MLOps platform
./deploy-platform.sh --region us-west-2 --github-org my-org
```

### Enterprise deployment (existing infrastructure)

```bash
# Use existing VPC, skip Identity Center
./deploy.sh --region us-west-2 \
    --vpc-id vpc-0abc123def \
    --private-subnets subnet-111,subnet-222,subnet-333 \
    --skip-identity-center \
    --domain-name my-team-smus-domain

# Deploy MLOps with existing OIDC provider
./deploy-platform.sh --region us-west-2 \
    --github-org my-enterprise-org \
    --existing-oidc-arn "arn:aws:iam::123456789012:oidc-provider/token.actions.githubusercontent.com"
```

---

## What Gets Deployed

### `deploy.sh` creates:

| Stack | Resources |
|-------|-----------|
| `smus-workshop-v1-platform` | VPC (3 AZs, NAT Gateway), IAM roles (Domain Execution, Service, Provisioning, ManageAccess), Identity Center (optional), DataZone Domain, Project Profiles, Blueprints |
| `smus-workshop-v1-airegistry` | DynamoDB tables, Lambda functions, API Gateway, CloudFront distribution for AI Registry UI |
| `smus-workshop-v1-code-editor` | EC2 instance, CloudFront distribution for browser-based Code Editor |

### `deploy-platform.sh` creates:

| Stack | Resources |
|-------|-----------|
| `smus-aiops-platform` | GitHub OIDC provider, IAM roles (GitHub Workflow, EventBridge, Lambda, Step Functions), Lambda functions (project creation, repo sync, model approval), EventBridge rules, Step Functions state machine, Secrets Manager secret |

---

## Troubleshooting

### Common errors

| Error | Cause | Fix |
|-------|-------|-----|
| `Unresolved resource dependencies [IdentityCenterStack]` | Using `--skip-identity-center` with an older template version | Update to the latest template (the `DependsOn` has been fixed) |
| `route table and network gateway belong to different networks` | Stale resources from a previous failed deployment | Run `--teardown`, clean up orphaned IGWs, then redeploy |
| `Federated principals must be valid domain names` | Using `--no-oidc` without `--existing-oidc-arn` | Provide the existing OIDC provider ARN |
| `Stack already exists` | Previous deployment wasn't fully cleaned up | Delete the stack manually or use `--teardown` first |
| `Bucket already exists` | Previous deployment left the assets bucket | The script handles this gracefully (reuses existing bucket) |
| `NAT Gateway limit exceeded` | Account quota reached | Request a quota increase or use an existing VPC |
| `InsufficientCapacity` for EC2 (Code Editor) | Instance type not available in AZ | Skip Code Editor (`--skip-code-editor`) or try a different region |

### Checking stack status

```bash
# List all workshop stacks
aws cloudformation list-stacks \
    --stack-status-filter CREATE_COMPLETE CREATE_IN_PROGRESS CREATE_FAILED ROLLBACK_COMPLETE \
    --region us-west-2 \
    --query "StackSummaries[?contains(StackName, 'smus')]"

# Get failure reason for a specific stack
aws cloudformation describe-stack-events \
    --stack-name smus-workshop-v1-platform \
    --region us-west-2 \
    --query "StackEvents[?ResourceStatus=='CREATE_FAILED'].[LogicalResourceId,ResourceStatusReason]" \
    --output table
```

### Viewing nested stack failures

The orchestrator stack uses nested stacks. To find the actual failure:

```bash
# List nested stacks
aws cloudformation list-stack-resources \
    --stack-name smus-workshop-v1-platform \
    --region us-west-2 \
    --query "StackResourceSummaries[?ResourceType=='AWS::CloudFormation::Stack']"

# Then describe events on the failed nested stack
aws cloudformation describe-stack-events \
    --stack-name <nested-stack-id> \
    --region us-west-2 \
    --query "StackEvents[?ResourceStatus=='CREATE_FAILED']"
```

---

## Clean Up

### Remove all resources

```bash
# Tear down MLOps platform
./deploy-platform.sh --teardown --region us-west-2

# Tear down SMUS platform (VPC, Domain, AI Registry, Code Editor)
./deploy.sh --teardown --region us-west-2
```

### Manual cleanup (if teardown fails)

If CloudFormation can't delete a stack (e.g., non-empty S3 bucket, active DataZone domain):

```bash
# 1. Empty any S3 buckets created by the stacks
aws s3 rm s3://smus-workshop-v1-assets-123456789012-us-west-2 --recursive

# 2. Delete DataZone domain (if stack deletion fails on it)
aws datazone delete-domain --identifier <domain-id> --region us-west-2

# 3. Force-delete the stuck stack
aws cloudformation delete-stack \
    --stack-name smus-workshop-v1-platform \
    --region us-west-2 \
    --retain-resources <resource-that-cant-be-deleted>
```

---

## Estimated Costs

| Component | Approximate cost |
|-----------|-----------------|
| VPC (NAT Gateway) | ~$1.08/day |
| EC2 (Code Editor, t3.medium) | ~$1.00/day |
| DataZone Domain | No charge (pay per project/user activity) |
| Lambda functions | Negligible (invocation-based) |
| S3 (assets) | < $0.10/month |
| DynamoDB (AI Registry) | < $1.00/month (on-demand) |

**Total estimated cost**: ~$2-3/day when idle, primarily from NAT Gateway and EC2.

To minimize costs when not in use:
- Use `--skip-code-editor` if you don't need the browser-based IDE
- Stop the EC2 instance when not in use
- Tear down the full environment when done evaluating

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         deploy.sh creates:                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │
│  │     VPC      │  │   IAM Roles  │  │  Identity    │                  │
│  │  (3 AZs,    │  │  (Domain,    │  │  Center      │                  │
│  │   NAT GW)   │  │   Service,   │  │  (optional)  │                  │
│  │             │  │   Provision)  │  │              │                  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                  │
│         │                  │                  │                          │
│         └──────────────────┼──────────────────┘                          │
│                            ▼                                             │
│                 ┌──────────────────────┐                                 │
│                 │   DataZone Domain    │                                 │
│                 │ (SageMaker Unified   │                                 │
│                 │      Studio)         │                                 │
│                 └──────────────────────┘                                 │
│                                                                          │
│  ┌──────────────────────┐    ┌──────────────────────┐                   │
│  │    AI Registry       │    │    Code Editor        │                   │
│  │  (DynamoDB + Lambda  │    │  (EC2 + CloudFront)   │                   │
│  │   + API Gateway)     │    │                       │                   │
│  └──────────────────────┘    └──────────────────────┘                   │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                     deploy-platform.sh creates:                           │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐          │
│  │ GitHub OIDC  │  │  Lambda Fns  │  │   Step Functions     │          │
│  │  Provider    │  │ (create repo,│  │   (MLOps Pipeline    │          │
│  │             │  │  sync, model │  │    Orchestration)    │          │
│  │             │  │  approval)   │  │                      │          │
│  └──────────────┘  └──────────────┘  └──────────────────────┘          │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐          │
│  │ EventBridge  │  │   Secrets    │  │    IAM Roles         │          │
│  │   Rules      │  │   Manager   │  │  (GitHub Workflow,   │          │
│  │ (triggers)   │  │ (GH Token)  │  │   Lambda, StepFn)    │          │
│  └──────────────┘  └──────────────┘  └──────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────┘
```
