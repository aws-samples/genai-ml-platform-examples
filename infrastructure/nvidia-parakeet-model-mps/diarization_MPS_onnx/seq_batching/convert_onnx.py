# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

from nemo.collections.asr.models import SortformerEncLabelModel
import torch

'''
---------------------------------------------------------------------------
Patch NeMo SortformerEncLabelModel.forward_for_export(...)
---------------------------------------------------------------------------
- Required as the forward_for_export function is built for async_streaming = True, 
  but the server implementation is using async_streaming = False.
- Removes the original concat_and_pad_script operation unsupported by ONNX with the 
  same concat function used in forward_streaming_step with async_streaming = False.
- Exported ONNX model details:
    - Contains the FastConformer + Transformer Encoders
    - The mel spectogram processor is NOT included (see SortformerEncLabelModelOnnx model)
    - Args:
        - chunk: Array containing audio waveform.
              The term "chunk" refers to the "input buffer" in the speech processing pipeline.
              The size of chunk (input buffer) determines the latency introduced by buffering.
              Shape: (batch_size, feature frame count, dimension)
        - chunk_lengths: Tensor containing lengths of audio waveforms
              Shape: (batch_size,)
        - spkcache (torch.Tensor): Tensor containing speaker cache embeddings from start
              Shape: (batch_size, spkcache_len, emb_dim)
        - fifo (torch.Tensor): Tensor containing embeddings from latest chunks
              Shape: (batch_size, fifo_len, emb_dim)
    - Returns:
          - spkcache_fifo_chunk_preds: Sorted tensor containing predicted speaker labels
        Shape: (batch_size, max. diar frame count, num_speakers)
    chunk_pre_encode_embs (torch.Tensor): Tensor containing pre-encoded embeddings from the chunk
        Shape: (batch_size, num_frames, emb_dim)
    chunk_pre_encode_lengths (torch.Tensor): Tensor containing lengths of pre-encoded embeddings
        from the chunk (=input buffer).
        Shape: (batch_size,)
---------------------------------------------------------------------------
'''
def _patched_forward_for_export(self, chunk, chunk_lengths, spkcache, fifo):
    # pre-encode the chunk
    chunk_pre_encode_embs, chunk_pre_encode_lengths = self.encoder.pre_encode(
        x=chunk, lengths=chunk_lengths
    )
    chunk_pre_encode_lengths = chunk_pre_encode_lengths.to(torch.int64)

    # concat embeddings without padding (for async_streaming = False ONLY)
    spkcache_fifo_chunk_pre_encode_embs = torch.cat(
        [spkcache, fifo, chunk_pre_encode_embs], dim=1
    )
    spkcache_fifo_chunk_pre_encode_lengths = (
        spkcache.shape[1] + fifo.shape[1] + chunk_pre_encode_lengths
    )

    # encode the concatenated embeddings
    spkcache_fifo_chunk_fc_encoder_embs, spkcache_fifo_chunk_fc_encoder_lengths = self.frontend_encoder(
        processed_signal=spkcache_fifo_chunk_pre_encode_embs,
        processed_signal_length=spkcache_fifo_chunk_pre_encode_lengths,
        bypass_pre_encode=True,
    )

    # forward pass for inference
    spkcache_fifo_chunk_preds = self.forward_infer(
        spkcache_fifo_chunk_fc_encoder_embs, spkcache_fifo_chunk_fc_encoder_lengths
    )

    # perform masking of outputs
    spkcache_fifo_chunk_preds = self.sortformer_modules.apply_mask_to_preds(
        spkcache_fifo_chunk_preds, spkcache_fifo_chunk_fc_encoder_lengths
    )

    return spkcache_fifo_chunk_preds, chunk_pre_encode_embs

## Apply patch
SortformerEncLabelModel.forward_for_export = _patched_forward_for_export
SortformerEncLabelModel.input_names = property(lambda self: ["chunk", "chunk_lengths", "spkcache", "fifo"])
SortformerEncLabelModel.output_names = property(lambda self: ["spkcache_fifo_chunk_preds", "chunk_pre_encode_embs"])

batch_size = 1
device = 'cuda' if torch.cuda.is_available() else 'cpu'

# Load model
model = SortformerEncLabelModel.from_pretrained(
    'nvidia/diar_streaming_sortformer_4spk-v2',
    map_location=device,
)
model.eval()

# ---------------------------------------------------------------------------
# Export configuration
# ---------------------------------------------------------------------------
feat_dim = 128
emb_dim = model.cfg.model_defaults.fc_d_model

## Settings used in the original code to set-up the Sortformer module
subsampling_factor = 8
mel_chunk_len = 120
mel_right_offset = 1
mel_left_offset = 1
spkcache_len = 254
fifo_len = 60

# ---------------------------------------------------------------------------
# Perform export
# ---------------------------------------------------------------------------
chunk_len = mel_chunk_len*subsampling_factor + mel_left_offset*subsampling_factor + mel_right_offset*subsampling_factor

# Chunk: mel frames [batch, chunk_len, feat_dim]
chunk = torch.rand(batch_size, chunk_len, feat_dim, device=device)
chunk_lengths = torch.tensor([chunk_len] * batch_size, dtype=torch.int64, device=device)

# Speaker cache: [batch, spkcache_len, emb_dim]
spkcache = torch.rand(batch_size, spkcache_len, emb_dim, device=device)

# FIFO: [batch, fifo_len, emb_dim]
fifo = torch.rand(batch_size, fifo_len, emb_dim, device=device)

input_example = (chunk, chunk_lengths, spkcache, fifo)

model.export(
    "diar_streaming_sortformer_4spk-v2.onnx",
    input_example=input_example,
    dynamic_axes={
        "chunk": {1: "chunk_frames"},
        "spkcache": {1: "spkcache_seq"},
        "fifo": {1: "fifo_seq"},
        "spkcache_fifo_chunk_preds": {1: "pred_seq"},
        "chunk_pre_encode_embs": {1: "enc_seq"},
    },
)
