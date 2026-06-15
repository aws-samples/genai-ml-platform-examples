# Streaming Speaker Diarization — Triton Sequence Batching

**Author:** Iman Abbasnejad (Applied Scientist) — imanaba@amazon.com

Production-grade streaming speaker diarization service built on NVIDIA Sortformer 4-speaker v2, served via Triton Inference Server with sequence batching and CUDA MPS for maximum GPU utilization.

## Performance Summary

Benchmarked on a single NVIDIA L40S (46GB) with 1-minute audio (4 × 15s chunks):

| Benchmark | Concurrency | RPS | Mean Latency | p95 Latency | p99 Latency |
|-----------|-------------|-----|-------------|-------------|-------------|
| Latency   | 20          | —   | 222ms       | 310ms       | 328ms       |
| Throughput | 10         | 75.8| 121ms       | 194ms       | 217ms       |

**Target:** <4–5s latency, 10 RPS — exceeded by ~7.5×.

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

### Key Optimizations

- **Sequence batching**: Triton manages per-recording state server-side — no client-side state needed
- **Pipelined CPU/GPU execution**: CPU→GPU transfer, model forward, and GPU→CPU segmentation run on separate CUDA streams
- **Incremental segmentation**: Only processes new "unstable" frames per chunk; committed segments are cached
- **torch.compile**: Encoder and Sortformer modules compiled with `reduce-overhead` mode
- **CUDA MPS**: 8 instances share the GPU with guaranteed SM allocation instead of time-slicing
- **bfloat16 autocast**: 2× memory efficiency on Ampere+
- **CPU thread pool**: Post-processing (argmax/VAD segmentation) offloaded to 8 CPU threads

## Quick Start

### Prerequisites

- Docker with NVIDIA Container Toolkit
- NVIDIA GPU (tested on L40S, works on any Ampere+ GPU)

### Build & Run

```bash
cd seq_batching

# Build both containers
docker compose build

# Start services (triton takes ~2 min for model loading + warmup)
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
├── Dockerfile.triton          # Triton + NeMo + Sortformer model weights
├── Dockerfile.gateway         # FastAPI gateway (no GPU)
├── docker-compose.yml         # Single-GPU deployment
├── auto_config.py             # Dynamic instance count + MPS config
├── server.py                  # FastAPI gateway (sequence lifecycle → Triton gRPC)
├── benchmark_latency.py       # Per-chunk latency benchmark
├── benchmark_rps.py           # Throughput / RPS benchmark
├── requirements-benchmark.txt
└── triton_model_repo/
    └── sortformer_diar/
        ├── config.pbtxt       # Triton model config (sequence batching, instances)
        └── 1/
            └── model.py       # Pipelined Sortformer inference (streaming state mgmt)
```
