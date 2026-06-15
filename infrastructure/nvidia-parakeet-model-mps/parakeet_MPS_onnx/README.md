# Parakeet TDT ASR with ONNX support — High-Throughput Speech-to-Text Service

**Author:** 
* Iman Abbasnejad (Applied Scientist) — imanaba@amazon.com
* Jerron Chua (Deep Learning Architect) - jerronc@amazon.com

Production-grade ASR service built on a optimised NVIDIA Parakeet TDT 0.6B v2 model whereby:
* Encoder running via ONNXruntime with TensorRT
* Decoder & Joint network running via Pytorch CUDA

Served via Triton Inference Server with CUDA MPS for maximum GPU utilization.

## Performance Summary

Benchmarked on a single RTX PRO 6000 (98GB) with 45-second audio clips. 4 different methods were benchmarked:

[Recommended approach] Only encoder running in ONNX, compiled with __dynamo__, __local attention__
```
    Conc       RPS       RPM     p50ms      mean     p99ms
       1      9.1       544      110.6     110.8     113.1
       4      34.4      2064     116.9     116.9     120.0
      16     113.2      6792     139.9     142.4     173.3 
      32     128.3      7696     187.3     251.8     558.2 
      64     138.3      8300     493.4     472.9     857.6 
     100     141.7      8502     737.7     728.9    1153.0 
```

Only encoder running in ONNX, compiled with __torch script__, __local attention__
```
    Conc       RPS       RPM     p50ms      mean     p99ms
       1       9.1       544     111.0     111.0     112.6
       4      33.9      2034     117.6     118.4     164.3
      16     103.1      6184     155.3     156.2     173.0 
      32     111.8      6708     330.7     289.7     454.6 
      64     110.4      6622     594.6     594.9     834.3 
     100     112.2      6734     878.9     933.4    1744.6 
```

Only encoder running in ONNX, compiled with __torch script__, __global attention__
```
    Conc       RPS       RPM     p50ms      mean     p99ms
       1       9.5       568     106.1     106.2     107.0  
       4      33.6      2016     119.2     119.5     124.2
      16     115.9      6952     138.5     138.9     155.7 
      32     135.7      8140     248.8     238.6     337.7 
      64     153.9      9232     421.0     424.4     605.8 
     100     152.5      9152     696.1     675.0     920.9 
```
*Note: This method is the fastest, however with longer audios, global attention will get exponentially more expensive, and accuracy might degrade since the pretrained NeMo model is trained with audio up to 40s long* 

Both encoder & decoder+joint network running in ONNX, compiled with __torch script__
```
    Conc       RPS       RPM     p50ms      mean     p99ms
       1       5.8       348     173.2     173.5     176.7
       4      18.1      1088     222.5     222.3     232.6
      16      64.0      3840     250.5     252.6     288.1 
      32      77.5      4648     448.9     420.4     654.4 
      64      83.8      5026     733.3     791.2    1226.3 
     100      89.0      5342     881.7    1187.5    2217.0 
```



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
5. **ONNX exporter** - exports the NeMo models into ONNX graphs

### Key Optimizations

- **Direct forward pass**: Bypasses NeMo's `transcribe()` API (which creates temp dirs, DataLoaders, manifests per request) and calls `model.forward()` + `decoding.rnnt_decoder_predictions_tensor()` directly
- **CUDA MPS**: 4 instances share the GPU with guaranteed SM allocation instead of time-slicing
- **bfloat16 autocast**: 2x memory efficiency, faster matmuls on Ampere+
- **Local attention**: `rel_pos_local_attn` with context [128, 128] — reduces quadratic attention cost
- **Pre-cached kernels**: Warmup with varying audio lengths (5s–45s) at startup
- **ONNX runtime with TensorRT**: Converting of the model components to ONNX graph allows TensorRT engine to run for faster inference speeds

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
├── Dockerfile.triton-onnx          # Triton + NeMo + model weights
├── Dockerfile.gateway         # FastAPI gateway (no GPU)
├── docker-compose.yml         # Single-GPU deployment
├── auto_config.py             # Dynamic instance count + MPS config
├── server.py                  # FastAPI gateway (OpenAI-compatible API)
├── patch_local_attn.py        # Patches unsupported ops from NeMo Local Attention implementation to fix ONNX export
├── export_onnx_docker.py      # [Deprecated - Reference only] Exports the NeMo ASRModel into 2 files - Encoder & (Decoder + Joint) graphs
├── export_onnx_dynamo_docker.py    # Exports the Encoder within NeMo ASRModel into ONNX graph via Torch Dynamo
├── benchmark_sla.py           # Capacity planning benchmark
├── benchmark_latency.py       # Latency benchmark
├── benchmark_rps.py           # Throughput benchmark
├── triton_model_repo/
│   └── parakeet_asr/
│       ├── config_onnx.pbtxt       # Triton model config (batching, instances)
│       └── 1/
│           ├── asr_model_onnx.py   # Custom implementation of NeMo ASRModel class to support ONNX runtime
│           └── model.py       # Direct forward pass (bypasses NeMo overhead)
└── requirements-benchmark.txt
```

## Additional Notes
We strongly recommend to use the approach where only the Encoder is compiled to ONNX, and the export is using Torch Dynamo. Local attention is enabled in this build.

However, the repo contains all relevant codes for other modes:
* Compiling & running Encoder & (Decoder + Joint) ONNX graphs
* Exporting with Torchscript instead of Dynamo
* Exporting without local attention (ie. the default global attention)