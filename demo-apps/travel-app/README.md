# Travel Planner - AI-Powered Trip Planning Application

An intelligent travel planning application built on AWS, using AI agents to create personalized itineraries with flights, hotels, and activities.

## 🌟 Overview

Travel Planner leverages AWS services and AI to help users plan their perfect trip. Simply describe your travel goals, and our specialized agents will:

- Find the best flights within your budget
- Recommend hotels that match your preferences
- Suggest activities and experiences
- Create a complete day-by-day itinerary
- Track costs to stay within budget

## 🏗️ Architecture

```
┌──────────────┐        ┌─────────────────┐        ┌──────────────────┐
│              │        │                 │        │                  │
│   Frontend   │◀──────▶│   API Gateway   │◀──────▶│  Lambda Functions│
│   (React)    │        │   (REST API)    │        │  (Orchestrator)  │
│              │        │                 │        │                  │
└──────────────┘        └─────────────────┘        └────────┬─────────┘
                                                             │
                                                    ┌────────▼─────────┐
                                                    │ Specialist Agents│
                                                    │ • Flight Search  │
                                                    │ • Hotel Finder   │
                                                    │ • Activities     │
                                                    │ • Destination    │
                                                    │ • Budget Analyst │
                                                    └────────┬─────────┘
                                                             │
                    ┌────────────────┬───────────────────────┼───────────────────────┬────────────────┐
                    │                │                       │                       │                │
              ┌─────▼─────┐   ┌──────▼──────┐      ┌────────▼────────┐      ┌──────▼──────┐  ┌─────▼─────┐
              │ DynamoDB  │   │    DSQL     │      │    Bedrock      │      │   Bedrock   │  │    S3     │
              │  (Plans)  │   │(Travel Data)│      │ Knowledge Base  │      │   Claude    │  │ (Storage) │
              └───────────┘   └─────────────┘      └─────────────────┘      └─────────────┘  └───────────┘
```

## 🚀 Key Features

### For Users
- **Natural Language Input**: Describe your trip in plain English
- **Real-time Planning**: Watch as AI agents build your itinerary
- **Interactive Refinement**: Provide feedback to customize recommendations
- **Budget Management**: Stay within budget with real-time cost tracking
- **Complete Itineraries**: Get flights, hotels, and activities in one plan

### Technical Highlights
- **Serverless Architecture**: Built on AWS Lambda for scalability
- **AI Agent Orchestration**: Multiple specialized agents working together
- **Real-time Updates**: WebSocket connections for live progress
- **Distributed SQL**: Amazon DSQL for travel data
- **RAG-powered Search**: Bedrock Knowledge Base for destination info
- **Infrastructure as Code**: Automated deployment scripts

## 📦 Components

### [Backend](./backend/)
- AWS Lambda functions for orchestration and agents
- Specialized AI agents for different planning tasks
- REST API via API Gateway
- DynamoDB for plan storage
- DSQL for travel data (flights, hotels, activities)
- Bedrock for AI capabilities

### [Frontend](./frontend/)
- React-based web application
- Real-time agent visualization
- Interactive planning interface
- Budget tracking dashboard

## 🛠️ Quick Start

### Prerequisites
- AWS Account with appropriate permissions
- AWS CLI v2 configured
- Python 3.12
- Node.js 16+
- PostgreSQL client

### 1. Deploy Backend

```bash
cd backend

# Set environment variables
export KB_ID=your-knowledge-base-id
export DSQL_ENDPOINT=your-cluster.dsql.region.on.aws
export AWS_REGION=us-west-2

# Deploy everything
./scripts/deploy_all.sh
```

### 2. Setup Database

```bash
cd backend/data-setup/dsql
./setup_dsql.sh fresh
```

### 3. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure API endpoint
echo "REACT_APP_API_ENDPOINT=https://your-api.execute-api.region.amazonaws.com/prod" > .env.local

# Start development server
npm start
```

## 📊 Sample Interactions

### Basic Trip Planning
```
User: "I want to plan a 5-day trip to Paris with a $3000 budget"

System: Creates complete itinerary with:
- Round-trip flights
- Hotel recommendations
- Daily activities
- Restaurant suggestions
- Total cost breakdown
```

### Advanced Preferences
```
User: "I need a romantic getaway to Tokyo for our anniversary. 
       We love fine dining and cultural experiences. Budget is $5000."

System: Customizes plan with:
- Premium flight options
- Luxury/boutique hotels
- Michelin-starred restaurants
- Private cultural tours
- Couple-focused activities
```

## 🔐 Security

- **IAM Roles**: Least-privilege access for all components
- **API Gateway**: Request validation and throttling
- **DSQL**: IAM-based authentication
- **Encryption**: At-rest and in-transit
- **CORS**: Configured for frontend domain only

## 📈 Monitoring

- **CloudWatch Logs**: All Lambda executions logged
- **X-Ray Tracing**: End-to-end request tracking
- **CloudWatch Metrics**: Performance and error metrics
- **Cost Tracking**: AWS Cost Explorer integration

## 🤝 Development

### Project Structure
```
travel-planner/
├── backend/               # Lambda functions and API
│   ├── lambda/           # Function code
│   ├── scripts/          # Deployment scripts
│   └── data-setup/       # Database setup
├── frontend/             # React application
│   ├── src/             # Source code
│   └── public/          # Static assets
└── docs/                # Documentation
```

## 🐛 Troubleshooting

### Common Issues

1. **"Cannot find flights"**
   - Check DSQL connection
   - Verify data seeding completed
   - Check date ranges in search

2. **"Agent timeout"**
   - Increase Lambda timeout
   - Check CloudWatch logs
   - Verify Bedrock model access

3. **"Frontend connection error"**
   - Verify API endpoint in .env.local
   - Check CORS configuration
   - Verify API Gateway deployment

## 📚 Resources

### Documentation
- [Backend README](./backend/README.md) - Detailed backend setup
- [Frontend README](./frontend/README.md) - Frontend configuration
- [Deployment Guide](./backend/DEPLOYMENT_GUIDE.md) - Step-by-step deployment

### AWS Services
- [AWS Lambda](https://docs.aws.amazon.com/lambda/)
- [Amazon DSQL](https://docs.aws.amazon.com/dsql/)
- [Amazon Bedrock](https://docs.aws.amazon.com/bedrock/)
- [API Gateway](https://docs.aws.amazon.com/apigateway/)

### Frameworks
- [React](https://react.dev/)
- [TypeScript](https://www.typescriptlang.org/)
- [AWS CDK](https://aws.amazon.com/cdk/) (optional)
