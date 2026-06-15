# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Export Sortformer diarization model to ONNX using torch.onnx.export(dynamo=True).

Produces a cleaner ONNX graph compared to the TorchScript-based export.

Usage:
  conda run -n dev_env python3 convert_onnx_dynamo.py
"""

from nemo.collections.asr.models import SortformerEncLabelModel
import torch
import torch.nn as nn


# ---------------------------------------------------------------------------
# Patch NeMo SortformerEncLabelModel.forward_for_export(...)
# (same patch as convert_onnx.py — needed for async_streaming=False)
# ---------------------------------------------------------------------------
def _patched_forward_for_export(self, chunk, chunk_lengths, spkcache, fifo):
    chunk_pre_encode_embs, chunk_pre_encode_lengths = self.encoder.pre_encode(
        x=chunk, lengths=chunk_lengths
    )
    chunk_pre_encode_lengths = chunk_pre_encode_lengths.to(torch.int64)

    spkcache_fifo_chunk_pre_encode_embs = torch.cat(
        [spkcache, fifo, chunk_pre_encode_embs], dim=1
    )
    spkcache_fifo_chunk_pre_encode_lengths = (
        spkcache.shape[1] + fifo.shape[1] + chunk_pre_encode_lengths
    )

    spkcache_fifo_chunk_fc_encoder_embs, spkcache_fifo_chunk_fc_encoder_lengths = self.frontend_encoder(
        processed_signal=spkcache_fifo_chunk_pre_encode_embs,
        processed_signal_length=spkcache_fifo_chunk_pre_encode_lengths,
        bypass_pre_encode=True,
    )

    spkcache_fifo_chunk_preds = self.forward_infer(
        spkcache_fifo_chunk_fc_encoder_embs, spkcache_fifo_chunk_fc_encoder_lengths
    )

    spkcache_fifo_chunk_preds = self.sortformer_modules.apply_mask_to_preds(
        spkcache_fifo_chunk_preds, spkcache_fifo_chunk_fc_encoder_lengths
    )

    return spkcache_fifo_chunk_preds, chunk_pre_encode_embs


SortformerEncLabelModel.forward_for_export = _patched_forward_for_export


class SortformerWrapper(nn.Module):
    """Wrapper that calls forward_for_export with a clean signature for dynamo."""

    def __init__(self, model):
        super().__init__()
        self.model = model

    def forward(
        self,
        chunk: torch.Tensor,
        chunk_lengths: torch.Tensor,
        spkcache: torch.Tensor,
        fifo: torch.Tensor,
    ):
        return self.model.forward_for_export(chunk, chunk_lengths, spkcache, fifo)


def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"

    model = SortformerEncLabelModel.from_pretrained(
        "nvidia/diar_streaming_sortformer_4spk-v2",
        map_location=device,
    )
    model.eval()

    # -----------------------------------------------------------------------
    # Export configuration
    # -----------------------------------------------------------------------
    feat_dim = 128
    emb_dim = model.cfg.model_defaults.fc_d_model

    subsampling_factor = 8
    mel_chunk_len = 120
    mel_right_offset = 1
    mel_left_offset = 1
    spkcache_len = 254
    fifo_len = 60

    chunk_len = (
        mel_chunk_len * subsampling_factor
        + mel_left_offset * subsampling_factor
        + mel_right_offset * subsampling_factor
    )

    chunk = torch.rand(1, chunk_len, feat_dim, device=device)
    chunk_lengths = torch.tensor([chunk_len], dtype=torch.int64, device=device)
    spkcache = torch.rand(1, spkcache_len, emb_dim, device=device)
    fifo = torch.rand(1, fifo_len, emb_dim, device=device)

    # -----------------------------------------------------------------------
    # Dynamic shapes
    # -----------------------------------------------------------------------
    chunk_frames_dim = torch.export.Dim("chunk_frames", min=1, max=1024)
    spkcache_seq_dim = torch.export.Dim("spkcache_seq", min=1, max=512)
    fifo_seq_dim = torch.export.Dim("fifo_seq", min=1, max=512)

    dynamic_shapes = {
        "chunk": {1: chunk_frames_dim},
        "chunk_lengths": {},
        "spkcache": {1: spkcache_seq_dim},
        "fifo": {1: fifo_seq_dim},
    }

    # -----------------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------------
    wrapper = SortformerWrapper(model).to(device)
    wrapper.eval()

    output_path = "diar_streaming_sortformer_4spk-v2.onnx"
    print(f"[export] Exporting Sortformer (dynamo) to {output_path} ...")

    torch.onnx.export(
        wrapper,
        (chunk, chunk_lengths, spkcache, fifo),
        output_path,
        input_names=["chunk", "chunk_lengths", "spkcache", "fifo"],
        output_names=["spkcache_fifo_chunk_preds", "chunk_pre_encode_embs"],
        dynamo=True,
        dynamic_shapes=dynamic_shapes,
    )

    print(f"[export] Done: {output_path}")


if __name__ == "__main__":
    main()
