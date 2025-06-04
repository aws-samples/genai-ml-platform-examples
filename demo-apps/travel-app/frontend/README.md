# Travel Planner Frontend

A React-based web application for intelligent travel planning, providing an interactive interface to the AWS-powered backend services.

## 🎯 Features

- **Interactive Travel Planning**: Chat-based interface for creating personalized travel plans
- **Real-time Updates**: Live planning progress through WebSocket connections
- **Multi-Agent Visualization**: See specialist agents working on your travel plan
- **Responsive Design**: Works on desktop and mobile devices
- **Budget Tracking**: Real-time cost calculations and budget management

## 🚀 Quick Start

### Prerequisites

- Node.js 16+ and npm
- Deployed backend API (see backend README)

### Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure API endpoints:**
   
   Create a `.env.local` file in the frontend directory:
   ```env
   REACT_APP_API_ENDPOINT=https://your-api-id.execute-api.region.amazonaws.com/prod
   REACT_APP_USE_SIMULATION=false
   REACT_APP_USE_BACKEND_STRANDS=true
   REACT_APP_WEBSOCKET_ENDPOINT=
   ```

   To get your API endpoint:
   ```bash
   # If you deployed the backend, check api_config.json
   cat ../backend/api_config.json
   ```

3. **Start development server:**
   ```bash
   npm start
   ```

   The app will open at http://localhost:3000

## 📂 Project Structure

```
frontend/
├── src/
│   ├── components/          # React components
│   │   ├── TravelPlanner.tsx   # Main planner interface
│   │   ├── AgentStatus.tsx     # Agent progress display
│   │   └── BudgetTracker.tsx   # Budget visualization
│   ├── services/           # API and WebSocket services
│   │   ├── apiClient.ts       # REST API client
│   │   └── TravelPlanService.ts # Travel plan management
│   ├── types/              # TypeScript definitions
│   └── App.tsx             # Main application
├── public/                 # Static assets
└── package.json           # Dependencies
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `REACT_APP_API_ENDPOINT` | Backend API URL | `https://api.example.com/prod` |

### API Integration

The frontend connects to these backend endpoints:

- `POST /api/planning/start` - Start new travel plan
- `POST /api/planning/continue` - Continue with user input
- `GET /api/planning/{plan_id}/status` - Get plan status
- `POST /api/planning/{plan_id}/finalize` - Finalize plan

## 🎨 UI Components

### Travel Planner
Main interface for travel planning conversations:
- User input field
- Agent responses
- Progress indicators
- Action buttons

### Agent Status Panel
Shows real-time agent activity:
- Flight Specialist
- Hotel Specialist
- Activities Curator
- Destination Expert
- Budget Analyst

### Budget Tracker
Displays cost breakdown:
- Flights
- Hotels
- Activities
- Total vs. Budget

## 🧪 Testing

### Run Tests
```bash
npm test
```

### Test Coverage
```bash
npm run test:coverage
```

### Manual Testing

1. **Basic Flow:**
   - Enter "Plan a 5-day trip to Paris with $3000 budget"
   - Watch agents process the request
   - Provide additional preferences when prompted
   - Review final itinerary

2. **Error Handling:**
   - Test with invalid API endpoint
   - Test network disconnection
   - Test invalid user inputs

## 🚢 Deployment

### Build for Production
```bash
npm run build
```

### Deploy to S3

1. **Create S3 bucket:**
   ```bash
   aws s3 mb s3://travel-planner-frontend-YOUR-ID
   ```

2. **Enable static hosting:**
   ```bash
   aws s3 website s3://travel-planner-frontend-YOUR-ID \
     --index-document index.html \
     --error-document error.html
   ```

3. **Deploy build:**
   ```bash
   aws s3 sync build/ s3://travel-planner-frontend-YOUR-ID \
     --delete \
     --cache-control max-age=31536000
   ```

## 🐛 Troubleshooting

### Common Issues

1. **"Cannot connect to API"**
   - Verify `REACT_APP_API_ENDPOINT` is correct
   - Check backend is deployed and running

## 📚 Additional Resources

- [React Documentation](https://react.dev/)
- [TypeScript Handbook](https://www.typescriptlang.org/docs/)
- [AWS API Gateway](https://docs.aws.amazon.com/apigateway/)
- [Backend README](../backend/README.md) 