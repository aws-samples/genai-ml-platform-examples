# Parakeet TDT ASR — High-Throughput Speech-to-Text Service

**Author:** Iman Abbasnejad (Applied Scientist) — imanaba@amazon.com

Production-grade ASR service built on NVIDIA Parakeet TDT 0.6B v2, served via Triton Inference Server with CUDA MPS for maximum GPU utilization.

## Performance Summary

Benchmarked on a single NVIDIA L40S (46GB) with 45-second audio clips:

| Concurrency | RPS | RPM | p95 Latency | SLA (p95 < 500ms) |
|-------------|-----|------|-------------|-----|
| 1 |           6.4 | 384  |       160ms |  ✅ |
| 4 |           25.2|1,512 |       160ms |  ✅ |
| 8 |          44.3 |2,656 |       203ms |  ✅ |
| 12 |         55.9 |3,352 |       241ms |  ✅ |
| 16 |         56.8 |3,408 |       336ms |  ✅ |
| 20 |         62.0 |3,720 |       387ms |  ✅ |
| 24 |         61.1 |3,664 |       608ms |  ❌ |

**Production targets** (100 concurrency, p95 < 500ms, ~10k RPM): **5 GPUs** — down from 16 (69% savings).

## Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │              NVIDIA GPU (L40S)              │
                         │                                             │
  HTTP ──► FastAPI       │   ┌─────-────┐  CUDA MPS  ┌────-─────┐      │
  Client   Gateway       │   │Instance 0│◄──────────►│Instance 1│      │
    │      (4 workers)   │   │  25% SM  │  Daemon    │  25% SM  │      │
    │         │          │   └────┬─────┘            └────┬─────┘      │
    │      gRPC          │        │    Shared GPU Memory  │            │
    │         │          │   ┌────┴─────┐            ┌────┴─────┐      │
    │         ▼          │   │Instance 2│◄──────────►│Instance 3│      │
    │      Triton        │   │  25% SM  │            │  25% SM  │      │
    │      Server        │   └──────────┘            └──────────┘      │
    │      (dynamic      │                                             │
    │       batching)    └─────────────────────────────────────────────┘
    │         │
    ▼         ▼
  :8002     :8000/:8001
  (HTTP)    (HTTP/gRPC)
```

### Components

1. **Triton Inference Server** (Python backend) — hosts the Parakeet model with dynamic batching (batch sizes 4/8/16, 50ms queue delay)
2. **FastAPI Gateway** (4 uvicorn workers) — OpenAI-compatible API, audio decoding (WAV/FLAC/MP3), multipart upload
3. **CUDA MPS Daemon** — enables true concurrent GPU execution across 4 model instances
4. **Auto-config** — dynamically sets instance count and MPS thread percentage based on available GPU memory

### Key Optimizations

- **Direct forward pass**: Bypasses NeMo's `transcribe()` API (which creates temp dirs, DataLoaders, manifests per request) and calls `model.forward()` + `decoding.rnnt_decoder_predictions_tensor()` directly
- **CUDA MPS**: 4 instances share the GPU with guaranteed SM allocation instead of time-slicing
- **bfloat16 autocast**: 2x memory efficiency, faster matmuls on Ampere+
- **Local attention**: `rel_pos_local_attn` with context [128, 128] — reduces quadratic attention cost
- **Pre-cached kernels**: Warmup with varying audio lengths (5s–45s) at startup

## How CUDA MPS Works

Without MPS, multiple GPU processes time-slice — only one runs at a time:

```
Time ──────────────────────────────────────────►
GPU:  [Instance 0][Instance 1][Instance 0][Instance 2]...
       ▲ idle      ▲ idle      ▲ idle      ▲ idle
```

With MPS, all instances run concurrently on partitioned streaming multiprocessors (SMs):

```
Time ──────────────────────────────────────────►
GPU:  ┌──────────────────────────────────────┐
  SM  │ Instance 0 ████████████████████████  │ 25% SMs
  SM  │ Instance 1 ████████████████████████  │ 25% SMs
  SM  │ Instance 2 ████████████████████████  │ 25% SMs
  SM  │ Instance 3 ████████████████████████  │ 25% SMs
      └──────────────────────────────────────┘
```

Each instance gets a dedicated CUDA stream and 25% of SMs, but can burst higher when other instances are idle. The MPS daemon manages this transparently.

**Configuration** (set in `Dockerfile.triton` and `auto_config.py`):
```
CUDA_MPS_PIPE_DIRECTORY=/tmp/nvidia-mps
CUDA_MPS_LOG_DIRECTORY=/tmp/nvidia-log
CUDA_MPS_ACTIVE_THREAD_PERCENTAGE=25    # 100% / 4 instances
```

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

### Test Transcription

```bash
# Simple file upload
curl -X POST http://localhost:8002/transcribe/file \
  -F "audio_file=@test_audio.wav"

# With word timestamps
curl -X POST http://localhost:8002/transcribe/file \
  -F "audio_file=@test_audio.wav" \
  -F "timestamps=true"

# OpenAI-compatible endpoint
curl -X POST http://localhost:8002/v1/audio/transcriptions \
  -F "file=@test_audio.wav" \
  -F "model=parakeet-tdt-0.6b-v2" \
  -F "response_format=verbose_json" \
  -F "timestamp_granularities=word"
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/transcribe/file` | POST | Multipart WAV upload, returns `{"text": "..."}` |
| `/transcribe` | POST | JSON with base64 audio: `{"audio_base64": "...", "timestamps": false}` |
| `/v1/audio/transcriptions` | POST | OpenAI Whisper-compatible API |
| `/v1/models` | GET | List available models |
| `/health` | GET | Service health + performance stats |
| `/metrics` | GET | Prometheus-format metrics |

## Benchmarking

### SLA Benchmark (capacity planning)

Sweeps concurrency levels under sustained load to determine GPU requirements:

```bash
python benchmark_sla.py --wav test_audio.wav --duration-sec 30
```

### Latency Benchmark (quick test)

Sustained load at a specific concurrency level:

```bash
python benchmark_latency.py --wav test_audio.wav --concurrency 20 --duration-sec 15
```

### Throughput Benchmark

```bash
python benchmark_rps.py --wav test_audio.wav --concurrency 10 --requests 100
```

## Project Structure

```
seq_batching/
├── Dockerfile.triton          # Triton + NeMo + model weights
├── Dockerfile.gateway         # FastAPI gateway (no GPU)
├── docker-compose.yml         # Single-GPU deployment
├── auto_config.py             # Dynamic instance count + MPS config
├── server.py                  # FastAPI gateway (OpenAI-compatible API)
├── benchmark_sla.py           # Capacity planning benchmark
├── benchmark_latency.py       # Latency benchmark
├── benchmark_rps.py           # Throughput benchmark
├── triton_model_repo/
│   └── parakeet_asr/
│       ├── config.pbtxt       # Triton model config (batching, instances)
│       └── 1/
│           └── model.py       # Direct forward pass (bypasses NeMo overhead)
└── requirements-benchmark.txt
```
