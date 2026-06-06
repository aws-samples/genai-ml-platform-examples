# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Monkey-patch RelPositionMultiHeadAttentionLongformer to replace
`as_strided` and in-place slice assignment / masked_fill_ calls
with ONNX-traceable equivalents.

Usage:
    import patch_local_attn
    patch_local_attn.apply()
    # ... then export as usual
"""

import torch
import torch.nn.functional as F
from typing import List
from nemo.collections.asr.parts.submodules.multi_head_attention import (
    RelPositionMultiHeadAttentionLongformer,
)

_orig_chunk_overlap = RelPositionMultiHeadAttentionLongformer._chunk_overlap
_orig_sliding_qk = RelPositionMultiHeadAttentionLongformer.sliding_chunks_matmul_qk
_orig_sliding_pv = RelPositionMultiHeadAttentionLongformer.sliding_chunks_matmul_pv
_orig_mask_invalid = RelPositionMultiHeadAttentionLongformer.mask_invalid_locations


# ── helpers ──────────────────────────────────────────────────
def _chunk_overlap_safe(self, x: torch.Tensor, w: int) -> torch.Tensor:
    """ONNX-safe: replace as_strided overlapping chunks with gather.

    Builds an index tensor [chunks, 2w] and uses advanced indexing to
    extract overlapping windows.  This is the only approach that handles
    dynamic sequence lengths in the TorchScript ONNX exporter — unfold
    and narrow+stack both bake the chunk count at trace time.
    """
    # x: [BH, T, D]
    T = x.size(1)
    chunks_count = T // w - 1  # number of overlapping windows
    # Build index grid: each row is [start, start+1, ..., start+2w-1]
    starts = torch.arange(chunks_count, device=x.device) * w          # [chunks]
    offsets = torch.arange(2 * w, device=x.device)                    # [2w]
    indices = starts.unsqueeze(1) + offsets.unsqueeze(0)               # [chunks, 2w]
    return x[:, indices, :]  # [BH, chunks, 2w, D]


def _sliding_chunks_matmul_qk_safe(
    self, q: torch.Tensor, k: torch.Tensor, w: int, padding_value: float
) -> torch.Tensor:
    """ONNX-safe: replace new_empty + slice assignment with cat/pad."""
    bsz, num_heads, seqlen, head_dim = q.size()
    chunks_count = seqlen // w - 1

    q = q.reshape(bsz * num_heads, seqlen, head_dim)
    k = k.reshape(bsz * num_heads, seqlen, head_dim)

    chunk_q = self._chunk_overlap(q, w)
    chunk_k = self._chunk_overlap(k, w)

    chunk_attn = torch.einsum('bcxd,bcyd->bcxy', (chunk_q, chunk_k))
    diagonal_chunk_attn = self._skew(chunk_attn, direction=(0, 0, 0, 1), padding_value=padding_value)
    # (BH, chunks_count, 2w, 2w+1)

    BH = bsz * num_heads
    n = chunks_count + 1  # number of output blocks

    # Build diagonal_attn (BH, n, w, 2w+1) from diagonal_chunk_attn
    # using torch.cat / torch.zeros instead of in-place slice writes.

    # Upper part (columns w:) for blocks 0..n-2 come from diagonal_chunk_attn[:, :, :w, :w+1]
    upper_main = diagonal_chunk_attn[:, :, :w, : w + 1]          # (BH, chunks_count, w, w+1)
    # Upper part for last block
    upper_last = diagonal_chunk_attn[:, -1:, w:, : w + 1]        # (BH, 1, w, w+1)
    upper_all = torch.cat([upper_main, upper_last], dim=1)        # (BH, n, w, w+1)

    # Lower part (columns :w) for blocks 1..n-1 come from diagonal_chunk_attn[:, :, -(w+1):-1, w+1:]
    lower_main = diagonal_chunk_attn[:, :, -(w + 1):-1, w + 1 :] # (BH, chunks_count, w, w)

    # Lower part for block 0: need special handling
    # diagonal_attn[:, 0, 1:w, 1:w] = diagonal_chunk_attn[:, 0, :w-1, 1-w:]
    # Build full (BH, 1, w, w) for block 0
    block0_lower_inner = diagonal_chunk_attn[:, 0:1, : w - 1, 1 - w :]  # (BH, 1, w-1, w-1)
    # Pad to (BH, 1, w, w): row 0 is zeros, col 0 is zeros
    block0_lower = F.pad(block0_lower_inner, (1, 0, 1, 0), value=padding_value)  # (BH, 1, w, w)

    lower_all = torch.cat([block0_lower, lower_main], dim=1)     # (BH, n, w, w)

    # Combine: lower (w cols) + upper (w+1 cols) = 2w+1 cols
    diagonal_attn = torch.cat([lower_all, upper_all], dim=-1)    # (BH, n, w, 2w+1)

    diagonal_attn = diagonal_attn.view(bsz, num_heads, seqlen, 2 * w + 1)

    diagonal_attn = self.mask_invalid_locations(diagonal_attn, w)
    return diagonal_attn


def _sliding_chunks_matmul_pv_safe(self, prob: torch.Tensor, v: torch.Tensor, w: int):
    """ONNX-safe: replace as_strided on padded_v with gather."""
    bsz, num_heads, seqlen, head_dim = v.size()
    chunks_count = seqlen // w - 1

    chunk_prob = prob.reshape(bsz * num_heads, seqlen // w, w, 2 * w + 1)
    v = v.reshape(bsz * num_heads, seqlen, head_dim)
    padded_v = F.pad(v, (0, 0, w, w), value=-1)

    # Gather overlapping windows of size 3w with step w
    n_chunks = chunks_count + 1
    starts = torch.arange(n_chunks, device=v.device) * w
    offsets = torch.arange(3 * w, device=v.device)
    indices = starts.unsqueeze(1) + offsets.unsqueeze(0)
    chunk_v = padded_v[:, indices, :]  # [BH, chunks, 3w, D]

    skewed_prob = self._skew2(chunk_prob, padding_value=0)
    context = torch.einsum('bcwd,bcdh->bcwh', (skewed_prob, chunk_v))
    return context.view(bsz, num_heads, seqlen, head_dim).transpose(1, 2)


def _mask_invalid_locations_safe(self, input_tensor: torch.Tensor, w: int):
    """ONNX-safe: fully out-of-place masking (no tensor mutation).

    For torch.export (dynamo) compatibility, we cannot do slice assignment
    even with torch.where on the RHS.  Instead, build full-size masks via
    padding and apply a single torch.where over the whole tensor.
    """
    beginning_mask, ending_mask = self._get_invalid_locations_mask(w, input_tensor.device)
    B, H, T, W = input_tensor.shape  # W = 2w+1
    seq_len = T

    # Beginning mask: [1, 1, w, w+1] → pad to [B, H, T, W]
    bm = beginning_mask[:, :, :seq_len].expand(B, H, w, w + 1)
    bm_full = F.pad(bm, (0, W - (w + 1), 0, T - w), value=False)

    # Ending mask: [1, 1, w, w+1] → pad to [B, H, T, W]
    em = ending_mask[:, :, -seq_len:].expand(B, H, w, w + 1)
    em_full = F.pad(em, (W - (w + 1), 0, T - w, 0), value=False)

    full_mask = bm_full | em_full
    neg_inf = torch.tensor(-float('inf'), device=input_tensor.device, dtype=input_tensor.dtype)
    return torch.where(full_mask, neg_inf, input_tensor)


def apply():
    """Monkey-patch all ONNX-problematic methods."""
    RelPositionMultiHeadAttentionLongformer._chunk_overlap = _chunk_overlap_safe
    RelPositionMultiHeadAttentionLongformer.sliding_chunks_matmul_qk = _sliding_chunks_matmul_qk_safe
    RelPositionMultiHeadAttentionLongformer.sliding_chunks_matmul_pv = _sliding_chunks_matmul_pv_safe
    RelPositionMultiHeadAttentionLongformer.mask_invalid_locations = _mask_invalid_locations_safe
    print("[patch_local_attn] Patched _chunk_overlap, sliding_chunks_matmul_qk, sliding_chunks_matmul_pv, mask_invalid_locations")


def revert():
    """Restore original methods."""
    RelPositionMultiHeadAttentionLongformer._chunk_overlap = _orig_chunk_overlap
    RelPositionMultiHeadAttentionLongformer.sliding_chunks_matmul_qk = _orig_sliding_qk
    RelPositionMultiHeadAttentionLongformer.sliding_chunks_matmul_pv = _orig_sliding_pv
    RelPositionMultiHeadAttentionLongformer.mask_invalid_locations = _orig_mask_invalid
    print("[patch_local_attn] Reverted to original methods")
