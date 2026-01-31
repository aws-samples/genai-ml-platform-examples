# Model Deployment Repository

This repository contains the deployment configuration for automatically deploying approved models from SageMaker Model Registry to production endpoints.

## 🎯 Overview

When a model is approved in the SageMaker Model Registry, this deployment pipeline automatically:
1. Detects the approval via EventBridge
2. Generates CloudFormation templates
3. Deploys the model to a SageMaker endpoint
4. Makes the model available for inference

## 📁 Repository Structure

```
model-deploy-repo/
├── buildspec.yml              # CodeBuild script to generate deployment artifacts
├── prod-config.json           # Production configuration template
├── test-endpoint.py           # Script to test deployed endpoint
└── README.md                  # This file
```

## 🔄 Deployment Flow

```
1. Model approved in Model Registry
   ↓
2. EventBridge triggers CodePipeline
   ↓
3. CodeBuild runs buildspec.yml
   - Gets latest approved model
   - Generates CloudFormation template
   - Generates production config
   ↓
4. CloudFormation deploys endpoint
   - Creates SageMaker Model
   - Creates Endpoint Configuration
   - Creates Endpoint
   ↓
5. Endpoint is live and ready for inference
```

## 🚀 How to Approve a Model

### Via SageMaker Console:
1. Go to SageMaker Console → Model Registry
2. Find your model package group
3. Select the model version you want to deploy
4. Click "Update status" → "Approve"
5. The deployment pipeline will automatically trigger

### Via AWS CLI:
```bash
aws sagemaker update-model-package \
  --model-package-arn <model-package-arn> \
  --model-approval-status Approved
```

### Via Python (boto3):
```python
import boto3

sm_client = boto3.client('sagemaker')
sm_client.update_model_package(
    ModelPackageArn='<model-package-arn>',
    ModelApprovalStatus='Approved'
)
```

## 🧪 Testing the Deployed Endpoint

After deployment completes, test your endpoint using the provided Jupyter notebook:

### Open the Test Notebook:
```bash
jupyter notebook test-endpoint.ipynb
```

Or open it in SageMaker Studio.

### The notebook includes:
- ✅ Finding your endpoint
- ✅ Checking endpoint status
- ✅ Summarization examples
- ✅ Question answering examples
- ✅ Instruction following examples
- ✅ Custom prompt testing
- ✅ Batch processing
- ✅ Performance measurement

### Quick CLI Test:
```bash
# Find your endpoint name
aws sagemaker list-endpoints --name-contains llama

# Test with AWS CLI
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name <your-endpoint-name> \
  --content-type application/json \
  --body '{"inputs":"Test prompt","parameters":{"max_new_tokens":50}}' \
  output.json && cat output.json
```

## 📝 Inference Format

The endpoint expects JSON payloads in this format:

```json
{
  "inputs": "Your prompt text here",
  "parameters": {
    "max_new_tokens": 150,
    "temperature": 0.7,
    "top_p": 0.95,
    "do_sample": true
  }
}
```

### Example with boto3:
```python
import boto3
import json

runtime = boto3.client('sagemaker-runtime')

payload = {
    "inputs": "Summarize: Machine learning is...",
    "parameters": {
        "max_new_tokens": 100,
        "temperature": 0.7
    }
}

response = runtime.invoke_endpoint(
    EndpointName='your-endpoint-name',
    ContentType='application/json',
    Body=json.dumps(payload)
)

result = json.loads(response['Body'].read().decode())
print(result)
```

### Example with curl:
```bash
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name your-endpoint-name \
  --content-type application/json \
  --body '{"inputs":"Your prompt","parameters":{"max_new_tokens":100}}' \
  output.json

cat output.json
```

## ⚙️ Configuration

### Production Settings (prod-config.json):
- **Instance Type:** `ml.g5.2xlarge` (GPU instance for LLaMA)
- **Instance Count:** `1` (can be increased for higher throughput)
- **Auto-scaling:** Not configured (can be added later)

### To Modify Configuration:
Edit `prod-config.json` and commit changes. The next deployment will use the new settings.

## 🔍 Monitoring

### Check Endpoint Status:
```bash
aws sagemaker describe-endpoint --endpoint-name <endpoint-name>
```

### View CloudWatch Metrics:
- Go to CloudWatch Console
- Navigate to SageMaker → Endpoints
- Select your endpoint to view:
  - Invocations
  - Model Latency
  - CPU/GPU Utilization
  - Errors

### View Logs:
```bash
# Get log group name
aws logs describe-log-groups --log-group-name-prefix /aws/sagemaker/Endpoints

# View logs
aws logs tail /aws/sagemaker/Endpoints/<endpoint-name> --follow
```

## 🛠️ Troubleshooting

### Endpoint Deployment Failed:
1. Check CloudFormation stack events in AWS Console
2. Common issues:
   - Insufficient service quotas for instance type
   - IAM role permissions
   - Model artifacts not accessible

### Endpoint Returns Errors:
1. Check CloudWatch logs for the endpoint
2. Verify payload format matches expected input
3. Check model was trained correctly

### Slow Inference:
1. Consider using larger instance type (ml.g5.4xlarge, ml.g5.12xlarge)
2. Enable auto-scaling for multiple instances
3. Optimize model with SageMaker Neo or TensorRT

## 🔐 Security

- Endpoints are deployed in your VPC (if configured)
- Access controlled via IAM policies
- Data encryption in transit and at rest
- Model artifacts stored securely in S3

## 💰 Cost Optimization

### Current Cost (ml.g5.2xlarge):
- **Hourly:** ~$1.52/hour
- **Daily:** ~$36.48/day (if running 24/7)
- **Monthly:** ~$1,094/month

### To Reduce Costs:
1. **Delete endpoint when not in use:**
   ```bash
   aws sagemaker delete-endpoint --endpoint-name <endpoint-name>
   ```

2. **Use smaller instance for testing:**
   - Change to `ml.g5.xlarge` in prod-config.json

3. **Implement auto-scaling:**
   - Scale down to 0 instances during off-hours
   - Scale up based on traffic

## 📚 Additional Resources

- [SageMaker Endpoints Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html)
- [Model Registry Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html)
- [CloudFormation SageMaker Resources](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/AWS_SageMaker.html)

## 🤝 Support

For issues or questions:
1. Check CloudWatch logs
2. Review CloudFormation stack events
3. Contact your ML platform team
