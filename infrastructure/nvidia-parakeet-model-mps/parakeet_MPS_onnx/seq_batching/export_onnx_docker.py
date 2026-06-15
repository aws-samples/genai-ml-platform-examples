#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Docker build-stage script: download Parakeet TDT, extract tokenizer, export ONNX.

Produces:
  /opt/onnx_out/encoder-parakeet.onnx
  /opt/onnx_out/decoder_joint-parakeet.onnx
  /opt/parakeet_tokenizer.model

Usage (inside builder stage):
  python3 /opt/export/export_onnx_docker.py
"""

import shutil
import sys
import tarfile
import tempfile

sys.path.insert(0, "/opt/export")
import patch_local_attn

patch_local_attn.apply()

from huggingface_hub import hf_hub_download
from nemo.collections.asr.models import ASRModel

REPO_ID = "nvidia/parakeet-tdt-0.6b-v2"
NEMO_FILENAME = "parakeet-tdt-0.6b-v2.nemo"
ONNX_OUT = "/opt/onnx_out"
TOKENIZER_OUT = "/opt/parakeet_tokenizer.model"


def extract_tokenizer(nemo_path: str):
    with tarfile.open(nemo_path, "r") as tar:
        for member in tar.getmembers():
            if member.name.endswith("_tokenizer.model"):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tar.extract(member, tmpdir)
                    shutil.copy(f"{tmpdir}/{member.name}", TOKENIZER_OUT)
                print(f"[tokenizer] Extracted to {TOKENIZER_OUT}")
                return
    raise FileNotFoundError(f"No *_tokenizer.model found in {nemo_path}")


def export_onnx(nemo_path: str):
    import os
    os.makedirs(ONNX_OUT, exist_ok=True)

    model = ASRModel.restore_from(nemo_path)
    model.change_attention_model("rel_pos_local_attn", [128, 128])
    model.change_subsampling_conv_chunking_factor(1)
    model.eval()
    model.freeze()

    model.export(
        f"{ONNX_OUT}/parakeet.onnx",
        check_trace=False,
    )
    print("[export] Done")


def main():
    nemo_path = hf_hub_download(  # nosec B615
        repo_id=REPO_ID, filename=NEMO_FILENAME, local_dir="/opt"
    )
    extract_tokenizer(nemo_path)
    export_onnx(nemo_path)


if __name__ == "__main__":
    main()
