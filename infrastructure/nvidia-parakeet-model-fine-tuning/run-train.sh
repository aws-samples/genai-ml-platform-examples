#!/bin/bash

# Script to run training across multiple GPUs using DDP
set -x

# # Performance and memory optimization settings
export NCCL_SOCKET_NTHREADS=4
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export CUDA_MANAGED_FORCE_DEVICE_ALLOC=0.9999
export TORCH_NCCL_ASYNC_ERROR_HANDLING=3
export CUDA_DEVICE_MAX_CONNECTIONS=1 # Tensor parallel speedup, recommended

# GPU configuration
export CUDA_VISIBLE_DEVICES=0,1,2,3  # Use 4 GPUs
export GPUS_PER_NODE=4

# Run the training script with accelerate
accelerate launch --mixed_precision bf16 trainer.py --config_path configs/fine_tuning_config.yaml 

