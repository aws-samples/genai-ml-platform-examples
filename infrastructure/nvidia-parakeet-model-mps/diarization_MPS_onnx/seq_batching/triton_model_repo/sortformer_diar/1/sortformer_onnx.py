# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import onnxruntime as ort

from nemo.collections.asr.modules import AudioToMelSpectrogramPreprocessor
from nemo.collections.asr.modules.sortformer_modules import SortformerModules

TRT_CACHE_DIR = os.environ.get("TRT_ENGINE_CACHE_DIR", "/models/sortformer_diar/trt_cache")

# Defaults for Sortformer model (these should not be configurable)
SUBSAMPLING_FACTOR = 8      ## Within AudioToMelSpectogramProcessor
FEAT_DIM = 128              ## Mel spectogram features
EMB_DIM = 512               ## Output embeddings size after FastConformer Encoder & Transformer Encoder
N_SPK = 4                   ## Output size of prediction head (sigmoid), defines total no. of speakers

@dataclass
class _EncoderStub:
    subsampling_factor: int


class SortformerEncLabelModelOnnx:
    def __init__(self, onnx_model_path: str, device: str = "cuda"):
        self.device = device
        self._load_onnx_session(onnx_model_path)

        ## Default values based on Sortformer v2 NeMo model_config.yaml & SortformerEncLabelModel impl
        self.streaming_mode = True
        self.training = False
        self.async_streaming = False
        self.max_batch_dur = 20000
        self.eps = 1e-3

        ## Default values based on Sortformer v2 NeMo model_config.yaml
        self.sortformer_modules = SortformerModules(
            num_spks=4,
            dropout_rate=0.5,
            fc_d_model=512,
            tf_d_model=192,
            spkcache_len=188,
            fifo_len=0,
            chunk_len=188,
            spkcache_update_period=188,
            chunk_left_context=1,
            chunk_right_context=1,
            spkcache_sil_frames_per_spk=3,
            scores_add_rnd=0,
            causal_attn_rate=0.5,
            causal_attn_rc=7,
        )
        self.sortformer_modules.eval()
        self.sortformer_modules.to(self.device)

        ## Default values based on Sortformer v2 NeMo model_config.yaml
        self.preprocessor = AudioToMelSpectrogramPreprocessor(
            normalize='NA',
            window_size=0.025,
            sample_rate=16000,
            window_stride=0.01,
            window='hann',
            features=128,
            n_fft=512,
            frame_splicing=1,
            dither=1.0e-05,
        )
        self.preprocessor.sample_rate=16000
        self.preprocessor.eval()
        self.preprocessor.to(self.device)

        self.encoder = _EncoderStub(subsampling_factor=SUBSAMPLING_FACTOR)  ## Default values based on Sortformer v2 NeMo model_config.yaml

        # Pre-allocate output buffers
        s = SortformerEncLabelModelOnnx._load_shape_config()
        max_chunk_len = int(s['full_chunk_len'] / 8)
        max_fullseq_len = max_chunk_len + s['spkcache_len'] + s['fifo_len']

        self._out_preds_buf = torch.empty((1, max_fullseq_len, N_SPK), dtype=torch.float32, device=self.device).contiguous()
        self._out_embs_buf = torch.empty((1, max_chunk_len, EMB_DIM), dtype=torch.float32, device=self.device).contiguous()
        self._device_id = torch.cuda.current_device() if device == "cuda" else 0
        self._io_binding = self.ort_session.io_binding()

    @staticmethod
    def _load_shape_config() -> dict:
        """Load streaming config and compute TRT profile shape values."""
        config_path = os.path.join(os.path.dirname(__file__), "sortformer_streaming_config.json")
        try:
            with open(config_path) as f:
                cfg = json.load(f).get("sortformer_modules_config", {})
        except (FileNotFoundError, json.JSONDecodeError):
            cfg = {}

        # Additional sortformer streaming hyperparameters configurable in sortformer_streaming_config.json
        spkcache_len = cfg.get("spkcache_len", 188)
        fifo_len = cfg.get("fifo_len", 0)
        chunk_len = cfg.get("chunk_len", 188)
        chunk_left_context = cfg.get("chunk_left_context", 1)
        chunk_right_context = cfg.get("chunk_right_context", 1)

        full_chunk_len = (chunk_len + chunk_left_context + chunk_right_context) * SUBSAMPLING_FACTOR

        return {
            "spkcache_len": spkcache_len,
            "fifo_len": fifo_len,
            "full_chunk_len": full_chunk_len,
            "feat_dim": FEAT_DIM,
            "emb_dim": EMB_DIM,
        }

    @staticmethod
    def _trt_ep_options() -> dict:
        Path(TRT_CACHE_DIR).mkdir(parents=True, exist_ok=True)
        s = SortformerEncLabelModelOnnx._load_shape_config()

        return {
            "trt_fp16_enable": True,
            "trt_engine_cache_enable": True,
            "trt_engine_cache_path": TRT_CACHE_DIR,
            "trt_profile_min_shapes": f"chunk:1x1x{s['feat_dim']},fifo:1x0x{s['emb_dim']},spkcache:1x0x{s['emb_dim']}",
            "trt_profile_max_shapes": f"chunk:1x{s['full_chunk_len']}x{s['feat_dim']},fifo:1x{s['fifo_len']}x{s['emb_dim']},spkcache:1x{s['spkcache_len']}x{s['emb_dim']}",
            "trt_profile_opt_shapes": f"chunk:1x{s['full_chunk_len']}x{s['feat_dim']},fifo:1x0x{s['emb_dim']},spkcache:1x{s['spkcache_len']}x{s['emb_dim']}",
        }

    def _load_onnx_session(self, onnx_path: str):
        providers = [
            ('TensorrtExecutionProvider', self._trt_ep_options()),
            'CUDAExecutionProvider',
            'CPUExecutionProvider',
        ]
        self.ort_session = ort.InferenceSession(onnx_path, providers=providers)

    @classmethod
    def warmup_trt_cache(cls, onnx_path: str):
        """Build TRT engine cache with a single session + dummy inference.

        Call this once before Triton starts so that all model instances
        reuse the cached engines instead of each rebuilding them.
        """
        cache_dir = Path(TRT_CACHE_DIR)
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Skip if cache already populated from a previous run
        if any(cache_dir.glob("*.engine")):
            print(f"[trt-warmup] Cache already exists at {TRT_CACHE_DIR}, skipping build", flush=True)
            return

        print(f"[trt-warmup] No cached engines found — building TRT cache at {TRT_CACHE_DIR} ...", flush=True)

        providers = [
            ('TensorrtExecutionProvider', cls._trt_ep_options()),
            'CUDAExecutionProvider',
            'CPUExecutionProvider',
        ]
        session = ort.InferenceSession(onnx_path, providers=providers)

        s = cls._load_shape_config()

        # Run a dummy inference to trigger engine build for the opt profile shapes
        dummy_chunk = np.zeros((1, s["full_chunk_len"], s["feat_dim"]), dtype=np.float32)
        dummy_chunk_lengths = np.array([s["full_chunk_len"]], dtype=np.int64)
        dummy_spkcache = np.zeros((1, s["spkcache_len"], s["emb_dim"]), dtype=np.float32)
        dummy_fifo = np.zeros((1, s["fifo_len"], s["emb_dim"]), dtype=np.float32)

        session.run(
            None,
            {
                "chunk": dummy_chunk,
                "chunk_lengths": dummy_chunk_lengths,
                "spkcache": dummy_spkcache,
                "fifo": dummy_fifo,
            },
        )
        del session
        print("[trt-warmup] TRT engine cache built successfully", flush=True)

    def eval(self):
        """No-op — keeps the same interface as the NeMo model."""
        return self

    ## 1-1 copy from SortformerEncLabelModel
    def process_signal(self, audio_signal, audio_signal_length):
        """
        Extract audio features from time-series signal for further processing in the model.

        This function performs the following steps:
        1. Moves the audio signal to the correct device.
        2. Normalizes the time-series audio signal.
        3. Extrac audio feature from from the time-series audio signal using the model's preprocessor.

        Args:
            audio_signal (torch.Tensor): The input audio signal.
                Shape: (batch_size, num_samples)
            audio_signal_length (torch.Tensor): The length of each audio signal in the batch.
                Shape: (batch_size,)

        Returns:
            processed_signal (torch.Tensor): The preprocessed audio signal.
                Shape: (batch_size, num_features, num_frames)
            processed_signal_length (torch.Tensor): The length of each processed signal.
                Shape: (batch_size,)
        """
        audio_signal, audio_signal_length = audio_signal.to(self.device), audio_signal_length.to(self.device)
        if not self.streaming_mode:
            audio_signal = (1 / (audio_signal.max() + self.eps)) * audio_signal

        batch_total_dur = audio_signal.shape[0] * audio_signal.shape[1] / self.preprocessor.sample_rate
        if self.max_batch_dur > 0 and self.max_batch_dur < batch_total_dur:
            processed_signal, processed_signal_length = self.oom_safe_feature_extraction(
                input_signal=audio_signal, input_signal_length=audio_signal_length
            )
        else:
            processed_signal, processed_signal_length = self.preprocessor(
                input_signal=audio_signal, length=audio_signal_length
            )
        # Note: torch.cuda.empty_cache() removed here — it causes severe contention
        # under concurrent requests and can invalidate IO binding GPU memory references.
        if not self.training and self.streaming_mode:
            del audio_signal, audio_signal_length
        return processed_signal, processed_signal_length

    ## 1-1 copy from SortformerEncLabelModel
    def oom_safe_feature_extraction(self, input_signal, input_signal_length):
        """
        This function divides the input signal into smaller sub-batches and processes them sequentially
        to prevent out-of-memory errors during feature extraction.

        Args:
            input_signal (torch.Tensor): The input audio signal.
            input_signal_length (torch.Tensor): The lengths of the input audio signals.

        Returns:
            processed_signal (torch.Tensor): The aggregated audio signal.
                                             The length of this tensor should match the original batch size.
            processed_signal_length (torch.Tensor): The lengths of the processed audio signals.
        """
        input_signal = input_signal.cpu()
        processed_signal_list, processed_signal_length_list = [], []
        max_batch_sec = input_signal.shape[1] / self.preprocessor.sample_rate
        org_batch_size = input_signal.shape[0]
        div_batch_count = min(int(max_batch_sec * org_batch_size // self.max_batch_dur + 1), org_batch_size)
        div_size = math.ceil(org_batch_size / div_batch_count)

        for div_count in range(div_batch_count):
            start_idx = int(div_count * div_size)
            end_idx = int((div_count + 1) * div_size)
            if start_idx >= org_batch_size:
                break
            input_signal_div = input_signal[start_idx:end_idx, :].to(self.device)
            input_signal_length_div = input_signal_length[start_idx:end_idx]
            processed_signal_div, processed_signal_length_div = self.preprocessor(
                input_signal=input_signal_div, length=input_signal_length_div
            )
            processed_signal_div = processed_signal_div.detach().cpu()
            processed_signal_length_div = processed_signal_length_div.detach().cpu()
            processed_signal_list.append(processed_signal_div)
            processed_signal_length_list.append(processed_signal_length_div)

        processed_signal = torch.cat(processed_signal_list, 0)
        processed_signal_length = torch.cat(processed_signal_length_list, 0)
        assert processed_signal.shape[0] == org_batch_size, (
            f"The resulting batch size of processed signal - {processed_signal.shape[0]} "
            f"is not equal to original batch size: {org_batch_size}"
        )
        processed_signal = processed_signal.to(self.device)
        processed_signal_length = processed_signal_length.to(self.device)
        return processed_signal, processed_signal_length

    def forward_streaming_step(
        self,
        processed_signal,
        processed_signal_length,
        streaming_state,
        total_preds,
        drop_extra_pre_encoded=0,
        left_offset=0,
        right_offset=0,
    ):
        """
        One-step forward pass for diarization inference in streaming mode.

        Args:
            processed_signal (torch.Tensor): Tensor containing mel spectrogram chunk
                Shape: (batch_size, num_frames, feat_dim)
            processed_signal_length (torch.Tensor): Tensor containing lengths of mel chunks
                Shape: (batch_size,)
            streaming_state (SortformerStreamingState): Streaming state with spkcache, fifo, etc.
            total_preds (torch.Tensor): Accumulated speaker activity predictions
                Shape: (batch_size, cumulative pred length, num_speakers)
            left_offset (int): left offset for the current chunk
            right_offset (int): right offset for the current chunk

        Returns:
            streaming_state: Updated streaming state.
            total_preds: Updated total predictions.

        NOTE: Logic is matched to SortformerEncLabelModel implementation for async_streaming=False & drop_extra_pre_encoded=0
        For async_streaming=True and/or drop_extra_pre_encoded>0, a different ONNX model export is required, this fn needs to be updated.
        """
        self._io_binding.clear_binding_inputs()
        self._io_binding.clear_binding_outputs()

        chunk = processed_signal.contiguous()
        chunk_lens = processed_signal_length.contiguous()
        spkcache = streaming_state.spkcache.contiguous()
        fifo = streaming_state.fifo.contiguous()

        for name, tensor, dtype in [
            ("chunk", chunk, np.float32),
            ("chunk_lengths", chunk_lens, np.int64),
            ("spkcache", spkcache, np.float32),
            ("fifo", fifo, np.float32),
        ]:
            self._io_binding.bind_input(
                name=name,
                device_type="cuda",
                device_id=self._device_id,
                element_type=dtype,
                shape=tuple(tensor.shape),
                buffer_ptr=tensor.data_ptr(),
            )

        chunk_embs_len = math.ceil(chunk.shape[1] / SUBSAMPLING_FACTOR)
        out_seq_len = chunk_embs_len + spkcache.shape[1] + fifo.shape[1]

        # Bind outputs to pre-allocated buffers with exact shape (no per-call allocation)
        self._io_binding.bind_output(
            name='spkcache_fifo_chunk_preds',
            device_type='cuda',
            device_id=self._device_id,
            element_type=np.float32,
            shape=(1, out_seq_len, N_SPK),
            buffer_ptr=self._out_preds_buf.data_ptr(),
        )
        self._io_binding.bind_output(
            name='chunk_pre_encode_embs',
            device_type='cuda',
            device_id=self._device_id,
            element_type=np.float32,
            shape=(1, chunk_embs_len, EMB_DIM),
            buffer_ptr=self._out_embs_buf.data_ptr(),
        )

        self.ort_session.run_with_iobinding(self._io_binding)

        spkcache_fifo_chunk_preds = self._out_preds_buf[:, :out_seq_len, :]
        chunk_pre_encode_embs = self._out_embs_buf[:, :chunk_embs_len, :]

        streaming_state, chunk_preds = self.sortformer_modules.streaming_update(
            streaming_state=streaming_state,
            chunk=chunk_pre_encode_embs,
            preds=spkcache_fifo_chunk_preds,
            lc=round(left_offset / self.encoder.subsampling_factor),
            rc=math.ceil(right_offset / self.encoder.subsampling_factor),
        )

        total_preds = torch.cat([total_preds, chunk_preds], dim=1)

        return streaming_state, total_preds
