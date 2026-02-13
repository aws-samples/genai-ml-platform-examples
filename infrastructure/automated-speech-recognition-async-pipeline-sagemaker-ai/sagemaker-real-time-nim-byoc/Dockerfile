FROM nvcr.io/nim/nvidia/parakeet-1-1b-ctc-en-us:latest
USER root

# Metadata for SageMaker
LABEL maintainer="Combined NIM Team"
LABEL description="NVIDIA NIM ASR (CTC EN-US) for SageMaker - unified HTTP+gRPC adapter"
LABEL com.amazonaws.sagemaker.capabilities.accept-bind-to-port=true
LABEL com.amazonaws.sagemaker.inference.cuda.verified_versions=12.2
LABEL com.amazonaws.sagemaker.capabilities.bidirectional-streaming=true

# Environment configuration
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1
ENV SAGEMAKER_BIND_TO_PORT=8080
ENV NIM_HOST=127.0.0.1
ENV NIM_HTTP_PORT=9000
ENV RIVA_GRPC_PORT=50051
# Proven working model settings (offline mode). Diarization optional via gRPC only
ENV NIM_TAGS_SELECTOR=name=parakeet-1-1b-ctc-en-us,mode=all,vad=silero,diarizer=sortformer

ENV LD_LIBRARY_PATH=/usr/lib/x86_64-linux-gnu/:/usr/local/cuda-13.0/lib64:/opt/tritonserver/backends/pytorch:/opt/tritonserver/lib:/opt/riva/lib:/usr/local/cuda/compat/lib:/usr/local/nvidia/lib:/usr/local/nvidia/lib64
# System deps and Python packages
RUN apt-get update && apt-get install -y \
    curl \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install --no-cache-dir --index-url https://pypi.org/simple/ \
    aiohttp==3.9.5 \
    nvidia-riva-client \
    grpcio==1.67.1 \
    protobuf==5.29.5 \
    python-multipart==0.0.6

RUN pip3 install --upgrade onnxruntime onnxruntime-gpu --index-url https://pypi.org/simple/

# Copy inference server
WORKDIR /opt/ml/code
COPY inference.py /opt/ml/code/
RUN chmod +x /opt/ml/code/inference.py

# Create directories expected by SageMaker
RUN mkdir -p /opt/ml/model /opt/ml/input /opt/ml/output /var/log

# Expose SageMaker port and set healthcheck
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD curl -f http://localhost:8080/ping || exit 1

# Entrypoint - start Python inference server which in turn starts NIM
ENTRYPOINT ["python3", "/opt/ml/code/inference.py"]


