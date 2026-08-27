#!/usr/bin/env bash
set -euo pipefail

NUM_GPUS="${NUM_GPUS:-4}"
CONFIG_PATH="${CONFIG_PATH:-configs/fine_tuning_config.yaml}"
MODEL_PATH="${MODEL_PATH:-trained_models/French_ASR_Parakeet_Finetuning.nemo}"

export NCCL_SOCKET_NTHREADS=4
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export TORCH_NCCL_ASYNC_ERROR_HANDLING=3
export CUDA_DEVICE_MAX_CONNECTIONS=1
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-0,1,2,3}"

args=(--config_path "$CONFIG_PATH" --model_path "$MODEL_PATH" --devices "$NUM_GPUS")
[[ -n "${MAX_EPOCHS:-}" ]] && args+=(--max_epochs "$MAX_EPOCHS")
[[ -n "${BATCH_SIZE:-}" ]] && args+=(--batch_size "$BATCH_SIZE")
[[ -n "${EXPERIMENT_DIR:-}" ]] && args+=(--experiment_dir "$EXPERIMENT_DIR")

# Lightning owns process creation; wrapping this in accelerate would launch twice.
python trainer.py "${args[@]}"

