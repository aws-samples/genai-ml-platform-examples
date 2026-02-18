# ec2-mnist Technical Documentation

## Architecture Overview

This project implements a complete MLOps pipeline on Amazon SageMaker with the following components:

### Training Pipeline
- **Entry Point**: `training/train.py`
- **Model Definition**: `training/model.py`
- **Dependencies**: See `training/requirements.txt`

### Inference Pipeline  
- **Handler**: `inference/inference.py`
- **Model Loading**: Supports both state_dict and TorchScript formats
- **Dependencies**: See `inference/requirements.txt`

### MLOps Pipeline
- **Definition**: `pipeline/pipeline.py`
- **Preprocessing**: `pipeline/preprocessing.py`
- **Evaluation**: `pipeline/evaluation.py`

## Key Migration Changes

### Environment Variables
Original code used hard-coded paths. SageMaker provides:
- `SM_CHANNEL_TRAINING`: Training data path
- `SM_MODEL_DIR`: Model output directory
- `SM_NUM_GPUS`: Number of available GPUs

### Hyperparameters
SageMaker passes hyperparameters via command line arguments automatically.

### Data Loading
- **Before**: Local file paths
- **After**: S3 paths via SageMaker channels

### Model Saving
- **Before**: Local filesystem
- **After**: `/opt/ml/model/` for SageMaker model artifacts

## Dependencies Analysis

### Compatible Packages
- torch

### Problematic Packages (Replaced)
- **torchvision** → manual_download

## Testing Strategy

### Unit Tests
- Training component validation
- Model architecture verification
- Data preprocessing validation

### Integration Tests
- End-to-end pipeline execution
- Inference endpoint testing
- Performance benchmarking

### Property-Based Tests
- Model consistency across inputs
- Pipeline robustness validation
- Infrastructure compliance checks

## Performance Considerations

### Instance Selection
- **Development**: ml.m5.large (CPU, cost-effective)
- **Production**: ml.p3.2xlarge (GPU, high performance)
- **Large Scale**: ml.p3.8xlarge (Multi-GPU)

### Cost Optimization
- Spot instances for training jobs
- Auto-scaling for inference endpoints
- Lifecycle policies for S3 storage

## Security Implementation

### IAM Roles
- Least privilege access policies
- Separate roles for training and inference
- Cross-account access controls

### Data Encryption
- S3 bucket encryption at rest
- In-transit encryption for training
- KMS key management

## Monitoring and Observability

### CloudWatch Metrics
- Training job performance
- Resource utilization
- Pipeline execution status
- Endpoint performance

### Logging
- Structured logging for all components
- CloudWatch integration
- Error tracking and alerting

---

For deployment instructions, see [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
