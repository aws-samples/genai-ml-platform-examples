#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Docker build-stage script: download Parakeet TDT, export encoder ONNX using dynamo.

Produces:
  /opt/onnx_out/encoder-parakeet.onnx  (dynamo export)

Usage (inside image builder stage):
  python3 /opt/export/export_onnx_docker.py
"""

import os
import shutil
import sys
import tarfile

import torch
import torch.nn as nn

sys.path.insert(0, "/opt/export")
import patch_local_attn

patch_local_attn.apply()

from huggingface_hub import hf_hub_download
from nemo.collections.asr.models import ASRModel

REPO_ID = "nvidia/parakeet-tdt-0.6b-v2"
NEMO_FILENAME = "parakeet-tdt-0.6b-v2.nemo"
ONNX_OUT = "/opt/onnx_out"

class EncoderWrapper(nn.Module):
    """Thin wrapper exposing only the offline inference inputs/outputs."""

    def __init__(self, encoder):
        super().__init__()
        self.encoder = encoder

    def forward(self, audio_signal: torch.Tensor, length: torch.Tensor):
        outputs, encoded_lengths = self.encoder(
            audio_signal=audio_signal, length=length
        )[:2]
        return outputs, encoded_lengths


def export_encoder(model):
    """Export encoder via dynamo."""
    os.makedirs(ONNX_OUT, exist_ok=True)
    output_path = f"{ONNX_OUT}/encoder-parakeet.onnx"
    device = next(model.parameters()).device

    wrapper = EncoderWrapper(model.encoder).to(device)
    wrapper.eval()

    batch = 2
    t_mel = 3001
    audio_signal = torch.randn(batch, 128, t_mel, device=device)
    length = torch.tensor([t_mel, t_mel // 2], dtype=torch.int64, device=device)

    batch_dim = torch.export.Dim("batch", min=1, max=16)
    t_mel_dim = torch.export.Dim("t_mel", min=100, max=6001)

    dynamic_shapes = {
        "audio_signal": {0: batch_dim, 2: t_mel_dim},
        "length": {0: batch_dim},
    }

    print(f"[export] Exporting encoder (dynamo) to {output_path} ...")
    torch.onnx.export(
        wrapper,
        (audio_signal, length),
        output_path,
        input_names=["audio_signal", "length"],
        output_names=["outputs", "encoded_lengths"],
        dynamo=True,
        dynamic_shapes=dynamic_shapes,
    )
    print(f"[export] Done: {output_path}")


def main():
    nemo_path = hf_hub_download(  # nosec B615
        repo_id=REPO_ID, filename=NEMO_FILENAME, local_dir="/opt"
    )

    model = ASRModel.restore_from(nemo_path)
    model.change_attention_model("rel_pos_local_attn", [128, 128])
    model.change_subsampling_conv_chunking_factor(1)
    model.eval()
    model.freeze()
    if torch.cuda.is_available():
        model = model.to('cuda')

    export_encoder(model)


if __name__ == "__main__":
    main()
