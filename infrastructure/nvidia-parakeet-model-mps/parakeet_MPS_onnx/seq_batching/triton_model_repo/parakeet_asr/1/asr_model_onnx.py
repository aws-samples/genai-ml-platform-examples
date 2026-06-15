# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
ASRModelOnnx: Lightweight ONNX-backed replacement for NeMo's ASRModel.

Exposes the same interface that model.py's _infer_batch() uses:
  - forward(input_signal, input_signal_length) → (encoded, encoded_len)
  - decoding.rnnt_decoder_predictions_tensor(encoded, encoded_len, ...)
  - cfg.decoding.compute_timestamps (read/write)
  - cfg['preprocessor']['window_stride']
  - encoder.subsampling_factor
  - change_decoding_strategy(cfg, verbose=False)
  - eval(), freeze(), to(device)

Backed by two ONNX files produced by convert_onnx.py:
  - encoder-parakeet.onnx       (preprocessor + conformer)
  - decoder_joint-parakeet.onnx (LSTM decoder + joint, fused)
"""

import os
from typing import List, Optional

import numpy as np
import onnxruntime as ort
import torch

from nemo.collections.asr.parts.utils.rnnt_utils import Hypothesis
from nemo.collections.asr.modules import AudioToMelSpectrogramPreprocessor
from nemo.collections.common.tokenizers import SentencePieceTokenizer


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
## From NeMo model
SUBSAMPLING_FACTOR = 8
WINDOW_STRIDE = 0.01       # preprocessor.window_stride
PRED_RNN_LAYERS = 2
PRED_HIDDEN = 640
VOCAB_SIZE = 1024
NUM_TDT_DURATIONS = 5      # durations: [0, 1, 2, 3, 4]
BLANK_INDEX = VOCAB_SIZE    # blank is last token in vocab
MAX_SYMBOLS_PER_STEP = 10
TDT_DURATIONS = [0, 1, 2, 3, 4]

## For TensorRT engine
TRT_CACHE_DIR = os.environ.get("TRT_ENGINE_CACHE_DIR", "/models/parakeet_asr/trt_cache")

MAX_BATCH_SIZE = 16

# ---------------------------------------------------------------------------
# Stub classes to satisfy attribute access from model.py
# ---------------------------------------------------------------------------
class _EncoderStub:
    def __init__(self):
        self.subsampling_factor = SUBSAMPLING_FACTOR


class _DecodingCfg:
    """Mutable config object mimicking OmegaConf DictConfig for decoding settings."""
    def __init__(self):
        self.compute_timestamps = False

    def get(self, key, default=None):
        return getattr(self, key, default)


class _Cfg:
    """Mimics model.cfg with the subset of keys model.py accesses."""
    def __init__(self):
        self.decoding = _DecodingCfg()
        self._data = {
            'preprocessor': {'window_stride': WINDOW_STRIDE},
        }

    def __getitem__(self, key):
        return self._data[key]


# ---------------------------------------------------------------------------
# ONNX session helpers
# ---------------------------------------------------------------------------
def _trt_ep_options(onnx_path: str) -> dict:
    """Build TRT EP options with shape profiles appropriate for the model."""
    from pathlib import Path
    Path(TRT_CACHE_DIR).mkdir(parents=True, exist_ok=True)

    basename = os.path.basename(onnx_path).lower()
    opts = {
        "trt_fp16_enable": True,
        "trt_engine_cache_enable": True,
        "trt_engine_cache_path": TRT_CACHE_DIR,
    }

    if "encoder" in basename:
        # Encoder: audio_signal [B, 128, T_mel], length [B]
        opts["trt_profile_min_shapes"] = "audio_signal:1x128x500,length:1"
        opts["trt_profile_max_shapes"] = f"audio_signal:{MAX_BATCH_SIZE}x128x6001,length:{MAX_BATCH_SIZE}"
        opts["trt_profile_opt_shapes"] = "audio_signal:4x128x4501,length:4"
    elif "decoder_joint" in basename:
        # Decoder_joint: encoder_outputs [B, 1024, 1], targets [B, 1],
        # target_length [B], input_states [2, B, 640] x2
        opts["trt_profile_min_shapes"] = (
            "encoder_outputs:1x1024x1,targets:1x1,target_length:1,"
            "input_states_1:2x1x640,input_states_2:2x1x640"
        )
        opts["trt_profile_max_shapes"] = (
            f"encoder_outputs:{MAX_BATCH_SIZE}x1024x1,targets:{MAX_BATCH_SIZE}x1,target_length:{MAX_BATCH_SIZE},"
            f"input_states_1:2x{MAX_BATCH_SIZE}x640,input_states_2:2x{MAX_BATCH_SIZE}x640"
        )
        opts["trt_profile_opt_shapes"] = (
            "encoder_outputs:4x1024x1,targets:4x1,target_length:4,"
            "input_states_1:2x4x640,input_states_2:2x4x640"
        )
    return opts


def _load_onnx_session(onnx_path: str) -> ort.InferenceSession:
    opts = ort.SessionOptions()
    opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    providers = [
        ('TensorrtExecutionProvider', _trt_ep_options(onnx_path)),
        'CUDAExecutionProvider',
        'CPUExecutionProvider',
    ]

    sess = ort.InferenceSession(onnx_path, sess_options=opts, providers=providers)

    active = sess.get_providers()
    print(f"[ORT] {os.path.basename(onnx_path)}: requested={[p if isinstance(p, str) else p[0] for p in providers]}, active={active}", flush=True)
    return sess


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------
class ASRModelOnnx:
    """
    Lightweight ONNX-backed replacement for NeMo's ASRModel.

    Usage:
        model = ASRModelOnnx(onnx_dir="/path/to/onnx_out", tokenizer=tokenizer)

    Then in model.py, self.model can be either a NeMo ASRModel or this class —
    the same _infer_batch() code works for both.

    Note: The exported encoder ONNX does NOT include the mel preprocessor.
    NeMo's export produces an encoder that expects [B, 128, T_frames] mel features,
    not raw audio. We run the preprocessor in PyTorch and feed its output to ONNX.
    """

    def __init__(self, onnx_dir: str, tokenizer_path: str, device: str = "cuda"):
        """
        Args:
            onnx_dir: Directory containing encoder-*.onnx and decoder_joint-*.onnx
            tokenizer_path: Path to tokenizer .model file, extracted from .nemo file
            device: "cuda" or "cpu"
        """
        self.device = device
        self.cfg = _Cfg()
        self.encoder = _EncoderStub()

        ## Default values based on Parakeet 0.6B TDT v2 NeMo model_config.yaml
        self.preprocessor = AudioToMelSpectrogramPreprocessor(
            sample_rate=16000,
            normalize='per_feature',
            window_size=0.025,
            window_stride=WINDOW_STRIDE,
            window='hann',
            features=128,
            n_fft=512,
            log=True,
            frame_splicing=1,
            dither=1.0e-05,
            pad_to=0,
            pad_value=0.0,
        )
        self.preprocessor.eval()
        self.preprocessor.to(self.device)

        # Load tokenizer
        self._tokenizer = SentencePieceTokenizer(model_path=tokenizer_path)

        # Resolve ONNX file names (NeMo names them encoder-<base>.onnx)
        encoder_path = self._find_onnx(onnx_dir, "encoder")
        decoder_joint_path = self._find_onnx(onnx_dir, "decoder_joint")

        print(f"[ASRModelOnnx] Loading encoder: {encoder_path}", flush=True)
        self._encoder_session = _load_onnx_session(encoder_path)
        self._enc_input_names = [i.name for i in self._encoder_session.get_inputs()]

        print(f"[ASRModelOnnx] Loading decoder_joint: {decoder_joint_path}", flush=True)
        dj_session = _load_onnx_session(decoder_joint_path)
        self.decoding = OnnxTDTDecoding(dj_session, self._tokenizer, device)

    @staticmethod
    def _find_onnx(onnx_dir: str, prefix: str) -> str:
        """Find the ONNX file matching a prefix (e.g. 'encoder' or 'decoder_joint')."""
        for f in os.listdir(onnx_dir):
            if f.startswith(prefix) and f.endswith(".onnx"):
                return os.path.join(onnx_dir, f)
        raise FileNotFoundError(f"No {prefix}*.onnx found in {onnx_dir}")

    @classmethod
    def warmup_trt_cache(cls, onnx_dir: str):
        """Build TRT engine cache with a single session + dummy inference.

        Call this once before Triton starts so that all model instances
        reuse the cached engines instead of each rebuilding them.
        """
        from pathlib import Path

        cache_dir = Path(TRT_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        if any(cache_dir.glob("*.engine")):
            print(f"[trt-warmup] Cache already exists at {TRT_CACHE_DIR}, skipping build", flush=True)
            return

        print(f"[trt-warmup] No cached engines found — building TRT cache at {TRT_CACHE_DIR} ...", flush=True)

        encoder_path = cls._find_onnx(onnx_dir, "encoder")
        decoder_joint_path = cls._find_onnx(onnx_dir, "decoder_joint")

        # Warm up encoder at opt shape [B=4, 128, 3001]
        enc_sess = _load_onnx_session(encoder_path)
        dummy_mel = np.zeros((4, 128, 3001), dtype=np.float32)
        dummy_mel_len = np.array([3001, 3001, 3001, 3001], dtype=np.int64)
        enc_sess.run(None, {
            enc_sess.get_inputs()[0].name: dummy_mel,
            enc_sess.get_inputs()[1].name: dummy_mel_len,
        })
        del enc_sess

        # Warm up decoder_joint at opt shape [B=4]
        OPT_B = 4
        dj_sess = _load_onnx_session(decoder_joint_path)
        dj_inputs = {
            dj_sess.get_inputs()[0].name: np.zeros((OPT_B, 1024, 1), dtype=np.float32),
            dj_sess.get_inputs()[1].name: np.full((OPT_B, 1), BLANK_INDEX, dtype=np.int32),
            dj_sess.get_inputs()[2].name: np.ones(OPT_B, dtype=np.int32),
            dj_sess.get_inputs()[3].name: np.zeros((PRED_RNN_LAYERS, OPT_B, PRED_HIDDEN), dtype=np.float32),
            dj_sess.get_inputs()[4].name: np.zeros((PRED_RNN_LAYERS, OPT_B, PRED_HIDDEN), dtype=np.float32),
        }
        dj_sess.run(None, dj_inputs)
        del dj_sess

        print("[trt-warmup] TRT engine cache built successfully", flush=True)


    def forward(self, input_signal=None, input_signal_length=None, **kwargs):
        """
        Run preprocessor (PyTorch) + encoder (ONNX).
        Same signature as EncDecRNNTModel.forward().

        The ONNX encoder expects mel features [B, D, T_frames], not raw audio.
        We run the NeMo preprocessor in PyTorch first.

        Returns:
            encoded: [B, D, T_enc] torch tensor
            encoded_len: [B] torch tensor
        """
        # Step 1: Mel spectrogram (PyTorch)
        with torch.no_grad():
            processed_signal, processed_signal_length = self.preprocessor(
                input_signal=input_signal, length=input_signal_length
            )

        # Step 2: Conformer encoder (ONNX)
        mel_np = processed_signal.detach().cpu().numpy().astype(np.float32)
        length_np = processed_signal_length.detach().cpu().numpy().astype(np.int64)

        feed = {
            self._enc_input_names[0]: mel_np,
            self._enc_input_names[1]: length_np,
        }
        enc_out, enc_len = self._encoder_session.run(None, feed)

        return (
            torch.from_numpy(enc_out).to(self.device),
            torch.from_numpy(enc_len).to(self.device).long(),
        )

    def change_decoding_strategy(self, decoding_cfg, verbose=False):
        """No-op — ONNX decoding doesn't use NeMo's strategy objects."""
        pass

    def eval(self):
        return self

    def freeze(self):
        pass

    def to(self, device):
        self.device = device if isinstance(device, str) else str(device)
        return self


# ---------------------------------------------------------------------------
# Hybrid model: ONNX encoder + NeMo PyTorch decoder/joint/decoding
# ---------------------------------------------------------------------------
class ASRModelHybrid:
    """
    ONNX encoder with NeMo's original PyTorch decoder, joint, and decoding.

    This gives us:
    - Fast ONNX/TRT encoder inference
    - NeMo's batched TDT greedy decoding (GreedyBatchedTDTInfer) for free
    - Full timestamp support without reimplementation

    The NeMo model is loaded for its decoder/joint/decoding/tokenizer/preprocessor,
    then the encoder forward is replaced with the ONNX session.
    """

    def __init__(self, onnx_dir: str, nemo_model, device: str = "cuda"):
        """
        Args:
            onnx_dir: Directory containing encoder-*.onnx
            nemo_model: NeMo EncDecRNNTBPEModel with encoder already deleted,
                        decoder/joint/preprocessor on device, eval'd and frozen.
            device: "cuda" or "cpu"
        """
        self.device = device

        # Expose NeMo model attributes that model.py accesses
        self.cfg = nemo_model.cfg
        self.encoder = _EncoderStub()
        self.decoding = nemo_model.decoding
        self.preprocessor = nemo_model.preprocessor
        self._tokenizer = nemo_model.tokenizer
        self.change_decoding_strategy = nemo_model.change_decoding_strategy

        # Load ONNX encoder
        encoder_path = ASRModelOnnx._find_onnx(onnx_dir, "encoder")
        print(f"[ASRModelHybrid] Loading ONNX encoder: {encoder_path}", flush=True)
        self._encoder_session = _load_onnx_session(encoder_path)
        self._enc_input_names = [i.name for i in self._encoder_session.get_inputs()]
        print(f"[ASRModelHybrid] Using NeMo PyTorch decoder/joint/decoding", flush=True)

    def forward(self, input_signal=None, input_signal_length=None, **kwargs):
        """
        Run preprocessor (PyTorch) + encoder (ONNX).
        Returns same format as EncDecRNNTModel.forward().
        """
        with torch.no_grad():
            processed_signal, processed_signal_length = self.preprocessor(
                input_signal=input_signal, length=input_signal_length
            )

        mel_np = processed_signal.detach().cpu().numpy().astype(np.float32)
        length_np = processed_signal_length.detach().cpu().numpy().astype(np.int64)

        feed = {
            self._enc_input_names[0]: mel_np,
            self._enc_input_names[1]: length_np,
        }
        enc_out, enc_len = self._encoder_session.run(None, feed)

        return (
            torch.from_numpy(enc_out).to(self.device),
            torch.from_numpy(enc_len).to(self.device).long(),
        )

    def eval(self):
        return self

    def freeze(self):
        pass

    def to(self, device):
        self.device = device if isinstance(device, str) else str(device)
        return self

    @classmethod
    def warmup_trt_cache(cls, onnx_dir: str):
        """Build TRT engine cache for the encoder only."""
        from pathlib import Path

        cache_dir = Path(TRT_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        if any(cache_dir.glob("*.engine")):
            print(f"[trt-warmup] Cache already exists at {TRT_CACHE_DIR}, skipping build", flush=True)
            return

        print(f"[trt-warmup] Building TRT cache for encoder...", flush=True)

        encoder_path = ASRModelOnnx._find_onnx(onnx_dir, "encoder")
        enc_sess = _load_onnx_session(encoder_path)
        dummy_mel = np.zeros((1, 128, 3000), dtype=np.float32)
        dummy_mel_len = np.array([3000], dtype=np.int64)
        enc_sess.run(None, {
            enc_sess.get_inputs()[0].name: dummy_mel,
            enc_sess.get_inputs()[1].name: dummy_mel_len,
        })
        del enc_sess
        print("[trt-warmup] TRT engine cache built successfully", flush=True)


# ---------------------------------------------------------------------------
# TDT greedy decoding over ONNX decoder_joint
# ---------------------------------------------------------------------------
class OnnxTDTDecoding:
    """
    Batched TDT greedy decoding using the fused decoder_joint ONNX session.

    Processes all samples in the batch simultaneously at each time step,
    similar to NeMo's GreedyBatchedTDTLabelLoopingComputer.

    The fused graph signature (from NeMo's RNNTDecoderJoint export):
        Inputs:
            encoder_outputs  [B, D_enc, T]
            targets          [B, U]        int32
            target_length    [B]           int32
            input_states_1   [layers, B, D_pred]  (LSTM hidden)
            input_states_2   [layers, B, D_pred]  (LSTM cell)
        Outputs:
            joint_output     [B, T, U, V+1+durations]
            prednet_lengths  [B]
            output_states_1  [layers, B, D_pred]
            output_states_2  [layers, B, D_pred]
    """

    def __init__(self, session: ort.InferenceSession, tokenizer, device: str = "cuda"):
        self._session = session
        self._tokenizer = tokenizer
        self._device = device
        self._input_names = [i.name for i in session.get_inputs()]

    def _run_decoder_joint_batched(self, enc_frames, targets, target_len, state_h, state_c):
        """Batched step through the fused ONNX decoder_joint graph.

        Args:
            enc_frames: [B, D_enc, 1] encoder frames for current time indices
            targets:    [B, 1] last emitted tokens (int32)
            target_len: [B] (int32, all ones)
            state_h:    [layers, B, D_pred] LSTM hidden
            state_c:    [layers, B, D_pred] LSTM cell

        Returns:
            joint_output: [B, 1, 1, V+1+durations]
            new_state_h:  [layers, B, D_pred]
            new_state_c:  [layers, B, D_pred]
        """
        feed = {
            self._input_names[0]: enc_frames,
            self._input_names[1]: targets,
            self._input_names[2]: target_len,
            self._input_names[3]: state_h,
            self._input_names[4]: state_c,
        }
        results = self._session.run(None, feed)
        return results[0], results[2], results[3]

    def rnnt_decoder_predictions_tensor(
        self,
        encoder_output: torch.Tensor,
        encoded_lengths: torch.Tensor,
        return_hypotheses: bool = False,
        partial_hypotheses=None,
    ) -> list:
        """
        Batched TDT greedy decoding.

        Args:
            encoder_output: [B, D, T] torch tensor
            encoded_lengths: [B] torch tensor
            return_hypotheses: if True, return Hypothesis objects with .text

        Returns:
            tuple of (list[Hypothesis], None)
        """
        encoded = encoder_output.detach().cpu().numpy()
        encoded_len = encoded_lengths.detach().cpu().numpy().astype(np.int64)

        batch_size = encoded.shape[0]
        max_time = encoded.shape[2]

        # Batched state
        state_h = np.zeros((PRED_RNN_LAYERS, batch_size, PRED_HIDDEN), dtype=np.float32)
        state_c = np.zeros((PRED_RNN_LAYERS, batch_size, PRED_HIDDEN), dtype=np.float32)

        time_indices = np.zeros(batch_size, dtype=np.int64)
        last_tokens = np.full(batch_size, BLANK_INDEX, dtype=np.int32)
        active = np.ones(batch_size, dtype=bool)

        token_ids_per_sample = [[] for _ in range(batch_size)]
        timestamps_per_sample = [[] for _ in range(batch_size)]

        while np.any(active):
            # Mark samples that have exceeded their encoded length as inactive
            for b in range(batch_size):
                if active[b] and time_indices[b] >= min(max_time, encoded_len[b]):
                    active[b] = False

            if not np.any(active):
                break

            # Gather encoder frames for all active samples at their current time index
            # Clamp time indices to valid range for gathering
            safe_t = np.minimum(time_indices, max_time - 1)
            enc_frames = np.stack([
                encoded[b, :, safe_t[b]:safe_t[b]+1] for b in range(batch_size)
            ], axis=0).astype(np.float32)  # [B, D, 1]

            targets = last_tokens.reshape(batch_size, 1).astype(np.int32)  # [B, 1]
            target_len = np.ones(batch_size, dtype=np.int32)               # [B]

            symbols_emitted = np.zeros(batch_size, dtype=np.int64)
            step_active = active.copy()

            for _ in range(MAX_SYMBOLS_PER_STEP):
                if not np.any(step_active):
                    break

                joint_out, new_sh, new_sc = self._run_decoder_joint_batched(
                    enc_frames, targets, target_len, state_h, state_c
                )
                # joint_out: [B, 1, 1, V+1+durations]
                logits = joint_out[:, 0, 0, :]  # [B, V+1+durations]

                token_logits = logits[:, :VOCAB_SIZE + 1]       # [B, V+1]
                duration_logits = logits[:, VOCAB_SIZE + 1:]    # [B, num_durations]

                token_ids = np.argmax(token_logits, axis=-1)    # [B]
                dur_ids = np.argmax(duration_logits, axis=-1)   # [B]
                durations = np.array([TDT_DURATIONS[d] if d < len(TDT_DURATIONS) else 1 for d in dur_ids])

                blank_mask = token_ids == BLANK_INDEX  # [B]

                for b in range(batch_size):
                    if not step_active[b]:
                        continue

                    if blank_mask[b]:
                        # Blank: advance time, do NOT update LSTM state
                        time_indices[b] += max(int(durations[b]), 1)
                        step_active[b] = False
                        if time_indices[b] >= min(max_time, encoded_len[b]):
                            active[b] = False
                    else:
                        # Token: emit, update state, stay at same time
                        token_ids_per_sample[b].append(int(token_ids[b]))
                        timestamps_per_sample[b].append(int(time_indices[b]))
                        symbols_emitted[b] += 1
                        last_tokens[b] = token_ids[b]
                        state_h[:, b:b+1, :] = new_sh[:, b:b+1, :]
                        state_c[:, b:b+1, :] = new_sc[:, b:b+1, :]

                # Update targets for next inner iteration (non-blank samples continue)
                targets = last_tokens.reshape(batch_size, 1).astype(np.int32)

                # Re-gather encoder frames (time indices unchanged for non-blank)
                safe_t = np.minimum(time_indices, max_time - 1)
                enc_frames = np.stack([
                    encoded[b, :, safe_t[b]:safe_t[b]+1] for b in range(batch_size)
                ], axis=0).astype(np.float32)

        # Build Hypothesis objects
        hypotheses = []
        for b in range(batch_size):
            ids = token_ids_per_sample[b]
            text = self._tokenizer.ids_to_text(ids) if ids else ""
            ts = timestamps_per_sample[b]

            hyp = Hypothesis(
                score=-1.0,
                y_sequence=torch.tensor(ids, dtype=torch.long),
                text=text,
                timestamp=ts,
            )
            hyp.length = torch.tensor(len(ids))

            if return_hypotheses and ids and ts:
                char_offsets = []
                for token_id, frame_idx in zip(ids, ts):
                    char_offsets.append({
                        "char": [token_id],
                        "start_offset": frame_idx,
                        "end_offset": frame_idx + 1,
                    })

                word_offsets = []
                current_word_tokens = []
                current_start = None

                for i, (token_id, frame_idx) in enumerate(zip(ids, ts)):
                    token_text = self._tokenizer.ids_to_tokens([token_id])[0]
                    is_word_start = token_text.startswith("▁") or i == 0

                    if is_word_start and current_word_tokens:
                        word_text = self._tokenizer.ids_to_text(current_word_tokens)
                        word_offsets.append({
                            "word": word_text,
                            "start_offset": current_start,
                            "end_offset": frame_idx,
                        })
                        current_word_tokens = []
                        current_start = frame_idx

                    if current_start is None:
                        current_start = frame_idx
                    current_word_tokens.append(token_id)

                if current_word_tokens:
                    word_text = self._tokenizer.ids_to_text(current_word_tokens)
                    last_frame = ts[-1] + 1 if ts else 0
                    word_offsets.append({
                        "word": word_text,
                        "start_offset": current_start,
                        "end_offset": last_frame,
                    })

                timestamp_dict = {
                    "timestep": ts,
                    "word": word_offsets,
                    "char": char_offsets,
                }
                hyp.timestamp = timestamp_dict
                hyp.timestep = timestamp_dict

            hypotheses.append(hyp)

        if return_hypotheses:
            return (hypotheses, None)
        return (hypotheses, None)
