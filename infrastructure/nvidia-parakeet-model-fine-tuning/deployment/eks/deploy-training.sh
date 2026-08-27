#!/usr/bin/env bash
set -euo pipefail

IMAGE_URI="${IMAGE_URI:?Set IMAGE_URI to the pushed ECR image URI}"
CLUSTER_NAME="${CLUSTER_NAME:-parakeet-demo}"
REGION="${REGION:-ap-northeast-2}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! "$IMAGE_URI" =~ ^[0-9]{12}\.dkr\.ecr\.[a-z0-9-]+\.amazonaws\.com/.+:[A-Za-z0-9_.-]+$ ]]; then
  echo "Invalid ECR IMAGE_URI: $IMAGE_URI" >&2
  exit 1
fi

for command in aws awk helm kubectl sed; do
  command -v "$command" >/dev/null || { echo "Required command not found: $command" >&2; exit 1; }
done

aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$REGION"

EBS_CSI_STATUS="$(aws eks describe-addon --cluster-name "$CLUSTER_NAME" --addon-name aws-ebs-csi-driver \
  --region "$REGION" --query 'addon.status' --output text 2>/dev/null || true)"
if [[ "$EBS_CSI_STATUS" != "ACTIVE" ]]; then
  echo "The aws-ebs-csi-driver add-on must be ACTIVE before deploying training (current: ${EBS_CSI_STATUS:-not installed})." >&2
  exit 1
fi

helm repo add nvdp https://nvidia.github.io/k8s-device-plugin >/dev/null 2>&1 || true
helm repo update nvdp
helm upgrade --install nvidia-device-plugin nvdp/nvidia-device-plugin \
  --namespace nvidia-device-plugin --create-namespace --version 0.18.0 \
  --values "$SCRIPT_DIR/nvidia-device-plugin-values.yaml" \
  --wait --timeout 10m

GPU_COUNT=0
for _ in {1..60}; do
  GPU_COUNT="$(kubectl get nodes -l workload=parakeet-training \
    -o jsonpath='{range .items[*]}{.status.allocatable.nvidia\.com/gpu}{"\n"}{end}' \
    | awk '{total += $1} END {print total + 0}')"
  [[ "$GPU_COUNT" -ge 4 ]] && break
  sleep 5
done
if [[ "$GPU_COUNT" -lt 4 ]]; then
  echo "Expected at least 4 allocatable GPUs, found $GPU_COUNT after 5 minutes." >&2
  exit 1
fi

STORAGE_CLASS_NAME="parakeet-gp3"
if kubectl get storageclass "$STORAGE_CLASS_NAME" >/dev/null 2>&1; then
  STORAGE_CLASS_CONFIG="$(kubectl get storageclass "$STORAGE_CLASS_NAME" \
    -o jsonpath='{.provisioner}|{.volumeBindingMode}|{.parameters.type}|{.parameters.encrypted}|{.parameters.fsType}')"
  EXPECTED_STORAGE_CLASS_CONFIG="ebs.csi.aws.com|WaitForFirstConsumer|gp3|true|ext4"
  if [[ "$STORAGE_CLASS_CONFIG" != "$EXPECTED_STORAGE_CLASS_CONFIG" ]]; then
    echo "Existing StorageClass $STORAGE_CLASS_NAME is incompatible: $STORAGE_CLASS_CONFIG" >&2
    echo "Expected: $EXPECTED_STORAGE_CLASS_CONFIG" >&2
    exit 1
  fi
  echo "Reusing compatible immutable StorageClass $STORAGE_CLASS_NAME."
else
  kubectl apply -f "$SCRIPT_DIR/storage-class.yaml"
fi

if kubectl get pvc parakeet-workspace -n parakeet-demo >/dev/null 2>&1; then
  PVC_STORAGE_CLASS="$(kubectl get pvc parakeet-workspace -n parakeet-demo \
    -o jsonpath='{.spec.storageClassName}')"
  if [[ "$PVC_STORAGE_CLASS" != "$STORAGE_CLASS_NAME" ]]; then
    echo "Existing PVC parakeet-workspace uses incompatible StorageClass: $PVC_STORAGE_CLASS" >&2
    exit 1
  fi
fi

kubectl apply -f "$SCRIPT_DIR/storage.yaml"
kubectl delete job parakeet-fine-tuning -n parakeet-demo --ignore-not-found
sed "s|REPLACE_WITH_ECR_IMAGE|$IMAGE_URI|" "$SCRIPT_DIR/training-job.yaml" | kubectl apply -f -
kubectl get pods -n parakeet-demo
