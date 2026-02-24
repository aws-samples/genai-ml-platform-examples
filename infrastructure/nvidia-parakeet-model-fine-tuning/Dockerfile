ARG FROM_IMAGE_NAME=nvcr.io/nvidia/pytorch:24.01-py3
FROM nvcr.io/nvidia/pytorch:24.01-py3

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=UTC

# Set the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsox-fmt-mp3 \
    gnupg \
    && rm -rf /var/lib/apt/lists/*
    
# Install Cython (needed for NeMo)
RUN pip install Cython

# Install pytorch-lightning from official PyPI
# If you need a specific version or patch, pin to a specific release version
RUN pip install pytorch-lightning

# Install TransformerEngine for optimization
RUN git clone https://github.com/NVIDIA/TransformerEngine.git && \
    cd TransformerEngine && \
    git fetch origin 8c9abbb80dba196f086b8b602a7cf1bce0040a6a && \
    git checkout FETCH_HEAD && \
    git submodule init && git submodule update && \
    NVTE_FRAMEWORK=pytorch NVTE_WITH_USERBUFFERS=1 MPI_HOME=/usr/local/mpi pip install .

# Create directories for data, models, logs, TensorBoard and MLflow
RUN mkdir -p /app/models /app/logs /app/tb_logs /app/mlruns /app/data

# Copy only the requirements file first to leverage Docker cache
COPY requirements.txt requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY configs configs
COPY trainer.py trainer.py
COPY data_preparation.py data_preparation.py
COPY evaluate_all_metrics.py evaluate_all_metrics.py
COPY install.sh install.sh
COPY run-train.sh run-train.sh
COPY run-eval.sh run-eval.sh

# Make all scripts executable
RUN chmod +x *.sh

# Create a non-root user 'admin' and give ownership of the app directory
RUN useradd -m admin && \
    chown -R admin:admin /app

# Create entrypoint script with improved error handling and GPU checks
RUN cat > /app/entrypoint.sh << 'EOF'
#!/bin/bash
set -e

# Check if NVIDIA GPUs are available
if ! command -v nvidia-smi &> /dev/null; then
    echo "WARNING: nvidia-smi not found, GPU acceleration may not be available"
else
    echo "Detected NVIDIA GPU:"
    nvidia-smi
fi

# Start tensorboard in the background
echo "Starting TensorBoard on port 6006..."
tensorboard --logdir=$TENSORBOARD_LOGS --host 0.0.0.0 --port 6006 &

# Start MLflow in the background
echo "Starting MLflow UI on port 5000..."
mlflow ui --host 0.0.0.0 --port 5000 &

# Give services time to start
sleep 5

# Execute the command passed to docker run
echo "Running command: $@"
exec "$@"
EOF

# Ensure the entrypoint script has the right permissions and is properly created
RUN chmod +x /app/entrypoint.sh

# Switch to the non-root user for better security
USER admin

# Expose the ports for TensorBoard and MLflow
EXPOSE 6006 5000 3000 6007 8888

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV MLFLOW_TRACKING_URI=/app/mlruns
ENV TENSORBOARD_LOGS=/app/logs/tensorboard

# Add healthcheck to ensure the application is running properly
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

# Use the startup script as an entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command to start training (without download step)
CMD ["/bin/bash", "-c", "./run-train.sh"]
