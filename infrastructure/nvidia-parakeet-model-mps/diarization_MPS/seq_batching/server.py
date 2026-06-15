#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
Thin FastAPI gateway for Triton-backed streaming diarization (Option A).

All streaming state lives inside Triton via sequence_batching. This server
only handles HTTP, base64 decoding, and maps recording lifecycle to Triton
sequence control signals (START / END / CORRID).

Endpoints (same API surface as original diarize_chunk_server.py):
    POST /diarize/chunk  - {"recording_id": "...", "chunk|audio_base64": "<b64 float32>"}
    POST /diarize/end    - {"recording_id": "..."}
    POST /diarize        - {"action": "chunk"|"end", ...}
    GET  /health

Usage:
    python server.py --port 8002 --triton-url localhost:8001
"""

import asyncio
import base64
import io
import os
import struct
import wave
from typing import Optional, Set

import numpy as np
import tritonclient.grpc as grpcclient
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
TRITON_URL = os.environ.get("TRITON_URL", "triton:8001")
TRITON_MODEL_NAME = "sortformer_diar"

# Track active sequences so we know when to send START
_active_sequences: Set[str] = set()

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class ChunkRequest(BaseModel):
    recording_id: str
    chunk: Optional[str] = None
    audio_base64: Optional[str] = None
    segmentation_mode: str = "argmax"


class EndRequest(BaseModel):
    recording_id: str
    segmentation_mode: str = "argmax"


class DiarizeRequest(BaseModel):
    action: str
    recording_id: str = "default"
    audio_base64: Optional[str] = None
    segmentation_mode: str = "argmax"


# ---------------------------------------------------------------------------
# Triton client
# ---------------------------------------------------------------------------
_triton_client: Optional[grpcclient.InferenceServerClient] = None


def _get_client() -> grpcclient.InferenceServerClient:
    global _triton_client
    if _triton_client is None:
        _triton_client = grpcclient.InferenceServerClient(url=TRITON_URL)
    return _triton_client

def _call_triton(
    recording_id: str,
    audio_np: Optional[np.ndarray],
    segmentation_mode: str,
    is_start: bool,
    is_end: bool,
) -> dict:
    """
    Send a single request to Triton with sequence control signals.
    """
    client = _get_client()

    # Audio input — empty array signals "no audio" (end-only request)
    if audio_np is not None and audio_np.size > 0:
        audio_data = audio_np.astype(np.float32).reshape(1, -1)
    else:
        audio_data = np.array([[0.0]], dtype=np.float32)

    inp_audio = grpcclient.InferInput("audio_chunk", list(audio_data.shape), "FP32")
    inp_audio.set_data_from_numpy(audio_data)

    mode_np = np.array([segmentation_mode.encode("utf-8")], dtype=object).reshape(1, 1)
    inp_mode = grpcclient.InferInput("segmentation_mode", [1, 1], "BYTES")
    inp_mode.set_data_from_numpy(mode_np)

    outputs = [
        grpcclient.InferRequestedOutput("segments"),
        grpcclient.InferRequestedOutput("is_final"),
        grpcclient.InferRequestedOutput("num_segments"),
    ]

    result = client.infer(
        model_name=TRITON_MODEL_NAME,
        inputs=[inp_audio, inp_mode],
        outputs=outputs,
        sequence_id=recording_id,
        sequence_start=is_start,
        sequence_end=is_end,
    )

    # Parse response
    seg_raw = result.as_numpy("segments")
    is_final = bool(result.as_numpy("is_final")[0])
    num_seg = int(result.as_numpy("num_segments")[0])

    segments = []
    if num_seg > 0:
        for s in seg_raw:
            line = s.decode("utf-8") if isinstance(s, bytes) else str(s)
            if line:
                segments.append(line)

    return {
        "recording_id": recording_id,
        "segments": segments,
        "final": is_final,
    }


def _process_wav_upload(wav_bytes: bytes) -> np.ndarray:
    """
    Read a WAV file from bytes, convert to mono float32, and resample to 16 kHz.
    """
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        raw = wf.readframes(wf.getnframes())

    # Decode PCM samples to float32
    if sampwidth == 2:
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32, copy=False)
        samples = samples * (1.0 / 32768.0)
    elif sampwidth == 4:
        samples = np.frombuffer(raw, dtype=np.int32).astype(np.float32, copy=False)
        samples = samples * (1.0 / 2147483648.0)
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    # Convert to mono by averaging channels
    if n_channels > 1:
        samples = samples.reshape(-1, n_channels).mean(axis=1)

    # Resample to 16 kHz if needed (fast linear interpolation)
    if framerate != 16000:
        num_target = int(len(samples) * 16000 / framerate)
        indices = np.linspace(0, len(samples) - 1, num_target)
        samples = np.interp(indices, np.arange(len(samples)), samples).astype(np.float32)

    return samples


async def _call_triton_async(
    recording_id: str,
    audio_np: Optional[np.ndarray],
    segmentation_mode: str,
    is_start: bool,
    is_end: bool,
) -> dict:
    return await asyncio.to_thread(
        _call_triton,
        recording_id,
        audio_np,
        segmentation_mode,
        is_start,
        is_end,
    )


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------
app = FastAPI(title="Diarization Server (Triton sequence_batching)", version="3.0.0")


@app.post("/diarize/chunk")
async def diarize_chunk(req: ChunkRequest):
    chunk_b64 = req.chunk or req.audio_base64
    if not chunk_b64:
        raise HTTPException(status_code=400, detail="Missing chunk or audio_base64")
    try:
        chunk_bytes = base64.b64decode(chunk_b64)
        audio_np = np.frombuffer(chunk_bytes, dtype=np.float32).copy()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid chunk: {e}") from e

    is_start = req.recording_id not in _active_sequences
    if is_start:
        _active_sequences.add(req.recording_id)

    return await _call_triton_async(
        recording_id=req.recording_id,
        audio_np=audio_np,
        segmentation_mode=req.segmentation_mode,
        is_start=is_start,
        is_end=False,
    )


@app.post("/diarize/end")
async def diarize_end(req: EndRequest):
    is_start = req.recording_id not in _active_sequences
    _active_sequences.discard(req.recording_id)

    return await _call_triton_async(
        recording_id=req.recording_id,
        audio_np=None,
        segmentation_mode=req.segmentation_mode,
        is_start=is_start,
        is_end=True,
    )


@app.post("/diarize")
async def diarize_unified(
    action: str = Form(...),
    recording_id: str = Form("default"),
    segmentation_mode: str = Form("argmax"),
    audio_base64: Optional[str] = Form(None),
    audio_file: Optional[UploadFile] = File(None),
):
    if action == "chunk":
        # Prefer file upload over base64
        if audio_file is not None:
            wav_bytes = await audio_file.read()
            audio_np = _process_wav_upload(wav_bytes)
        elif audio_base64:
            chunk_bytes = base64.b64decode(audio_base64)
            audio_np = np.frombuffer(chunk_bytes, dtype=np.float32).copy()
        else:
            raise HTTPException(status_code=400, detail="Provide audio_file or audio_base64")

        is_start = recording_id not in _active_sequences
        if is_start:
            _active_sequences.add(recording_id)

        return await _call_triton_async(
            recording_id=recording_id,
            audio_np=audio_np,
            segmentation_mode=segmentation_mode,
            is_start=is_start,
            is_end=False,
        )

    if action == "end":
        is_start = recording_id not in _active_sequences
        _active_sequences.discard(recording_id)
        return await _call_triton_async(
            recording_id=recording_id,
            audio_np=None,
            segmentation_mode=segmentation_mode,
            is_start=is_start,
            is_end=True,
        )

    raise HTTPException(status_code=400, detail=f"Unknown action: {action}")


@app.get("/health")
async def health():
    try:
        client = _get_client()
        alive = client.is_server_live()
        model_ready = client.is_model_ready(TRITON_MODEL_NAME)
    except Exception:
        alive, model_ready = False, False
    return {
        "triton_live": alive,
        "model_ready": model_ready,
        "active_sequences": len(_active_sequences),
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Diarization gateway (Triton sequence_batching)")
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--host", type=str, default="0.0.0.0")  # nosec B104
    parser.add_argument("--triton-url", type=str, default=TRITON_URL)
    args = parser.parse_args()

    TRITON_URL = args.triton_url

    print("Diarization Gateway (Triton sequence_batching)")
    print(f"  Triton gRPC: {TRITON_URL}")
    print(f"  POST /diarize/chunk")
    print(f"  POST /diarize/end")
    print(f"  POST /diarize")
    print(f"  GET  /health")

    uvicorn.run("server:app", host=args.host, port=args.port, workers=1)

