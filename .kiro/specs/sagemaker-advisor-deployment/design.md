# Design Document: SageMaker Migration Advisor Deployment

## Overview

This design document outlines the technical architecture and implementation approach for fixing, testing, and deploying the SageMaker Migration Advisor Streamlit application to AWS Fargate with internal Amazon user authentication. The solution addresses current issues with diagram generation and PDF report creation, while providing a production-ready, scalable, and secure deployment on AWS infrastructure.

### Key Design Goals

1. **Fix Critical Issues**: Resolve diagram generation and PDF report problems
2. **Production-Ready**: Deploy a secure, scalable, and monitored application
3. **Cost-Effective**: Optimize for cost using Fargate Spot and auto-scaling
4. **Secure**: Implement authentication and follow AWS security best practices
5. **Maintainable**: Use infrastructure as code for reproducible deployments

## Architecture

### High-Level Architecture

The solution consists of three main layers:

1. **Application Layer**: Streamlit application running in Docker containers
2. **Infrastructure Layer**: AWS Fargate, ECS, ALB, VPC, and networking
3. **Security Layer**: AWS Cognito for authentication, IAM roles, security groups

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         Internet Users                           │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS (443)
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Application Load Balancer                     │
│  • SSL/TLS Termination                                          │
│  • Health Checks                                                │
│  • Traffic Distribution                                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AWS Cognito                                 │
│  • User Authentication                                          │
│  • Session Management                                           │
│  • Token Validation                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ECS Fargate Service                          │
│  ┌──────────────────┐  ┌──────────────────┐                   │
│  │  Fargate Task 1  │  │  Fargate Task 2  │                   │
│  │  ┌────────────┐  │  │  ┌────────────┐  │                   │
│  │  │ Streamlit  │  │  │  │ Streamlit  │  │                   │
│  │  │    App     │  │  │  │    App     │  │                   │
│  │  └────────────┘  │  │  └────────────┘  │                   │
│  └──────────────────┘  └──────────────────┘                   │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      AWS Services                                │
│  • Bedrock (Claude AI)                                          │
│  • CloudWatch Logs                                              │
│  • CloudWatch Metrics                                           │
│  • Secrets Manager                                              │
└─────────────────────────────────────────────────────────────────┘
```

### Network Architecture

```
VPC (10.0.0.0/16)
├── Public Subnets (10.0.1.0/24, 10.0.2.0/24)
│   ├── Application Load Balancer
│   └── NAT Gateway
└── Private Subnets (10.0.10.0/24, 10.0.11.0/24)
    └── ECS Fargate Tasks
```

## Components and Interfaces

### 1. Diagram Generation Component

**Purpose**: Generate and save architecture diagrams using AWS Diagram MCP Server

**Current Issues**:
- Diagrams not being saved to the `generated-diagrams/` folder
- MCP server integration not properly configured
- Workspace directory not passed to diagram generation tool

**Design Solution**:

```python
class DiagramGenerator:
    """Handles diagram generation using MCP server"""
    
    def __init__(self, workspace_dir: str):
        self.workspace_dir = workspace_dir
        self.diagram_folder = os.path.join(workspace_dir, 'generated-diagrams')
        self._ensure_diagram_folder()
    
    def _ensure_diagram_folder(self):
        """Create diagram folder if it doesn't exist"""
        os.makedirs(self.diagram_folder, exist_ok=True)
        logger.info(f"Diagram folder ready: {os.path.abspath(self.diagram_folder)}")
    
    def generate_diagram(self, architecture_design: str) -> Dict[str, Any]:
        """
        Generate architecture diagram from design
        
        Args:
            architecture_design: SageMaker architecture design text
            
        Returns:
            Dict with status, diagram_paths, and any errors
        """
        try:
            # Setup MCP client with proper configuration
            mcp_client = MCPClient(lambda: stdio_client(
                StdioServerParameters(
                    command="uvx",
                    args=["awslabs.aws-diagram-mcp-server"]
                )
            ))
            
            with mcp_client:
                tools = mcp_client.list_tools_sync() + [image_reader, use_llm, load_tool]
                
                diagram_agent = Agent(
                    model=self.bedrock_model,
                    tools=tools,
                    system_prompt=DIAGRAM_GENERATION_SYSTEM_PROMPT,
                    load_tools_from_directory=False
                )
                
                # CRITICAL: Pass workspace_dir to diagram generation
                prompt = f"""
{architecture_design}

{DIAGRAM_GENERATION_USER_PROMPT}

IMPORTANT: Save all diagrams to the workspace directory: {self.workspace_dir}
Use the workspace_dir parameter when calling diagram generation tools.
"""
                
                response = diagram_agent(prompt)
                
                # Verify diagrams were created
                diagram_files = self._list_diagram_files()
                
                return {
                    'status': 'success' if diagram_files else 'no_files',
                    'diagram_paths': diagram_files,
                    'response': str(response),
                    'folder': self.diagram_folder
                }
                
        except Exception as e:
            logger.error(f"Diagram generation failed: {e}", exc_info=True)
            return {
                'status': 'error',
                'error': str(e),
                'diagram_paths': [],
                'folder': self.diagram_folder
            }
    
    def _list_diagram_files(self) -> List[str]:
        """List all diagram files in the diagram folder"""
        if not os.path.exists(self.diagram_folder):
            return []
        
        files = []
        for f in os.listdir(self.diagram_folder):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg')):
                full_path = os.path.join(self.diagram_folder, f)
                if os.path.getsize(full_path) > 0:  # Only include non-empty files
                    files.append(full_path)
        
        return files
```

**Key Improvements**:
1. Explicit workspace directory management
2. Folder creation verification before generation
3. Post-generation file verification
4. Detailed logging for troubleshooting
5. Graceful error handling with fallback options

### 2. PDF Report Generator Component

**Purpose**: Generate comprehensive PDF reports with all analysis sections and embedded diagrams

**Current Issues**:
- Images not being embedded correctly
- reportlab configuration issues
- Missing error handling for image loading

**Design Solution**:

```python
class PDFReportGenerator:
    """Generates comprehensive PDF migration reports"""
    
    def __init__(self, workflow_state: Dict[str, Any], diagram_folder: str):
        self.workflow_state = workflow_state
        self.diagram_folder = diagram_folder
        self.model_name = "Claude AI"
    
    def generate_report(self) -> Optional[bytes]:
        """
        Generate complete PDF report
        
        Returns:
            PDF bytes if successful, None if failed
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import (
                SimpleDocTemplate, Paragraph, Spacer, PageBreak,
                Table, TableStyle, Image as RLImage
            )
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
            from io import BytesIO
            from PIL import Image
            
            buffer = BytesIO()
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=18
            )
            
            styles = self._create_styles(getSampleStyleSheet())
            story = []
            
            # Build report sections
            self._add_title_page(story, styles)
            self._add_table_of_contents(story, styles)
            self._add_executive_summary(story, styles)
            self._add_architecture_analysis(story, styles)
            self._add_qa_section(story, styles)
            self._add_sagemaker_design(story, styles)
            self._add_diagrams(story, styles)  # Improved diagram embedding
            self._add_tco_analysis(story, styles)
            self._add_migration_roadmap(story, styles)
            self._add_recommendations(story, styles)
            
            doc.build(story)
            buffer.seek(0)
            return buffer.getvalue()
            
        except ImportError as e:
            logger.error(f"Missing reportlab dependency: {e}")
            return None
        except Exception as e:
            logger.error(f"PDF generation failed: {e}", exc_info=True)
            return None
    
    def _add_diagrams(self, story: List, styles: Dict):
        """Add architecture diagrams with robust error handling"""
        from reportlab.platypus import Paragraph, Spacer, Image as RLImage
        from reportlab.lib.units import inch
        from PIL import Image
        
        story.append(Paragraph("Architecture Diagrams", styles['heading']))
        
        if not os.path.exists(self.diagram_folder):
            story.append(Paragraph(
                "No diagrams folder found. Diagrams may not have been generated.",
                styles['body']
            ))
            return
        
        diagram_files = [
            f for f in os.listdir(self.diagram_folder)
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif'))
        ]
        
        if not diagram_files:
            story.append(Paragraph(
                "No diagram files found in the diagrams folder.",
                styles['body']
            ))
            return
        
        for idx, diagram_file in enumerate(diagram_files[:4], 1):  # Limit to 4 diagrams
            try:
                img_path = os.path.join(self.diagram_folder, diagram_file)
                
                # Verify file exists and has content
                if not os.path.exists(img_path) or os.path.getsize(img_path) == 0:
                    logger.warning(f"Skipping empty or missing file: {diagram_file}")
                    continue
                
                # Open with PIL to get dimensions and verify it's a valid image
                pil_img = Image.open(img_path)
                img_width, img_height = pil_img.size
                
                # Calculate dimensions to fit on page (max 6 inches wide)
                max_width = 6 * inch
                max_height = 4 * inch
                
                aspect_ratio = img_width / img_height
                
                if img_width > img_height:
                    display_width = min(max_width, img_width)
                    display_height = display_width / aspect_ratio
                else:
                    display_height = min(max_height, img_height)
                    display_width = display_height * aspect_ratio
                
                # Add diagram title
                diagram_title = diagram_file.replace('_', ' ').replace('.png', '').title()
                story.append(Paragraph(
                    f"<b>Diagram {idx}: {diagram_title}</b>",
                    styles['subheading']
                ))
                
                # Add the image
                rl_img = RLImage(img_path, width=display_width, height=display_height)
                story.append(rl_img)
                story.append(Spacer(1, 0.2 * inch))
                
                # Add caption
                story.append(Paragraph(
                    f"<i>Figure {idx}: {diagram_title}</i>",
                    styles['body']
                ))
                story.append(Spacer(1, 0.3 * inch))
                
            except Exception as e:
                logger.error(f"Failed to embed diagram {diagram_file}: {e}")
                story.append(Paragraph(
                    f"<i>Note: Could not embed {diagram_file} - {str(e)}</i>",
                    styles['body']
                ))
                story.append(Spacer(1, 0.1 * inch))
        
        if len(diagram_files) > 4:
            story.append(Paragraph(
                f"<i>Note: {len(diagram_files) - 4} additional diagrams available in the generated-diagrams folder.</i>",
                styles['body']
            ))
    
    def _create_styles(self, base_styles) -> Dict:
        """Create custom PDF styles"""
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
        from reportlab.lib.styles import ParagraphStyle
        
        return {
            'title': ParagraphStyle(
                'CustomTitle',
                parent=base_styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor=colors.HexColor('#2E86AB')
            ),
            'heading': ParagraphStyle(
                'CustomHeading',
                parent=base_styles['Heading2'],
                fontSize=16,
                spaceAfter=12,
                spaceBefore=20,
                textColor=colors.HexColor('#FF6B35')
            ),
            'subheading': ParagraphStyle(
                'CustomSubHeading',
                parent=base_styles['Heading3'],
                fontSize=14,
                spaceAfter=8,
                spaceBefore=12,
                textColor=colors.HexColor('#2E86AB')
            ),
            'body': ParagraphStyle(
                'CustomBody',
                parent=base_styles['Normal'],
                fontSize=11,
                spaceAfter=8,
                alignment=TA_JUSTIFY
            )
        }
```

**Key Improvements**:
1. Robust image validation before embedding
2. Proper aspect ratio calculation
3. PIL integration for image verification
4. Graceful error handling per diagram
5. Clear error messages in PDF when images fail

### 3. Docker Container Configuration

**Purpose**: Package the Streamlit application with all dependencies

**Dockerfile Design**:

```dockerfile
# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for reportlab, Pillow, and graphviz (for diagrams)
RUN apt-get update && apt-get install -y \
    graphviz \
    libgraphviz-dev \
    pkg-config \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Install uvx for MCP server
RUN pip install --no-cache-dir uv

# Copy application code
COPY . .

# Create directories for generated content
RUN mkdir -p generated-diagrams logs

# Set environment variables
ENV STREAMLIT_SERVER_PORT=8501
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Run the application
CMD ["streamlit", "run", "sagemaker_migration_advisor.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

**Key Features**:
1. Slim base image for smaller container size
2. System dependencies for diagram generation
3. Layer caching optimization
4. Health check endpoint
5. Proper directory creation
6. Environment variable configuration

### 4. AWS Cognito Authentication Integration

**Purpose**: Secure the application with internal Amazon user authentication

**Authentication Flow**:

```
1. User accesses application URL
2. ALB checks for valid session cookie
3. If no valid session, redirect to Cognito login
4. User authenticates with Cognito
5. Cognito returns JWT token
6. ALB validates token and creates session cookie
7. User accesses application with valid session
```

**Implementation Approach**:

We'll use ALB's built-in Cognito integration rather than application-level authentication for simplicity and security:

```python
# CDK Configuration for ALB Cognito Integration
from aws_cdk import (
    aws_elasticloadbalancingv2 as elbv2,
    aws_cognito as cognito,
    aws_certificatemanager as acm
)

# Create Cognito User Pool
user_pool = cognito.UserPool(
    self, "SageMakerAdvisorUserPool",
    user_pool_name="sagemaker-advisor-users",
    self_sign_up_enabled=False,  # Admin-managed users only
    sign_in_aliases=cognito.SignInAliases(email=True),
    password_policy=cognito.PasswordPolicy(
        min_length=12,
        require_lowercase=True,
        require_uppercase=True,
        require_digits=True,
        require_symbols=True
    ),
    mfa=cognito.Mfa.OPTIONAL,
    account_recovery=cognito.AccountRecovery.EMAIL_ONLY
)

# Create User Pool Client
user_pool_client = user_pool.add_client(
    "SageMakerAdvisorClient",
    generate_secret=True,
    o_auth=cognito.OAuthSettings(
        flows=cognito.OAuthFlows(authorization_code_grant=True),
        scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL, cognito.OAuthScope.PROFILE],
        callback_urls=[f"https://{domain_name}/oauth2/idpresponse"]
    )
)

# Create User Pool Domain
user_pool_domain = user_pool.add_domain(
    "SageMakerAdvisorDomain",
    cognito_domain=cognito.CognitoDomainOptions(
        domain_prefix="sagemaker-advisor"
    )
)

# Configure ALB Listener with Cognito Authentication
listener.add_action(
    "AuthenticateAction",
    priority=1,
    conditions=[elbv2.ListenerCondition.path_patterns(["/*"])],
    action=elbv2.ListenerAction.authenticate_cognito(
        user_pool=user_pool,
        user_pool_client=user_pool_client,
        user_pool_domain=user_pool_domain,
        next=elbv2.ListenerAction.forward([target_group])
    )
)
```

**Key Features**:
1. ALB-level authentication (no application code changes needed)
2. Secure JWT token validation
3. Session management handled by ALB
4. Admin-managed user pool for internal users
5. MFA support for enhanced security

### 5. AWS CDK Infrastructure Stack

**Purpose**: Define all infrastructure as code for reproducible deployments

**Stack Structure**:

```python
from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_elasticloadbalancingv2 as elbv2,
    aws_ecr as ecr,
    aws_logs as logs,
    aws_iam as iam,
    aws_cognito as cognito,
    aws_certificatemanager as acm,
    Duration,
    RemovalPolicy
)

class SageMakerAdvisorStack(Stack):
    def __init__(self, scope, construct_id, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # VPC with public and private subnets
        vpc = ec2.Vpc(
            self, "SageMakerAdvisorVPC",
            max_azs=2,
            nat_gateways=1,  # Cost optimization: single NAT gateway
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=24
                )
            ]
        )
        
        # ECS Cluster
        cluster = ecs.Cluster(
            self, "SageMakerAdvisorCluster",
            vpc=vpc,
            container_insights=True
        )
        
        # ECR Repository
        repository = ecr.Repository(
            self, "SageMakerAdvisorRepo",
            repository_name="sagemaker-advisor",
            removal_policy=RemovalPolicy.DESTROY,
            lifecycle_rules=[
                ecr.LifecycleRule(
                    max_image_count=10,
                    description="Keep only 10 most recent images"
                )
            ]
        )
        
        # Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self, "SageMakerAdvisorTask",
            memory_limit_mib=2048,
            cpu=1024
        )
        
        # Grant Bedrock permissions
        task_definition.add_to_task_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:InvokeModel",
                    "bedrock:InvokeModelWithResponseStream"
                ],
                resources=["*"]
            )
        )
        
        # Container Definition
        container = task_definition.add_container(
            "SageMakerAdvisorContainer",
            image=ecs.ContainerImage.from_ecr_repository(repository),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="sagemaker-advisor",
                log_retention=logs.RetentionDays.ONE_MONTH
            ),
            environment={
                "AWS_DEFAULT_REGION": self.region,
                "STREAMLIT_SERVER_PORT": "8501"
            }
        )
        
        container.add_port_mappings(
            ecs.PortMapping(container_port=8501, protocol=ecs.Protocol.TCP)
        )
        
        # Cognito User Pool (as shown in section 4)
        user_pool = self._create_user_pool()
        user_pool_client = self._create_user_pool_client(user_pool)
        user_pool_domain = self._create_user_pool_domain(user_pool)
        
        # Application Load Balanced Fargate Service
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self, "SageMakerAdvisorService",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=1,
            min_healthy_percent=50,
            max_healthy_percent=200,
            public_load_balancer=True,
            assign_public_ip=False,  # Tasks in private subnets
            health_check_grace_period=Duration.seconds(60)
        )
        
        # Configure health check
        fargate_service.target_group.configure_health_check(
            path="/_stcore/health",
            interval=Duration.seconds(30),
            timeout=Duration.seconds(10),
            healthy_threshold_count=2,
            unhealthy_threshold_count=3
        )
        
        # Auto Scaling
        scaling = fargate_service.service.auto_scale_task_count(
            min_capacity=1,
            max_capacity=5
        )
        
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=70,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60)
        )
        
        scaling.scale_on_memory_utilization(
            "MemoryScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60)
        )
        
        # Add Cognito authentication to ALB
        self._configure_alb_authentication(
            fargate_service.listener,
            fargate_service.target_group,
            user_pool,
            user_pool_client,
            user_pool_domain
        )
```

**Key Features**:
1. Multi-AZ deployment for high availability
2. Private subnets for Fargate tasks
3. Auto-scaling based on CPU and memory
4. CloudWatch Logs integration
5. ECR lifecycle policies for cost optimization
6. Cognito authentication at ALB level
7. Health check configuration

## Data Models

### Workflow State Model

```python
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class AgentInteraction:
    """Represents a single agent interaction"""
    timestamp: str
    agent: str
    step: str
    input: str
    output: str

@dataclass
class QAExchange:
    """Represents a Q&A exchange"""
    question: str
    answer: str
    synthesis: Optional[str] = None

@dataclass
class QASession:
    """Represents a complete Q&A session"""
    conversation: List[QAExchange] = field(default_factory=list)
    current_question: Optional[str] = None
    questions_asked: int = 0
    context_built: str = ""
    session_active: bool = False

@dataclass
class WorkflowState:
    """Complete workflow state"""
    current_step: str = 'input'
    completed_steps: List[str] = field(default_factory=list)
    agent_responses: Dict[str, AgentInteraction] = field(default_factory=dict)
    user_inputs: Dict[str, Any] = field(default_factory=dict)
    errors: Dict[str, str] = field(default_factory=dict)
    conversation_history: List[AgentInteraction] = field(default_factory=list)
    qa_session: Optional[QASession] = None
```

### Diagram Generation Result Model

```python
@dataclass
class DiagramGenerationResult:
    """Result of diagram generation"""
    status: str  # 'success', 'no_files', 'error'
    diagram_paths: List[str] = field(default_factory=list)
    response: str = ""
    error: Optional[str] = None
    folder: str = ""
```

### PDF Generation Configuration Model

```python
@dataclass
class PDFConfig:
    """Configuration for PDF generation"""
    include_diagrams: bool = True
    max_diagrams: int = 4
    page_size: str = "A4"
    margin_inches: float = 1.0
    max_image_width_inches: float = 6.0
    max_image_height_inches: float = 4.0
```

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*


### Property 1: Diagram Folder Creation Precedes Save Operations

*For any* diagram generation request, the generated-diagrams folder must exist before any diagram save operations are attempted.

**Validates: Requirements 1.7**

### Property 2: Diagram File Verification

*For any* saved diagram file, the file must exist on the filesystem and have a non-zero size.

**Validates: Requirements 1.2, 1.3**

### Property 3: MCP Server Invocation with Architecture Design

*For any* architecture design text, when diagram generation is triggered, the MCP server must be invoked with that design as input.

**Validates: Requirements 1.1**

### Property 4: Error Logging Completeness

*For any* error that occurs during diagram generation or PDF generation, both detailed logs and user-friendly error messages must be generated.

**Validates: Requirements 1.5, 2.4, 10.5, 10.6**

### Property 5: PDF Section Completeness

*For any* set of completed workflow sections, the generated PDF must include all those sections in the table of contents and document body.

**Validates: Requirements 2.1, 2.5**

### Property 6: Image Aspect Ratio Preservation

*For any* image with dimensions (width, height), when resized to fit within page margins, the resized dimensions must maintain the original aspect ratio within a tolerance of 1%.

**Validates: Requirements 2.3**

### Property 7: PDF Generation Resilience

*For any* invalid or missing diagram file, PDF generation must continue and include an explanatory note rather than failing completely.

**Validates: Requirements 2.4**

### Property 8: Bedrock Model Initialization with Fallbacks

*For any* Bedrock model initialization attempt, if the primary model fails, the system must attempt fallback models in the configured order until one succeeds or all fail.

**Validates: Requirements 3.1**

### Property 9: Session State Preservation Across Steps

*For any* workflow step transition, all data from previous steps must be preserved in the session state.

**Validates: Requirements 3.4, 10.4**

### Property 10: Image Processing Success

*For any* valid image file (PNG, JPG, JPEG, GIF) uploaded by a user, the application must successfully process and analyze the image without throwing exceptions.

**Validates: Requirements 3.3**

### Property 11: Error Logging with Stack Traces

*For any* exception that occurs in the application, a log entry must be created that includes the error message, stack trace, and timestamp.

**Validates: Requirements 3.5, 9.2**

### Property 12: Q&A Session State Management

*For any* Q&A session, when a question is generated and an answer is provided, the conversation history must include both the question and answer with synthesis.

**Validates: Requirements 3.6**

### Property 13: Bedrock Retry with Exponential Backoff

*For any* failed Bedrock API call, the system must retry with exponentially increasing delays (e.g., 1s, 2s, 4s, 8s) up to a maximum number of retries.

**Validates: Requirements 10.1**

### Property 14: Workflow Degradation Gracefully

*For any* optional workflow step (diagram generation, PDF generation), if that step fails, the workflow must allow the user to skip it and continue to the next step.

**Validates: Requirements 10.2, 10.3**

### Property 15: Session Recovery from Interruption

*For any* interrupted user session, when the user returns, the application must restore the workflow state to the last completed step.

**Validates: Requirements 10.7**

## Error Handling

### Error Categories

1. **Transient Errors**: Network failures, service unavailability, rate limiting
   - **Strategy**: Retry with exponential backoff
   - **Max Retries**: 3 attempts
   - **User Feedback**: "Retrying... (attempt X of 3)"

2. **Permanent Errors**: Invalid input, missing dependencies, configuration errors
   - **Strategy**: Fail fast with clear error message
   - **User Feedback**: Specific error message with remediation steps
   - **Logging**: Full stack trace to CloudWatch

3. **Degraded Functionality**: Optional features fail (diagrams, PDF)
   - **Strategy**: Allow skip and continue workflow
   - **User Feedback**: Warning message with skip option
   - **Logging**: Warning level log entry

### Error Handling Patterns

```python
class ErrorHandler:
    """Centralized error handling for the application"""
    
    @staticmethod
    def handle_bedrock_error(error: Exception, context: str) -> Dict[str, Any]:
        """Handle Bedrock API errors with retry logic"""
        if "serviceUnavailableException" in str(error):
            return {
                'type': 'transient',
                'message': 'AWS Bedrock is temporarily unavailable. Retrying...',
                'retry': True,
                'user_message': 'The AI service is temporarily busy. Please wait...'
            }
        elif "throttlingException" in str(error):
            return {
                'type': 'transient',
                'message': 'Rate limit exceeded. Backing off...',
                'retry': True,
                'backoff_multiplier': 2.0,
                'user_message': 'Too many requests. Slowing down...'
            }
        else:
            return {
                'type': 'permanent',
                'message': f'Bedrock error: {str(error)}',
                'retry': False,
                'user_message': 'An error occurred with the AI service. Please check your AWS credentials.'
            }
    
    @staticmethod
    def handle_diagram_error(error: Exception) -> Dict[str, Any]:
        """Handle diagram generation errors"""
        logger.error(f"Diagram generation failed: {error}", exc_info=True)
        
        return {
            'type': 'degraded',
            'message': f'Diagram generation failed: {str(error)}',
            'allow_skip': True,
            'user_message': 'Diagram generation encountered an issue. You can skip this step or retry later.',
            'skip_button_text': 'Skip Diagrams',
            'retry_button_text': 'Retry Diagram Generation'
        }
    
    @staticmethod
    def handle_pdf_error(error: Exception) -> Dict[str, Any]:
        """Handle PDF generation errors"""
        logger.error(f"PDF generation failed: {error}", exc_info=True)
        
        if "reportlab" in str(error).lower():
            return {
                'type': 'permanent',
                'message': 'reportlab library not installed',
                'user_message': 'PDF generation requires reportlab. Install with: pip install reportlab',
                'fallback': 'json_export'
            }
        else:
            return {
                'type': 'degraded',
                'message': f'PDF generation failed: {str(error)}',
                'user_message': 'PDF generation failed. You can still download the JSON data.',
                'fallback': 'json_export'
            }
    
    @staticmethod
    def handle_session_error(error: Exception) -> Dict[str, Any]:
        """Handle session state errors"""
        logger.error(f"Session error: {error}", exc_info=True)
        
        return {
            'type': 'permanent',
            'message': f'Session error: {str(error)}',
            'user_message': 'Your session encountered an error. Please refresh the page to start over.',
            'recovery_action': 'reset_session'
        }
```

### Retry Logic Implementation

```python
import time
from typing import Callable, Any, Optional
from functools import wraps

def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_multiplier: float = 2.0,
    max_delay: float = 60.0
):
    """Decorator for retry logic with exponential backoff"""
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            delay = initial_delay
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    error_info = ErrorHandler.handle_bedrock_error(e, func.__name__)
                    
                    if not error_info.get('retry', False):
                        # Permanent error, don't retry
                        raise
                    
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                        delay = min(delay * backoff_multiplier, max_delay)
                    else:
                        logger.error(f"All {max_retries} attempts failed")
            
            # All retries exhausted
            raise last_exception
        
        return wrapper
    return decorator

# Usage example
@retry_with_backoff(max_retries=3, initial_delay=1.0)
def call_bedrock_api(prompt: str) -> str:
    """Call Bedrock API with automatic retry"""
    response = bedrock_model(prompt)
    return str(response)
```

## Testing Strategy

### Dual Testing Approach

The testing strategy employs both unit tests and property-based tests to ensure comprehensive coverage:

- **Unit Tests**: Verify specific examples, edge cases, and error conditions
- **Property Tests**: Verify universal properties across all inputs

Both approaches are complementary and necessary for production readiness.

### Unit Testing Focus

Unit tests should focus on:
1. **Specific Examples**: Concrete test cases that demonstrate correct behavior
2. **Integration Points**: Interactions between components (Streamlit ↔ Bedrock, MCP server integration)
3. **Edge Cases**: Empty inputs, missing files, invalid configurations
4. **Error Conditions**: Network failures, service unavailability, invalid credentials

**Avoid writing too many unit tests** - property-based tests handle covering lots of inputs. Unit tests should be targeted and specific.

### Property-Based Testing Configuration

**Library Selection**: Use `hypothesis` for Python property-based testing

**Configuration**:
- Minimum 100 iterations per property test (due to randomization)
- Each property test must reference its design document property
- Tag format: `# Feature: sagemaker-advisor-deployment, Property {number}: {property_text}`

**Example Property Test**:

```python
from hypothesis import given, strategies as st
import pytest

# Feature: sagemaker-advisor-deployment, Property 6: Image Aspect Ratio Preservation
@given(
    width=st.integers(min_value=100, max_value=5000),
    height=st.integers(min_value=100, max_value=5000),
    max_width=st.integers(min_value=400, max_value=800),
    max_height=st.integers(min_value=300, max_value=600)
)
def test_image_resize_preserves_aspect_ratio(width, height, max_width, max_height):
    """
    Property 6: For any image dimensions, resizing to fit within page margins
    must maintain the original aspect ratio within 1% tolerance.
    """
    original_aspect_ratio = width / height
    
    # Calculate resized dimensions
    resized_width, resized_height = resize_image_for_pdf(
        width, height, max_width, max_height
    )
    
    resized_aspect_ratio = resized_width / resized_height
    
    # Verify aspect ratio is preserved within 1% tolerance
    aspect_ratio_diff = abs(original_aspect_ratio - resized_aspect_ratio)
    tolerance = original_aspect_ratio * 0.01
    
    assert aspect_ratio_diff <= tolerance, \
        f"Aspect ratio not preserved: {original_aspect_ratio} -> {resized_aspect_ratio}"
    
    # Verify dimensions fit within constraints
    assert resized_width <= max_width, "Width exceeds maximum"
    assert resized_height <= max_height, "Height exceeds maximum"
```

### Test Organization

```
tests/
├── unit/
│   ├── test_diagram_generator.py
│   ├── test_pdf_generator.py
│   ├── test_error_handling.py
│   ├── test_session_state.py
│   └── test_authentication.py
├── property/
│   ├── test_diagram_properties.py
│   ├── test_pdf_properties.py
│   ├── test_state_properties.py
│   └── test_error_properties.py
├── integration/
│   ├── test_bedrock_integration.py
│   ├── test_mcp_integration.py
│   └── test_workflow_integration.py
└── e2e/
    ├── test_complete_workflow.py
    └── test_deployment.py
```

### Testing Requirements by Property

| Property | Test Type | Test Focus |
|----------|-----------|------------|
| Property 1 | Unit | Folder creation before save |
| Property 2 | Property | File existence and size validation |
| Property 3 | Unit | MCP server invocation |
| Property 4 | Property | Error logging completeness |
| Property 5 | Property | PDF section inclusion |
| Property 6 | Property | Aspect ratio preservation |
| Property 7 | Unit | PDF resilience to bad images |
| Property 8 | Unit | Model fallback sequence |
| Property 9 | Property | State preservation |
| Property 10 | Property | Image processing success |
| Property 11 | Property | Error logging format |
| Property 12 | Property | Q&A state management |
| Property 13 | Unit | Retry backoff timing |
| Property 14 | Unit | Workflow skip functionality |
| Property 15 | Unit | Session recovery |

### Integration Testing

Integration tests verify interactions between components:

1. **Bedrock Integration**: Test actual Bedrock API calls with real credentials
2. **MCP Server Integration**: Test diagram generation with real MCP server
3. **Streamlit Session State**: Test state persistence across page refreshes
4. **PDF Generation Pipeline**: Test complete PDF generation with all sections

### End-to-End Testing

E2E tests verify complete workflows:

1. **Complete Migration Workflow**: Test all steps from input to roadmap
2. **Error Recovery**: Test workflow recovery after failures
3. **Deployment Verification**: Test deployed application on Fargate

### Local Testing Checklist

Before deployment, verify:

- [ ] All unit tests pass
- [ ] All property tests pass (100+ iterations each)
- [ ] Integration tests pass with real AWS credentials
- [ ] Application starts without errors
- [ ] Diagram generation works and saves files
- [ ] PDF generation works and embeds images
- [ ] All workflow steps complete successfully
- [ ] Error handling works for common failures
- [ ] Session state persists across refreshes

### CI/CD Testing Pipeline

```yaml
# .github/workflows/test.yml
name: Test and Deploy

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run unit tests
        run: pytest tests/unit/ -v
      
      - name: Run property tests
        run: pytest tests/property/ -v --hypothesis-show-statistics
      
      - name: Run integration tests
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: pytest tests/integration/ -v
      
      - name: Build Docker image
        run: docker build -t sagemaker-advisor:test .
      
      - name: Test Docker container
        run: |
          docker run -d -p 8501:8501 --name test-container sagemaker-advisor:test
          sleep 10
          curl --fail http://localhost:8501/_stcore/health || exit 1
          docker stop test-container
  
  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2
      
      - name: Deploy CDK stack
        run: |
          cd infrastructure
          npm install
          npm run build
          npx cdk deploy --require-approval never
```

## Deployment Architecture

### Deployment Phases

1. **Phase 1: Local Development and Testing**
   - Fix diagram generation and PDF issues
   - Test all functionality locally
   - Verify AWS Bedrock integration

2. **Phase 2: Containerization**
   - Create Dockerfile
   - Build and test container locally
   - Push to Amazon ECR

3. **Phase 3: Infrastructure Setup**
   - Write CDK code for VPC, ECS, ALB
   - Deploy infrastructure to AWS
   - Verify connectivity and health checks

4. **Phase 4: Authentication Integration**
   - Configure AWS Cognito
   - Integrate with ALB
   - Test authentication flow

5. **Phase 5: Production Deployment**
   - Deploy application to Fargate
   - Configure auto-scaling
   - Set up monitoring and alarms

### Deployment Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     Developer Workstation                        │
│  1. Fix code issues                                             │
│  2. Run local tests                                             │
│  3. Build Docker image                                          │
│  4. Push to ECR                                                 │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Amazon ECR                                   │
│  • Store Docker images                                          │
│  • Lifecycle policies                                           │
│  • Image scanning                                               │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AWS CDK Deployment                           │
│  1. Synthesize CloudFormation                                   │
│  2. Deploy VPC and networking                                   │
│  3. Deploy ECS cluster and service                              │
│  4. Deploy ALB and Cognito                                      │
│  5. Configure auto-scaling                                      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Production Environment                       │
│  • ECS Fargate tasks running                                    │
│  • ALB routing traffic                                          │
│  • Cognito authenticating users                                 │
│  • CloudWatch monitoring                                        │
└─────────────────────────────────────────────────────────────────┘
```

### Rollback Strategy

If deployment fails or issues are discovered:

1. **Immediate Rollback**: Use ECS service update to revert to previous task definition
2. **CDK Rollback**: Use CloudFormation rollback to previous stack version
3. **Manual Rollback**: Update task definition to use previous image tag

### Monitoring and Alerting

**CloudWatch Metrics**:
- ECS service CPU utilization
- ECS service memory utilization
- ALB request count
- ALB target response time
- ALB 4xx/5xx error rates

**CloudWatch Alarms**:
- High CPU utilization (> 80% for 5 minutes)
- High memory utilization (> 85% for 5 minutes)
- High error rate (> 5% 5xx errors)
- Unhealthy target count (> 0 for 2 minutes)

**CloudWatch Logs**:
- Application logs from Streamlit
- ECS task logs
- ALB access logs

### Cost Estimation

**Monthly Cost Breakdown** (estimated):

| Service | Configuration | Monthly Cost |
|---------|--------------|--------------|
| ECS Fargate | 1 task (1 vCPU, 2GB RAM, 24/7) | ~$30 |
| Application Load Balancer | 1 ALB with minimal traffic | ~$20 |
| NAT Gateway | 1 NAT gateway | ~$35 |
| CloudWatch Logs | 10 GB/month | ~$5 |
| ECR Storage | 5 GB | ~$0.50 |
| Bedrock API Calls | Variable (pay per use) | Variable |
| **Total (excluding Bedrock)** | | **~$90/month** |

**Cost Optimization Strategies**:
1. Use Fargate Spot for non-production environments (70% savings)
2. Scale to zero tasks during off-hours if acceptable
3. Use single NAT gateway instead of one per AZ
4. Set CloudWatch log retention to 30 days
5. Use ECR lifecycle policies to delete old images

## Security Considerations

### Application Security

1. **No Hardcoded Credentials**: All AWS credentials via IAM roles
2. **Environment Variables**: Sensitive config via AWS Secrets Manager
3. **Input Validation**: Validate all user inputs before processing
4. **Output Sanitization**: Sanitize all outputs to prevent XSS
5. **Dependency Scanning**: Regular security scans of Python packages

### Infrastructure Security

1. **Private Subnets**: Fargate tasks in private subnets only
2. **Security Groups**: Least privilege network access
3. **IAM Roles**: Minimal permissions for task execution
4. **Encryption**: TLS for data in transit, encryption at rest for logs
5. **VPC Flow Logs**: Network traffic monitoring

### Authentication Security

1. **Strong Passwords**: Enforce password complexity requirements
2. **MFA**: Optional multi-factor authentication
3. **Session Timeout**: Automatic logout after inactivity
4. **Token Validation**: ALB validates JWT tokens
5. **Audit Logging**: Log all authentication events

## Maintenance and Operations

### Operational Runbook

**Common Operations**:

1. **Deploy New Version**:
   ```bash
   # Build and push image
   docker build -t sagemaker-advisor:v1.2.0 .
   docker tag sagemaker-advisor:v1.2.0 <account>.dkr.ecr.us-west-2.amazonaws.com/sagemaker-advisor:v1.2.0
   docker push <account>.dkr.ecr.us-west-2.amazonaws.com/sagemaker-advisor:v1.2.0
   
   # Update ECS service
   aws ecs update-service --cluster sagemaker-advisor --service sagemaker-advisor-service --force-new-deployment
   ```

2. **Scale Service**:
   ```bash
   # Manual scaling
   aws ecs update-service --cluster sagemaker-advisor --service sagemaker-advisor-service --desired-count 3
   ```

3. **View Logs**:
   ```bash
   # Stream logs
   aws logs tail /ecs/sagemaker-advisor --follow
   ```

4. **Rollback Deployment**:
   ```bash
   # Revert to previous task definition
   aws ecs update-service --cluster sagemaker-advisor --service sagemaker-advisor-service --task-definition sagemaker-advisor-task:42
   ```

### Troubleshooting Guide

**Issue: Diagrams not generating**
- Check MCP server is accessible: `uvx awslabs.aws-diagram-mcp-server`
- Verify workspace_dir is passed to diagram generation
- Check generated-diagrams folder permissions
- Review CloudWatch logs for MCP errors

**Issue: PDF generation fails**
- Verify reportlab is installed: `pip list | grep reportlab`
- Check diagram files exist and are valid images
- Review error logs for specific PIL/reportlab errors
- Test with smaller diagrams first

**Issue: Bedrock authentication fails**
- Verify IAM role has bedrock:InvokeModel permission
- Check AWS region is correct (us-west-2)
- Verify Bedrock model access is enabled in account
- Test with AWS CLI: `aws bedrock invoke-model ...`

**Issue: Application won't start**
- Check all dependencies are installed
- Verify port 8501 is not in use
- Review startup logs for import errors
- Test with minimal Streamlit app first

**Issue: High memory usage**
- Check for memory leaks in session state
- Verify images are being properly closed after processing
- Monitor CloudWatch metrics for trends
- Consider increasing task memory allocation

### Backup and Recovery

**Data to Backup**:
- User pool configuration (Cognito)
- CDK code and configuration
- Docker images (ECR retention)
- CloudWatch logs (30-day retention)

**Recovery Procedures**:
1. **Application Failure**: ECS automatically restarts tasks
2. **Service Failure**: Deploy from previous working image
3. **Infrastructure Failure**: Redeploy CDK stack
4. **Data Loss**: No persistent data to recover (stateless application)

## Future Enhancements

### Potential Improvements

1. **Multi-User Session Isolation**: Separate session state per user
2. **Persistent Storage**: Save workflow state to DynamoDB
3. **Advanced Diagrams**: Interactive diagrams with zoom/pan
4. **Export Formats**: Word documents, PowerPoint presentations
5. **API Access**: REST API for programmatic access
6. **Custom Agents**: User-defined analysis agents
7. **Collaboration**: Share workflows with team members
8. **Version History**: Track changes to migration plans
9. **Cost Calculator**: Real-time AWS cost estimation
10. **Migration Tracking**: Track actual migration progress

### Scalability Considerations

Current design supports:
- **Concurrent Users**: 10-50 users (with auto-scaling)
- **Request Rate**: 100 requests/minute
- **Data Volume**: Diagrams up to 10MB each

For higher scale:
- Add ElastiCache for session state
- Use CloudFront CDN for static assets
- Implement request queuing with SQS
- Add read replicas for any databases
- Use Lambda for background processing

## Conclusion

This design provides a comprehensive solution for fixing, testing, and deploying the SageMaker Migration Advisor application to AWS Fargate with production-ready security, monitoring, and scalability. The key improvements include:

1. **Fixed diagram generation** with proper MCP server integration and workspace directory management
2. **Fixed PDF generation** with robust image embedding and error handling
3. **Production-ready deployment** on AWS Fargate with auto-scaling
4. **Secure authentication** using AWS Cognito and ALB integration
5. **Infrastructure as code** using AWS CDK for reproducible deployments
6. **Comprehensive monitoring** with CloudWatch Logs and Metrics
7. **Cost optimization** strategies to minimize AWS spending

The solution is designed to be maintainable, scalable, and secure, following AWS best practices throughout.
