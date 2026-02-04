# SageMaker Migration Advisor - Streamlit Application

A comprehensive web interface for the SageMaker Migration Advisor that provides interactive architecture analysis, conversational state management, and error recovery capabilities.

## 🚀 Features

### Core Functionality
- **Interactive Architecture Analysis**: Upload diagrams or provide text descriptions
- **Conversational State Management**: Maintains context throughout the workflow
- **Error Recovery**: Resume from any failed step after fixing issues
- **Real-time Progress Tracking**: Visual workflow progress in sidebar
- **Multi-Agent Orchestration**: Seamless integration of all advisor agents

### User Experience
- **Responsive Web Interface**: Clean, professional Streamlit UI
- **Step-by-Step Guidance**: Clear workflow progression with visual indicators
- **Download Results**: Export complete analysis as JSON
- **Image Support**: Upload and analyze architecture diagrams
- **Error Handling**: Graceful error recovery with retry mechanisms

## 📋 Prerequisites

### Required Software
- Python 3.8 or higher
- AWS CLI configured with appropriate credentials
- Access to AWS Bedrock (Claude models)

### AWS Permissions
Your AWS credentials need access to:
- Amazon Bedrock (Claude models)
- Amazon S3 (for data storage)
- SageMaker (for the analysis)

## 🛠️ Installation

### 1. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure AWS Credentials
```bash
# Option 1: Configure your profile with SSO wizard 
# https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html#cli-configure-sso-prereqs
aws configure sso

# Option 2: Environment Variables
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-west-2
```


## 🚀 3. Launch SageMaker Migration Advisor app

```bash
python run_sagemaker_migration_advisor.py
```

The application will open in your default web browser at `http://localhost:8501`

## 📖 User Guide

### Workflow Steps

#### 1. **Architecture Input** 📋
- Choose between uploading a diagram or providing text description
- **With Diagram**: Upload PNG/JPG files, system analyzes visual architecture
- **Text Description**: Provide detailed description of your current architecture

#### 2. **Clarification Q&A** ❓
- System generates clarifying questions based on your input
- Helps resolve ambiguities and gather additional context
- Ensures comprehensive understanding of your architecture

#### 3. **SageMaker Design** 🚀
- Generates modernized SageMaker architecture
- Provides detailed component mapping and recommendations
- Explains migration benefits and considerations

#### 4. **Diagram Generation** 📊
- Creates visual diagrams of the proposed SageMaker architecture
- Generates multiple diagram types (detailed, workflow, complete)
- Saves diagrams to `generated-diagrams/` folder

#### 5. **TCO Analysis** 💰
- Comprehensive Total Cost of Ownership analysis
- Compares current vs. SageMaker costs
- Includes operational and infrastructure considerations

#### 6. **Migration Roadmap** 🗺️
- Step-by-step migration plan
- Prioritized implementation phases
- Risk mitigation strategies

### Navigation Features

#### Sidebar Controls
- **Progress Tracking**: Visual indicators for each workflow step
- **Reset Workflow**: Start over with a clean slate
- **Download Results**: Export complete analysis
- **Error Recovery**: Retry failed steps

#### Error Recovery
- **Automatic Detection**: System identifies and logs errors
- **Retry Mechanism**: Resume from failed step after fixing issues
- **State Preservation**: Maintains all previous progress
- **Error Details**: Clear error messages with troubleshooting hints

## 🔧 Advanced Configuration

### Model Selection
The application automatically tries multiple Claude models in order of preference:
1. Claude 4.5 Sonnet (latest)
2. Claude 4 Sonnet
3. Claude 3.7 Sonnet

### Custom Configuration
Edit `sagemaker_migration_advisor.py` to customize:
- Model selection logic
- Workflow steps
- UI styling
- Error handling behavior

### Environment Variables
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-west-2

# Optional: Custom model preferences
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-5-20250929-v1:0
```

## 📁 File Structure

```
├── sagemaker_migration_advisor.py    # Main Streamlit application
├── run_sagemaker_migration_advisor.py # Launcher script
├── requirements.txt                  # Python dependencies
├── README.md                         # This documentation
├── README_CLI.md                     # CLI version documentation
├── prompts.py                       # Agent prompts (required)
├── logger_config.py                 # Logging configuration (required)
├── tools/                           # Agent tools (required)
│   ├── __init__.py
│   └── user_prompt.py
├── generated-diagrams/              # Generated architecture diagrams
└── advisor_agent_interactions.txt   # Interaction logs
```

## 🐛 Troubleshooting

### Common Issues

#### 1. **AWS Authentication Errors**
```
Error: Unable to locate credentials
```
**Solution**: Configure AWS credentials using `aws configure` or environment variables

#### 2. **Bedrock Model Access**
```
Error: Access denied to Bedrock model
```
**Solution**: Ensure your AWS account has Bedrock access and model permissions

#### 3. **Missing Dependencies**
```
ModuleNotFoundError: No module named 'streamlit'
```
**Solution**: Install requirements with `pip install -r requirements.txt`

#### 4. **Port Already in Use**
```
Error: Port 8501 is already in use
```
**Solution**: Use a different port: `streamlit run sagemaker_migration_advisor.py --server.port 8502`

### Debug Mode
Enable debug logging by setting:
```bash
export STREAMLIT_LOGGER_LEVEL=debug
```

### Log Files
- **Application Logs**: Check `logs/app.log`
- **Interaction Logs**: Check `advisor_agent_interactions.txt`
- **Streamlit Logs**: Displayed in terminal

## 🔄 State Management

### Session State
The application maintains state across browser sessions using Streamlit's session state:
- **Workflow Progress**: Current and completed steps
- **Agent Responses**: All generated content
- **User Inputs**: Architecture descriptions and uploads
- **Error States**: Failed steps and error messages

### Persistence
- **Interaction Logs**: Saved to `advisor_agent_interactions.txt`
- **Generated Diagrams**: Saved to `generated-diagrams/` folder
- **Results Export**: JSON format with complete workflow data

### Recovery Mechanisms
- **Step Retry**: Resume from any failed step
- **State Reset**: Clear all data and start fresh
- **Partial Recovery**: Continue from last successful step

## 🎨 Customization

### UI Styling
Modify the CSS in `sagemaker_migration_advisor.py`:
```python
st.markdown("""
<style>
    .main-header { color: #your-color; }
    .step-header { font-size: your-size; }
</style>
""", unsafe_allow_html=True)
```

### Workflow Modification
Add or modify steps by:
1. Adding new agent setup in `setup_agents()`
2. Creating new step handler method
3. Adding step to workflow progression logic

## 📊 Performance Considerations

### Resource Usage
- **Memory**: ~500MB for base application
- **CPU**: Moderate during agent processing
- **Network**: Depends on Bedrock API calls

### Optimization Tips
- Use smaller images for diagram uploads
- Clear browser cache if experiencing slowdowns
- Monitor AWS Bedrock usage and costs

## 🤝 Support

### Getting Help
1. Check this README for common solutions
2. Review log files for detailed error information
3. Ensure all prerequisites are met
4. Verify AWS credentials and permissions

### Reporting Issues
When reporting issues, include:
- Error messages from logs
- Steps to reproduce
- Environment details (Python version, OS)
- AWS region and model access status

### Usage Examples

**Use Case Description :**
Customer is running pytorch distributed training workload  on 2 nodes of p5.48xlarge. Their pain points are related to: 1.Experiment tracking 2. Automation 3. Model governance 4. Cost. 


**Source System Architecture Diagram:**
Upload the source system architecutre diagram using the streamlit app:  ![on-prem-data-science-arch](rocket-mortgage-legacy-ds-arch.png)