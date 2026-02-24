#!/bin/bash

ENV_NAME="nemo-env"
PYTHON_VERSION="3.12"

echo "Creating conda environment: $ENV_NAME with Python $PYTHON_VERSION..."
conda create -n $ENV_NAME python=$PYTHON_VERSION -y

# Use conda run instead of conda activate in scripts
echo "Installing packages in the conda environment: $ENV_NAME..."
conda run -n $ENV_NAME pip install torch==2.10.0 torchaudio==2.10.0 torchvision==0.25.0
conda run -n $ENV_NAME pip install -r requirements.txt


echo "Installing system dependencies..."
sudo apt-get update 
sudo apt-get install -y \
    wget \
    curl \
    poppler-utils \
    build-essential \
    git \
    gcc \
    g++ \
    make \
    cmake \
    ninja-build \
    libsox-fmt-mp3 \
    gnupg \
    sox

# Install Cython (needed for NeMo)
conda run -n $ENV_NAME python -m pip install Cython
conda run -n $ENV_NAME pip install --upgrade torch torchvision torchaudio numba


echo "Setup complete! You can activate your environment using: conda activate $ENV_NAME"
