#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. This material is AWS Content under the AWS Enterprise Agreement
# or AWS Customer Agreement (as applicable) and is provided under the AWS Intellectual Property License.

"""
FastAPI gateway for Triton-backed ASR (Parakeet TDT).
OpenAI-compatible API + simple endpoints.

Endpoints:
    POST /v1/audio/transcriptions  - OpenAI-compatible
    POST /transcribe               - JSON: {"audio_base64": "<b64 float32>"}
    POST /transcribe/file          - Multipart: audio_file (WAV upload)
    GET  /v1/models
    GET  /health
    GET  /metrics
"""

import asyncio
import os
import base64
import io
import json
import os
import time
import wave
from typing import List, Optional

import numpy as np
import tritonclient.grpc as grpcclient
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

TRITON_URL = os.environ.get("TRITON_URL", "triton:8001")
TRITON_MODEL_NAME = "parakeet_asr"

# --- Performance monitor ---

class PerfMonitor:
    def __init__(self):
        self.count = 0
        self.total_time = 0.0
        self.latencies: list[float] = []
        self.start = time.time()

    def record(self, latency: float):
        self.count += 1
        self.total_time += latency
        if len(self.latencies) >= 1000:
            self.latencies.pop(0)
        self.latencies.append(latency)

    def quantile(self, q: float) -> float:
        if not self.latencies:
            return 0.0
        s = sorted(self.latencies)
        return s[min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))]

perf = PerfMonitor()

# --- Request models ---

class TranscribeRequest(BaseModel):
    audio_base64: str
    timestamps: bool = False

# --- Triton client ---

_triton_client: Optional[grpcclient.InferenceServerClient] = None
_decode_pool = None

def _get_client() -> grpcclient.InferenceServerClient:
    global _triton_client
    if _triton_client is None:
        _triton_client = grpcclient.InferenceServerClient(url=TRITON_URL)
    return _triton_client


def _get_decode_pool():
    global _decode_pool
    if _decode_pool is None:
        import concurrent.futures, os
        _decode_pool = concurrent.futures.ThreadPoolExecutor(max_workers=os.cpu_count() or 4)
    return _decode_pool


def _call_triton(audio_np: np.ndarray, timestamps: bool) -> dict:
    client = _get_client()

    audio_data = audio_np.astype(np.float32).reshape(1, -1)
    inp_audio = grpcclient.InferInput("audio", list(audio_data.shape), "FP32")
    inp_audio.set_data_from_numpy(audio_data)

    ts_np = np.array([[timestamps]], dtype=bool)
    inp_ts = grpcclient.InferInput("timestamps", [1, 1], "BOOL")
    inp_ts.set_data_from_numpy(ts_np)

    outputs = [
        grpcclient.InferRequestedOutput("text"),
        grpcclient.InferRequestedOutput("word_timestamps"),
        grpcclient.InferRequestedOutput("num_words"),
    ]

    result = client.infer(
        model_name=TRITON_MODEL_NAME,
        inputs=[inp_audio, inp_ts],
        outputs=outputs,
    )

    text_raw = result.as_numpy("text")[0]
    text = text_raw.decode("utf-8") if isinstance(text_raw, bytes) else str(text_raw)

    num_words = int(result.as_numpy("num_words")[0])
    word_timestamps = []
    if num_words > 0:
        for w in result.as_numpy("word_timestamps"):
            line = w.decode("utf-8") if isinstance(w, bytes) else str(w)
            if line:
                word_timestamps.append(json.loads(line))

    return {"text": text, "word_timestamps": word_timestamps}


async def _call_triton_async(audio_np: np.ndarray, timestamps: bool) -> dict:
    return await asyncio.to_thread(_call_triton, audio_np, timestamps)


async def _decode_audio_async(raw_bytes: bytes, filename: str = "") -> tuple[np.ndarray, float]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_get_decode_pool(), _decode_audio, raw_bytes, filename)


# --- Audio processing ---

def _decode_audio(raw_bytes: bytes, filename: str = "") -> tuple[np.ndarray, float]:
    """Decode audio bytes to 16kHz mono float32 numpy array. Returns (samples, duration_sec)."""
    try:
        import soundfile as sf
        audio_data, sample_rate = sf.read(io.BytesIO(raw_bytes), dtype="float32")
    except Exception:
        # Fallback to wave module for plain WAV
        with wave.open(io.BytesIO(raw_bytes), "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            sample_rate = wf.getframerate()
            raw = wf.readframes(wf.getnframes())
        if sampwidth == 2:
            audio_data = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        elif sampwidth == 4:
            audio_data = np.frombuffer(raw, dtype=np.int32).astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported sample width: {sampwidth}")
        if n_channels > 1:
            audio_data = audio_data.reshape(-1, n_channels)

    # Mono
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    # Resample to 16kHz
    if sample_rate != 16000:
        num_target = int(len(audio_data) * 16000 / sample_rate)
        indices = np.linspace(0, len(audio_data) - 1, num_target)
        audio_data = np.interp(indices, np.arange(len(audio_data)), audio_data).astype(np.float32)
        sample_rate = 16000

    duration = len(audio_data) / sample_rate
    return audio_data.astype(np.float32), duration


# --- Helpers ---

def _duration_to_srt(d: float) -> str:
    h, rem = divmod(d, 3600)
    m, s = divmod(rem, 60)
    ms = int((s % 1) * 1000)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"

def _duration_to_vtt(d: float) -> str:
    h, rem = divmod(d, 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"


# --- FastAPI app ---

app = FastAPI(title="ASR Server (Triton + Parakeet TDT)", version="2.0.0")

_allowed_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/v1/audio/transcriptions")
async def openai_transcribe(
    file: UploadFile = File(...),
    model: Optional[str] = Form("parakeet-tdt-0.6b-v2"),
    language: Optional[str] = Form("en"),
    response_format: Optional[str] = Form("json"),
    temperature: Optional[float] = Form(0.0),
    timestamp_granularities: Optional[str] = Form(None),
):
    """OpenAI-compatible transcription endpoint."""
    t0 = time.time()

    content = await file.read()
    try:
        audio_np, duration = await _decode_audio_async(content, file.filename or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not decode audio: {e}") from e

    want_ts = timestamp_granularities is not None and "word" in timestamp_granularities
    result = await _call_triton_async(audio_np, want_ts)
    text = result["text"]
    words = result.get("word_timestamps", [])

    latency = time.time() - t0
    perf.record(latency)

    if response_format == "text":
        return Response(content=text, media_type="text/plain")
    elif response_format == "srt":
        return Response(
            content=f"1\n00:00:00,000 --> {_duration_to_srt(duration)}\n{text}\n",
            media_type="application/x-subrip",
        )
    elif response_format == "vtt":
        return Response(
            content=f"WEBVTT\n\n1\n00:00:00.000 --> {_duration_to_vtt(duration)}\n{text}\n",
            media_type="text/vtt",
        )
    elif response_format == "verbose_json":
        return JSONResponse({
            "task": "transcribe",
            "language": language,
            "duration": round(duration, 2),
            "text": text,
            "words": words if want_ts else [],
            "segments": [{
                "id": 0, "seek": 0, "start": 0.0, "end": round(duration, 2),
                "text": text, "tokens": [], "temperature": temperature,
                "avg_logprob": 0.0, "compression_ratio": len(text) / max(duration, 1),
                "no_speech_prob": 0.0,
            }],
            "performance": {
                "processing_time": round(latency, 3),
                "real_time_factor": round(latency / duration, 4) if duration > 0 else 0,
            },
        })
    else:
        return JSONResponse({"text": text})


@app.post("/transcribe")
async def transcribe(req: TranscribeRequest):
    t0 = time.time()
    try:
        audio_bytes = base64.b64decode(req.audio_base64)
        audio_np = np.frombuffer(audio_bytes, dtype=np.float32).copy()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio: {e}") from e

    result = await _call_triton_async(audio_np, req.timestamps)
    perf.record(time.time() - t0)
    resp = {"text": result["text"]}
    if req.timestamps:
        resp["word_timestamps"] = result["word_timestamps"]
    return resp


@app.post("/transcribe/file")
async def transcribe_file(
    audio_file: UploadFile = File(...),
    timestamps: bool = Form(False),
):
    t0 = time.time()
    content = await audio_file.read()
    try:
        audio_np, _ = await _decode_audio_async(content, audio_file.filename or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid audio: {e}") from e

    result = await _call_triton_async(audio_np, timestamps)
    perf.record(time.time() - t0)
    resp = {"text": result["text"]}
    if timestamps:
        resp["word_timestamps"] = result["word_timestamps"]
    return resp


@app.get("/v1/models")
async def list_models():
    return {"object": "list", "data": [
        {"id": "parakeet-tdt-0.6b-v2", "object": "model", "created": int(time.time()), "owned_by": "nvidia"},
    ]}


@app.get("/health")
async def health():
    try:
        client = _get_client()
        alive = client.is_server_live()
        model_ready = client.is_model_ready(TRITON_MODEL_NAME)
    except Exception:
        alive, model_ready = False, False
    return {
        "status": "healthy" if model_ready else "unhealthy",
        "triton_live": alive,
        "model_ready": model_ready,
        "performance": {
            "total_requests": perf.count,
            "avg_latency_s": round(perf.total_time / max(1, perf.count), 3),
            "rps": round(perf.count / max(1, time.time() - perf.start), 2),
        },
    }


@app.get("/metrics")
async def metrics():
    p50 = perf.quantile(0.50)
    p90 = perf.quantile(0.90)
    p95 = perf.quantile(0.95)
    p99 = perf.quantile(0.99)
    avg = perf.total_time / max(1, perf.count)
    labels = 'service="parakeet-asr"'
    lines = [
        f"# HELP asr_requests_total Total transcription requests.",
        f"# TYPE asr_requests_total counter",
        f"asr_requests_total{{{labels}}} {perf.count}",
        f"# HELP asr_latency_seconds Request latency.",
        f"# TYPE asr_latency_seconds gauge",
        f'asr_latency_seconds{{{labels},quantile="0.5"}} {p50:.6f}',
        f'asr_latency_seconds{{{labels},quantile="0.9"}} {p90:.6f}',
        f'asr_latency_seconds{{{labels},quantile="0.95"}} {p95:.6f}',
        f'asr_latency_seconds{{{labels},quantile="0.99"}} {p99:.6f}',
        f'asr_latency_seconds_avg{{{labels}}} {avg:.6f}',
        f"# HELP asr_rps Requests per second.",
        f"# TYPE asr_rps gauge",
        f"asr_rps{{{labels}}} {perf.count / max(1, time.time() - perf.start):.6f}",
    ]
    return Response(content="\n".join(lines) + "\n", media_type="text/plain")


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8002)
    parser.add_argument("--host", type=str, default="0.0.0.0")  # nosec B104
    parser.add_argument("--triton-url", type=str, default=TRITON_URL)
    args = parser.parse_args()
    TRITON_URL = args.triton_url

    uvicorn.run("server:app", host=args.host, port=args.port, workers=1)
