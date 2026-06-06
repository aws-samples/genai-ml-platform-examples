# Streaming Speaker Diarization — Triton Sequence Batching

**Author:** 
- Iman Abbasnejad (Applied Scientist) — imanaba@amazon.com
- Jerron Chua (Deep learning Architect) - jerronc@amazon.com

Production-grade streaming speaker diarization service built on NVIDIA Sortformer 4-speaker v2, served via Triton Inference Server running on TensorRT via ONNX Runtime with sequence batching and CUDA MPS for maximum GPU utilization.

## Performance Summary

Benchmarked on a single NVIDIA L40S (46GB) with 1-minute audio (4 × 15s chunks):

Latency computed below is per-chunk latency (15s chunk)

| Benchmark | Concurrency | RPS | Mean Latency | p95 Latency | p99 Latency |
|-----------|-------------|-----|-------------|-------------|-------------|
| Latency   | 20          | —   | 98ms       | 130ms       | 136ms       |
| Throughput | -         | 10| 116ms       | 123ms       | 131ms       |

**Target:** <4–5s overall latency, 10 RPS — Diarization only takes up ~600ms for a 60s audio.

## Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │              NVIDIA GPU (L40S)              │
                         │                                             │
  HTTP ──► FastAPI       │   ┌──────────┐  CUDA MPS  ┌──────────┐    │
  Client   Gateway       │   │Instance 0│◄──────────►│Instance 1│    │
    │      (port 8002)   │   │  12% SM  │  Daemon    │  12% SM  │    │
    │         │          │   └──────────┘            └──────────┘    │
    │      gRPC          │        ...  up to 8 instances  ...        │
    │         │          │   ┌──────────┐            ┌──────────┐    │
    │         ▼          │   │Instance 6│◄──────────►│Instance 7│    │
    │      Triton        │   │  12% SM  │            │  12% SM  │    │
    │      Server        │   └──────────┘            └──────────┘    │
    │      (sequence     │                                             │
    │       batching)    └─────────────────────────────────────────────┘
    │         │
    ▼         ▼
  :8002     :8000/:8001
  (HTTP)    (HTTP/gRPC)
```

### Components

1. **Triton Inference Server** (Python backend) — hosts Sortformer with sequence batching, maintaining per-recording streaming state across chunks
2. **FastAPI Gateway** — stateless HTTP proxy that maps recording lifecycle (start/chunk/end) to Triton sequence control signals (START/END/CORRID)
3. **CUDA MPS Daemon** — enables true concurrent GPU execution across up to 8 model instances (12% SM each)
4. **Auto-config** — dynamically sets instance count based on available GPU memory (~1.8GB per instance)
5. **Onnx Conversion** - Python script to convert default NeMo model to onnx graph

### Key Optimizations

- **Sequence batching**: Triton manages per-recording state server-side — no client-side state needed
- **Pipelined CPU/GPU execution**: CPU→GPU transfer, model forward, and GPU→CPU segmentation run on separate CUDA streams
- **Incremental segmentation**: Only processes new "unstable" frames per chunk; committed segments are cached
- **torch.compile**: Encoder and Sortformer modules compiled with `reduce-overhead` mode
- **CUDA MPS**: 8 instances share the GPU with guaranteed SM allocation instead of time-slicing
- **bfloat16 autocast**: 2× memory efficiency on Ampere+
- **CPU thread pool**: Post-processing (argmax/VAD segmentation) offloaded to 8 CPU threads
- **ONNX runtime**: Model is compiled as onnx graph during container image creation where the resulting onnx graph covers the Encoder modules (Conformer + Transformer). Configured to run on TensorRT Execution Provider
- **SortformerEncLabelModelOnnx**: A "drop-in" replacement for the original SortformerEncLabelModel NeMo class, with the initialize & infer functions replaced with ONNX Runtime scripts.

## Quick Start

### Prerequisites

- Docker with NVIDIA Container Toolkit
- NVIDIA GPU (tested on L40S, works on any Ampere+ GPU)

### Build & Run

```bash
cd seq_batching

# Build both containers
docker compose build

# Start services (triton with TensorRT + Onnx Runtime takes ~4 min for model loading + warmup)
docker compose up -d

# Check health
curl http://localhost:8000/v2/health/ready   # Triton
curl http://localhost:8002/health             # Gateway
```

### Test Diarization

```bash
# Send a chunk (multipart WAV upload)
curl -X POST http://localhost:8002/diarize \
  -F "action=chunk" \
  -F "recording_id=test-1" \
  -F "audio_file=@chunk.wav"

# End the recording
curl -X POST http://localhost:8002/diarize \
  -F "action=end" \
  -F "recording_id=test-1"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/diarize` | POST | Unified endpoint — multipart form with `action=chunk\|end`, `recording_id`, optional `audio_file` or `audio_base64` |
| `/diarize/chunk` | POST | JSON with `recording_id` + `audio_base64` (base64 float32 PCM) |
| `/diarize/end` | POST | JSON with `recording_id` — finalizes and returns merged segments |
| `/health` | GET | Triton liveness + model readiness + active sequence count |

### Response Format

```json
{
  "recording_id": "test-1",
  "segments": [
    "0.0 3.52 speaker_0",
    "3.52 7.84 speaker_1",
    "7.84 12.16 speaker_0"
  ],
  "final": false
}
```

## Benchmarking

```bash
pip install numpy

# Latency benchmark (sustained concurrent load)
python benchmark_latency.py --wav test_audio.wav --concurrency 20

# Throughput benchmark (RPS measurement)
python benchmark_rps.py --wav test_audio.wav --concurrency 10
```

## Project Structure

```
seq_batching/
├── Dockerfile.triton-onnx     # Triton + NeMo + Sortformer model weights
├── Dockerfile.gateway         # FastAPI gateway (no GPU)
├── docker-compose.yml         # Single-GPU deployment
├── auto_config.py             # Dynamic instance count + MPS config
├── convert_onnx.py            # [Deprecated - Reference only] Script to convert Encoders in the model to ONNX graph (using legacy Torchscript)
├── convert_onnx_dynamo.py     # Script to convert Encoders in the model to ONNX graph via Torch Dynamo
├── server.py                  # FastAPI gateway (sequence lifecycle → Triton gRPC)
├── benchmark_latency.py       # Per-chunk latency benchmark
├── benchmark_rps.py           # Throughput / RPS benchmark
├── requirements-benchmark.txt
└── triton_model_repo/
    └── sortformer_diar/
        ├── config_onnx.pbtxt  # Triton model config (sequence batching, instances)
        └── 1/
            ├── __init__.py
            ├── model.py       # Pipelined Sortformer inference (streaming state mgmt)
            ├── sortformer_onnx.py                # Custom implementation of SortformerEncLabelModel class
            └── sortformer_streaming_config.json  # Config for streaming Sortformer params
```
