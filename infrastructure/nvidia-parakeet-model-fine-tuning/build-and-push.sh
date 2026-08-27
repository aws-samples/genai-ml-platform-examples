#!/usr/bin/env bash
set -euo pipefail

REGION="${REGION:-ap-northeast-2}"
REPOSITORY="${REPOSITORY:-parakeet-fine-tuning}"
IMAGE_TAG="${IMAGE_TAG:-eks-demo}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for command in aws docker; do
  command -v "$command" >/dev/null || { echo "Required command not found: $command" >&2; exit 1; }
done
docker buildx version >/dev/null

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REGISTRY="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
IMAGE_URI="$REGISTRY/$REPOSITORY:$IMAGE_TAG"

if ! aws ecr describe-repositories --region "$REGION" --repository-names "$REPOSITORY" >/dev/null 2>&1; then
  aws ecr create-repository --region "$REGION" --repository-name "$REPOSITORY" \
    --image-scanning-configuration scanOnPush=true \
    --encryption-configuration encryptionType=AES256 \
    --tags Key=auto-delete,Value=no Key=auto-stop,Value=no >/dev/null
fi

REPOSITORY_ARN="$(aws ecr describe-repositories --region "$REGION" --repository-names "$REPOSITORY" \
  --query 'repositories[0].repositoryArn' --output text)"
aws ecr tag-resource --region "$REGION" --resource-arn "$REPOSITORY_ARN" \
  --tags Key=auto-delete,Value=no Key=auto-stop,Value=no

aws ecr get-login-password --region "$REGION" | \
  docker login --username AWS --password-stdin "$REGISTRY"
docker buildx build --platform linux/amd64 --provenance=false --load -t "$IMAGE_URI" "$SCRIPT_DIR"
docker push "$IMAGE_URI"
printf '%s\n' "$IMAGE_URI"
