#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Auto-configure Triton model instance count based on available GPU memory.

Each Sortformer instance uses ~1.8GB VRAM. This script:
1. Queries GPU free memory via nvidia-smi
2. Reserves memory for OS/driver/Triton overhead
3. Calculates max instances that fit
4. Rewrites config.pbtxt
5. Launches Triton
"""

import subprocess
import sys
import re
from pathlib import Path

CONFIG_PATH = Path("/models/sortformer_diar/config.pbtxt")
PER_INSTANCE_MB = 1800  # ~1.8GB per model instance (measured from nvidia-smi)
RESERVED_MB = 2048      # reserve 2GB for Triton server + driver + CUDA context
MIN_INSTANCES = 1
MAX_INSTANCES = 8       # sweet spot: enough parallelism without GPU contention
GPU_UTILIZATION = 0.80


def get_gpu_free_mb() -> int:
    """Get free GPU memory in MB."""
    result = subprocess.run(
        ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
        capture_output=True, text=True
    )
    return int(result.stdout.strip().split("\n")[0])


def calculate_instances(free_mb: int) -> int:
    available = int((free_mb - RESERVED_MB) * GPU_UTILIZATION)
    return min(MAX_INSTANCES, max(MIN_INSTANCES, available // PER_INSTANCE_MB))


def rewrite_config(config_path: Path, instance_count: int):
    text = config_path.read_text()
    # Replace instance_group block
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

    print(f"[auto-config] GPU free: {free_mb}MB, reserved: {RESERVED_MB}MB, per-instance: {PER_INSTANCE_MB}MB, utilization: {GPU_UTILIZATION:.0%}")
    print(f"[auto-config] Setting instance_group count = {instances}", flush=True)

    rewrite_config(CONFIG_PATH, instances)

    # Exec tritonserver with remaining args
    triton_args = ["tritonserver"] + sys.argv[1:]
    import os
    os.execvp("tritonserver", triton_args)


if __name__ == "__main__":
    main()
