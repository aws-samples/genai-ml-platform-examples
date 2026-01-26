# Requirements Document: SageMaker Migration Advisor Deployment

## Introduction

This document specifies the requirements for fixing, testing, and deploying the SageMaker Migration Advisor Streamlit application to AWS Fargate with internal Amazon user authentication. The application helps users migrate ML/GenAI workloads to AWS SageMaker through an interactive web interface with AI-powered analysis, architecture design, and migration planning.

## Glossary

- **Application**: The SageMaker Migration Advisor Streamlit web application
- **Bedrock**: AWS Bedrock service providing Claude AI models
- **MCP_Server**: Model Context Protocol server for diagram generation
- **Diagram_Generator**: Component responsible for creating architecture diagrams
- **PDF_Generator**: Component responsible for creating comprehensive PDF reports
- **Container**: Docker container packaging the Application
- **Fargate**: AWS ECS Fargate serverless container orchestration service
- **ALB**: Application Load Balancer for routing HTTPS traffic
- **Cognito**: AWS Cognito service for user authentication
- **CDK**: AWS Cloud Development Kit for infrastructure as code
- **Session_State**: Streamlit session state maintaining workflow progress
- **Workflow**: Multi-step migration analysis process (input → analysis → Q&A → design → diagrams → TCO → roadmap)

## Requirements

### Requirement 1: Diagram Generation Fix

**User Story:** As a user, I want architecture diagrams to be generated and saved correctly, so that I can visualize the proposed SageMaker architecture.

#### Acceptance Criteria

1. WHEN the diagram generation step is triggered, THE Diagram_Generator SHALL invoke the MCP_Server with the SageMaker architecture design
2. WHEN the MCP_Server generates a diagram, THE Diagram_Generator SHALL save the diagram file to the generated-diagrams folder
3. WHEN diagram files are saved, THE Application SHALL verify the files exist and have non-zero size
4. WHEN diagram generation completes, THE Application SHALL display the generated diagrams in the web interface
5. IF the MCP_Server fails, THEN THE Diagram_Generator SHALL log detailed error information and provide user-friendly error messages
6. WHEN multiple diagrams are generated, THE Application SHALL display all diagrams in a grid layout
7. WHEN the generated-diagrams folder does not exist, THE Application SHALL create it before attempting to save diagrams

### Requirement 2: PDF Report Generation Fix

**User Story:** As a user, I want to download a comprehensive PDF report with all analysis sections and embedded diagrams, so that I can share the migration plan with stakeholders.

#### Acceptance Criteria

1. WHEN PDF generation is triggered, THE PDF_Generator SHALL include all completed workflow sections in the report
2. WHEN architecture diagrams exist, THE PDF_Generator SHALL embed the diagram images in the PDF document
3. WHEN embedding images, THE PDF_Generator SHALL resize images to fit within page margins while maintaining aspect ratio
4. IF an image cannot be embedded, THEN THE PDF_Generator SHALL include a note explaining the issue and continue processing
5. WHEN the PDF is generated, THE PDF_Generator SHALL include a table of contents with all sections
6. WHEN the PDF is complete, THE Application SHALL provide a download button with the PDF file
7. WHEN reportlab dependencies are missing, THE PDF_Generator SHALL display a clear error message with installation instructions

### Requirement 3: Local Testing Verification

**User Story:** As a developer, I want to verify the application runs correctly on macOS, so that I can ensure all functionality works before deployment.

#### Acceptance Criteria

1. WHEN the application starts, THE Application SHALL successfully initialize all Bedrock models with fallback options
2. WHEN AWS credentials are configured, THE Application SHALL authenticate with Bedrock and verify access
3. WHEN a user uploads an architecture diagram, THE Application SHALL process and analyze the image without errors
4. WHEN the workflow progresses through all steps, THE Application SHALL maintain Session_State correctly
5. WHEN errors occur, THE Application SHALL log detailed information to the logs directory
6. WHEN the Q&A session is active, THE Application SHALL generate questions and process answers correctly
7. WHEN all dependencies are installed, THE Application SHALL start without import errors

### Requirement 4: Docker Containerization

**User Story:** As a DevOps engineer, I want the application containerized with Docker, so that it can be deployed consistently across environments.

#### Acceptance Criteria

1. WHEN the Dockerfile is built, THE Container SHALL include all Python dependencies from requirements.txt
2. WHEN the Container starts, THE Application SHALL run on port 8501 inside the container
3. WHEN AWS credentials are provided via environment variables, THE Container SHALL authenticate with AWS services
4. WHEN the Container is built, THE build process SHALL optimize layer caching to minimize build time
5. WHEN the Container runs, THE Application SHALL have write access to the generated-diagrams directory
6. WHEN the Container is deployed, THE Application SHALL log to stdout for CloudWatch integration
7. WHEN the Dockerfile is created, THE Container SHALL use a Python 3.11 base image for compatibility

### Requirement 5: AWS Fargate Deployment

**User Story:** As a DevOps engineer, I want the application deployed to AWS Fargate, so that it runs as a scalable, serverless container service.

#### Acceptance Criteria

1. WHEN the ECS task is created, THE Fargate SHALL allocate sufficient CPU and memory resources for the Application
2. WHEN the task starts, THE Fargate SHALL pull the Container image from Amazon ECR
3. WHEN the Application is running, THE ALB SHALL route HTTPS traffic to the Fargate tasks
4. WHEN traffic increases, THE Fargate SHALL auto-scale tasks based on CPU and memory utilization
5. WHEN a task fails, THE Fargate SHALL automatically restart the task and maintain availability
6. WHEN the VPC is configured, THE Fargate tasks SHALL run in private subnets with NAT gateway access
7. WHEN security groups are configured, THE Fargate tasks SHALL only accept traffic from the ALB

### Requirement 6: HTTPS and Load Balancing

**User Story:** As a user, I want to access the application via HTTPS, so that my data is encrypted in transit.

#### Acceptance Criteria

1. WHEN the ALB is created, THE ALB SHALL listen on port 443 for HTTPS traffic
2. WHEN an SSL certificate is configured, THE ALB SHALL use the certificate for TLS termination
3. WHEN HTTP requests are received on port 80, THE ALB SHALL redirect them to HTTPS
4. WHEN the ALB performs health checks, THE Application SHALL respond with HTTP 200 status
5. WHEN multiple Fargate tasks are running, THE ALB SHALL distribute traffic evenly across tasks
6. WHEN a task becomes unhealthy, THE ALB SHALL stop routing traffic to that task
7. WHEN the ALB is configured, THE security group SHALL only allow traffic on ports 80 and 443

### Requirement 7: Internal Amazon User Authentication

**User Story:** As a security administrator, I want only authorized internal Amazon users to access the application, so that sensitive migration data is protected.

#### Acceptance Criteria

1. WHEN a user accesses the application, THE Application SHALL redirect unauthenticated users to the Cognito login page
2. WHEN a user authenticates, THE Cognito SHALL verify the user is an authorized internal Amazon user
3. WHEN authentication succeeds, THE Cognito SHALL issue a session token to the user
4. WHEN a session token is provided, THE Application SHALL validate the token before allowing access
5. WHEN a session expires, THE Application SHALL redirect the user to re-authenticate
6. WHEN a user logs out, THE Application SHALL invalidate the session token
7. WHEN authentication fails, THE Application SHALL display an error message and deny access

### Requirement 8: Infrastructure as Code with AWS CDK

**User Story:** As a DevOps engineer, I want all infrastructure defined as code using AWS CDK, so that deployments are reproducible and version-controlled.

#### Acceptance Criteria

1. WHEN the CDK stack is synthesized, THE CDK SHALL generate CloudFormation templates for all resources
2. WHEN the CDK stack is deployed, THE CDK SHALL create the VPC, subnets, security groups, ALB, ECS cluster, and Fargate service
3. WHEN IAM roles are created, THE CDK SHALL grant the Fargate tasks permissions to access Bedrock and CloudWatch
4. WHEN the ECR repository is created, THE CDK SHALL configure lifecycle policies to manage image retention
5. WHEN the stack is updated, THE CDK SHALL perform rolling updates to minimize downtime
6. WHEN the stack is destroyed, THE CDK SHALL clean up all created resources
7. WHEN the CDK code is written, THE CDK SHALL use TypeScript or Python for consistency with the Application

### Requirement 9: CloudWatch Logging and Monitoring

**User Story:** As a DevOps engineer, I want comprehensive logging and monitoring, so that I can troubleshoot issues and track application performance.

#### Acceptance Criteria

1. WHEN the Application logs messages, THE Fargate SHALL send logs to CloudWatch Logs
2. WHEN errors occur, THE Application SHALL log stack traces and error details to CloudWatch
3. WHEN the ECS service is running, THE CloudWatch SHALL collect metrics for CPU, memory, and task count
4. WHEN the ALB receives requests, THE CloudWatch SHALL log access logs to an S3 bucket
5. WHEN CloudWatch alarms are configured, THE alarms SHALL trigger notifications for critical errors
6. WHEN log retention is configured, THE CloudWatch SHALL retain logs for 30 days
7. WHEN the Application starts, THE Application SHALL log the initialization status and configuration

### Requirement 10: Error Handling and Resilience

**User Story:** As a user, I want the application to handle errors gracefully, so that I can recover from failures without losing my progress.

#### Acceptance Criteria

1. WHEN a Bedrock API call fails, THE Application SHALL retry with exponential backoff
2. WHEN the MCP_Server is unavailable, THE Application SHALL allow users to skip diagram generation
3. WHEN PDF generation fails, THE Application SHALL still allow JSON export of results
4. WHEN a workflow step fails, THE Application SHALL preserve Session_State and allow retry
5. WHEN network errors occur, THE Application SHALL display user-friendly error messages
6. WHEN the Application encounters an unexpected error, THE Application SHALL log the error and display a generic error message
7. WHEN a user's session is interrupted, THE Application SHALL allow resuming from the last completed step

### Requirement 11: Cost Optimization

**User Story:** As a cost-conscious administrator, I want the deployment to be cost-effective, so that we minimize AWS spending.

#### Acceptance Criteria

1. WHEN Fargate tasks are idle, THE auto-scaling SHALL scale down to the minimum task count
2. WHEN Fargate Spot is available, THE ECS service SHALL use Spot capacity for cost savings
3. WHEN the ALB is configured, THE ALB SHALL use the Application Load Balancer type for cost efficiency
4. WHEN CloudWatch logs are configured, THE log retention SHALL be set to 30 days to avoid excessive storage costs
5. WHEN the ECR repository is configured, THE lifecycle policy SHALL delete old images to reduce storage costs
6. WHEN the VPC is configured, THE NAT gateway SHALL be shared across availability zones to reduce costs
7. WHEN the Application is not in use, THE auto-scaling SHALL scale to zero tasks if configured

### Requirement 12: Security Best Practices

**User Story:** As a security administrator, I want the deployment to follow AWS security best practices, so that the application and data are protected.

#### Acceptance Criteria

1. WHEN the VPC is created, THE Fargate tasks SHALL run in private subnets without direct internet access
2. WHEN security groups are configured, THE security groups SHALL follow the principle of least privilege
3. WHEN IAM roles are created, THE roles SHALL have minimal permissions required for operation
4. WHEN secrets are needed, THE Application SHALL retrieve them from AWS Secrets Manager
5. WHEN the Container is built, THE Container SHALL not include hardcoded credentials or secrets
6. WHEN the ALB is configured, THE ALB SHALL enforce HTTPS and disable insecure protocols
7. WHEN CloudWatch logs are created, THE logs SHALL be encrypted at rest

### Requirement 13: Deployment Automation

**User Story:** As a DevOps engineer, I want automated deployment pipelines, so that I can deploy updates quickly and reliably.

#### Acceptance Criteria

1. WHEN the CDK stack is deployed, THE deployment SHALL complete without manual intervention
2. WHEN the Container image is built, THE build process SHALL tag the image with the git commit SHA
3. WHEN the Container image is pushed to ECR, THE ECS service SHALL automatically deploy the new image
4. WHEN the deployment completes, THE deployment process SHALL verify the Application is healthy
5. WHEN the deployment fails, THE deployment process SHALL roll back to the previous version
6. WHEN environment variables change, THE deployment process SHALL update the task definition
7. WHEN the CDK code changes, THE deployment process SHALL synthesize and deploy the updated stack
