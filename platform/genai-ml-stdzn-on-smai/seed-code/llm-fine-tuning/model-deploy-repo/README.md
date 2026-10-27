# Model Deployment Repository

This repository contains the deployment configuration for automatically deploying approved models from SageMaker Model Registry to production endpoints.

## 🎯 Overview

When a model is approved in the SageMaker Model Registry, this deployment pipeline automatically:
1. Detects the approval via EventBridge
2. Deploys the model to a SageMaker endpoint, trying GPU instance types in order until one has capacity
3. Runs smoke tests against the endpoint
4. Makes the model available for inference

## 📁 Repository Structure

```
model-deploy-repo/
├── buildspec.yml              # CodeBuild script that runs deploy_with_fallback.py
├── deploy_with_fallback.py    # Deploys the endpoint, falling back across GPU types
├── deploy-config.json         # Ordered list of endpoint instance types to try
├── test/buildspec.yml         # Smoke tests run against the endpoint after deploy
├── test-endpoint.ipynb        # Notebook to test the deployed endpoint
└── README.md                  # This file
```

## 🔄 Deployment Flow

```
1. Model approved in Model Registry
   ↓
2. EventBridge triggers CodePipeline
   ↓
3. CodeBuild runs buildspec.yml -> deploy_with_fallback.py
   - Gets latest approved model
   - Creates SageMaker Model (once)
   - For each instance type in deploy-config.json:
       creates an Endpoint Configuration, then creates or updates the Endpoint
       capacity error -> clean up, try the next type
       InService       -> stop, write deploy-output.json
   ↓
4. CodeBuild runs test/buildspec.yml (smoke tests)
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

### Deployment Settings (deploy-config.json):
You do not need to edit this file. The defaults work as shipped.

| Key | Default | Meaning |
|---|---|---|
| `EndpointInstanceTypes` | `ml.g6.xlarge`, `ml.g5.xlarge`, `ml.g6.2xlarge`, `ml.g5.2xlarge`, `ml.g6.4xlarge`, `ml.g5.4xlarge` | Types to try, in order. All have a 24 GB GPU. Same order as Lab 3b. |
| `EndpointInstanceCount` | `1` | Instances behind the endpoint |
| `Rounds` | `1` | How many times to walk the whole list before giving up |
| `WaitBetweenRoundsSeconds` | `60` | Pause between rounds |
| `PollSeconds` | `30` | How often to check endpoint status |

To change the order or the types, edit `deploy-config.json` and commit. The next deployment uses the new settings.

### GPU Capacity Fallback:
GPU instances are sometimes unavailable in a Region (`InsufficientInstanceCapacity`, or
"Unable to provision requested ML compute capacity"). Instead of waiting on one type,
`deploy_with_fallback.py` (a port of Lab 3b's `deploy_with_fallback()`):

1. Creates the SageMaker Model once.
2. For each type in `EndpointInstanceTypes`, creates a new endpoint config and creates the
   endpoint, or updates it if it already exists. The endpoint name is always
   `<project-name>-<project-id>`.
3. If the type has no capacity, deletes the failed endpoint (if any) and the unused
   endpoint config, then tries the next type. A failed update rolls back to the old
   config, so the previous model keeps serving.
4. Stops at the first type that reaches `InService` and writes `deploy-output.json`
   (endpoint name, instance type, endpoint config, model).

Any other error stops the deploy, including `ResourceLimitExceeded` (a service quota of 0
for that type). If every type is out of capacity, the build fails with the list of types
it tried. Re-run the pipeline later ("Release change" in CodePipeline).

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
1. Check the CodeBuild logs of the deploy build. Each `[attempt]` line shows the type tried and the result.
2. Common issues:
   - No capacity on any configured instance type (re-run later, or add types to `deploy-config.json`)
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

### Current Cost:
The cost depends on which type the fallback picked; `deploy-output.json` and the
deploy build logs show it. For example, `ml.g5.2xlarge` is about $1.52/hour
(~$36.48/day if running 24/7).

### To Reduce Costs:
1. **Delete the endpoint when not in use.** The endpoint is not part of a
   CloudFormation stack, so deleting a stack does not remove it. Delete the
   endpoint, its endpoint config and its model directly:
   ```bash
   EP=<endpoint-name>
   CFG=$(aws sagemaker describe-endpoint --endpoint-name $EP --query EndpointConfigName --output text)
   MODEL=$(aws sagemaker describe-endpoint-config --endpoint-config-name $CFG --query 'ProductionVariants[0].ModelName' --output text)
   aws sagemaker delete-endpoint --endpoint-name $EP
   aws sagemaker delete-endpoint-config --endpoint-config-name $CFG
   aws sagemaker delete-model --model-name $MODEL
   ```

2. **Prefer smaller instances:**
   - Put the cheaper types first in `EndpointInstanceTypes` in deploy-config.json

3. **Implement auto-scaling:**
   - Scale down to 0 instances during off-hours
   - Scale up based on traffic

## 📚 Additional Resources

- [SageMaker Endpoints Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/realtime-endpoints.html)
- [Model Registry Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/model-registry.html)
- [Create an endpoint with boto3](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/sagemaker/client/create_endpoint.html)

## 🤝 Support

For issues or questions:
1. Check CloudWatch logs
2. Review the deploy CodeBuild logs
3. Contact your ML platform team
