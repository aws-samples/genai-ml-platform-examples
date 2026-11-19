# Serve GLM-5.3 on SageMaker HyperPod and benchmark its inference features

Companion code for an AWS blog post. It deploys the full GLM-5.3 model (FP8, about 756 GB) on an Amazon SageMaker HyperPod cluster orchestrated by Amazon EKS, then runs three experiments:

| Experiment | Compared | Workload | Metric |
|---|---|---|---|
| 1 | Managed tiered KV cache with prefix-aware routing, against round robin | Multi-turn coding sessions that resend a large repository context | Time to first token (TTFT), cost per million tokens |
| 2 | HyperPod Inference Gateway, against round robin | Bursty open-loop traffic with mixed prompt lengths | p95 and p99 latency during bursts |
| 3 | Model weights and container image caching, on and off | Adding one replica to a running endpoint | Time from scale-out to first answered request |

Each replica runs vLLM with tensor parallelism across the 8 H200 GPUs of one `ml.p5en.48xlarge` node (1,128 GB of GPU memory). Three GPU nodes are enough for every experiment: experiments 1 and 2 use three replicas, and experiment 3 starts with two and scales to three.

## Contents

| Path | What it is |
|---|---|
| `cloudformation/01-network-eks.yaml` | Stack 1: VPC (one public and two private subnets), NAT gateway, S3 gateway endpoint, EKS control plane, OIDC provider |
| `cloudformation/02-model-storage.yaml` | Stack 2: S3 bucket for the model weights. Retained when the stack is deleted |
| `cloudformation/03-hyperpod-cluster.yaml` | Stack 3: HyperPod cluster (system and GPU instance groups), IAM roles, EKS add-ons including the HyperPod inference operator and Inference Gateway |
| `k8s/namespace.yaml` | Model namespace, service accounts and the load generator's Role |
| `k8s/download-model-job.yaml`, `k8s/download_to_s3.py` | Job that copies GLM-5.3 from Hugging Face to the model bucket, one file at a time, resumable |
| `k8s/toolbox.yaml` | Pod on the system nodes for running the load generators inside the cluster |
| `k8s/endpoints/` | One `InferenceEndpointConfig` per experiment arm; `qwen3-0.6b/` has the same arms for a small-model rehearsal |
| `loadgen/` | Load generators for the three experiments (Python, `httpx`) |

## Prerequisites

- AWS CLI v2, `kubectl`, `helm`, `git`, `envsubst` (from GNU gettext) and Python 3.10 or later.
- An `ml.m5.2xlarge for cluster usage` quota of at least 3. HyperPod allows only 14 pods on each of these nodes, and the inference add-on with its dependencies needs more than two nodes hold.
- GPU capacity for 3 `ml.p5en.48xlarge` nodes (2 at minimum), through a SageMaker flexible training plan or an `ml.p5en.48xlarge for cluster usage` quota. Stacks 1 to 3 deploy without GPUs, so you can build and test everything else first.
- An IAM role ARN for cluster administration, in the form `arn:aws:iam::<account>:role/...`. For an IAM Identity Center user this is the `AWSReservedSSO_...` role ARN, not the `assumed-role` ARN that `aws sts get-caller-identity` prints. EKS access entries reject the latter.

Run every command from this directory.

## Deploy

```bash
export AWS_REGION=us-west-2
export ADMIN_ARN=arn:aws:iam::111122223333:role/YourAdminRole

# 1. Network and EKS control plane (about 15 minutes)
aws cloudformation deploy --stack-name hpglm-net \
  --template-file cloudformation/01-network-eks.yaml \
  --parameter-overrides ClusterAdminPrincipalArn=$ADMIN_ARN \
  --capabilities CAPABILITY_IAM

aws eks update-kubeconfig --name hpglm-net-eks --region $AWS_REGION

# 2. HyperPod dependency Helm chart. Required before the HyperPod cluster exists.
#    Same command as the HelmCommands output of stack 1.
git clone --depth 1 https://github.com/aws/sagemaker-hyperpod-cli.git /tmp/hyperpod-cli
helm dependencies update /tmp/hyperpod-cli/helm_chart/HyperPodHelmChart
helm install hyperpod-dependencies /tmp/hyperpod-cli/helm_chart/HyperPodHelmChart --namespace kube-system

# 3. Model bucket
aws cloudformation deploy --stack-name hpglm-models \
  --template-file cloudformation/02-model-storage.yaml

# 4. HyperPod cluster and add-ons, system nodes only (about 30 minutes)
aws cloudformation deploy --stack-name hpglm-hp \
  --template-file cloudformation/03-hyperpod-cluster.yaml \
  --parameter-overrides GpuInstanceCount=0 \
  --capabilities CAPABILITY_IAM

# 5. Shell variables for the k8s/ and loadgen/ steps
eval "$(aws cloudformation describe-stacks --stack-name hpglm-hp \
  --query "Stacks[0].Outputs[?OutputKey=='EnvExports'].OutputValue" --output text)"
```

Some HyperPod Helm chart pods stay `Pending` until HyperPod nodes join. That is expected.

Check the add-ons and the inference operator:

```bash
aws eks list-addons --cluster-name hpglm-net-eks
kubectl get pods -n hyperpod-inference-system
kubectl get crd | grep -E 'inferenceendpointconfigs|inferencegatewayconfigs'
```

### Copy the model to S3

The job runs on the system nodes, so you can do this before the GPU nodes arrive.

```bash
export HF_REPO=zai-org/GLM-5.3   # Hugging Face repository to copy
envsubst < k8s/namespace.yaml | kubectl apply -f -
kubectl create configmap download-to-s3 -n $NAMESPACE \
  --from-file=k8s/download_to_s3.py --dry-run=client -o yaml | kubectl apply -f -
```

Run a smoke test first. Set `ONLY` to `config.json,tokenizer_config.json` in `k8s/download-model-job.yaml`, then:

```bash
envsubst < k8s/download-model-job.yaml | kubectl apply -f -
kubectl logs -n $NAMESPACE -f job/download-glm53
aws s3 ls s3://$MODEL_BUCKET/$MODEL_PREFIX/
kubectl delete job -n $NAMESPACE download-glm53
```

Then set `ONLY` back to `""` and apply the job again for the full copy. It skips files already in the bucket with the right size, so you can rerun it after a failure.

The download comes from the internet through the NAT gateway, which charges per GB processed. Check the [Amazon VPC pricing page](https://aws.amazon.com/vpc/pricing/) for your Region before copying 756 GB.

### Start the load-test toolbox

```bash
kubectl create configmap loadgen-scripts -n $NAMESPACE --from-file=loadgen/ \
  --dry-run=client -o yaml | kubectl apply -f -
envsubst < k8s/toolbox.yaml | kubectl apply -f -
kubectl logs -n $NAMESPACE deploy/loadgen-toolbox   # wait for "ready"
```

### Add the GPU nodes

When the training plan is active, update stack 3:

```bash
aws cloudformation deploy --stack-name hpglm-hp \
  --template-file cloudformation/03-hyperpod-cluster.yaml \
  --parameter-overrides GpuInstanceCount=3 \
    TrainingPlanArn=arn:aws:sagemaker:us-west-2:111122223333:training-plan/your-plan \
  --capabilities CAPABILITY_IAM

kubectl get nodes -L hpglm/role,node.kubernetes.io/instance-type
```

Adding GPU nodes also turns on the cluster's managed tiered storage, which experiment 1 uses as its L2 KV cache. `TieredStorageMemoryPercent` (default 20) sets the share of each node's memory it takes; set `TieredStorage=Disable` if your GPU instance type doesn't support it. Leave `GpuDeepHealthChecks=false` unless you can afford the longer node start-up.

If GPU launches fail with "insufficient capacity", give the GPU group more zones. Redeploy stack 1 with `ExtraPrivateSubnetAzId` set to a third zone ID (for example `usw2-az3`), then pass all three private subnets from its outputs to stack 3 as `GpuSubnetIds=subnet-a,subnet-b,subnet-c`. Only the GPU group moves; the cluster's own subnets can't change without replacing it.

### Rehearse with a small model (optional)

`k8s/endpoints/qwen3-0.6b/` has the same five arms for Qwen3-0.6B, one replica per A10G GPU (`ml.g5.8xlarge` or `ml.g5.12xlarge`). Use it to check the operator, router, gateway and caches end to end before GPU time for GLM-5.3. It proves the features work; the model is too small to show realistic gains.

```bash
export HF_REPO=Qwen/Qwen3-0.6B MODEL_PREFIX=Qwen/Qwen3-0.6B INSTANCE_TYPE=ml.g5.8xlarge
envsubst < k8s/download-model-job.yaml | kubectl apply -f -
envsubst < k8s/endpoints/qwen3-0.6b/exp1-roundrobin.yaml | kubectl apply -f -
```

Pass `--model qwen3-0.6b` to the load generators. The endpoint manifests also need `VLLM_IMAGE` and `NVME_HOST_PATH`, set as in [Run the experiments](#run-the-experiments).

## Run the experiments

The endpoint manifests need two more variables:

```bash
export VLLM_IMAGE=vllm/vllm-openai:v0.33.0
export NVME_HOST_PATH=/opt/dlami/nvme
```

Deploy one arm at a time. Each arm needs every GPU node, and an endpoint can't use the Inference Gateway and intelligent routing at once, so each arm is a separate `InferenceEndpointConfig`. A replica takes several minutes to load 756 GB of weights. Wait until every pod is `Ready` before you start the load.

```bash
envsubst < k8s/endpoints/exp1-roundrobin.yaml | kubectl apply -f -
kubectl get inferenceendpointconfig -n $NAMESPACE
kubectl get pods,svc -n $NAMESPACE -o wide
```

Run the load generators from the toolbox, using the service address from `kubectl get svc`:

```bash
kubectl exec -it -n $NAMESPACE deploy/loadgen-toolbox -- bash
cd /work
```

**Experiment 1.** Deploy `exp1-roundrobin.yaml`, run, delete it, then do the same for `exp1-prefixaware-tiered.yaml`. Pass the per-node hourly price you pay, so the script can report cost per million tokens.

```bash
python multiturn_coding.py --base-url http://<service>:8000 --arm roundrobin \
  --node-count 3 --node-hourly-usd <price>
python multiturn_coding.py --base-url http://<router-service>:8000 --arm prefixaware \
  --node-count 3 --node-hourly-usd <price>
```

**Experiment 2.** Compare `exp1-roundrobin.yaml` with `exp2-gateway.yaml`.

```bash
python bursty_traffic.py --base-url http://<service>:8000 --arm roundrobin
python bursty_traffic.py --base-url http://<gateway-address> --arm gateway
```

**Experiment 3.** Deploy `exp3-cache-off.yaml` (2 replicas), time a third replica, delete it, then repeat with `exp3-cache-on.yaml`. Run the cache-on arm twice: the first run fills the cache on the new node.

```bash
python scaleout_timer.py --endpoint glm53-cold --namespace $NAMESPACE --label cache-off --restore
python scaleout_timer.py --endpoint glm53-warm --namespace $NAMESPACE --label cache-on --restore
```

Every script writes JSON to `/work/results`. Copy it out with:

```bash
kubectl cp $NAMESPACE/<toolbox-pod>:/work/results ./results
```

Run `--help` on any script for its workload options.

## Security notes

- The Inference Gateway in `exp2-gateway.yaml` has no JWT authentication. It is reachable only inside the VPC. Add authentication before you put real traffic on it.
- Every IAM role is scoped to one service account. The download job's role can write only to the model prefix, and the inference roles can only read it.
- The bucket policy rejects requests that don't use TLS.

## Clean up

Delete in this order. Deleting the inference add-on before its endpoints leaves finalizers that block namespace deletion.

```bash
kubectl delete inferenceendpointconfig --all -n $NAMESPACE
kubectl delete namespace $NAMESPACE

# Load balancers created by the ALB controller keep the VPC from deleting
aws elbv2 describe-load-balancers \
  --query "LoadBalancers[?VpcId=='$(aws cloudformation describe-stacks --stack-name hpglm-net \
  --query "Stacks[0].Outputs[?OutputKey=='VpcId'].OutputValue" --output text)'].LoadBalancerArn"

aws cloudformation delete-stack --stack-name hpglm-hp
aws cloudformation wait stack-delete-complete --stack-name hpglm-hp
helm uninstall hyperpod-dependencies --namespace kube-system
aws cloudformation delete-stack --stack-name hpglm-net
aws cloudformation wait stack-delete-complete --stack-name hpglm-net
```

Delete any load balancer the query lists before you delete `hpglm-net`.

The model bucket outlives `hpglm-models`, so a later deploy doesn't have to download the weights again. To remove it:

```bash
aws s3 rm s3://$MODEL_BUCKET --recursive
aws cloudformation delete-stack --stack-name hpglm-models
aws s3 rb s3://$MODEL_BUCKET
```

## Open items

These need GPU nodes and are not yet verified:

- The NVMe host path on HyperPod `ml.p5en.48xlarge` nodes. The docs use `/opt/dlami/nvme`; HyperPod may mount instance storage under `/opt/sagemaker`.
- Whether the tiered KV cache arm needs an LMCache-enabled vLLM image (`lmcache/vllm-openai`) rather than `vllm/vllm-openai`.
- The `/dev/shm` size vLLM needs for TP8.
- The names of the services and router the operator creates for each arm.
