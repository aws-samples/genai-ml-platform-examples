# NVIDIA Parakeet EKS Demo Runbook

This runbook explains how to deploy, run, verify, and clean up the NVIDIA Parakeet fine-tuning demo on Amazon EKS. The demonstrated topology is one training pod using all four NVIDIA L40S GPUs on a single `g6e.12xlarge` managed node.

> [!WARNING]
> **Security warning:** The Kubernetes API endpoint is currently reachable from any internet address because `publicAccessCIDRs` is set to `0.0.0.0/0`. Authentication and authorization still apply, but network-level restriction is disabled. Restore a trusted `/32` CIDR as soon as unrestricted access is no longer required.

## What the demo does

1. Creates or uses an EKS cluster in Seoul (`ap-northeast-2`).
2. Runs system workloads on `m7i.large` nodes.
3. Runs training on one tainted and labeled `g6e.12xlarge` node.
4. Installs the NVIDIA device plugin and verifies four GPUs are allocatable.
5. Creates an encrypted 200 GiB gp3 PVC.
6. Downloads and prepares the French FLEURS dataset on the PVC.
7. Fine-tunes `nvidia/parakeet-tdt-0.6b-v2` for one epoch with four local DDP ranks.
8. Persists logs, TensorBoard events, checkpoints, and the final `.nemo` model.

The default Job is a smoke test, not a production training configuration. It has a six-hour deadline and uses one epoch.

## Validated reference environment

| Component | Validated value |
|---|---|
| AWS Region | `ap-northeast-2` |
| EKS cluster | `parakeet-demo` |
| Kubernetes | `1.35` |
| GPU node group | `gpu-g6e` |
| GPU instance | `g6e.12xlarge` with four L40S GPUs |
| System node group | `system`, two `m7i.large` nodes |
| Storage | Encrypted 200 GiB gp3 PVC |
| Container architecture | Linux AMD64 |
| Training | One pod, four GPUs, Lightning DDP |
| Dataset | FLEURS French: 3,193 train, 289 validation, 676 test samples |

## Prerequisites

Install and configure:

- AWS CLI with credentials for the target account
- `eksctl`
- `kubectl`
- Helm 3
- Docker with Buildx
- Git

Your AWS principal needs permissions for EKS, EC2/VPC, IAM, ECR, EBS, and related CloudFormation stacks. Confirm sufficient `g6e.12xlarge` quota and regional capacity before cluster creation.

Run commands from the project directory:

```bash
cd infrastructure/nvidia-parakeet-model-fine-tuning
export AWS_REGION=ap-northeast-2
export CLUSTER_NAME=parakeet-demo
aws sts get-caller-identity
```

## Fast path: rerun the existing validated environment

Use this path when the `parakeet-demo` cluster and `eks-demo-v5` image already exist in account `412381761882`.

The deployment script deletes and recreates the training Job but preserves the PVC, prepared dataset, previous experiments, and trained models.

```bash
aws eks update-kubeconfig \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION"

export IMAGE_URI="412381761882.dkr.ecr.ap-northeast-2.amazonaws.com/parakeet-fine-tuning:eks-demo-v5"

kubectl get nodes -L node.kubernetes.io/instance-type,workload,topology.kubernetes.io/zone
kubectl get pvc -n parakeet-demo

IMAGE_URI="$IMAGE_URI" \
CLUSTER_NAME="$CLUSTER_NAME" \
REGION="$AWS_REGION" \
  deployment/eks/deploy-training.sh
```

The EKS public endpoint is currently open to `0.0.0.0/0` for unrestricted demo access. This removes network-level filtering; restore a trusted `/32` as soon as broad access is no longer required.

## Full deployment: start from the cluster configuration

### Step 1: review the account-specific cluster values

Open `deployment/eks/cluster.yaml` and verify:

- `metadata.region` is `ap-northeast-2`.
- The requested Kubernetes version is available.
- The VPC ID belongs to the target account.
- Both subnet IDs belong to that VPC and their availability zones match the map keys.
- The API `publicAccessCIDRs` value is a trusted `/32` source address.
- The account has quota for one `g6e.12xlarge` and two `m7i.large` instances.

The checked-in VPC, subnets, and API CIDR are specific to the validated environment. Do not reuse them in another account without replacing them.

### Step 2: create the EKS cluster

```bash
eksctl create cluster --config-file deployment/eks/cluster.yaml
aws eks update-kubeconfig \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION"
```

Cluster creation can take 20–40 minutes. Confirm the node groups and add-ons before building the image:

```bash
aws eks describe-nodegroup \
  --cluster-name "$CLUSTER_NAME" \
  --nodegroup-name system \
  --region "$AWS_REGION" \
  --query 'nodegroup.{status:status,scaling:scalingConfig,types:instanceTypes}'

aws eks describe-nodegroup \
  --cluster-name "$CLUSTER_NAME" \
  --nodegroup-name gpu-g6e \
  --region "$AWS_REGION" \
  --query 'nodegroup.{status:status,scaling:scalingConfig,types:instanceTypes}'

aws eks describe-addon \
  --cluster-name "$CLUSTER_NAME" \
  --addon-name aws-ebs-csi-driver \
  --region "$AWS_REGION" \
  --query 'addon.{status:status,version:addonVersion,issues:health.issues}'

kubectl get nodes -o wide
```

Both node groups and the EBS CSI add-on must be `ACTIVE`.

### Step 3: build and push a uniquely tagged image

The image is large, so build and push can take several minutes. Use a unique tag to prevent Kubernetes from reusing a cached image when `imagePullPolicy` is `IfNotPresent`.

```bash
export IMAGE_TAG="eks-demo-$(date +%Y%m%d-%H%M%S)"
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/parakeet-fine-tuning:${IMAGE_TAG}"

REGION="$AWS_REGION" \
IMAGE_TAG="$IMAGE_TAG" \
  ./build-and-push.sh
```

Verify the pushed image:

```bash
aws ecr describe-images \
  --region "$AWS_REGION" \
  --repository-name parakeet-fine-tuning \
  --image-ids "imageTag=$IMAGE_TAG" \
  --query 'imageDetails[0].{digest:imageDigest,size:imageSizeInBytes,pushed:imagePushedAt}'
```

### Step 4: deploy the training Job

```bash
IMAGE_URI="$IMAGE_URI" \
CLUSTER_NAME="$CLUSTER_NAME" \
REGION="$AWS_REGION" \
  deployment/eks/deploy-training.sh
```

The script performs these checks and actions:

1. Updates the local kubeconfig.
2. Requires an active EBS CSI add-on.
3. Installs NVIDIA device plugin chart `0.18.0` with the GPU-node toleration.
4. Waits for at least four allocatable GPUs.
5. Creates `parakeet-gp3` when absent, or validates and reuses a compatible existing immutable StorageClass.
6. Applies the namespace and PVC without replacing an existing bound volume.
7. Deletes an older Job with the same name.
8. Injects `IMAGE_URI` and creates the new Job.

The first run downloads FLEURS and the pretrained NVIDIA model, so the worker node needs outbound internet access. Later runs reuse the PVC caches and dataset.

## Monitor the run

Watch scheduling and startup:

```bash
kubectl get job,pod,pvc -n parakeet-demo -o wide
kubectl describe job parakeet-fine-tuning -n parakeet-demo
kubectl get events -n parakeet-demo --sort-by='.lastTimestamp'
```

Follow logs:

```bash
kubectl logs -f -n parakeet-demo job/parakeet-fine-tuning
```

Wait for completion in another terminal:

```bash
kubectl wait \
  --for=condition=complete \
  job/parakeet-fine-tuning \
  -n parakeet-demo \
  --timeout=6h
```

A healthy run should show:

- Four ranks with `LOCAL_RANK` values `0` through `3`.
- The pretrained Parakeet model loading successfully.
- `267/267` steps for the validated one-epoch dataset and batch size.
- Validation WER output.
- `Trainer.fit stopped: max_epochs=1 reached`.
- `Last Epoch Model Saved to` followed by the persistent model path.

Confirm final state:

```bash
kubectl get job,pod,pvc -n parakeet-demo
kubectl logs -n parakeet-demo job/parakeet-fine-tuning --tail=100
```

Expected Job state is `Complete` with `1/1` completions and zero pod restarts.

## Verify and download artifacts

The completed container is no longer running, so mount the PVC in the supplied artifact pod:

```bash
kubectl delete pod parakeet-artifacts \
  -n parakeet-demo \
  --ignore-not-found
kubectl apply -f deployment/eks/artifact-pod.yaml
kubectl wait \
  --for=condition=Ready \
  pod/parakeet-artifacts \
  -n parakeet-demo \
  --timeout=5m
```

Inspect persistent files:

```bash
kubectl exec -n parakeet-demo parakeet-artifacts -- \
  ls -lh /workspace/experiments/trained_models

kubectl exec -n parakeet-demo parakeet-artifacts -- \
  find /workspace/experiments/French_ASR_Parakeet_Finetuning -type f

kubectl exec -n parakeet-demo parakeet-artifacts -- \
  tail -n 100 /workspace/training.log
```

Download the main model and log:

```bash
kubectl cp \
  parakeet-demo/parakeet-artifacts:/workspace/experiments/trained_models/French_ASR_Parakeet_Finetuning.nemo \
  ./French_ASR_Parakeet_Finetuning.nemo

kubectl cp \
  parakeet-demo/parakeet-artifacts:/workspace/training.log \
  ./training.log
```

The validated main model was 2,472,212,480 bytes. Check that the local file is non-empty before deleting any AWS storage:

```bash
ls -lh ./French_ASR_Parakeet_Finetuning.nemo ./training.log
```

Delete the temporary artifact pod when copying is complete:

```bash
kubectl delete pod parakeet-artifacts -n parakeet-demo
```

## View TensorBoard data

MLflow is disabled for this NeMo/Lightning combination. TensorBoard event files are stored under each timestamped experiment directory.

With the artifact pod running, copy the experiment directory:

```bash
kubectl cp \
  parakeet-demo/parakeet-artifacts:/workspace/experiments/French_ASR_Parakeet_Finetuning \
  ./French_ASR_Parakeet_Finetuning

tensorboard --logdir ./French_ASR_Parakeet_Finetuning
```

Open the local URL printed by TensorBoard. This demo does not expose TensorBoard through an EKS Service or public load balancer.

## Change the training settings

The Kubernetes smoke-test overrides are in `deployment/eks/training-job.yaml`:

```yaml
env:
  - {name: NUM_GPUS, value: "4"}
  - {name: MAX_EPOCHS, value: "1"}
  - {name: BATCH_SIZE, value: "3"}
```

For longer training, increase `MAX_EPOCHS`. If the run can exceed six hours, also increase `spec.activeDeadlineSeconds`.

Model architecture, optimizer, augmentation, data-loader, and checkpoint options are in `configs/fine_tuning_config.yaml`. If files copied into the container change, rebuild and push a new image tag before redeploying.

Keep `NUM_GPUS=4` for this topology. Lightning launches the four DDP workers; do not wrap `run-train.sh` in `accelerate launch`, `torchrun`, or another distributed launcher.

## Rerun behavior

Rerunning `deployment/eks/deploy-training.sh`:

- Deletes the existing `parakeet-fine-tuning` Job.
- Leaves the PVC and its previous outputs intact.
- Reuses the prepared FLEURS dataset when the train manifest exists.
- Appends new process output to `/workspace/training.log`.
- Creates a new timestamped NeMo experiment directory.
- Overwrites the main model path after successful training.

Copy any model version that must be preserved before another run overwrites the main model path.

## Troubleshooting

### `kubectl` times out

Check the EKS public endpoint allowlist:

```bash
aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --query 'cluster.resourcesVpcConfig.{public:endpointPublicAccess,private:endpointPrivateAccess,cidrs:publicAccessCidrs}'
```

If your trusted source address changed, update it and wait for the returned EKS update to reach `Successful`:

```bash
export TRUSTED_CIDR="YOUR.PUBLIC.IP.ADDRESS/32"
export UPDATE_ID="$(aws eks update-cluster-config \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --resources-vpc-config "endpointPublicAccess=true,endpointPrivateAccess=true,publicAccessCidrs=$TRUSTED_CIDR" \
  --query 'update.id' \
  --output text)"

aws eks describe-update \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --update-id "$UPDATE_ID"
```

### Pod remains `Pending`

```bash
kubectl describe pod -n parakeet-demo \
  -l app=parakeet-fine-tuning
kubectl get nodes \
  -L workload,node.kubernetes.io/instance-type,topology.kubernetes.io/zone
```

Common causes:

- No GPU node is ready.
- The GPU node does not have `workload=parakeet-training`.
- The `dedicated=parakeet-training:NoSchedule` toleration is missing.
- Fewer than four GPUs are allocatable.
- The bound EBS volume and available GPU node are in different availability zones.
- The pod requests more CPU or memory than the node can allocate.

### GPUs are not allocatable

```bash
kubectl get pods -n nvidia-device-plugin -o wide
kubectl describe daemonset nvidia-device-plugin \
  -n nvidia-device-plugin
kubectl get nodes -l workload=parakeet-training \
  -o jsonpath='{range .items[*]}{.metadata.name}{" GPUs="}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}'
```

The custom values file must retain the `dedicated=parakeet-training` toleration.

### PVC remains `Pending` or fails to mount

```bash
aws eks describe-addon \
  --cluster-name "$CLUSTER_NAME" \
  --addon-name aws-ebs-csi-driver \
  --region "$AWS_REGION"
kubectl get pods -n kube-system -l app=ebs-csi-controller
kubectl describe pvc parakeet-workspace -n parakeet-demo
```

The StorageClass uses `WaitForFirstConsumer`, so the PVC can remain pending until the training pod is scheduled. Once created, the EBS volume is tied to one availability zone.

### `ImagePullBackOff`

```bash
kubectl describe pod -n parakeet-demo \
  -l app=parakeet-fine-tuning
aws ecr describe-images \
  --region "$AWS_REGION" \
  --repository-name parakeet-fine-tuning
```

Verify the account, region, repository, tag, node IAM permissions, and generated `IMAGE_URI`.

### Job fails during training

```bash
kubectl get pods -n parakeet-demo
kubectl logs -n parakeet-demo job/parakeet-fine-tuning
kubectl describe job parakeet-fine-tuning -n parakeet-demo
```

The manifest already provides a 32 GiB memory-backed `/dev/shm` to avoid PyTorch data-loader shared-memory failures. The validated dependency pins in `requirements.txt` also avoid known NeMo TDT CUDA JIT and logger compatibility failures.

## Security checks

After deployment, verify the API endpoint is not globally exposed:

```bash
aws eks describe-cluster \
  --name "$CLUSTER_NAME" \
  --region "$AWS_REGION" \
  --query 'cluster.resourcesVpcConfig.publicAccessCidrs'
```

Expected output is one or more trusted CIDRs, not `0.0.0.0/0`. Also avoid placing AWS credentials, Hugging Face tokens, or other secrets directly in manifests or container images.

## Cost controls

The EKS control plane, three worker nodes, EBS volume, and ECR image storage are billable. The `g6e.12xlarge` is the largest compute cost.

To stop worker compute while preserving the cluster and PVC data:

```bash
aws eks update-nodegroup-config \
  --cluster-name "$CLUSTER_NAME" \
  --nodegroup-name gpu-g6e \
  --region "$AWS_REGION" \
  --scaling-config minSize=0,maxSize=1,desiredSize=0

aws eks update-nodegroup-config \
  --cluster-name "$CLUSTER_NAME" \
  --nodegroup-name system \
  --region "$AWS_REGION" \
  --scaling-config minSize=0,maxSize=2,desiredSize=0
```

Scaling system nodes to zero leaves the EKS control plane available but no nodes remain for Kubernetes workloads. EBS and EKS charges continue.

Before restoring the GPU node, ensure the node group can launch in the availability zone containing the bound PVC. Restore the validated capacity with:

```bash
aws eks update-nodegroup-config \
  --cluster-name "$CLUSTER_NAME" \
  --nodegroup-name system \
  --region "$AWS_REGION" \
  --scaling-config minSize=1,maxSize=2,desiredSize=2

aws eks update-nodegroup-config \
  --cluster-name "$CLUSTER_NAME" \
  --nodegroup-name gpu-g6e \
  --region "$AWS_REGION" \
  --scaling-config minSize=1,maxSize=1,desiredSize=1
```

## Cleanup

Delete only the Job while retaining artifacts:

```bash
kubectl delete job parakeet-fine-tuning \
  -n parakeet-demo \
  --ignore-not-found
```

Delete the PVC only after copying every required artifact. This permanently deletes the dataset, logs, caches, checkpoints, and models stored on the EBS volume:

```bash
kubectl delete pvc parakeet-workspace -n parakeet-demo
```

Delete the entire EKS environment when finished:

```bash
eksctl delete cluster --config-file deployment/eks/cluster.yaml
```

Optionally delete an image tag after it is no longer needed:

```bash
aws ecr batch-delete-image \
  --region "$AWS_REGION" \
  --repository-name parakeet-fine-tuning \
  --image-ids "imageTag=$IMAGE_TAG"
```

## Validated completion criteria

The demo is complete when all of these are true:

- The Job reports `Complete` and `1/1` completions.
- Four DDP ranks initialized.
- Training and validation completed without pod restarts.
- The log contains `max_epochs=1 reached`.
- The log contains `Last Epoch Model Saved to`.
- The main `.nemo` file exists and is non-empty.
- Timestamped checkpoint `.nemo` and `.ckpt` files exist.
- The API endpoint is restricted to trusted CIDRs.
- The artifact pod is deleted after file retrieval.

The validated run completed 267 training steps, reported `val_wer=0.84329`, and produced the main 2,472,212,480-byte `.nemo` model.