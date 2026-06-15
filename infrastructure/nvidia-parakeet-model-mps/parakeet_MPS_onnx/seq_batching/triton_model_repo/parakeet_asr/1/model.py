# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Triton Python backend for Parakeet TDT ASR (stateless).

Bypasses NeMo's high-level transcribe() API to avoid per-request overhead:
- No tempdir creation, no DataLoader, no manifest, no tqdm
- Direct: audio → preprocessor → encoder → decoder
- Dedicated CUDA stream per instance for MPS overlap
"""

import fcntl
import json
import os
import numpy as np
import torch
import tempfile
from omegaconf import open_dict

import triton_python_backend_utils as pb_utils

from nemo.collections.asr.models import ASRModel

SAMPLE_RATE = 16000
_LOAD_LOCK = os.path.join(tempfile.gettempdir(), "parakeet_load.lock")
_OPTIMIZED_PATH = "/opt/parakeet_optimized.nemo"


class TritonPythonModel:

    @staticmethod
    def _patch_abstract_methods():
        """Remove abstract method enforcement from ASRModel and all subclasses for inference-only use."""
        def _clear(cls):
            if getattr(cls, '__abstractmethods__', None):
                cls.__abstractmethods__ = frozenset()
            for sub in cls.__subclasses__():
                _clear(sub)
        _clear(ASRModel)

    @staticmethod
    def _restore_lenient(path):
        """Restore .nemo checkpoint, tolerating extra keys and missing abstract methods."""
        import torch.nn as nn
        _orig = nn.Module.load_state_dict
        def _lenient(self, sd, *a, strict=True, **kw):
            return _orig(self, sd, *a, strict=False, **kw)
        nn.Module.load_state_dict = _lenient
        TritonPythonModel._patch_abstract_methods()
        try:
            return ASRModel.restore_from(path, map_location="cpu")
        finally:
            nn.Module.load_state_dict = _orig

    @staticmethod
    def _from_pretrained_lenient(model_name):
        """from_pretrained with abstract method stubs."""
        TritonPythonModel._patch_abstract_methods()
        m = ASRModel.from_pretrained(model_name, map_location="cpu")
        m.change_attention_model("rel_pos_local_attn", [128, 128])
        m.change_subsampling_conv_chunking_factor(1)
        return m

    def initialize(self, args):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        model_config = json.loads(args["model_config"])
        params = model_config.get("parameters", {})
        self.use_onnx = params.get("use_onnx", {}).get("string_value", "false").lower() == "true"

        self._open_dict = open_dict

        print("Initialising Parakeet model...", flush=True)
        if self.use_onnx:
            self._initialize_onnx(params)
        else:
            self._initialize_pytorch(params)

        if self.device == "cuda":
            print("Warming up...", flush=True)
            self._stream = torch.cuda.Stream()
            self._warmup()

    def _initialize_onnx(self, params):
        """Load ONNX-backed model. Two modes:

        use_orig_decoder_joint=true (hybrid):
            ONNX encoder + NeMo PyTorch decoder & joint greedy loop.

        use_orig_decoder_joint=false (full ONNX):
            ONNX encoder + ONNX combined decoder+joint with custom greedy loop. (not recommended)
        """
        onnx_dir = params.get("onnx_dir", {}).get("string_value", "/models/parakeet_asr/1")
        use_orig = params.get("use_orig_decoder_joint", {}).get("string_value", "false").lower() == "true"

        if use_orig:
            from asr_model_onnx import ASRModelHybrid

            # Load NeMo model on CPU — avoids putting the encoder on GPU at all
            model_name = params.get("model_name", {}).get("string_value", "nvidia/parakeet-tdt-0.6b-v2")
            with open(_LOAD_LOCK, "w") as lf:
                fcntl.flock(lf, fcntl.LOCK_EX)
                try:
                    if os.path.exists(_OPTIMIZED_PATH):
                        nemo_model = self._restore_lenient(_OPTIMIZED_PATH)
                    elif model_name.endswith(".nemo"):
                        nemo_model = self._restore_lenient(model_name)
                    else:
                        nemo_model = self._from_pretrained_lenient(model_name)

                    # Delete encoder, not needed in this mode
                    del nemo_model.encoder

                    nemo_model.eval()
                    nemo_model.freeze()

                    # Move only decoder/joint/preprocessor to GPU
                    nemo_model = nemo_model.to(self.device)

                    with open_dict(nemo_model.cfg.decoding):
                        nemo_model.cfg.decoding.compute_timestamps = False
                    nemo_model.change_decoding_strategy(nemo_model.cfg.decoding, verbose=False)
                finally:
                    fcntl.flock(lf, fcntl.LOCK_UN)

            self.model = ASRModelHybrid(
                onnx_dir=onnx_dir,
                nemo_model=nemo_model,
                device=self.device,
            )
        else:
            from asr_model_onnx import ASRModelOnnx

            tokenizer_path = params.get("tokenizer_path", {}).get("string_value", "/opt/parakeet_tokenizer.model")
            self.model = ASRModelOnnx(
                onnx_dir=onnx_dir,
                tokenizer_path=tokenizer_path,
                device=self.device,
            )

    def _initialize_pytorch(self, params):
        """Load NeMo PyTorch model (original path)."""
        model_name = params.get("model_name", {}).get("string_value", "nvidia/parakeet-tdt-0.6b-v2")

        with open(_LOAD_LOCK, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            try:
                import os
                if os.path.exists(_OPTIMIZED_PATH):
                    self.model = self._restore_lenient(_OPTIMIZED_PATH)
                elif model_name.endswith(".nemo"):
                    self.model = self._restore_lenient(model_name)
                else:
                    self.model = self._from_pretrained_lenient(model_name)
                    self.model.change_attention_model("rel_pos_local_attn", [128, 128])
                    self.model.change_subsampling_conv_chunking_factor(1)

                self.model = self.model.to(self.device)
                self.model.eval()
                self.model.freeze()

                # Keep timestamps disabled by default for speed
                # _infer_batch will toggle it only when needed
                with open_dict(self.model.cfg.decoding):
                    self.model.cfg.decoding.compute_timestamps = False
                self.model.change_decoding_strategy(self.model.cfg.decoding, verbose=False)

                if self.device == "cuda":
                    torch.cuda.empty_cache()
            finally:
                fcntl.flock(lf, fcntl.LOCK_UN)

    def _infer_batch(self, audio_arrays, timestamps=False):
        """Direct forward pass: audio numpy arrays → list of text strings or Hypothesis objects.
        Bypasses NeMo's transcribe() to avoid DataLoader/tempdir/tqdm overhead."""
        # Toggle timestamp decoding only when needed
        if timestamps and not self.model.cfg.decoding.get('compute_timestamps', False):
            with self._open_dict(self.model.cfg.decoding):
                self.model.cfg.decoding.compute_timestamps = True
            self.model.change_decoding_strategy(self.model.cfg.decoding, verbose=False)
            self._ts_enabled = True
        elif not timestamps and getattr(self, '_ts_enabled', False):
            with self._open_dict(self.model.cfg.decoding):
                self.model.cfg.decoding.compute_timestamps = False
            self.model.change_decoding_strategy(self.model.cfg.decoding, verbose=False)
            self._ts_enabled = False

        # Pad and batch
        lengths = [len(a) for a in audio_arrays]
        max_len = max(lengths)
        batch = np.zeros((len(audio_arrays), max_len), dtype=np.float32)
        for i, a in enumerate(audio_arrays):
            batch[i, :len(a)] = a

        signal = torch.from_numpy(batch).to(self.device)
        signal_len = torch.tensor(lengths, dtype=torch.long, device=self.device)

        # Encoder: preprocessor + encoder
        encoded, encoded_len = self.model.forward(
            input_signal=signal, input_signal_length=signal_len
        )

        # Decoder: greedy RNNT decoding
        hyps = self.model.decoding.rnnt_decoder_predictions_tensor(
            encoded, encoded_len, return_hypotheses=timestamps, partial_hypotheses=None,
        )

        del signal, signal_len, encoded, encoded_len

        best = hyps[0] if isinstance(hyps, tuple) else hyps

        if timestamps and best and hasattr(best[0], 'timestep'):
            from nemo.collections.asr.parts.utils.timestamp_utils import process_timestamp_outputs
            best = process_timestamp_outputs(
                best,
                self.model.encoder.subsampling_factor,
                self.model.cfg['preprocessor']['window_stride'],
            )

        return best

    def _warmup(self):
        """Pre-cache CUDA kernels and cuDNN plans."""
        with torch.no_grad(), torch.cuda.stream(self._stream), torch.cuda.amp.autocast(dtype=torch.bfloat16):
            for dur in [5, 15, 30, 45]:
                self._infer_batch([np.zeros(SAMPLE_RATE * dur, dtype=np.float32)])
            for _ in range(3):
                self._infer_batch([np.zeros(SAMPLE_RATE * 45, dtype=np.float32)])
        self._stream.synchronize()

    def execute(self, requests):
        audio_arrays = []
        ts_flags = []
        errors = [None] * len(requests)

        for i, request in enumerate(requests):
            try:
                audio_np = pb_utils.get_input_tensor_by_name(request, "audio").as_numpy()
                ts_flag = pb_utils.get_input_tensor_by_name(request, "timestamps").as_numpy().item()
                audio_arrays.append(audio_np.flatten())
                ts_flags.append(bool(ts_flag))
            except Exception as e:
                audio_arrays.append(None)
                ts_flags.append(False)
                errors[i] = str(e)

        valid_indices = [i for i, a in enumerate(audio_arrays) if a is not None]
        valid_audios = [audio_arrays[i] for i in valid_indices]
        results = [None] * len(requests)

        if valid_audios:
            any_ts = any(ts_flags[i] for i in valid_indices)
            with torch.no_grad(), torch.cuda.stream(self._stream), torch.cuda.amp.autocast(dtype=torch.bfloat16):
                hyps = self._infer_batch(valid_audios, timestamps=any_ts)
            self._stream.synchronize()

            for vi, i in enumerate(valid_indices):
                results[i] = hyps[vi] if vi < len(hyps) else ""

        responses = []
        for i in range(len(requests)):
            if errors[i]:
                responses.append(pb_utils.InferenceResponse(
                    error=pb_utils.TritonError(f"Inference failed: {errors[i]}")
                ))
                continue

            hyp = results[i]
            if hyp is None:
                responses.append(pb_utils.InferenceResponse(
                    error=pb_utils.TritonError("No result")
                ))
                continue

            if hasattr(hyp, 'text'):
                text = hyp.text
                words = []
                if ts_flags[i] and hasattr(hyp, 'timestep') and hyp.timestep:
                    for w in hyp.timestep.get('word', []):
                        words.append(json.dumps({
                            "word": w["word"],
                            "start": round(w["start"], 3),
                            "end": round(w["end"], 3),
                        }))
            else:
                text = str(hyp)
                words = []

            responses.append(pb_utils.InferenceResponse(output_tensors=[
                pb_utils.Tensor("text", np.array([str(text)], dtype=object)),
                pb_utils.Tensor("word_timestamps", np.array(words if words else [""], dtype=object)),
                pb_utils.Tensor("num_words", np.array([len(words)], dtype=np.int32)),
            ]))

        return responses

    def finalize(self):
        del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
