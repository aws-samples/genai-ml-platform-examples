# Implementation Plan: SageMaker Migration Advisor Deployment

## Overview

This implementation plan breaks down the deployment of the SageMaker Migration Advisor into discrete, actionable tasks. The plan follows a phased approach: first fixing critical application issues, then containerizing, and finally deploying to AWS Fargate with authentication and monitoring.

## Tasks

- [x] 1. Fix diagram generation functionality
  - [x] 1.1 Create DiagramGenerator class with workspace directory management
    - Implement `__init__` method that accepts workspace_dir parameter
    - Implement `_ensure_diagram_folder()` method to create generated-diagrams folder
    - Implement `_list_diagram_files()` method to verify saved diagrams
    - Add comprehensive logging for troubleshooting
    - _Requirements: 1.1, 1.2, 1.3, 1.7_
  
  - [x] 1.2 Update handle_diagram_step() to use DiagramGenerator class
    - Instantiate DiagramGenerator with current working directory
    - Pass workspace_dir to MCP diagram generation tools
    - Add post-generation file verification
    - Display all generated diagrams in grid layout
    - _Requirements: 1.1, 1.2, 1.4, 1.6_
  
  - [ ]* 1.3 Write property test for diagram folder creation
    - **Property 1: Diagram Folder Creation Precedes Save Operations**
    - **Validates: Requirements 1.7**
  
  - [ ]* 1.4 Write property test for diagram file verification
    - **Property 2: Diagram File Verification**
    - **Validates: Requirements 1.2, 1.3**
  
  - [x] 1.5 Implement error handling for MCP server failures
    - Add try-catch blocks around MCP server calls
    - Log detailed error information with stack traces
    - Provide user-friendly error messages
    - Add "Skip Diagram Generation" button for failures
    - _Requirements: 1.5, 10.2_
  
  - [ ]* 1.6 Write unit tests for diagram error handling
    - Test MCP server unavailable scenario
    - Test invalid architecture design input
    - Test file system permission errors
    - _Requirements: 1.5_

- [x] 2. Fix PDF report generation functionality
  - [x] 2.1 Create PDFReportGenerator class
    - Implement `__init__` method accepting workflow_state and diagram_folder
    - Implement `generate_report()` method returning PDF bytes
    - Implement `_create_styles()` method for custom PDF styling
    - Add comprehensive error handling
    - _Requirements: 2.1, 2.5_
  
  - [x] 2.2 Implement robust diagram embedding in PDF
    - Implement `_add_diagrams()` method with PIL image validation
    - Calculate proper aspect ratios for page fitting
    - Handle missing or invalid image files gracefully
    - Add explanatory notes for failed image embeds
    - Limit to 4 diagrams to avoid PDF bloat
    - _Requirements: 2.2, 2.3, 2.4_
  
  - [ ]* 2.3 Write property test for aspect ratio preservation
    - **Property 6: Image Aspect Ratio Preservation**
    - **Validates: Requirements 2.3**
  
  - [ ]* 2.4 Write property test for PDF section completeness
    - **Property 5: PDF Section Completeness**
    - **Validates: Requirements 2.1, 2.5**
  
  - [x] 2.5 Update download_results() to use PDFReportGenerator
    - Instantiate PDFReportGenerator with current state
    - Handle reportlab import errors with clear messages
    - Provide JSON export fallback if PDF fails
    - Add download buttons for both PDF and JSON
    - _Requirements: 2.6, 2.7, 10.3_
  
  - [ ]* 2.6 Write unit tests for PDF generation
    - Test PDF generation with all sections
    - Test PDF generation with missing diagrams
    - Test reportlab missing dependency error
    - Test JSON fallback when PDF fails
    - _Requirements: 2.1, 2.4, 2.7_

- [ ] 3. Implement error handling and resilience improvements
  - [ ] 3.1 Create ErrorHandler class with centralized error handling
    - Implement `handle_bedrock_error()` method
    - Implement `handle_diagram_error()` method
    - Implement `handle_pdf_error()` method
    - Implement `handle_session_error()` method
    - Categorize errors as transient, permanent, or degraded
    - _Requirements: 10.1, 10.2, 10.3, 10.5, 10.6_
  
  - [ ] 3.2 Implement retry logic with exponential backoff
    - Create `retry_with_backoff` decorator
    - Configure max_retries, initial_delay, backoff_multiplier
    - Add logging for retry attempts
    - Apply decorator to Bedrock API calls
    - _Requirements: 10.1_
  
  - [ ]* 3.3 Write property test for retry backoff
    - **Property 13: Bedrock Retry with Exponential Backoff**
    - **Validates: Requirements 10.1**
  
  - [ ]* 3.4 Write property test for session state preservation
    - **Property 9: Session State Preservation Across Steps**
    - **Validates: Requirements 3.4, 10.4**
  
  - [ ] 3.5 Add session recovery functionality
    - Implement session state persistence check on startup
    - Allow users to resume from last completed step
    - Add "Resume Session" button if interrupted session detected
    - _Requirements: 10.7_
  
  - [ ]* 3.6 Write unit tests for error handling
    - Test transient error retry logic
    - Test permanent error fail-fast behavior
    - Test degraded functionality skip options
    - Test session recovery from interruption
    - _Requirements: 10.1, 10.2, 10.3, 10.7_

- [ ] 4. Checkpoint - Verify local functionality
  - Ensure all tests pass
  - Test complete workflow end-to-end locally
  - Verify diagram generation saves files correctly
  - Verify PDF generation embeds images correctly
  - Test error handling and recovery scenarios
  - Ask the user if questions arise

- [ ] 5. Create Docker container configuration
  - [ ] 5.1 Write Dockerfile for Streamlit application
    - Use Python 3.11-slim base image
    - Install system dependencies (graphviz, libgraphviz-dev, gcc, g++)
    - Copy requirements.txt and install Python dependencies
    - Install uvx for MCP server support
    - Copy application code
    - Create generated-diagrams and logs directories
    - Set environment variables for Streamlit
    - Configure health check endpoint
    - Set CMD to run Streamlit application
    - _Requirements: 4.1, 4.2, 4.5, 4.6, 4.7_
  
  - [ ] 5.2 Create .dockerignore file
    - Exclude __pycache__, *.pyc files
    - Exclude .git, .gitignore
    - Exclude logs/, generated-diagrams/ (will be created in container)
    - Exclude test files and documentation
    - _Requirements: 4.4_
  
  - [ ] 5.3 Test Docker container locally
    - Build Docker image
    - Run container with port mapping
    - Test health check endpoint
    - Test application functionality in container
    - Verify AWS credentials can be passed via environment variables
    - _Requirements: 4.2, 4.3, 4.5, 4.6_
  
  - [ ]* 5.4 Write integration tests for Docker container
    - Test container starts successfully
    - Test health check returns 200
    - Test application accessible on port 8501
    - Test AWS credentials work in container
    - _Requirements: 4.2, 4.3_

- [ ] 6. Create AWS CDK infrastructure stack
  - [ ] 6.1 Initialize CDK project and install dependencies
    - Create infrastructure/ directory
    - Run `cdk init app --language=python`
    - Install required CDK packages (ec2, ecs, elbv2, cognito, ecr, logs, iam)
    - Configure cdk.json with stack parameters
    - _Requirements: 8.1, 8.7_
  
  - [ ] 6.2 Implement VPC and networking resources
    - Create VPC with public and private subnets across 2 AZs
    - Configure NAT gateway for private subnet internet access
    - Set up security groups for ALB and Fargate tasks
    - Configure VPC flow logs for monitoring
    - _Requirements: 5.6, 12.1, 12.2_
  
  - [ ] 6.3 Implement ECR repository
    - Create ECR repository for Docker images
    - Configure lifecycle policy to keep only 10 most recent images
    - Set removal policy for stack cleanup
    - _Requirements: 8.4, 11.5_
  
  - [ ] 6.4 Implement ECS cluster and task definition
    - Create ECS cluster with container insights enabled
    - Create Fargate task definition with 1 vCPU, 2GB memory
    - Add container definition with ECR image reference
    - Configure CloudWatch Logs for container logging
    - Add IAM role with Bedrock permissions
    - _Requirements: 5.1, 5.2, 8.2, 8.3, 9.1_
  
  - [ ] 6.5 Implement Application Load Balancer
    - Create ALB in public subnets
    - Configure target group with health checks
    - Set up HTTPS listener on port 443
    - Configure HTTP to HTTPS redirect on port 80
    - _Requirements: 5.3, 6.1, 6.2, 6.3, 6.7_
  
  - [ ] 6.6 Implement Cognito user pool and authentication
    - Create Cognito user pool with email sign-in
    - Configure password policy and MFA options
    - Create user pool client with OAuth settings
    - Create user pool domain
    - Configure ALB listener with Cognito authentication action
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7_
  
  - [ ] 6.7 Implement ECS Fargate service
    - Create ApplicationLoadBalancedFargateService
    - Configure desired count, min/max healthy percent
    - Set tasks to run in private subnets
    - Configure health check grace period
    - _Requirements: 5.1, 5.2, 5.5, 5.7_
  
  - [ ] 6.8 Implement auto-scaling policies
    - Configure auto-scaling with min 1, max 5 tasks
    - Add CPU-based scaling policy (target 70%)
    - Add memory-based scaling policy (target 80%)
    - Configure scale-in and scale-out cooldown periods
    - _Requirements: 5.4, 11.1_
  
  - [ ]* 6.9 Write unit tests for CDK stack
    - Test VPC creation with correct subnet configuration
    - Test IAM role has Bedrock permissions
    - Test ECR lifecycle policy configuration
    - Test ALB listener has Cognito authentication
    - _Requirements: 8.1, 8.3, 8.4_

- [ ] 7. Implement CloudWatch monitoring and alerting
  - [ ] 7.1 Configure CloudWatch Logs
    - Set log retention to 30 days for cost optimization
    - Enable log encryption at rest
    - Configure log groups for ECS tasks
    - _Requirements: 9.1, 9.6, 12.7_
  
  - [ ] 7.2 Configure CloudWatch Metrics
    - Enable ECS service metrics (CPU, memory, task count)
    - Enable ALB metrics (request count, response time, errors)
    - Create custom metrics dashboard
    - _Requirements: 9.3, 9.4_
  
  - [ ] 7.3 Create CloudWatch Alarms
    - Create alarm for high CPU utilization (> 80% for 5 min)
    - Create alarm for high memory utilization (> 85% for 5 min)
    - Create alarm for high error rate (> 5% 5xx errors)
    - Create alarm for unhealthy targets (> 0 for 2 min)
    - Configure SNS topic for alarm notifications
    - _Requirements: 9.5_
  
  - [ ] 7.4 Add application startup logging
    - Log initialization status on application start
    - Log Bedrock model selection and configuration
    - Log AWS region and credentials status
    - _Requirements: 9.7_

- [ ] 8. Create deployment automation
  - [ ] 8.1 Write build and push script for Docker images
    - Create build.sh script to build Docker image
    - Tag image with git commit SHA
    - Authenticate with ECR
    - Push image to ECR repository
    - _Requirements: 13.2_
  
  - [ ] 8.2 Write CDK deployment script
    - Create deploy.sh script to synthesize and deploy CDK stack
    - Add environment variable configuration
    - Add deployment verification checks
    - _Requirements: 13.1_
  
  - [ ] 8.3 Create GitHub Actions workflow
    - Configure workflow for push to main branch
    - Add job for running unit tests
    - Add job for running property tests
    - Add job for building Docker image
    - Add job for deploying CDK stack
    - Configure AWS credentials from GitHub secrets
    - _Requirements: 13.1, 13.3_
  
  - [ ]* 8.4 Write integration tests for deployment
    - Test CDK stack synthesizes without errors
    - Test Docker image builds successfully
    - Test image can be pushed to ECR
    - _Requirements: 8.1, 13.2_

- [ ] 9. Create operational documentation
  - [ ] 9.1 Write deployment README
    - Document prerequisites (AWS account, credentials, CDK CLI)
    - Document deployment steps
    - Document configuration options
    - Document troubleshooting common issues
    - _Requirements: 8.1, 8.2_
  
  - [ ] 9.2 Write operational runbook
    - Document how to deploy new versions
    - Document how to scale the service
    - Document how to view logs
    - Document how to rollback deployments
    - Document common troubleshooting scenarios
    - _Requirements: 5.5, 8.5_
  
  - [ ] 9.3 Create architecture diagrams
    - Create high-level architecture diagram
    - Create network architecture diagram
    - Create deployment flow diagram
    - _Requirements: 8.2_

- [ ] 10. Checkpoint - Verify infrastructure deployment
  - Ensure CDK stack synthesizes without errors
  - Deploy infrastructure to AWS test environment
  - Verify VPC, subnets, and security groups created correctly
  - Verify ECS cluster and service running
  - Verify ALB accessible via HTTPS
  - Verify Cognito authentication working
  - Ask the user if questions arise

- [ ] 11. Deploy application to production
  - [ ] 11.1 Build and push production Docker image
    - Build Docker image with production tag
    - Run security scan on image
    - Push to ECR production repository
    - _Requirements: 13.2_
  
  - [ ] 11.2 Deploy CDK stack to production
    - Synthesize CDK stack for production environment
    - Review CloudFormation changeset
    - Deploy stack with approval
    - Verify deployment success
    - _Requirements: 8.2, 13.1_
  
  - [ ] 11.3 Configure Cognito users
    - Create initial admin user in Cognito user pool
    - Test authentication flow
    - Document user management procedures
    - _Requirements: 7.1, 7.2_
  
  - [ ] 11.4 Verify production deployment
    - Test application accessible via HTTPS
    - Test authentication flow end-to-end
    - Test complete migration workflow
    - Test diagram generation in production
    - Test PDF generation in production
    - Verify CloudWatch logs and metrics
    - _Requirements: 5.3, 6.1, 6.4, 9.1, 9.3_
  
  - [ ]* 11.5 Run end-to-end tests against production
    - Test complete workflow from input to roadmap
    - Test error recovery scenarios
    - Test session persistence
    - Test auto-scaling behavior
    - _Requirements: 3.4, 5.4, 10.4, 10.7_

- [ ] 12. Final checkpoint - Production verification
  - Ensure all production tests pass
  - Verify monitoring and alerting working
  - Verify auto-scaling configured correctly
  - Verify cost optimization settings applied
  - Document any issues or improvements needed
  - Ask the user if questions arise

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties
- Unit tests validate specific examples and edge cases
- The implementation follows a phased approach: fix → containerize → deploy
- Infrastructure tasks use AWS CDK for reproducible deployments
- Monitoring and operational tasks ensure production readiness
