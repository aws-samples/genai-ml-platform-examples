FROM pytorch/pytorch:2.10.0-cuda12.8-cudnn9-devel

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    MLFLOW_TRACKING_URI=/workspace/mlruns \
    TENSORBOARD_LOGS=/workspace/tensorboard

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    git \
    libsndfile1 \
    libsox-fmt-mp3 \
    rubberband-cli \
    sox \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN python -m pip install --break-system-packages --no-cache-dir --upgrade pip Cython && \
    python -m pip install --break-system-packages --no-cache-dir -r requirements.txt

COPY configs configs
COPY trainer.py data_preparation_fleurs.py ./
COPY download-and-prepare-fleurs.sh run-train.sh ./
RUN chmod +x download-and-prepare-fleurs.sh run-train.sh && \
    mkdir -p /workspace && \
    chown -R 1000:1000 /app /workspace

USER 1000:1000
CMD ["./run-train.sh"]
