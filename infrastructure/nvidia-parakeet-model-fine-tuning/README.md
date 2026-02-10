#  Enhancing speech recognition accuracy by fine-tuning NVIDIA Parakeet models on Amazon EKS Auto Mode

This repository contains code for fine-tuning NVIDIA Parakeet ASR models.

## Repository Structure
```
.
├── Dockerfile
├── README.md
├── configs
│   └── fine_tuning_config.yaml
├── data_preparation_fleurs.py
├── download-and-prepare-data-fleurs.sh
├── install.sh
├── requirements.txt
├── run-app.sh
├── run-docker.sh
├── run-train.sh
└── trainer.py
```

## Clone the Repository
### Clone the repository (dev-0 branch)
```
git clone -b dev-0 https://github.com/oscerai/asr-parakeet.git
```
### Navigate to the project directory
```
cd asr-parakeet/asr-parakeet-fine-tuning
```
## Overview

This project fine-tunes NVIDIA's Parakeet-tdt-0.6b-v2 ASR model.

## Features

### Domain: Fine-tunes pre-trained Parakeet models on a dataset
### Multi-GPU Training: Supports distributed training across multiple GPUs using DeepSpeed and DDP
### Data Preparation: Includes utilities for preparing audio datasets in the required format
### Evaluation: Measures Word Error Rate (WER), Character Error Rate (CER) and Drug Name Recall

## Pre-requisites

### Hardware Requirements
- GPU: At least one NVIDIA GPU with 16GB+ VRAM (4x GPUs recommended for full training)
- Storage: At least 100GB free disk space for datasets and model checkpoints

### Software Requirements
- CUDA: CUDA 12.8
- Python: Python 3.12
- AWS CLI: Configured with appropriate permissions to access the dataset

### Getting Started

#### Step 1: Install Dependencies
Run the installation script to set up the required environment:
```
chmod +x install.sh
./install.sh
```
This will create a Conda environment with all necessary dependencies including PyTorch, NVIDIA NeMo, and other libraries.

#### Step 2: Activate the conda environment
```
conda activate nemo-env
```

#### Step 3: Download and Prepare Data

Download and prepare the dataset. You need to provide the absolute path to the download directory:
```
chmod +x download-and-prepare-data.sh
./download-and-prepare-data.sh
```

This script will:

- Download data from AWS S3, Process the data into the format required by NeMo.

#### Step 3: Configure Training Parameters
Edit the configuration file at configs/fine_tuning_config.yaml to adjust training parameters such as:

- Batch size
- Learning rate
- Number of epochs
- Model architecture settings (if required)
- Data augmentation settings

Step 4: Start Training
- Begin the fine-tuning process:
```
chmod +x run-train.sh
./run-train.sh
```

The script uses DeepSpeed for distributed training across all available GPUs. Training progress will be logged to the console and to MLflow/TensorBoard.

- Model Configuration
The fine-tuning process uses a YAML configuration file with settings for:

- Model Architecture: Based on Parakeet Token and Duration Transducer (TDT)

- Training Data: Path to processed recordings

- Optimization: Learning rate schedule, weight decay, and other hyperparameters
- Distributed Training: DeepSpeed stage 2 configuration

#### Run as an app
Simply run the app by modifying the batch size, absolute path to the dataset and the number of epochs:
```
chmod +x run-app.sh
./run-app.sh
```

#### Run as a docker file
Simply run it as a docker file. You can modify the batch size, absolute path to the dataset, number of epochs, container name and path to mapped models:
```
chmod +x run-docker.sh
./run-docker.sh
```

### Authors

- Iman Abbasnejad (Applied Scientist, AWS)

- Faisal Masood (AppMod and Inferencing, AWS)


### Acknowledgments
- Based on NVIDIA NeMo framework and Parakeet ASR models


