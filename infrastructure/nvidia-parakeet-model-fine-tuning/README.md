# Enhancing Speech Recognition Accuracy by Fine-tuning NVIDIA Parakeet Models on Amazon EKS Auto Mode

This repository contains code for fine-tuning NVIDIA Parakeet ASR models on custom datasets.

## Repository Structure
```
.
├── Dockerfile
├── README.md
├── configs/
│   └── fine_tuning_config.yaml
├── data_preparation_fleurs.py
├── download-and-prepare-data-fleurs.sh
├── install.sh
├── requirements.txt
├── run-app.sh
├── run-docker.sh
├── run-train.sh
└── trainer.py
```

## Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/aws-samples/genai-ml-platform-examples.git
cd genai-ml-platform-examples/infrastructure/nvidia-parakeet-model-fine-tuning
```

### 2. Install Dependencies
```bash
chmod +x install.sh
./install.sh
conda activate nemo-env
```

### 3. Download and Prepare Data
```bash
chmod +x download-and-prepare-data-fleurs.sh
./download-and-prepare-data-fleurs.sh
```

### 4. Start Training
```bash
chmod +x run-train.sh
./run-train.sh
```

## Overview

This project fine-tunes NVIDIA's Parakeet-tdt-0.6b-v2 ASR model for improved speech recognition on domain-specific datasets.

## Features

- **Domain Adaptation**: Fine-tune pre-trained Parakeet models on custom datasets
- **Multi-GPU Training**: Distributed training with DeepSpeed and DDP
- **Data Preparation**: Utilities for audio dataset preprocessing
- **Evaluation Metrics**: WER, CER, and Drug Name Recall
- **Experiment Tracking**: MLflow and TensorBoard integration

## Requirements

### Hardware
- GPU: NVIDIA GPU with 16GB+ VRAM (4x GPUs recommended)
- Storage: 100GB+ free disk space

### Software
- CUDA 12.8+
- Python 3.12
- AWS CLI (configured with appropriate permissions)

## Configuration

Edit `configs/fine_tuning_config.yaml` to adjust:
- Batch size
- Learning rate
- Number of epochs
- Model architecture
- Data augmentation

Training progress is logged to console, MLflow, and TensorBoard.

## Alternative Deployment Options

### Run as Application
```bash
chmod +x run-app.sh
./run-app.sh
```

### Run with Docker
```bash
chmod +x run-docker.sh
./run-docker.sh
```

## Authors

- Iman Abbasnejad (Applied Scientist, AWS)
- Faisal Masood (AppMod and Inferencing, AWS)

## Acknowledgments

Based on NVIDIA NeMo framework and Parakeet ASR models.
