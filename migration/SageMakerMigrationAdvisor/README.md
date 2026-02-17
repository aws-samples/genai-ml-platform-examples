# SageMaker Migration Advisor

AI-powered tool to migrate ML workloads to AWS SageMaker with automated architecture analysis, TCO estimation, and migration recommendations.

## 🎯 Overview

Streamlit web application using AWS Bedrock (Claude Sonnet) to analyze ML infrastructure and provide:

- Architecture analysis and migration recommendations
- TCO comparison between current and SageMaker setup
- Professional PDF reports with architecture diagrams
- Two analysis modes: **Lite** (5-10 min) and **Regular** (15-30 min)

## ✨ Features

- 🔐 Cognito authentication and secure user management
- 🤖 AI-powered analysis using AWS Bedrock (Claude Sonnet)
- 📊 Architecture diagrams using AWS Diagram MCP Server
- 💰 Detailed TCO estimation and cost comparison
- 📄 Professional PDF reports
- 🐳 Containerized deployment (ECS Fargate with CloudFront)
- 📈 CloudWatch logging and monitoring

## 🚀 Quick Start

**Prerequisites:** AWS Account, AWS CLI, Python 3.11+

```bash
# 1. Clone and setup
cd SageMakerMigrationAdvisor

# 2. Install dependencies
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env with your AWS credentials

# 4. Run locally
streamlit run app.py
```

Access at: http://localhost:8501

See [Quick Start Guide](docs/user-guides/QUICKSTART.md) for detailed instructions.

## 🌐 Production Deployment

**Current Deployment:** ECS Fargate with CloudFront CDN

- **CloudFront URL:** https://YOUR_CLOUDFRONT_DIST_ID.cloudfront.net
- **Architecture:** CloudFront → ALB → ECS Fargate
- **Region:** us-east-1

```bash
# Deploy to ECS Fargate
cd deploy && ./deploy-ecs.sh
```

See [Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md) for complete instructions.

## 👥 User Management

```bash
cd deploy

# Create user
./create-user.sh email@example.com "Name" "Password123!" "Admins"

# List users
./list-users.sh

# Reset password
./reset-password.sh email@example.com "NewPassword123!"
```

## 📊 Mode Comparison

| Feature | Lite Mode | Regular Mode |
|---------|-----------|--------------|
| Duration | 5-10 min | 15-30 min |
| Architecture Analysis | Basic | Detailed with Q&A |
| TCO Analysis | Basic | Comprehensive |
| Diagram Generation | ❌ | ✅ |
| Migration Roadmap | Simplified | Detailed |
| PDF Report | ✅ | ✅ |
| Best For | Quick assessments | Complex migrations |

**Example Output:** See [SageMaker_Migration_Report_Example.pdf](SageMaker_Migration_Report_Example.pdf)

## 📚 Documentation

- **[Quick Start Guide](docs/user-guides/QUICKSTART.md)** - Get started in 5 minutes
- **[Deployment Guide](docs/deployment/DEPLOYMENT_GUIDE.md)** - Production deployment
- **[Project Overview](docs/technical/PROJECT_OVERVIEW.md)** - Technical architecture
- **[Troubleshooting](docs/technical/TROUBLESHOOTING.md)** - Common issues
- **[Security Considerations](docs/technical/SECURITY_CONSIDERATIONS.md)** - Security best practices
- **[Deployment Scripts](deploy/README.md)** - Deployment automation


## 📁 Project Structure

```
SageMakerMigrationAdvisor/
├── app.py                              # Main entry point with Cognito auth
├── sagemaker_migration_advisor.py      # Regular mode (comprehensive)
├── sagemaker_migration_advisor_lite.py # Lite mode (quick assessment)
├── prompts.py / prompts_lite.py        # AI prompts for each mode
├── pdf_report_generator.py             # PDF generation with diagrams
├── diagram_generator.py                # Architecture diagram generation
├── advisor_config.py                   # Configuration settings
├── logger_config.py                    # Logging configuration
├── requirements.txt                    # Python dependencies
├── Dockerfile                          # Container image
├── .env.example                        # Environment template
│
├── docs/                               # Documentation
│   ├── deployment/                     # Deployment guides
│   ├── user-guides/                    # User documentation
│   ├── technical/                      # Technical docs
│   └── diagrams/                       # Diagram documentation
│
├── deploy/                             # Deployment automation
│   ├── terraform/                      # Infrastructure as Code
│   │   ├── main.tf                     # Core resources (Cognito, ECR, S3)
│   │   ├── ecs-fargate.tf              # ECS Fargate configuration
│   │   └── cloudfront.tf               # CloudFront CDN
│   ├── deploy-ecs.sh                   # ECS deployment script
│   ├── update-ecs-deployment.sh        # Update running deployment
│   ├── create-user.sh                  # User management scripts
│   └── README.md                       # Deployment documentation
│
├── generated-diagrams/                 # Generated diagram output
└── logs/                               # Application logs
```

## 🔧 Configuration

Environment variables in `.env`:

```bash
AWS_REGION=us-east-1
COGNITO_USER_POOL_ID=us-east-1_xxxxxxxxx
COGNITO_CLIENT_ID=xxxxxxxxxxxxxxxxxx
COGNITO_CLIENT_SECRET=xxxxxxxxxxxxxxxxxx
S3_BUCKET=sagemaker-migration-advisor-artifacts-xxxxxxxxxxxx
```

## 💰 Estimated Monthly Costs

| Component | Cost |
|-----------|------|
| ECS Fargate (1 task, 1 vCPU, 2GB) | ~$30 |
| Application Load Balancer | ~$16 |
| CloudFront CDN | ~$1 |
| AWS Bedrock (Claude Sonnet) | ~$15 |
| **Total** | **~$62/mo** |

*Cognito (100 users), S3 storage, and CloudWatch logs are minimal/free tier*

## 🏗️ Architecture

```
User Browser
     ↓
CloudFront CDN (Global)
     ↓
Application Load Balancer
     ↓
ECS Fargate (Streamlit App)
├─ Cognito Authentication
├─ Mode Selection (Lite/Regular)
├─ AI Analysis (Bedrock)
├─ Diagram Generation (MCP Server)
└─ PDF Report Generation
     ↓
AWS Services: Cognito, Bedrock, S3, CloudWatch
```

## 🔒 Security

- Cognito authentication with password policies
- IAM roles with least privilege (no credentials in containers)
- CloudFront with ALB origin for secure global access
- Data encrypted at rest (S3) and in transit (HTTPS)
- Security groups and VPC isolation
- CloudWatch audit logging

## 🐛 Troubleshooting

```bash
# Check logs locally
tail -f logs/app.log

# Check ECS logs
aws logs tail /ecs/sagemaker-migration-advisor --follow

# Verify environment
source .env && echo $COGNITO_USER_POOL_ID

# Reset user password
cd deploy && ./reset-password.sh email@example.com "NewPass123!"
```

See [Troubleshooting Guide](docs/technical/TROUBLESHOOTING.md) for more solutions.

## 📊 Monitoring

- **CloudWatch Logs:** `/ecs/sagemaker-migration-advisor`
- **Metrics:** Request count, error rate, Bedrock token usage
- **Health Checks:** ALB health checks on `/_stcore/health`
- **CloudFront Metrics:** Cache hit rate, origin latency

---

**Version:** 1.0.0  
**Last Updated:** February 2026  
**Deployment:** ECS Fargate with CloudFront  
**Status:** ✅ Production Ready
