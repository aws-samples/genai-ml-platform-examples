# Fine-tuning NVIDIA Parakeet on Amazon EKS

This demo fine-tunes `nvidia/parakeet-tdt-0.6b-v2` on the French FLEURS dataset. One Kubernetes Job pod consumes all four NVIDIA L40S GPUs on one `g6e.12xlarge`; PyTorch Lightning launches four local DDP ranks.

For a detailed, command-by-command walkthrough, see [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md).

> [!WARNING]
> **Security warning:** The Kubernetes API endpoint is currently reachable from any internet address because `publicAccessCIDRs` is set to `0.0.0.0/0`. Authentication and authorization still apply, but network-level restriction is disabled. Restore a trusted `/32` CIDR as soon as unrestricted access is no longer required.

## Architecture

- Amazon EKS in `ap-northeast-2` with public and private API endpoints
- Two `m7i.large` system nodes and one managed `g6e.12xlarge` GPU node
- NVIDIA device plugin `0.18.0` exposing four `nvidia.com/gpu` resources
- EBS CSI driver and an encrypted 200 GiB gp3 PVC for datasets, caches, logs, checkpoints, and models
- One training pod requesting all four GPUs, 32 CPUs, 128 GiB memory, and a 32 GiB memory-backed `/dev/shm`
- NeMo `2.7.2`, PyTorch `2.10.0+cu128`, CUDA 12.8, and Lightning DDP

The checked-in Job is a one-epoch smoke run with a six-hour deadline. Increase `MAX_EPOCHS` in `deployment/eks/training-job.yaml` for a longer run.

## Files

```text
.
├── Dockerfile
├── build-and-push.sh
├── configs/fine_tuning_config.yaml
├── data_preparation_fleurs.py
├── download-and-prepare-fleurs.sh
├── requirements.txt
├── run-train.sh
├── trainer.py
└── deployment/eks/
    ├── artifact-pod.yaml
    ├── cluster.yaml
    ├── deploy-training.sh
    ├── nvidia-device-plugin-values.yaml
    ├── storage-class.yaml
    ├── storage.yaml
    └── training-job.yaml
```

## Prerequisites

- AWS CLI authenticated to the target account
- `eksctl`, `kubectl`, Helm, Docker, and Docker Buildx
- Permissions for EKS, EC2/VPC, IAM, ECR, and EBS resources
- `g6e.12xlarge` quota and capacity in Seoul

`deployment/eks/cluster.yaml` contains deployment-specific VPC, subnet, Kubernetes version, and API allowlist values. Replace them before creating a different cluster. Keep the public API CIDR restricted to trusted `/32` addresses; do not use `0.0.0.0/0` for normal operation.

## Deploy

Run all commands from this directory.

### 1. Create the cluster

```bash
eksctl create cluster --config-file deployment/eks/cluster.yaml
aws eks update-kubeconfig --name parakeet-demo --region ap-northeast-2
```

The cluster configuration creates a tainted GPU managed node group labeled `workload=parakeet-training`. The deployment script installs the matching NVIDIA device-plugin toleration.

### 2. Build and push the image

```bash
export REGION=ap-northeast-2
export IMAGE_TAG=eks-demo
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/parakeet-fine-tuning:${IMAGE_TAG}"
./build-and-push.sh
```

The script creates the ECR repository if needed, builds a Linux AMD64 image, and pushes the selected tag.

### 3. Start training

```bash
IMAGE_URI="$IMAGE_URI" deployment/eks/deploy-training.sh
```

The script verifies that the EBS CSI add-on is active, installs the NVIDIA device plugin, waits for four allocatable GPUs, creates or validates the immutable StorageClass, applies the namespace and PVC, and submits the Job. A compatible existing StorageClass and bound PVC are preserved on reruns. The first run downloads and prepares FLEURS on the PVC; later runs reuse it.

## Monitor

```bash
kubectl get job,pod,pvc -n parakeet-demo -o wide
kubectl logs -f -n parakeet-demo job/parakeet-fine-tuning
kubectl wait --for=condition=complete job/parakeet-fine-tuning \
  -n parakeet-demo --timeout=6h
```

Successful output includes four DDP ranks, completion of training and validation, and `Last Epoch Model Saved to`.

## Persistent outputs

The PVC contains:

- Main model: `/workspace/experiments/trained_models/French_ASR_Parakeet_Finetuning.nemo`
- NeMo checkpoints: `/workspace/experiments/French_ASR_Parakeet_Finetuning/<timestamp>/checkpoints/`
- TensorBoard event files: `/workspace/experiments/French_ASR_Parakeet_Finetuning/<timestamp>/`
- Combined training log: `/workspace/training.log`
- Prepared dataset: `/workspace/dataset/fleurs_french/`

A completed Job container cannot be used with `kubectl cp`. Mount the PVC in the artifact pod instead:

```bash
kubectl apply -f deployment/eks/artifact-pod.yaml
kubectl wait --for=condition=Ready pod/parakeet-artifacts \
  -n parakeet-demo --timeout=5m
kubectl exec -n parakeet-demo parakeet-artifacts -- \
  ls -lh /workspace/experiments/trained_models
kubectl cp \
  parakeet-demo/parakeet-artifacts:/workspace/experiments/trained_models/French_ASR_Parakeet_Finetuning.nemo \
  ./French_ASR_Parakeet_Finetuning.nemo
kubectl cp parakeet-demo/parakeet-artifacts:/workspace/training.log ./training.log
kubectl delete pod parakeet-artifacts -n parakeet-demo
```

MLflow is disabled for this NeMo/Lightning combination. TensorBoard events are enabled; copy the experiment directory locally and run `tensorboard --logdir <directory>` if desired.

## Configuration

Edit `configs/fine_tuning_config.yaml` for model, optimizer, data-loader, augmentation, and checkpoint settings. Runtime environment variables supported by the Job are:

- `NUM_GPUS` — defaults to `4`
- `MAX_EPOCHS` — defaults to `1` in the Job
- `BATCH_SIZE` — defaults to `3` in the Job
- `DATA_DIR`, `EXPERIMENT_DIR`, and `MODEL_PATH` — persistent `/workspace` paths

Lightning owns DDP process creation. Do not wrap `run-train.sh` in `accelerate launch` or another distributed launcher.

## Cost and cleanup

The two `m7i.large` nodes, one `g6e.12xlarge`, EBS volume, and EKS control plane are billable. Deleting only the Job preserves the PVC and trained model:

```bash
kubectl delete job parakeet-fine-tuning -n parakeet-demo --ignore-not-found
```

To stop compute while keeping the cluster and EBS data:

```bash
aws eks update-nodegroup-config --cluster-name parakeet-demo --nodegroup-name gpu-g6e \
  --region ap-northeast-2 --scaling-config minSize=0,maxSize=1,desiredSize=0
aws eks update-nodegroup-config --cluster-name parakeet-demo --nodegroup-name system \
  --region ap-northeast-2 --scaling-config minSize=0,maxSize=2,desiredSize=0
```

Before scaling the GPU group back up, ensure it can launch in the availability zone of the bound EBS volume. Restore the demo capacity with:

```bash
aws eks update-nodegroup-config --cluster-name parakeet-demo --nodegroup-name system \
  --region ap-northeast-2 --scaling-config minSize=1,maxSize=2,desiredSize=2
aws eks update-nodegroup-config --cluster-name parakeet-demo --nodegroup-name gpu-g6e \
  --region ap-northeast-2 --scaling-config minSize=1,maxSize=1,desiredSize=1
```

Deleting the PVC permanently deletes the dataset, logs, checkpoints, and trained model. Copy required artifacts first:

```bash
kubectl delete pvc parakeet-workspace -n parakeet-demo
```

Delete the entire environment only when it is no longer needed:

```bash
eksctl delete cluster --config-file deployment/eks/cluster.yaml
```

## Validated smoke run

The EKS workflow was validated in `ap-northeast-2` on one `g6e.12xlarge` with all four L40S GPUs. The one-epoch run completed 267 training steps, reported `val_wer=0.84329`, and produced a 2,472,212,480-byte main `.nemo` model plus NeMo checkpoint files.

## Authors

- Iman Abbasnejad (Applied Scientist, AWS)
- Faisal Masood (AppMod and Inferencing, AWS)
- Vincent Wang (GenAI Specailist SA, AWS)

## Acknowledgments

Based on NVIDIA NeMo and the NVIDIA Parakeet ASR models.
