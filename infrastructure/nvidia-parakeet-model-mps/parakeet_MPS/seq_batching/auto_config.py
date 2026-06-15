#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Auto-configure Triton model instance count based on available GPU memory.

Each Parakeet TDT instance uses ~2GB VRAM at steady state, but needs
~4GB during loading (weights loaded then converted in-place).
This script serializes loading via the model's file lock, so we only
need to budget for 1 loading + N-1 loaded instances.
"""

import subprocess  # nosec B404
import sys
import re
from pathlib import Path

CONFIG_PATH = Path("/models/parakeet_asr/config.pbtxt")
PER_INSTANCE_MB = 3000  # ~2.9GB per instance (measured from nvidia-smi)
LOADING_OVERHEAD_MB = 4000  # extra headroom for one instance loading at a time
RESERVED_MB = 3000  # Triton server + driver + CUDA context
MIN_INSTANCES = 1
MAX_INSTANCES = 4


def get_gpu_free_mb() -> int:
    result = subprocess.run(  # nosec B603 B607
        ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        capture_output=True, text=True
    )
    return int(result.stdout.strip().split("\n")[0])


def calculate_instances(free_mb: int) -> int:
    # Budget: RESERVED + LOADING_OVERHEAD + N * PER_INSTANCE <= free
    available = free_mb - RESERVED_MB - LOADING_OVERHEAD_MB
    n = max(MIN_INSTANCES, available // PER_INSTANCE_MB)
    return min(MAX_INSTANCES, n)


def rewrite_config(config_path: Path, instance_count: int):
    text = config_path.read_text()
    text = re.sub(
        r'instance_group\s*\[.*?\]',
        f'instance_group [\n  {{ count: {instance_count}, kind: KIND_GPU }}\n]',
        text,
        flags=re.DOTALL,
    )
    config_path.write_text(text)


def main():
    free_mb = get_gpu_free_mb()
    instances = calculate_instances(free_mb)

    print(f"[auto-config] GPU free: {free_mb}MB, reserved: {RESERVED_MB}MB, per-instance: {PER_INSTANCE_MB}MB")
    print(f"[auto-config] Setting instance_group count = {instances}", flush=True)

    rewrite_config(CONFIG_PATH, instances)

    # Set MPS thread percentage to match instance count (equal share of SMs)
    import os
    mps_pct = max(10, 100 // instances)
    os.environ["CUDA_MPS_ACTIVE_THREAD_PERCENTAGE"] = str(mps_pct)
    print(f"[auto-config] CUDA_MPS_ACTIVE_THREAD_PERCENTAGE = {mps_pct}%", flush=True)

    triton_args = ["tritonserver"] + sys.argv[1:]
    os.execvp("tritonserver", triton_args)  # nosec B606 B607


if __name__ == "__main__":
    main()
