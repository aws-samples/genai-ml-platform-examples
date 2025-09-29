# Voice Demo Application

A real-time voice transcription demo application using AWS SageMaker endpoints, WebSocket connections, Cognito authentication, and React frontend.

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
    "region": "<deployment-region",
    "websocket_url": "wss://xxxxxxxxxx.execute-api.us-west-2.amazonaws.com/prod",
    "api_url": "https://xxxxxxxxxx.execute-api.us-west-2.amazonaws.com",
    "user_pool_id": "YOUR_USER_POOL_ID",
    "user_pool_client_id": "YOUR_USER_POOL_CLIENT_ID",
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
- `region`: Region to deploy the demo app
- `websocket_url`: Websocket which publishes transcription results (obtained from backend deployment)
- `api_url`: API hosting the transcription requests and upload functionality (obtained from backend deployment)
- `endpoint_name`: Your SageMaker endpoint name
- `type`: Either "async" or "realtime"
- `sns_topic_arn`: SNS topic for async endpoint notifications (async only)
- `output_bucket`: S3 bucket for async endpoint outputs (async only)
- `user_pool_id`: Cognito User Pool ID (obtained from backend deployment)
- `user_pool_client_id`: Cognito User Pool Client ID (obtained from backend deployment)

### 4. Deploy VoiceDemoBackend Stack First

```bash
cd infra

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy backend stack
cdk deploy VoiceDemoBackend
```

After deployment, note the outputs:
- **WebSocket API Gateway URL**: Copy this to `websocket_url` in configs.json
- **REST API Gateway URL**: Copy this to `` in configs.json
- **UserPoolId**: Copy this to `user_pool_id` in configs.json
- **UserPoolClientId**: Copy this to `user_pool_client_id` in configs.json

### 5. Update configs.json with Deployed Resources

Update `infra/configs/configs.json` with the deployed API endpoints and Cognito configuration:

```json
{
    "websocket_url": "wss://[your-websocket-id].execute-api.us-west-2.amazonaws.com/prod",
    "api_url": "https://[your-api-id].execute-api.us-west-2.amazonaws.com",
    "user_pool_id": "us-west-2_xxxxxxxxx",
    "user_pool_client_id": "xxxxxxxxxxxxxxxxxxxxxxxxxx",
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

- **User Authentication**: Secure login with AWS Cognito (email-based signup/signin)
- **Real-time Audio Recording**: Record audio directly in the browser
- **File Upload**: Upload WAV files for transcription
- **Multiple Endpoint Support**: Switch between different SageMaker endpoints
- **Async Processing**: Upload audio files for batch processing
- **Real-time Streaming**: Stream audio for immediate transcription
- **WebSocket Communication**: Real-time status updates and results
- **Responsive UI**: Modern and retro cassette themes

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

## Authentication

### User Registration and Login

1. **First-time users**: Click "Sign Up" to create an account
   - Provide username, email, and password
   - Check email for confirmation code
   - Enter confirmation code to activate account

2. **Returning users**: Use "Sign In" with username/password

3. **Password Requirements**:
   - Minimum 8 characters
   - Must contain uppercase, lowercase, and numbers

### API Protection

All transcription and upload endpoints are protected with JWT tokens from Cognito. Users must be authenticated to access the application features.

## Security

- **Cognito Authentication**: JWT-based API protection
- **API Gateway**: Uses Cognito JWT authorizer
- **Lambda functions**: Minimal required permissions
- **S3 buckets**: Server-side encryption
- **CloudFront distribution**: HTTPS only