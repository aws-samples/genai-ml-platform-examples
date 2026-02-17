# Local Testing Guide

Quick guide for testing the SageMaker Migration Advisor locally with Cognito authentication.

## 🚀 Quick Start

### 1. Start the Application

```bash
cd migration/SageMakerMigrationAdvisor
source venv/bin/activate
streamlit run app.py
```

**Access:** http://localhost:8501

### 2. User Management

**Create a test user:**
```bash
cd deploy
./create-user.sh admin@example.com "Admin User" "SecurePass123!" "Admins"
```

**Reset password:**
```bash
./reset-password.sh admin@example.com "NewPassword123!"
```

**List users:**
```bash
./list-users.sh
```

## 🧪 Testing Workflow

### 1. Login
- Open http://localhost:8501
- Enter credentials (username/password)
- Click "Login"

### 2. Select Mode
- **Lite Mode**: Quick assessment (5-10 min)
- **Regular Mode**: Comprehensive analysis (15-30 min)

### 3. Test Features

**Lite Mode:**
- Upload diagram or describe architecture
- Generate recommendations
- View TCO analysis
- Download PDF report

**Regular Mode:**
- Interactive Q&A session
- Architecture analysis
- Detailed TCO comparison
- Architecture diagrams
- Comprehensive PDF report

### 4. Test Navigation
- Logout button
- Back to mode selection
- Mode switching without re-authentication

## 🐛 Troubleshooting

### Can't access localhost:8501
- Check if Streamlit is running
- Try http://127.0.0.1:8501
- Check firewall settings

### "Cognito not configured" warning
```bash
# Verify .env file exists
cat .env | grep COGNITO
```

### Authentication fails
```bash
# Verify user exists
cd deploy && ./list-users.sh

# Reset password
./reset-password.sh your-email@example.com "NewPass123!"

# Check user status
source ../.env
aws cognito-idp admin-get-user \
  --user-pool-id $COGNITO_USER_POOL_ID \
  --username your-email@example.com \
  --region $AWS_REGION
```

### App crashes
```bash
# Check dependencies
source venv/bin/activate
pip install -r requirements.txt

# Check required files
ls -la sagemaker_migration_advisor*.py app.py
```

## 📝 Development Mode

If Cognito is not configured, the app runs in development mode:
- Any credentials will work
- No actual authentication
- Useful for local development without AWS setup

---

**For deployment guides, see:**
- `QUICKSTART.md` - Quick deployment guide
- `DEPLOYMENT_GUIDE.md` - Complete deployment documentation
- `deploy/README.md` - Deployment scripts reference
