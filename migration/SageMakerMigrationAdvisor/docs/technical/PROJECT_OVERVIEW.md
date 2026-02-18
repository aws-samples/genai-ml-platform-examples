# SageMaker Migration Advisor - Project Overview

## 🎯 Project Purpose

The SageMaker Migration Advisor is an AI-powered web application designed to help organizations migrate their machine learning workloads to AWS SageMaker. It provides automated architecture analysis, cost estimation, and detailed migration recommendations.

---

## 🏗️ What This Project Does

### Core Functionality

1. **Architecture Analysis**
   - Analyzes current ML infrastructure (on-premises or cloud)
   - Identifies components, dependencies, and workflows
   - Understands training patterns, data pipelines, and deployment strategies

2. **Migration Planning**
   - Generates step-by-step migration recommendations
   - Maps current architecture to SageMaker services
   - Provides best practices and optimization suggestions

3. **Cost Analysis (TCO)**
   - Compares current infrastructure costs vs. SageMaker costs
   - Breaks down costs by service and component
   - Identifies cost optimization opportunities

4. **Documentation**
   - Generates professional PDF reports
   - Creates architecture diagrams
   - Provides implementation roadmaps

---

## 🎭 Two Operating Modes

### Lite Mode (Quick Assessment)
**Duration**: 5-10 minutes  
**Use Case**: Initial assessments, quick wins, straightforward migrations

**Workflow**:
1. User uploads architecture diagram or describes setup
2. AI analyzes architecture
3. Generates migration recommendations
4. Provides basic TCO estimation
5. Creates PDF report

**Output**:
- Migration recommendations
- Basic cost comparison
- PDF report

### Regular Mode (Comprehensive Analysis)
**Duration**: 15-30 minutes  
**Use Case**: Complex migrations, enterprise deployments, detailed planning

**Workflow**:
1. User uploads architecture diagram or describes setup
2. AI conducts interactive Q&A session
3. Deep architecture analysis
4. Detailed TCO comparison
5. Architecture diagram generation
6. Comprehensive PDF report

**Output**:
- Detailed migration plan
- Comprehensive TCO analysis
- Architecture diagrams
- Detailed PDF report

---

## 🔧 Technical Architecture

### Application Stack

**Frontend**:
- Streamlit (Python web framework)
- Custom CSS for styling
- Interactive forms and file uploads

**Backend**:
- Python 3.8+
- AWS Bedrock (Claude Sonnet) for AI analysis
- AWS Cognito for authentication
- AWS S3 for artifact storage

**Infrastructure**:
- Docker containerization
- AWS ECS Fargate or Lightsail for hosting
- Application Load Balancer (ALB) for ECS
- CloudWatch for logging and monitoring

### Key Components

```
app.py
├── CognitoAuth class          # Handles authentication
├── MigrationAdvisorApp class  # Main application logic
│   ├── render_login_page()    # Login interface
│   ├── render_mode_selection() # Mode selection
│   └── render_advisor_app()   # Advisor interface
│
sagemaker_migration_advisor.py  # Regular mode implementation
├── Multi-agent workflow
├── Interactive Q&A
├── Detailed analysis
└── Comprehensive reporting

sagemaker_migration_advisor_lite.py  # Lite mode implementation
├── Streamlined workflow
├── Quick analysis
└── Basic reporting
```

---

## 📦 Deployment Options

### 1. Local Development
**Purpose**: Testing and development  
**Requirements**: Python 3.8+, AWS credentials  
**Cost**: Free  
**Setup Time**: 5 minutes

**Use When**:
- Developing new features
- Testing changes
- Debugging issues
- Training users

### 2. AWS ECS Fargate with ALB
**Purpose**: Production deployment for enterprises  
**Requirements**: AWS account, Docker, Terraform  
**Cost**: ~$135/month  
**Setup Time**: 15-20 minutes

**Features**:
- Auto-scaling
- High availability
- HTTPS support
- Load balancing
- Container insights

**Use When**:
- Production workloads
- Multiple users
- High availability required
- Enterprise security needed

---

## 🔐 Security Model

### Authentication
- **AWS Cognito User Pools**
- Password policies enforced
- Email verification
- User groups (Admins, Users)

### Authorization
- **IAM Roles** with least privilege
- Separate roles for:
  - ECS task execution (ECR, CloudWatch)
  - ECS task (Bedrock, S3, Cognito)

### Data Protection
- **Encryption at rest**: S3 (AES-256)
- **Encryption in transit**: HTTPS/TLS
- **Secrets management**: Environment variables
- **Network isolation**: Security groups, VPC

### Audit & Compliance
- **CloudWatch Logs**: All activities logged
- **Access logs**: ALB logs to S3
- **User tracking**: Cognito user events

---

## 💾 Data Flow

### User Journey

```
1. User Login
   ↓
2. Cognito Authentication
   ↓
3. Mode Selection (Lite or Regular)
   ↓
4. Architecture Input (Upload or Text)
   ↓
5. AI Analysis (Bedrock/Claude)
   ↓
6. Results Display
   ↓
7. PDF Report Generation
   ↓
8. Download Report
```

### Data Storage

**S3 Bucket**: `sagemaker-migration-advisor-artifacts-{account-id}`
- Architecture diagrams (uploaded)
- Generated diagrams
- PDF reports
- Temporary analysis files

**CloudWatch Logs**: `/ecs/sagemaker-migration-advisor`
- Application logs
- Error logs
- User activity logs

---

## 🛠️ Configuration Management

### Environment Variables (.env)

```bash
# AWS Configuration
AWS_REGION=us-east-1

# Cognito (Generated by setup-cognito.sh)
COGNITO_USER_POOL_ID=us-east-1_XXXXXXXXX
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx
COGNITO_DOMAIN=your-domain.auth.us-east-1.amazoncognito.com

# S3 Storage
S3_BUCKET=sagemaker-migration-advisor-artifacts-123456789012

# Bedrock AI Model
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0

# Application
LOG_LEVEL=INFO
```

### Terraform Variables

```hcl
# Core Configuration
aws_region = "us-east-1"
app_name   = "sagemaker-migration-advisor"

# ECS Configuration
ecs_task_cpu    = "2048"  # 2 vCPU
ecs_task_memory = "4096"  # 4 GB
ecs_desired_count = 1

# Security
my_ip_address = "YOUR_IP/32"  # For IP whitelisting

# Optional: HTTPS
certificate_arn = ""  # ACM certificate ARN
domain_name     = ""  # Custom domain
```

---

## 📊 Cost Breakdown

### ECS Fargate Deployment (~$135/month)

| Component | Specification | Monthly Cost |
|-----------|--------------|--------------|
| ECS Fargate | 2 vCPU, 4GB RAM, 24/7 | ~$100 |
| Application Load Balancer | 24/7 operation | ~$20 |
| Cognito | 100 users | Free |
| Bedrock (Claude) | 1M tokens/month | ~$15 |
| S3 Storage | 10 GB | ~$0.23 |
| ECR | 1 image | ~$0.10 |
| CloudWatch Logs | 5 GB/month | ~$2.50 |
| **Total** | | **~$137.83/month** |

### Cost Optimization Tips

1. **Use Spot Instances**: Not applicable for Fargate, but consider for batch processing
2. **Right-size Resources**: Monitor usage and adjust CPU/memory
3. **Implement Auto-scaling**: Scale down during off-hours
4. **Optimize Bedrock Usage**: Cache responses, optimize prompts
5. **S3 Lifecycle Policies**: Archive old reports to Glacier

---

## 🚀 Deployment Workflow

### Initial Setup (One-Time)

```bash
# 1. Setup Cognito
cd deploy
./setup-cognito.sh

# 2. Create admin user
./create-user.sh admin@example.com "Admin User" "SecurePass123!" "Admins"

# 3. Test locally
cd ..
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

### ECS Deployment

```bash
# 1. Build and push Docker image
cd deploy
./build-and-push.sh

# 2. Deploy infrastructure
cd terraform
terraform init
terraform apply

# 3. Access application
# URL provided in terraform output
```

---

## 🧪 Testing Strategy

### Local Testing
1. **Authentication Test**: `python3 test_cognito_auth.py`
2. **Application Test**: `streamlit run app.py`
3. **Full Workflow Test**: Complete Lite and Regular modes

### Integration Testing
1. **Cognito Integration**: Login/logout functionality
2. **Bedrock Integration**: AI analysis responses
3. **S3 Integration**: File upload/download
4. **PDF Generation**: Report creation

### Deployment Testing
1. **Health Checks**: ALB health check endpoint
2. **Load Testing**: Concurrent user simulation
3. **Security Testing**: Authentication, authorization
4. **Performance Testing**: Response times, throughput

---

## 📈 Monitoring & Observability

### CloudWatch Metrics

**Application Metrics**:
- Request count
- Response time (p50, p95, p99)
- Error rate
- Active users

**Infrastructure Metrics**:
- CPU utilization
- Memory utilization
- Network throughput
- Container health

**Business Metrics**:
- Lite mode usage
- Regular mode usage
- PDF downloads
- Bedrock token consumption

### Logging

**Application Logs** (`/ecs/sagemaker-migration-advisor`):
- User actions
- AI interactions
- Errors and exceptions
- Performance metrics

**Access Logs** (S3):
- HTTP requests
- Response codes
- Client IPs
- Request timing

### Alerts

**Critical Alerts**:
- Application down
- High error rate (> 5%)
- Authentication failures
- Bedrock API errors

**Warning Alerts**:
- High CPU (> 80%)
- High memory (> 80%)
- Slow response time (> 5s)
- High Bedrock costs

---

## 🔄 Maintenance & Operations

### Regular Maintenance

**Daily**:
- Monitor CloudWatch dashboards
- Check error logs
- Review Bedrock usage

**Weekly**:
- Review user feedback
- Check cost reports
- Update documentation

**Monthly**:
- Security patches
- Dependency updates
- Performance optimization
- Cost optimization review

### Backup & Recovery

**Automated Backups**:
- S3 versioning enabled
- CloudWatch logs retained (7 days)
- Terraform state in S3

**Recovery Procedures**:
1. Infrastructure: `terraform apply`
2. Application: Redeploy container
3. Data: Restore from S3 versions

---

## 🎓 User Roles & Permissions

### Admin Users
**Capabilities**:
- Full access to both modes
- User management (via AWS Console)
- Configuration changes
- Cost monitoring

**Use Cases**:
- System administrators
- ML platform team
- DevOps engineers

### Standard Users
**Capabilities**:
- Access to both modes
- Generate reports
- Download PDFs

**Use Cases**:
- Data scientists
- ML engineers
- Business analysts
- Solution architects

---

## 📚 Documentation Structure

### For Users
- **QUICKSTART.md**: Get started in 5 minutes
- **LOCAL_TESTING_GUIDE.md**: Test locally
- **LAUNCHER_GUIDE.md**: Using launcher scripts

### For Administrators
- **ECS_DEPLOYMENT_SUMMARY.md**: ECS deployment
- **LIGHTSAIL_DEPLOYMENT_STEPS.md**: Lightsail deployment
- **PERMISSIONS_AND_USERS_SUMMARY.md**: User management

### For Developers
- **PROJECT_SUMMARY.md**: Technical overview
- **IMPLEMENTATION_SUMMARY.md**: Implementation details
- **README_CLI.md**: CLI usage

### For Operations
- **TROUBLESHOOTING.md**: Common issues
- **SECURITY_CONSIDERATIONS.md**: Security best practices
- **TESTING_CHECKLIST.md**: Testing procedures

---

## 🎯 Success Criteria

### Technical Success
- ✅ Application accessible 24/7
- ✅ < 5 second response time
- ✅ < 1% error rate
- ✅ Successful authentication
- ✅ PDF generation working

### Business Success
- ✅ Users can complete workflows
- ✅ Reports are accurate and useful
- ✅ Cost estimates are reliable
- ✅ Positive user feedback
- ✅ Adoption by target teams

### Operational Success
- ✅ Automated deployments
- ✅ Monitoring and alerting
- ✅ Clear documentation
- ✅ Efficient troubleshooting
- ✅ Cost within budget

---

## 🚦 Current Status

### Completed
- ✅ Core application development
- ✅ Cognito authentication
- ✅ Lite and Regular modes
- ✅ PDF report generation
- ✅ Local testing setup
- ✅ ECS deployment configuration
- ✅ Lightsail deployment configuration
- ✅ Comprehensive documentation

### In Progress
- 🔄 User acceptance testing
- 🔄 Performance optimization
- 🔄 Cost optimization

### Planned
- 📋 Additional deployment options
- 📋 Enhanced monitoring dashboards
- 📋 User feedback integration
- 📋 Multi-region support

---

## 📞 Support & Resources

### Getting Help
1. **Documentation**: Check relevant guide in docs
2. **Troubleshooting**: See TROUBLESHOOTING.md
3. **Testing**: Follow TESTING_CHECKLIST.md
4. **AWS Support**: Contact your AWS account team

### Key Contacts
- **Project Owner**: AWS ML Solutions Team
- **Technical Support**: AWS Support
- **Security Issues**: AWS Security Team

---

**Document Version**: 1.0  
**Last Updated**: February 2026  
**Maintained By**: AWS ML Solutions Team
