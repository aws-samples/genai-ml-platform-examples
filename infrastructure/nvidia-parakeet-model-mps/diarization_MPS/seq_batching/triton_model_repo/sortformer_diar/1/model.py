# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Triton Python backend for streaming Sortformer diarization.

Uses sequence_batching with 'oldest' scheduling. Pipelines CPU and GPU work:
- CPU threads: request parsing, audio pinning, segmentation post-processing
- GPU: only process_signal + forward_streaming_step
- CUDA streams: overlap data transfer with compute
"""

from dataclasses import dataclass, field
from typing import Any, Dict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import torch
import triton_python_backend_utils as pb_utils

from omegaconf import OmegaConf
from nemo.collections.asr.models import SortformerEncLabelModel
from nemo.collections.asr.parts.utils.vad_utils import (
    PostProcessingParams,
    ts_vad_post_processing,
)
from nemo.collections.asr.parts.utils.speaker_utils import (
    generate_diarization_output_lines,
    get_contiguous_stamps,
    merge_stamps,
)

DEFAULT_COLLAR_SEC = 0.25
DEFAULT_MIN_SPEECH_PROB = 0.3
ONLINE_SEGMENTATION_MODE = "argmax"
ONLINE_TAIL_SEC = 1.5


@dataclass
class SequenceState:
    streaming_state: Any
    total_preds: torch.Tensor
    emitted_until_frame: int = 0
    committed_segments: list[str] = field(default_factory=list)


class TritonPythonModel:
    """Stateful Sortformer diarization model with pipelined CPU/GPU execution."""

    def initialize(self, args):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        model_name = "nvidia/diar_streaming_sortformer_4spk-v2"
        import json
        model_config = json.loads(args["model_config"])
        params = model_config.get("parameters", {})
        if "model_name" in params:
            model_name = params["model_name"]["string_value"]

        self.model = SortformerEncLabelModel.from_pretrained(model_name).to(self.device)
        self.model.eval()
        self._configure_streaming()

        # Compile encoder for faster inference (default mode — stable with dynamic shapes)
        if self.device == "cuda":
            try:
                self.model.encoder = torch.compile(self.model.encoder, mode="reduce-overhead")
            except Exception:
                pass
            try:
                self.model.sortformer_modules = torch.compile(self.model.sortformer_modules, mode="reduce-overhead")
            except Exception:
                pass

        self.n_spk = self.model.sortformer_modules.n_spk
        self.sub_factor = self.model.encoder.subsampling_factor
        self.frame_duration_sec = 0.01 * self.sub_factor
        self.online_tail_frames = max(1, int(round(ONLINE_TAIL_SEC / self.frame_duration_sec)))

        self.states: Dict[str, SequenceState] = {}

        # Dedicated CUDA streams for pipelining
        if self.device == "cuda":
            self._transfer_stream = torch.cuda.Stream()   # CPU→GPU audio
            self._d2h_stream = torch.cuda.Stream()         # GPU→CPU preds

        # Pre-allocate reusable tensors to avoid per-request allocation
        self._offset_zero = torch.zeros((1,), dtype=torch.long, device=self.device) if self.device == "cuda" else None
        self._length_buf = torch.empty((1,), dtype=torch.long, device=self.device) if self.device == "cuda" else None

        # CPU thread pool for post-processing (segmentation is pure CPU work)
        self._cpu_pool = ThreadPoolExecutor(max_workers=8)

        # Warmup: run a dummy forward pass to trigger torch.compile + CUDA caching
        if self.device == "cuda":
            self._warmup()

    def _configure_streaming(self):
        m = self.model
        m.streaming_mode = True
        m.sortformer_modules.chunk_len = 120
        m.sortformer_modules.chunk_right_context = 1
        m.sortformer_modules.fifo_len = 60
        m.sortformer_modules.spkcache_update_period = 124
        m.sortformer_modules.spkcache_len = 254
        m.sortformer_modules._check_streaming_parameters()

    def _warmup(self):
        """Run dummy inference 5x to fully trigger torch.compile + warm CUDA caches."""
        for _ in range(5):
            dummy_audio = torch.randn(1, 16000 * 15, device=self.device)
            length = torch.tensor([dummy_audio.shape[1]], device=self.device, dtype=torch.long)
            state = self.model.sortformer_modules.init_streaming_state(
                batch_size=1, async_streaming=self.model.async_streaming, device=self.device,
            )
            total_preds = torch.zeros((1, 0, self.n_spk), device=self.device)
            with torch.no_grad(), torch.cuda.amp.autocast(dtype=torch.bfloat16):
                processed_signal, proc_len = self.model.process_signal(
                    audio_signal=dummy_audio, audio_signal_length=length,
                )
                processed_signal = processed_signal[:, :, :proc_len.max()]
                offset = torch.zeros((1,), dtype=torch.long, device=self.device)
                loader = self.model.sortformer_modules.streaming_feat_loader(
                    feat_seq=processed_signal, feat_seq_length=proc_len, feat_seq_offset=offset,
                )
                for _, chunk_feat, feat_len, lo, ro in loader:
                    state, total_preds = self.model.forward_streaming_step(
                        processed_signal=chunk_feat, processed_signal_length=feat_len,
                        streaming_state=state, total_preds=total_preds,
                        left_offset=lo, right_offset=ro,
                    )
            torch.cuda.synchronize()
            del dummy_audio, state, total_preds

    def _init_state(self, corrid: str):
        streaming_state = self.model.sortformer_modules.init_streaming_state(
            batch_size=1,
            async_streaming=self.model.async_streaming,
            device=self.device,
        )
        total_preds = torch.zeros((1, 0, self.n_spk), device=self.device)

        self.states[corrid] = SequenceState(
            streaming_state=streaming_state,
            total_preds=total_preds,
        )

    def _cleanup_state(self, corrid: str):
        self.states.pop(corrid, None)

    # ------------------------------------------------------------------
    # Triton execute — pipelined CPU/GPU
    # ------------------------------------------------------------------
    def execute(self, requests):
        # Phase 1 (CPU): Parse all requests + start async GPU transfers
        parsed = []
        gpu_tensors = []
        for request in requests:
            try:
                p = self._parse_request(request)
                parsed.append(p)
                if p["has_audio"]:
                    # Start CPU→GPU transfer on separate CUDA stream
                    # This overlaps with parsing the next request
                    gpu_tensors.append(self._prepare_gpu_tensor(p["audio_np"]))
                else:
                    gpu_tensors.append(None)
            except Exception as e:
                parsed.append({"error": e})
                gpu_tensors.append(None)

        # Sync transfer stream before compute
        if self.device == "cuda":
            self._transfer_stream.synchronize()

        # Phase 2 (GPU): Run inference — only the model forward passes
        with torch.no_grad(), torch.cuda.amp.autocast(dtype=torch.bfloat16):
            for i, p in enumerate(parsed):
                if "error" in p or not p["has_audio"]:
                    continue
                self._process_audio_gpu(p["corrid"], gpu_tensors[i])

        # Phase 3 (CPU, parallel): Build segments using thread pool
        # Start async GPU→CPU transfers first, then submit CPU work
        preds_copies = []
        for p in parsed:
            if "error" in p:
                preds_copies.append(None)
                continue
            corrid = p["corrid"]
            state = self.states.get(corrid)
            if state is None or state.total_preds.shape[1] == 0:
                preds_copies.append(None)
            else:
                if p["is_end"] and p["seg_mode"] == "vad":
                    # vad finalization needs full history
                    tail = state.total_preds
                else:
                    # Only copy from emitted_until_frame onward
                    tail = state.total_preds[:, state.emitted_until_frame:, :]
                if tail.shape[1] == 0:
                    preds_copies.append(None)
                else:
                    with torch.cuda.stream(self._d2h_stream):
                        preds_copies.append(tail.to("cpu", non_blocking=True))

        # Wait for D2H transfers to complete before CPU work
        if self.device == "cuda":
            self._d2h_stream.synchronize()

        futures = []
        for idx, p in enumerate(parsed):
            if "error" in p:
                futures.append(None)
                continue
            corrid = p["corrid"]
            is_end = p["is_end"]
            state = self.states.get(corrid)
            if state is None:
                futures.append(None)
            elif preds_copies[idx] is None:
                futures.append(None)
                if is_end:
                    self._cleanup_state(corrid)
            elif is_end:
                committed = list(state.committed_segments)
                emitted = state.emitted_until_frame
                preds_cpu = preds_copies[idx]
                seg_mode = p["seg_mode"]
                def _final_work(pc=preds_cpu, c=committed, e=emitted, m=seg_mode):
                    return self._finalize_segments_cpu(pc, c, e, m)
                futures.append(self._cpu_pool.submit(_final_work))
                self._cleanup_state(corrid)
            else:
                emitted = state.emitted_until_frame
                total_frames = state.total_preds.shape[1]
                preds_cpu = preds_copies[idx]
                # Advance committed segments inline (fast — only processes new stable frames)
                self._advance_committed_segments_cpu(preds_cpu, state, emitted, total_frames)
                committed = list(state.committed_segments)
                new_emitted = state.emitted_until_frame
                def _current_work(pc=preds_cpu, c=committed, e=emitted, ne=new_emitted):
                    # Tail is the unstable portion: from new_emitted onward in preds_cpu
                    # preds_cpu starts at original emitted, so offset into it
                    tail_start = ne - e
                    tail = pc[:, tail_start:, :]
                    return self._current_segments_cpu(tail, c, ne)
                futures.append(self._cpu_pool.submit(_current_work))

        # Phase 4: Collect results
        responses = []
        for i, p in enumerate(parsed):
            if "error" in p:
                responses.append(pb_utils.InferenceResponse(
                    error=pb_utils.TritonError(f"Inference failed: {p['error']}")
                ))
            elif futures[i] is None:
                responses.append(self._make_response([], is_final=p["is_end"]))
            else:
                try:
                    segments = futures[i].result()
                    responses.append(self._make_response(segments, is_final=p["is_end"]))
                except Exception as e:
                    responses.append(pb_utils.InferenceResponse(
                        error=pb_utils.TritonError(f"Post-processing failed: {e}")
                    ))
        return responses

    def _parse_request(self, request) -> dict:
        corrid = pb_utils.get_input_tensor_by_name(request, "CORRID").as_numpy().item()
        if isinstance(corrid, bytes):
            corrid = corrid.decode("utf-8")

        is_start = bool(pb_utils.get_input_tensor_by_name(request, "START").as_numpy().item())
        is_end = bool(pb_utils.get_input_tensor_by_name(request, "END").as_numpy().item())

        seg_mode_raw = pb_utils.get_input_tensor_by_name(request, "segmentation_mode").as_numpy().item()
        seg_mode = seg_mode_raw.decode("utf-8") if isinstance(seg_mode_raw, bytes) else str(seg_mode_raw)
        if seg_mode not in ("argmax", "vad"):
            seg_mode = "argmax"

        if is_start or corrid not in self.states:
            self._init_state(corrid)

        audio_np = pb_utils.get_input_tensor_by_name(request, "audio_chunk").as_numpy()
        has_audio = audio_np.size > 0 and not (audio_np.size == 1 and audio_np.flat[0] == 0.0)

        return {
            "corrid": corrid,
            "is_start": is_start,
            "is_end": is_end,
            "seg_mode": seg_mode,
            "audio_np": audio_np if has_audio else None,
            "has_audio": has_audio,
        }

    def _prepare_gpu_tensor(self, audio_np: np.ndarray) -> torch.Tensor:
        """Direct CPU→GPU async transfer."""
        if audio_np.dtype != np.float32:
            audio_np = audio_np.astype(np.float32)
        audio_t = torch.from_numpy(audio_np).reshape(1, -1)
        with torch.cuda.stream(self._transfer_stream):
            audio_t = audio_t.to(self.device, non_blocking=True)
        return audio_t

    def _process_audio_gpu(self, corrid: str, audio_t: torch.Tensor) -> None:
        """GPU-only: process_signal + forward."""
        state = self.states[corrid]

        self._length_buf[0] = audio_t.shape[1]

        processed_signal, proc_len = self.model.process_signal(
            audio_signal=audio_t, audio_signal_length=self._length_buf
        )
        feat = processed_signal[:, :, :proc_len.max()]

        offset = self._offset_zero
        streaming_loader = self.model.sortformer_modules.streaming_feat_loader(
            feat_seq=feat,
            feat_seq_length=proc_len,
            feat_seq_offset=offset,
        )
        for _, chunk_feat_seq_t, feat_lengths, left_offset, right_offset in streaming_loader:
            state.streaming_state, state.total_preds = self.model.forward_streaming_step(
                processed_signal=chunk_feat_seq_t,
                processed_signal_length=feat_lengths,
                streaming_state=state.streaming_state,
                total_preds=state.total_preds,
                left_offset=left_offset,
                right_offset=right_offset,
            )

    # ------------------------------------------------------------------
    # CPU-side segmentation (runs on thread pool, uses idle CPU cores)
    # ------------------------------------------------------------------
    def _current_segments_cpu(self, preds_cpu: torch.Tensor, committed: list[str], emitted: int) -> list[str]:
        if preds_cpu.shape[1] == 0:
            return list(committed)
        # preds_cpu is already the tail (unstable region after committed segments)
        tail_lines = self._preds_to_segments(
            preds_cpu, ONLINE_SEGMENTATION_MODE,
            offset_sec=emitted * self.frame_duration_sec, apply_collar=False,
        )
        return self._merge_segment_lists(committed, tail_lines)

    def _finalize_segments_cpu(self, preds_cpu: torch.Tensor, committed: list[str], emitted: int, mode: str) -> list[str]:
        if mode == "vad":
            # vad mode: preds_cpu is full history (copied from frame 0)
            return self._preds_to_segments(preds_cpu, mode, offset_sec=0.0, apply_collar=True)

        # argmax mode: preds_cpu is tail only (from emitted onward)
        tail_lines = []
        if preds_cpu.shape[1] > 0:
            tail_lines = self._preds_to_segments(
                preds_cpu, ONLINE_SEGMENTATION_MODE,
                offset_sec=emitted * self.frame_duration_sec, apply_collar=False,
            )
        return self._format_segments(
            self._merge_segment_lists(committed, tail_lines), DEFAULT_COLLAR_SEC,
        )

    # ------------------------------------------------------------------
    # Incremental segmentation (called on CPU thread pool)
    # ------------------------------------------------------------------
    def _advance_committed_segments_cpu(self, tail_preds_cpu: torch.Tensor, state: SequenceState, emitted: int, total_frames: int) -> None:
        """Advance committed segments using CPU-side tail preds."""
        stable_end = max(0, total_frames - self.online_tail_frames)
        if stable_end <= emitted:
            return

        # tail_preds_cpu starts at emitted, so stable region is [:stable_end - emitted]
        stable_len = stable_end - emitted
        new_preds = tail_preds_cpu[:, :stable_len, :]
        if new_preds.shape[1] == 0:
            return

        offset_sec = emitted * self.frame_duration_sec
        new_lines = self._preds_to_segments(
            new_preds, ONLINE_SEGMENTATION_MODE, offset_sec=offset_sec, apply_collar=False,
        )
        state.committed_segments = self._merge_segment_lists(state.committed_segments, new_lines)
        state.emitted_until_frame = stable_end

    def _advance_committed_segments(self, state: SequenceState) -> None:
        total_frames = state.total_preds.shape[1]
        stable_end = max(0, total_frames - self.online_tail_frames)
        if stable_end <= state.emitted_until_frame:
            return

        new_preds = state.total_preds[:, state.emitted_until_frame:stable_end, :]
        if new_preds.shape[1] == 0:
            return

        offset_sec = state.emitted_until_frame * self.frame_duration_sec
        new_lines = self._preds_to_segments(
            new_preds, ONLINE_SEGMENTATION_MODE, offset_sec=offset_sec, apply_collar=False,
        )
        state.committed_segments = self._merge_segment_lists(state.committed_segments, new_lines)
        state.emitted_until_frame = stable_end

    # ------------------------------------------------------------------
    # Segment helpers (CPU-bound, safe to call from thread pool)
    # ------------------------------------------------------------------
    def _preds_to_segments(self, preds, mode, offset_sec=0.0, apply_collar=True) -> list[str]:
        if preds.shape[1] == 0:
            return []
        preds_2d = preds.squeeze(0)
        lines = self._vad_segments(preds_2d, offset_sec) if mode == "vad" else self._argmax_segments(preds_2d, offset_sec)
        return self._format_segments(lines, DEFAULT_COLLAR_SEC if apply_collar else 0.0)

    def _argmax_segments(self, preds: torch.Tensor, offset_sec: float = 0.0) -> list[str]:
        max_probs, argmax_spk = preds.max(dim=-1)
        labels = argmax_spk.numpy()
        mask = max_probs.numpy() < DEFAULT_MIN_SPEECH_PROB
        labels[mask] = -1

        n = len(labels)
        if n == 0:
            return []

        # Vectorized run-length encoding
        changes = np.empty(n, dtype=bool)
        changes[0] = True
        np.not_equal(labels[1:], labels[:-1], out=changes[1:])
        run_starts = np.flatnonzero(changes)
        run_labels = labels[run_starts]

        # Filter out silence runs
        speech_mask = run_labels >= 0
        if not speech_mask.any():
            return []

        starts = run_starts[speech_mask]
        spks = run_labels[speech_mask]
        # Compute ends: next run start, or n for the last run
        all_ends = np.empty_like(run_starts)
        all_ends[:-1] = run_starts[1:]
        all_ends[-1] = n
        ends = all_ends[speech_mask]

        fd = self.frame_duration_sec
        lines = []
        for i in range(len(starts)):
            s = round(offset_sec + starts[i] * fd, 2)
            e = round(offset_sec + ends[i] * fd, 2)
            if e > s:
                lines.append(f"{s} {e} speaker_{spks[i]}")
        return lines

    def _vad_segments(self, preds: torch.Tensor, offset_sec: float = 0.0) -> list[str]:
        pp = OmegaConf.structured(PostProcessingParams(onset=0.25, offset=0.10))
        speaker_timestamps = []
        for spk_id in range(preds.shape[-1]):
            ts_mat = ts_vad_post_processing(
                preds[:, spk_id], cfg_vad_params=pp,
                unit_10ms_frame_count=self.sub_factor, bypass_postprocessing=False,
            )
            ts_list = [[round(s + offset_sec, 2), round(e + offset_sec, 2)] for s, e in ts_mat.tolist()]
            speaker_timestamps.append(ts_list)
        return generate_diarization_output_lines(
            speaker_timestamps=speaker_timestamps, model_spk_num=len(speaker_timestamps),
        )

    def _format_segments(self, lines: list[str], collar: float) -> list[str]:
        if not lines:
            return []
        sorted_lines = sorted(lines, key=lambda x: float(x.split()[0]))
        contiguous = get_contiguous_stamps(sorted_lines)
        merged = merge_stamps(contiguous)
        return self._apply_collar(merged, collar) if collar > 0 else merged

    def _merge_segment_lists(self, left: list[str], right: list[str]) -> list[str]:
        if not left:
            return list(right)
        if not right:
            return list(left)
        # Both lists are already sorted by start time — merge without re-sorting
        merged = []
        li = ri = 0
        while li < len(left) and ri < len(right):
            ls = float(left[li].split(None, 1)[0])
            rs = float(right[ri].split(None, 1)[0])
            if ls <= rs:
                merged.append(left[li]); li += 1
            else:
                merged.append(right[ri]); ri += 1
        merged.extend(left[li:])
        merged.extend(right[ri:])
        contiguous = get_contiguous_stamps(merged)
        return merge_stamps(contiguous)

    @staticmethod
    def _apply_collar(lines: list[str], collar: float) -> list[str]:
        if not lines or collar <= 0:
            return lines
        result = []
        i = 0
        while i < len(lines):
            parts = lines[i].split()
            start, end, speaker = float(parts[0]), float(parts[1]), parts[2]
            if (end - start) >= collar:
                result.append(lines[i])
                i += 1
                continue
            merged = False
            if result and result[-1].split()[2] == speaker:
                p0, _, _ = result[-1].split()
                result[-1] = f"{float(p0)} {end} {speaker}"
                merged = True
            if not merged and i + 1 < len(lines):
                nparts = lines[i + 1].split()
                if nparts[2] == speaker:
                    lines[i + 1] = f"{start} {float(nparts[1])} {speaker}"
                    i += 1
                    continue
            if not merged:
                result.append(lines[i])
            i += 1
        return result

    @staticmethod
    def _make_response(segments: list[str], is_final: bool):
        seg_arr = np.array(segments, dtype=object) if segments else np.array([""], dtype=object)
        out_segments = pb_utils.Tensor("segments", seg_arr)
        out_final = pb_utils.Tensor("is_final", np.array([is_final], dtype=bool))
        out_count = pb_utils.Tensor("num_segments", np.array([len(segments)], dtype=np.int32))
        return pb_utils.InferenceResponse(output_tensors=[out_segments, out_final, out_count])

    def finalize(self):
        self._cpu_pool.shutdown(wait=False)
        self.states.clear()
        del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
