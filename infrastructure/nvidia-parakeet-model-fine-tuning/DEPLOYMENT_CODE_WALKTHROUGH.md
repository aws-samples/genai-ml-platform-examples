# NVIDIA Parakeet EKS Deployment Code Walkthrough

This document explains the code path used to deploy and run the NVIDIA Parakeet French fine-tuning demo on Amazon EKS. It complements [`DEMO_RUNBOOK.md`](DEMO_RUNBOOK.md): use the runbook for commands and expected operational output, and use this walkthrough to understand how the files fit together and where to change behavior.

> [!IMPORTANT]
> In this demo, **deployment means deploying a fine-tuning Job to EKS**. The validated workflow produces and downloads a fine-tuned `.nemo` model, but it does not deploy that model behind an inference endpoint. The separate files under `deployment/docker/` are an unintegrated inference prototype and do not load the generated French model.

## 1. Deployment flow at a glance

```text
deployment/eks/cluster.yaml
        │
        ├─ eksctl creates EKS, system nodes, GPU node, and EBS CSI add-on
        │
Dockerfile + build-and-push.sh
        │
        ├─ build the training image and push it to Amazon ECR
        │
deployment/eks/deploy-training.sh
        │
        ├─ validate the ECR image URI and EBS CSI add-on
        ├─ install the NVIDIA device plugin
        ├─ wait for four allocatable GPUs
        ├─ validate or create storage-class.yaml
        ├─ apply storage.yaml for the namespace and PVC
        └─ inject IMAGE_URI into training-job.yaml and create the Job
                │
                ├─ download-and-prepare-fleurs.sh
                │      └─ data_preparation_fleurs.py
                │
                └─ run-train.sh
                       └─ trainer.py
                              ├─ configs/fine_tuning_config.yaml
                              ├─ pretrained nvidia/parakeet-tdt-0.6b-v2
                              └─ final model, checkpoints, logs, and TensorBoard data
                                      │
                                      └─ PVC mounted by artifact-pod.yaml for download
```

The important runtime parameter path is:

```text
training-job.yaml environment variables
    → run-train.sh command-line arguments
    → trainer.py argparse overrides
    → configs/fine_tuning_config.yaml / OmegaConf
    → Lightning Trainer and NeMo ASRModel
```

## 2. File map

| File | Role in deployment |
|---|---|
| `DEMO_RUNBOOK.md` | Command-by-command deployment, monitoring, artifact retrieval, and cleanup instructions. |
| `deployment/eks/cluster.yaml` | Defines the EKS control plane settings, add-ons, system node group, and four-GPU node group. |
| `build-and-push.sh` | Creates or reuses the ECR repository, builds the AMD64 image, and pushes a tag. |
| `Dockerfile` | Packages the NeMo/PyTorch environment, configuration, data preparation, and trainer code. |
| `deployment/eks/deploy-training.sh` | Main deployment orchestrator after the cluster and image exist. |
| `deployment/eks/nvidia-device-plugin-values.yaml` | Allows the NVIDIA device-plugin DaemonSet to run on the tainted GPU node. |
| `deployment/eks/storage-class.yaml` | Defines the immutable encrypted gp3 EBS CSI StorageClass for first deployment. |
| `deployment/eks/storage.yaml` | Creates the namespace and 200 GiB workspace PVC. |
| `deployment/eks/training-job.yaml` | Defines GPU scheduling, resources, mounts, smoke-test overrides, and the container command. |
| `download-and-prepare-fleurs.sh` | Starts dataset preparation when the training manifest is absent. |
| `data_preparation_fleurs.py` | Downloads French FLEURS, writes WAV files, and creates NeMo JSONL manifests. |
| `run-train.sh` | Converts environment variables into `trainer.py` arguments and sets CUDA/NCCL runtime values. |
| `trainer.py` | Loads configuration and the base model, creates DDP training, runs `fit`, and saves the `.nemo` model. |
| `configs/fine_tuning_config.yaml` | Defines manifests, model architecture, augmentation, optimizer, DDP settings, and experiment outputs. |
| `deployment/eks/artifact-pod.yaml` | Temporarily mounts the workspace PVC after the Job completes so artifacts can be inspected or copied. |

## 3. Cluster infrastructure

### `deployment/eks/cluster.yaml`

This is an `eksctl` `ClusterConfig`. Its key design choice is to separate ordinary Kubernetes workloads from the GPU training workload:

- The `system` managed node group runs EKS system components on `m7i.large` instances.
- The `gpu-g6e` managed node group supplies one `g6e.12xlarge` with four NVIDIA L40S GPUs.
- The GPU node is labeled `workload=parakeet-training`.
- The GPU node is tainted `dedicated=parakeet-training:NoSchedule`.
- The `aws-ebs-csi-driver` add-on provisions the persistent workspace volume.

The label and taint work together. The training pod selects the label and explicitly tolerates the taint, preventing unrelated pods from consuming the expensive GPU node.

Before cluster creation, replace the checked-in account-specific values:

- VPC ID
- public subnet IDs and Availability Zones
- EKS API endpoint CIDR
- region or Kubernetes version, if needed

The checked-in API allowlist is `0.0.0.0/0`. Change it to trusted CIDRs before treating the cluster as secure. Authentication still applies, but a global CIDR removes network-level filtering.

The EBS CSI add-on is not optional for this workflow. `deploy-training.sh` stops before creating the Job unless the add-on reports `ACTIVE`.

## 4. Building and publishing the training image

### `Dockerfile`

The image contains everything the Job needs at runtime:

- CUDA-enabled PyTorch base environment
- NeMo and Python dependencies from `requirements.txt`
- `configs/fine_tuning_config.yaml`
- `trainer.py`
- FLEURS preparation code
- shell entry points

The image targets Linux AMD64 because the selected EKS nodes use that architecture. The default image command is `./run-train.sh`, although `training-job.yaml` replaces it with a wrapper that first prepares data and configures persistent paths.

Changes to files copied by the Dockerfile do not reach an existing image. After changing training code, configuration, or data preparation, build and push a new tag.

### `build-and-push.sh`

The script derives the account and region, creates the `parakeet-fine-tuning` ECR repository if needed, logs Docker into ECR, and builds and pushes the image with Buildx.

Use a unique tag for each code revision:

```bash
export IMAGE_TAG="eks-demo-$(date +%Y%m%d-%H%M%S)"
REGION="$AWS_REGION" IMAGE_TAG="$IMAGE_TAG" ./build-and-push.sh
```

This matters because the Job uses:

```yaml
imagePullPolicy: IfNotPresent
```

Reusing a mutable tag can cause Kubernetes to run a cached image instead of the code just built.

## 5. The deployment orchestrator

### `deployment/eks/deploy-training.sh`

This script is the main entry point once the EKS cluster and ECR image exist:

```bash
IMAGE_URI="$IMAGE_URI" \
CLUSTER_NAME="$CLUSTER_NAME" \
REGION="$AWS_REGION" \
  deployment/eks/deploy-training.sh
```

Its execution sequence is intentional:

1. **Validate input.** `IMAGE_URI` is required and must resemble a tagged ECR URI. Digest-only or untagged values do not pass the regular expression.
2. **Check local tools.** The script requires `aws`, `awk`, `helm`, `kubectl`, and `sed`.
3. **Select the cluster.** `aws eks update-kubeconfig` updates the current kubeconfig context.
4. **Verify storage support.** The EBS CSI add-on must report `ACTIVE`.
5. **Install GPU discovery.** Helm installs NVIDIA device plugin chart `0.18.0` with the dedicated-node toleration.
6. **Wait for capacity.** The script polls labeled nodes for at least four allocatable `nvidia.com/gpu` resources.
7. **Prepare persistent storage.** If `parakeet-gp3` does not exist, the script applies `storage-class.yaml`. If it exists, the script validates its provisioner, binding mode, type, encryption, and filesystem without attempting an immutable update. It then applies `storage.yaml` for the namespace and PVC.
8. **Replace the previous Job.** The same-name Job is deleted, but the PVC is preserved.
9. **Inject the image.** `sed` replaces `REPLACE_WITH_ECR_IMAGE` in `training-job.yaml`, and the rendered manifest is piped to `kubectl apply`.

The image URI is injected at deployment time rather than committed to the manifest. This keeps account IDs and build tags out of the reusable Job template.

## 6. GPU discovery and scheduling

### `deployment/eks/nvidia-device-plugin-values.yaml`

The GPU node is tainted, so the NVIDIA device-plugin DaemonSet also needs a matching toleration. Without it, Kubernetes can see the node but will not advertise `nvidia.com/gpu`, and `deploy-training.sh` eventually fails its four-GPU readiness check.

### `deployment/eks/training-job.yaml`

The Job is pinned to the intended hardware:

```yaml
nodeSelector:
  workload: parakeet-training
  kubernetes.io/arch: amd64
tolerations:
  - key: dedicated
    operator: Equal
    value: parakeet-training
    effect: NoSchedule
```

The container requests all four GPUs:

```yaml
resources:
  requests: {cpu: "32", memory: 128Gi, nvidia.com/gpu: "4"}
  limits: {cpu: "44", memory: 176Gi, nvidia.com/gpu: "4"}
```

Because a single pod requests four GPUs, Kubernetes must place it on one node with all four GPUs available. This is one-node, four-process DDP—not multi-node training.

The Job also sets:

- `backoffLimit: 0`: Kubernetes does not retry a failed training pod.
- `activeDeadlineSeconds: 21600`: the smoke test is terminated after six hours.
- `restartPolicy: Never`: a failed process results in a failed pod.
- `fsGroup: 1000`: files on the mounted volume are writable by the image’s non-root user/group arrangement.

For longer training, increasing `MAX_EPOCHS` without increasing `activeDeadlineSeconds` can cause an otherwise healthy run to be terminated.

## 7. Persistent storage and runtime paths

### `deployment/eks/storage-class.yaml` and `storage.yaml`

`storage-class.yaml` defines an encrypted gp3 EBS CSI StorageClass named `parakeet-gp3`. `storage.yaml` creates:

- namespace `parakeet-demo`
- a 200 GiB `ReadWriteOnce` PVC named `parakeet-workspace`

StorageClass parameters are immutable. On reruns, `deploy-training.sh` validates and reuses a compatible existing class instead of applying changes to it, preserving any bound PVC and EBS data. The StorageClass uses `WaitForFirstConsumer`. EBS provisioning waits until Kubernetes knows where the training pod can be scheduled, then creates the volume in that Availability Zone.

After binding, the EBS volume remains tied to that zone. If the GPU node group later comes back in another zone, the pod can remain `Pending` because the volume cannot attach across Availability Zones.

### Workspace layout

`training-job.yaml` mounts the PVC at `/workspace` and assigns stable locations:

```text
/workspace/
├── dataset/fleurs_french/        # WAV files and train/validation/test manifests
├── huggingface-cache/            # downloaded model and dataset cache
├── experiments/
│   ├── French_ASR_Parakeet_Finetuning/<timestamp>/
│   │   ├── checkpoints/          # .ckpt and .nemo checkpoints
│   │   └── TensorBoard events
│   └── trained_models/
│       └── French_ASR_Parakeet_Finetuning.nemo
└── training.log                  # output appended across reruns
```

A second memory-backed volume is mounted at `/dev/shm` with a 32 GiB limit. PyTorch data-loader workers use shared memory; the larger mount avoids the small default container shared-memory allocation.

## 8. Container startup and dataset preparation

The Job replaces the image default command with `/bin/bash -lc` and runs this logical sequence:

```bash
exec > >(tee -a /workspace/training.log) 2>&1
export DATA_DIR=/workspace/dataset/fleurs_french
export EXPERIMENT_DIR=/workspace/experiments
export MODEL_PATH=/workspace/experiments/trained_models/French_ASR_Parakeet_Finetuning.nemo

if [[ ! -s "$DATA_DIR/train_manifest.jsonl" ]]; then
  ./download-and-prepare-fleurs.sh
fi

./run-train.sh
```

Key implications:

- Both stdout and stderr are appended to persistent `training.log`.
- Dataset, Hugging Face cache, experiments, and final model survive Job deletion.
- Preparation is skipped when a non-empty training manifest exists.
- A successful rerun overwrites the stable final model path but creates a new timestamped experiment directory.

The skip test checks only `train_manifest.jsonl`. If preparation was interrupted after the training manifest was written but before validation/test data completed, a rerun can skip preparation and fail later. In that case, inspect or remove the incomplete dataset on the PVC before redeploying.

### `data_preparation_fleurs.py`

The preparation code loads the pinned French `google/fleurs` dataset revision and processes `train`, `validation`, and `test`. For each sample it:

1. writes the audio array as a WAV file;
2. records the audio path, transcript, and duration;
3. appends a JSON object to the split’s NeMo manifest.

Each JSONL record has the shape:

```json
{"audio_filepath":"/workspace/dataset/fleurs_french/audio/train/train_000000.wav","text":"...","duration":4.2}
```

The manifest paths are consumed directly by the NeMo data-loader configuration.

## 9. Runtime overrides and distributed launch

### `training-job.yaml` environment

The checked-in Job is deliberately a smoke test:

```yaml
env:
  - {name: NUM_GPUS, value: "4"}
  - {name: MAX_EPOCHS, value: "1"}
  - {name: BATCH_SIZE, value: "3"}
  - {name: HF_HOME, value: /workspace/huggingface-cache}
```

These values take precedence over relevant defaults in `fine_tuning_config.yaml` because `run-train.sh` converts them into explicit CLI arguments.

### `run-train.sh`

The shell entry point maps values as follows:

| Environment value | `trainer.py` argument |
|---|---|
| `NUM_GPUS` | `--devices` |
| `MAX_EPOCHS` | `--max_epochs` |
| `BATCH_SIZE` | `--batch_size` for train, validation, and test |
| `EXPERIMENT_DIR` | `--experiment_dir` |
| `MODEL_PATH` | `--model_path` |

It also configures CUDA/NCCL values and makes devices `0,1,2,3` visible.

Do not wrap this command in `torchrun`, `accelerate launch`, or another process launcher. `trainer.py` creates a Lightning Trainer using DDP, and Lightning launches the four local workers. Adding another launcher would create duplicate distributed processes.

## 10. Training configuration

### `configs/fine_tuning_config.yaml`

The main configuration sets:

- experiment name: `French_ASR_Parakeet_Finetuning`
- base model: `nvidia/parakeet-tdt-0.6b-v2`
- manifests resolved from the `DATA_DIR` environment variable
- 16 kHz ASR preprocessing
- speed perturbation and SpecAugment
- Conformer encoder and TDT/RNNT decoder settings
- AdamW with cosine annealing
- bf16 precision
- TensorBoard and checkpoint output through NeMo `exp_manager`

The YAML default is 40 epochs, but the Kubernetes Job passes `MAX_EPOCHS=1`. The Job therefore controls the validated smoke-test duration.

There are two strategy-related sections in the YAML:

```yaml
trainer:
  strategy:
    _target_: lightning.pytorch.strategies.DeepSpeedStrategy
    ...

trainer_strategy:
  strategy: ddp
```

The effective value in this code path is `trainer_strategy.strategy`, because `trainer.py` calls:

```python
Trainer(strategy=self.config.trainer_strategy.strategy, ...)
```

Therefore this EKS demo uses `ddp`. Editing only the larger DeepSpeed object under `trainer.strategy` has no effect unless `trainer.py` is also changed to consume it.

The test manifest and test data loader are configured, but `trainer.py` does not call `trainer.test()`. The validated workflow performs training and validation during `trainer.fit()`; it does not run a separate final test evaluation.

## 11. `trainer.py` execution path

`ASRTrainer` owns the training lifecycle.

### Configuration and CLI overrides

`main()` loads `configs/fine_tuning_config.yaml`, then applies optional CLI overrides for:

- device count
- maximum epochs
- all data-loader batch sizes
- experiment directory
- final model output path

This is why the Kubernetes environment can alter smoke-test settings without editing the image’s YAML at pod startup.

### Base model loading

`get_base_model()` enforces that only one initialization source is active:

- `init_from_nemo_model` restores an existing `.nemo` file; or
- `init_from_pretrained_model` downloads a named pretrained model.

The checked-in configuration selects `nvidia/parakeet-tdt-0.6b-v2`. Each DDP rank moves its model to `cuda:$LOCAL_RANK`, unfreezes the encoder, and associates the model with the Lightning Trainer. `HF_HOME` points downloads at the PVC so later runs can reuse the cache.

### Data and optimization

`setup_dataloaders()` connects the generated train, validation, and test manifests to NeMo. The training method then:

1. creates the Lightning Trainer and NeMo experiment manager;
2. loads the base ASR model;
3. optionally replaces the tokenizer;
4. configures the data loaders;
5. sets up AdamW and its scheduler;
6. creates SpecAugment from configuration;
7. calls `trainer.fit(asr_model)`;
8. saves the final `.nemo` model to `MODEL_PATH`.

NeMo `exp_manager` handles timestamped TensorBoard data and monitored checkpoints. The stable `MODEL_PATH` is a separate final save after `fit` returns.

The code does not currently place an explicit global-rank-zero guard around the final `save_to()` call. If this workflow is extended or upgraded, confirm NeMo’s distributed save behavior or add a rank-zero guard before relying on concurrent final saves.

## 12. Monitoring the code path

Use logs to identify which layer has failed:

| Symptom | Most relevant code/configuration |
|---|---|
| EBS CSI validation fails | `deploy-training.sh`, `cluster.yaml` add-on configuration |
| Four GPUs never become allocatable | `nvidia-device-plugin-values.yaml`, GPU node taint/label, plugin pods |
| Pod remains `Pending` | `training-job.yaml` selectors/resources or PVC Availability Zone |
| `ImagePullBackOff` | injected `IMAGE_URI`, ECR tag, node IAM/ECR access |
| Data preparation fails | `download-and-prepare-fleurs.sh`, `data_preparation_fleurs.py`, outbound network |
| DDP or CUDA failure | `run-train.sh`, `trainer_strategy.strategy`, GPU/plugin state |
| No checkpoint or final model | `exp_manager` config, `trainer.fit()`, final `save_to()` |

A healthy smoke run should expose four `LOCAL_RANK` values, complete training and validation, report `max_epochs=1 reached`, and log `Last Epoch Model Saved to` with the PVC path.

## 13. Artifact retrieval

A completed Job’s container is no longer available for `kubectl cp`. `deployment/eks/artifact-pod.yaml` creates a temporary BusyBox pod that mounts the same PVC.

The retrieval sequence is:

1. apply `artifact-pod.yaml`;
2. wait for the pod to become ready;
3. inspect `/workspace/experiments` and `/workspace/training.log`;
4. use `kubectl cp` to copy the final model, logs, or experiment directory;
5. delete the artifact pod.

The artifact pod is scheduled using the GPU workload label and toleration, although it does not request a GPU. As a result, it cannot run when the GPU node group is scaled to zero. Retrieve artifacts before scaling down, or update the pod’s scheduling rules so it can mount the EBS volume from a suitable non-GPU node in the same Availability Zone.

## 14. Rerun and cleanup semantics

Redeploying with `deploy-training.sh` deletes only the existing Job. It intentionally preserves the PVC, which means:

- prepared FLEURS data is reused;
- Hugging Face downloads can be reused;
- logs are appended;
- old timestamped experiment directories remain;
- the stable final `.nemo` path is overwritten after a successful run.

Cleanup operations have different impact:

| Action | What remains |
|---|---|
| Delete the Job | PVC, dataset, caches, logs, checkpoints, and model remain. |
| Scale node groups to zero | EKS control plane and EBS data remain billable; no pods can run. |
| Delete the PVC | Dataset, caches, logs, checkpoints, and models are permanently deleted with the dynamic EBS volume. |
| Delete the cluster | eksctl/CloudFormation-managed EKS resources are removed; ECR images remain separate. |
| Delete the ECR tag | Only the selected image tag is removed. |

Always copy and verify required model artifacts before deleting the PVC or cluster.

## 15. Inference deployment is not part of the validated path

The repository also contains:

- `deployment/docker/Dockerfile.nemo`
- `deployment/docker/preload_model.py`
- `deployment/docker/nemo-parakeet-optimised.py`
- `deployment/nemo-parakeet-optimised.yaml`

These files should not be treated as the next working step of this fine-tuning deployment. As currently written, they:

- load `nvidia/parakeet-rnnt-1.1b` with `from_pretrained` rather than restoring `French_ASR_Parakeet_Finetuning.nemo`;
- contain a placeholder image URI;
- reference an undeclared model PVC;
- use inconsistent namespaces;
- depend on Prometheus Operator and KEDA resources not installed by the runbook;
- use scheduling assumptions that differ from the training cluster.

A production inference phase would need its own image build, a defined mechanism to deliver or download the `.nemo` artifact, `restore_from()` integration for the fine-tuned TDT model, consistent namespace/storage/scheduling configuration, a Service or ingress path, health checks, and an independently validated request flow.

## 16. Safe extension points

For common changes, start in these locations:

| Goal | Primary file(s) |
|---|---|
| Change VPC, subnets, EKS access, or instance types | `deployment/eks/cluster.yaml` |
| Change image dependencies | `requirements.txt`, `Dockerfile` |
| Change epoch count or batch size for EKS | `deployment/eks/training-job.yaml` |
| Change CPU, memory, GPU, deadline, or scheduling | `deployment/eks/training-job.yaml` |
| Change dataset preparation | `download-and-prepare-fleurs.sh`, `data_preparation_fleurs.py` |
| Change model architecture, augmentation, or optimizer | `configs/fine_tuning_config.yaml` |
| Change runtime override behavior or training lifecycle | `run-train.sh`, `trainer.py` |
| Change persistent capacity or storage class | `deployment/eks/storage.yaml`, `deployment/eks/storage-class.yaml` |
| Add inference for the trained artifact | create and validate a separate inference deployment path; do not assume the current prototype is integrated |

After changing files copied into the image, always rebuild with a new ECR tag and deploy that exact `IMAGE_URI`.

## 17. Deployment review checklist

Before deployment:

- [ ] Account-specific VPC and subnet values are correct.
- [ ] EKS public access is restricted to trusted CIDRs.
- [ ] `g6e.12xlarge` quota and regional capacity are available.
- [ ] The EBS CSI add-on is configured.
- [ ] A unique image tag was built and verified in ECR.

During deployment:

- [ ] NVIDIA device plugin runs on the tainted GPU node.
- [ ] The node advertises at least four allocatable GPUs.
- [ ] The PVC binds in an Availability Zone usable by the GPU node.
- [ ] The Job runs the expected ECR tag.
- [ ] Four Lightning DDP ranks initialize.

After training:

- [ ] The Job reports `Complete` with no pod restarts.
- [ ] Training and validation finished successfully.
- [ ] The final `.nemo` file and timestamped checkpoints exist.
- [ ] Required artifacts were copied and verified locally.
- [ ] The temporary artifact pod was deleted.
- [ ] Expensive GPU capacity was scaled down or the environment was removed.
