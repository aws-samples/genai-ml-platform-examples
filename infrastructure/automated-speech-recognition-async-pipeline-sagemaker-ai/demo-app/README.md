# Voice Demo Application

A real-time voice transcription demo application using AWS SageMaker endpoints, WebSocket connections, and React frontend.

## Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.9+
- Node.js 18+
- AWS CDK v2 installed
- SageMaker endpoints deployed (async and/or real-time)

## Setup Instructions

### 1. Install CDK Infrastructure

#### Setup Python Environment
```bash
cd demo-app/infra

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure SageMaker Endpoints

Before deploying, ensure you have SageMaker endpoints ready:

- **Async Endpoint**: For batch audio processing (e.g., Parakeet ASR)
- **Real-time Endpoint**: For streaming audio processing (e.g., NIM ASR)

### 3. Configure configs.json

Edit `infra/configs/configs.json` with your SageMaker endpoint details:

```json
{
    "websocket_url": "wss://xxxxxxxxxx.execute-api.us-west-2.amazonaws.com/prod",
    "api_url": "https://xxxxxxxxxx.execute-api.us-west-2.amazonaws.com",
    "sagemaker_endpoints": [
        {
            "name": "parakeet",
            "endpoint_name": "<your-async-endpoint-name>",
            "type": "async",
            "sns_topic_arn": "arn:aws:sns:us-west-2:xxxxxxxxxx:async-success",
            "output_bucket": "sagemaker-us-west-2-xxxxxxxxxx"
        },
        {
            "name": "nim",
            "endpoint_name": "<your-realtime-endpoint-name>",
            "type": "realtime"
        }
    ]
}
```

**Configuration Fields:**
- `endpoint_name`: Your SageMaker endpoint name
- `type`: Either "async" or "realtime"
- `sns_topic_arn`: SNS topic for async endpoint notifications (async only)
- `output_bucket`: S3 bucket for async endpoint outputs (async only)

### 4. Deploy VoiceDemoBackend Stack First

```bash
cd infra

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy backend stack
cdk deploy VoiceDemoBackend
```

After deployment, note the outputs:
- WebSocket API Gateway URL
- REST API Gateway URL

### 5. Update configs.json with Endpoints

Update `infra/configs/configs.json` with the deployed API endpoints:

```json
{
    "websocket_url": "wss://[your-websocket-id].execute-api.us-west-2.amazonaws.com/prod",
    "api_url": "https://[your-api-id].execute-api.us-west-2.amazonaws.com",
    "sagemaker_endpoints": [
        // ... your endpoint configurations
    ]
}
```

### 6. Deploy VoiceDemoFrontend Stack

```bash
# Deploy frontend stack
cdk deploy VoiceDemoFrontend
```

## Accessing the Frontend

After successful deployment of the frontend stack, you'll receive a CloudFront distribution URL:

```
FrontendUrl = https://[distribution-id].cloudfront.net
```

Open this URL in your browser to access the voice demo application.

## Application Features

- **Real-time Audio Recording**: Record audio directly in the browser
- **Multiple Endpoint Support**: Switch between different SageMaker endpoints
- **Async Processing**: Upload audio files for batch processing
- **Real-time Streaming**: Stream audio for immediate transcription
- **WebSocket Communication**: Real-time status updates and results

## Troubleshooting

### Common Issues

1. **CDK Bootstrap Error**: Ensure your AWS credentials have sufficient permissions
2. **Endpoint Not Found**: Verify SageMaker endpoint names in configs.json
3. **CORS Issues**: Check API Gateway CORS configuration in backend stack
4. **WebSocket Connection Failed**: Verify WebSocket URL in configs.json

### Logs and Monitoring

- Check CloudWatch logs for Lambda function errors
- Monitor API Gateway access logs
- Review SageMaker endpoint logs for inference issues

## Development

### Local Frontend Development

```bash
cd frontend
npm install
npm start
```

Update `frontend/src/config/AppConfigDev.js` for local development endpoints.

### Stack Management

```bash
# List all stacks
cdk list

# View stack differences
cdk diff VoiceDemoBackend
cdk diff VoiceDemoFrontend

# Destroy stacks (in reverse order)
cdk destroy VoiceDemoFrontend
cdk destroy VoiceDemoBackend
```

## Architecture

The application consists of:

- **Backend Stack**: API Gateway (REST + WebSocket), Lambda functions, DynamoDB
- **Frontend Stack**: React app deployed via CloudFront and S3
- **SageMaker Integration**: Async and real-time inference endpoints
- **Real-time Communication**: WebSocket for status updates and streaming

## Security

- API Gateway uses IAM authentication
- Lambda functions have minimal required permissions
- S3 buckets use server-side encryption
- CloudFront distribution uses HTTPS only