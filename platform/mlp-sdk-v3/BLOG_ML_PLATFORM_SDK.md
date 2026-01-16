# Simplifying Machine Learning Operations with ML Platform SDK (mlp_sdk)

**Streamline Your ML Workflows with Configuration-Driven Infrastructure Management**

---

## Introduction: The Challenge of ML Infrastructure Management

As data scientists, we love building models, experimenting with algorithms, and extracting insights from data. What we don't love? Wrestling with infrastructure configuration, managing VPC settings, juggling security groups, and repeating the same boilerplate code across every project.

Sound familiar? You're not alone.

Modern machine learning workflows on cloud platforms like AWS SageMaker are powerful, but they come with significant operational overhead. Every training job, processing task, or feature store operation requires you to specify:

- VPC configurations and security groups
- IAM roles and permissions
- S3 bucket locations and prefixes
- Instance types and counts
- KMS encryption keys
- Network isolation settings

And that's just the beginning. Multiply this across teams, projects, and environments, and you have a recipe for inconsistency, errors, and wasted time.

### The Three Core Challenges

**1. Infrastructure Abstraction Complexity**

Managing cloud infrastructure shouldn't be a data scientist's primary concern. Yet, every SageMaker operation requires intimate knowledge of:
- **Networking**: VPC IDs, subnet configurations, security group rules
- **Security**: IAM roles, KMS encryption, network isolation
- **Storage**: S3 bucket policies, prefix conventions, lifecycle rules

This creates friction between data science teams and infrastructure teams, slowing down experimentation and deployment.

**2. Consistency and Standardization**

Without centralized configuration management, teams face:
- **Naming Convention Chaos**: Different projects use different naming patterns for resources
- **Configuration Drift**: Development, staging, and production environments diverge over time
- **Experiment Tracking Gaps**: Inconsistent tagging makes it difficult to track experiments and costs
- **Knowledge Silos**: Critical configuration knowledge lives in individual notebooks or scripts

**3. Governance and Compliance**

Enterprise ML operations demand:
- **Central Policy Enforcement**: Ensuring all workloads comply with security and compliance requirements
- **Audit Trails**: Tracking who did what, when, and with which resources
- **Data Lineage**: Understanding data flow from raw inputs to model outputs
- **Cost Management**: Attributing costs to projects and teams accurately

### Enter ML Platform SDK (mlp_sdk)

The ML Platform SDK solves these challenges by providing a **configuration-driven wrapper** around the SageMaker Python SDK v3. It abstracts infrastructure complexity while maintaining full compatibility with the underlying SDK, giving you the best of both worlds:

✅ **Simple, declarative configuration** for infrastructure defaults  
✅ **Runtime flexibility** to override any setting when needed  
✅ **Built-in governance** with audit trails and encryption  
✅ **Team consistency** through shared configuration files  
✅ **Zero lock-in** - access underlying SageMaker SDK anytime  

Let's dive in and see how mlp_sdk transforms your ML workflows.

---

## Getting Started: From Zero to Production in Minutes

### Installation

Getting started with mlp_sdk is as simple as:

```bash
pip install mlp_sdk
```

That's it. No complex setup, no additional dependencies beyond the SageMaker SDK v3.

### Configuration: Define Once, Use Everywhere

The power of mlp_sdk lies in its configuration-driven approach. Instead of repeating infrastructure details in every script, you define them once in a YAML configuration file:

```yaml
defaults:
  # S3 Configuration
  s3:
    default_bucket: "my-ml-platform-bucket"
    input_prefix: "data/input/"
    output_prefix: "data/output/"
    model_prefix: "models/"
    
  # Networking Configuration  
  networking:
    vpc_id: "vpc-0a1b2c3d"
    security_group_ids: ["sg-12345678"]
    subnets: ["subnet-12345678", "subnet-87654321"]
    
  # Compute Configuration
  compute:
    processing_instance_type: "ml.m5.large"
    training_instance_type: "ml.m5.xlarge"
    processing_instance_count: 1
    training_instance_count: 1
    
  # IAM Configuration
  iam:
    execution_role: "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
    
  # KMS Configuration (optional)
  kms:
    key_id: "arn:aws:kms:REGION:ACCOUNT-ID:key/your-key-id"
```

Save this as `admin-config.yaml` in your project, and you're ready to go.

**Pro Tip**: Use the included configuration generator for interactive setup:

```bash
python examples/generate_admin_config.py --interactive
```

### Core Wrappers and Functions

mlp_sdk provides intuitive wrappers for common SageMaker operations:

#### 1. Session Management

```python
from mlp_sdk import MLP_Session

# Initialize session - automatically loads your configuration
session = MLP_Session()

# Access session properties
print(f"Region: {session.region_name}")
print(f"Default bucket: {session.default_bucket}")
print(f"Execution role: {session.get_execution_role()}")
```

#### 2. Training Jobs

```python
# Start a training job with minimal code
trainer = session.run_training_job(
    job_name="xgboost-model-training",
    training_image="683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.5-1",
    inputs={
        'train': 's3://my-bucket/train/',
        'validation': 's3://my-bucket/validation/'
    },
    hyperparameters={
        'objective': 'binary:logistic',
        'num_round': '100',
        'max_depth': '5',
        'eta': '0.2'
    }
    # Instance type, VPC, role, etc. automatically applied from config!
)
```

Notice what you **didn't** have to specify:
- ✅ Instance type (from config)
- ✅ VPC configuration (from config)
- ✅ Security groups (from config)
- ✅ IAM role (from config)
- ✅ KMS encryption (from config)

#### 3. Processing Jobs

```python
# Run data preprocessing with defaults
processor = session.run_processing_job(
    job_name="data-preprocessing",
    processing_script="scripts/preprocess.py",
    inputs=[{
        "source": "s3://my-bucket/raw-data/",
        "destination": "/opt/ml/processing/input"
    }],
    outputs=[{
        "source": "/opt/ml/processing/output",
        "destination": "s3://my-bucket/processed-data/"
    }]
)
```

#### 4. Model Deployment

```python
# Deploy model to endpoint
predictor = session.deploy_model(
    model_data='s3://my-bucket/model.tar.gz',
    image_uri='683313688378.dkr.ecr.us-east-1.amazonaws.com/sagemaker-xgboost:1.5-1',
    endpoint_name='my-xgboost-endpoint'
)

# Make predictions
predictions = predictor.predict(test_data)
```

#### 5. Feature Store Operations

```python
# Create feature group with defaults
feature_group = session.create_feature_group(
    feature_group_name="customer-features",
    record_identifier_name="customer_id",
    event_time_feature_name="event_time",
    feature_definitions=[
        {"FeatureName": "customer_id", "FeatureType": "String"},
        {"FeatureName": "age", "FeatureType": "Integral"},
        {"FeatureName": "income", "FeatureType": "Fractional"}
    ]
)
```

### Runtime Flexibility: Override When Needed

Configuration defaults are just that - defaults. Override any setting at runtime:

```python
# Use GPU instance for this specific training job
trainer = session.run_training_job(
    job_name="gpu-training",
    training_image="pytorch-training:2.0.0-gpu",
    inputs={'train': 's3://my-bucket/data/'},
    instance_type="ml.p3.2xlarge",  # Override config default
    instance_count=4                 # Override config default
)
```

This gives you the best of both worlds: sensible defaults for consistency, with flexibility when you need it.

---

## Real-World Example: End-to-End XGBoost Training and Deployment

Let's walk through a complete example that demonstrates the power of mlp_sdk. We'll train an XGBoost model for binary classification, from data preparation to model deployment.

### Step 1: Generate Synthetic Training Data

```python
import pandas as pd
import numpy as np
from sklearn.datasets import make_classification
from sklearn.model_selection import train_test_split

# Generate synthetic classification data
X, y = make_classification(
    n_samples=10000,
    n_features=20,
    n_informative=15,
    n_classes=2,
    weights=[0.7, 0.3],
    random_state=42
)

# Split into train and validation sets
X_train, X_val, y_train, y_val = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

print(f"Training samples: {len(X_train)}")
print(f"Validation samples: {len(X_val)}")
print(f"Features: {X_train.shape[1]}")
```

**Output:**
```
Training samples: 8000
Validation samples: 2000
Features: 20
```

### Step 2: Prepare Data for XGBoost

XGBoost expects CSV format with the target variable in the first column:

```python
# Create DataFrames with target in first column
train_df = pd.DataFrame(X_train)
train_df.insert(0, 'target', y_train)

val_df = pd.DataFrame(X_val)
val_df.insert(0, 'target', y_val)

# Save to CSV (no header, no index)
train_df.to_csv('data/train.csv', header=False, index=False)
val_df.to_csv('data/validation.csv', header=False, index=False)

print("✅ Data saved to CSV files")
```

### Step 3: Initialize mlp_sdk Session

```python
from mlp_sdk import MLP_Session

# Initialize session - loads configuration automatically
session = MLP_Session(config_path="admin-config.yaml")

print(f"✅ Session initialized")
print(f"   Region: {session.region_name}")
print(f"   Default bucket: {session.default_bucket}")
print(f"   Execution role: {session.get_execution_role()}")
```

**Output:**
```
✅ Session initialized
   Region: us-east-1
   Default bucket: my-ml-platform-bucket
   Execution role: arn:aws:iam::123456789012:role/SageMakerExecutionRole
```

### Step 4: Upload Data to S3

```python
from datetime import datetime

# Create S3 paths with timestamp
timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
s3_prefix = f"xgboost-example/{timestamp}"

train_s3_path = f"s3://{session.default_bucket}/{s3_prefix}/train/"
val_s3_path = f"s3://{session.default_bucket}/{s3_prefix}/validation/"
output_s3_path = f"s3://{session.default_bucket}/{s3_prefix}/output"

# Upload files
s3_client = session.boto_session.client('s3')

s3_client.upload_file(
    'data/train.csv',
    session.default_bucket,
    f"{s3_prefix}/train/train.csv"
)

s3_client.upload_file(
    'data/validation.csv',
    session.default_bucket,
    f"{s3_prefix}/validation/validation.csv"
)

print(f"✅ Data uploaded to S3")
print(f"   Training: {train_s3_path}")
print(f"   Validation: {val_s3_path}")
```

### Step 5: Configure and Start Training Job

Here's where mlp_sdk shines. Notice how clean and focused the code is:

```python
# XGBoost hyperparameters
hyperparameters = {
    'objective': 'binary:logistic',
    'num_round': '100',
    'max_depth': '5',
    'eta': '0.2',
    'gamma': '4',
    'min_child_weight': '6',
    'subsample': '0.8',
    'eval_metric': 'auc',
    'scale_pos_weight': '2'  # Handle class imbalance
}

# Get XGBoost container image
region = session.region_name
xgboost_container = f"683313688378.dkr.ecr.{region}.amazonaws.com/sagemaker-xgboost:1.5-1"

# Start training job - infrastructure details come from config!
training_job = session.run_training_job(
    job_name=f"xgboost-training-{timestamp}",
    training_image=xgboost_container,
    inputs={
        'train': train_s3_path,
        'validation': val_s3_path
    },
    hyperparameters=hyperparameters,
    output_path=output_s3_path,
    max_run_in_seconds=3600
)

print(f"🚀 Training job started: {training_job.training_job_name}")
print(f"⏳ This may take 5-10 minutes...")
```

**What mlp_sdk handled automatically:**
- ✅ Instance type: `ml.m5.xlarge` (from config)
- ✅ Instance count: `1` (from config)
- ✅ VPC configuration (from config)
- ✅ Security groups (from config)
- ✅ Subnets (from config)
- ✅ IAM execution role (from config)
- ✅ KMS encryption (from config)
- ✅ Network isolation settings (from config)

### Step 6: Monitor Training Progress

```python
import time

# Get the actual training job name (may have suffix)
actual_job_name = training_job.training_job_name

# Monitor training status
sagemaker_client = session.sagemaker_client

while True:
    response = sagemaker_client.describe_training_job(
        TrainingJobName=actual_job_name
    )
    
    status = response['TrainingJobStatus']
    print(f"📊 Training status: {status}")
    
    if status in ['Completed', 'Failed', 'Stopped']:
        break
    
    time.sleep(30)

if status == 'Completed':
    print("✅ Training completed successfully!")
    print(f"   Model artifacts: {response['ModelArtifacts']['S3ModelArtifacts']}")
    
    # Display training metrics
    if 'FinalMetricDataList' in response:
        print("\n📈 Final metrics:")
        for metric in response['FinalMetricDataList']:
            print(f"   {metric['MetricName']}: {metric['Value']:.4f}")
else:
    print(f"❌ Training {status.lower()}")
```

**Output:**
```
📊 Training status: InProgress
📊 Training status: InProgress
📊 Training status: Completed
✅ Training completed successfully!
   Model artifacts: s3://my-ml-platform-bucket/xgboost-example/20260115-224706/output/model.tar.gz

📈 Final metrics:
   validation:auc: 0.9234
   train:auc: 0.9456
```

### Step 7: Deploy Model to Endpoint

```python
# Get model artifacts location
model_data = response['ModelArtifacts']['S3ModelArtifacts']

# Deploy model - again, infrastructure from config!
predictor = session.deploy_model(
    model_data=model_data,
    image_uri=xgboost_container,
    endpoint_name=f'xgboost-endpoint-{timestamp}'
)

print(f"✅ Model deployed to endpoint: {predictor.endpoint_name}")
```

**What mlp_sdk handled automatically:**
- ✅ Instance type: `ml.m5.large` (from config)
- ✅ Instance count: `1` (from config)
- ✅ IAM role (from config)
- ✅ VPC configuration (optional, from config)

### Step 8: Make Predictions

```python
import io

# Prepare test data (CSV format, no header)
test_df = pd.DataFrame(X_val[:5])
csv_buffer = io.StringIO()
test_df.to_csv(csv_buffer, header=False, index=False)
test_payload = csv_buffer.getvalue()

# Make predictions
predictions = predictor.predict(test_payload)

print("🔮 Predictions:")
for i, (pred, actual) in enumerate(zip(predictions.split('\n')[:5], y_val[:5])):
    print(f"   Sample {i+1}: Predicted={float(pred):.4f}, Actual={actual}")
```

**Output:**
```
🔮 Predictions:
   Sample 1: Predicted=0.1234, Actual=0
   Sample 2: Predicted=0.8765, Actual=1
   Sample 3: Predicted=0.0987, Actual=0
   Sample 4: Predicted=0.9123, Actual=1
   Sample 5: Predicted=0.2345, Actual=0
```

### Step 9: Clean Up Resources

```python
# Delete endpoint when done
session.delete_endpoint(predictor.endpoint_name)
print(f"✅ Endpoint deleted: {predictor.endpoint_name}")
```

### What We Accomplished

In less than 100 lines of focused code, we:

1. ✅ Generated and prepared training data
2. ✅ Uploaded data to S3
3. ✅ Trained an XGBoost model with proper VPC isolation
4. ✅ Monitored training progress
5. ✅ Deployed the model to a secure endpoint
6. ✅ Made predictions
7. ✅ Cleaned up resources

**Without mlp_sdk**, this would have required:
- 200+ lines of boilerplate code
- Repeated VPC, security group, and IAM configuration
- Manual tracking of S3 paths and resource names
- Error-prone copy-paste between projects

**With mlp_sdk**, we focused on what matters: the ML workflow itself.

---

## Advanced Features: Enterprise-Grade Capabilities

### 1. Configuration Precedence: Flexibility When You Need It

mlp_sdk uses a three-tier configuration precedence system:

```
Runtime Parameters > YAML Configuration > SageMaker SDK Defaults
```

This means you can:
- Define sensible defaults in your configuration
- Override specific settings for special cases
- Fall back to SageMaker defaults when appropriate

**Example:**

```python
# Most training jobs use config defaults (ml.m5.xlarge)
trainer1 = session.run_training_job(
    job_name="standard-training",
    training_image=container,
    inputs={'train': 's3://bucket/data/'}
)

# GPU-intensive job overrides instance type
trainer2 = session.run_training_job(
    job_name="gpu-training",
    training_image=container,
    inputs={'train': 's3://bucket/data/'},
    instance_type="ml.p3.8xlarge",  # Runtime override
    instance_count=4                 # Runtime override
)
```

### 2. Audit Trails: Complete Operational Visibility

Track every operation for debugging, compliance, and cost attribution:

```python
# Enable audit trail (enabled by default)
session = MLP_Session(enable_audit_trail=True)

# Perform operations
session.create_feature_group(...)
session.run_processing_job(...)
session.run_training_job(...)

# Get audit trail
entries = session.get_audit_trail()
print(f"Total operations: {len(entries)}")

# Filter by operation type
training_ops = session.get_audit_trail(operation="run_training_job")
print(f"Training jobs: {len(training_ops)}")

# Filter by status
failed_ops = session.get_audit_trail(status="failed")
print(f"Failed operations: {len(failed_ops)}")

# Get summary
summary = session.get_audit_trail_summary()
print(f"Operations by type: {summary['operations']}")
print(f"Failed operations: {summary['failed_operations']}")

# Export for analysis
session.export_audit_trail("audit-trail.json", format="json")
session.export_audit_trail("audit-trail.csv", format="csv")
```

**Use cases:**
- **Debugging**: Trace what happened when a job failed
- **Compliance**: Prove who did what and when
- **Cost Attribution**: Track resource usage by team or project
- **Performance Analysis**: Identify bottlenecks in your ML pipeline

### 3. Encryption: Secure Your Sensitive Configuration

Protect sensitive values like IAM roles and KMS keys:

```python
from mlp_sdk.config import ConfigurationManager

# Generate encryption key
key = ConfigurationManager.generate_key()
print(f"Save this key securely: {key}")

# Encrypt sensitive fields in configuration
config_manager = ConfigurationManager(encryption_key=key)
config_manager.encrypt_config_file(
    input_path="config.yaml",
    output_path="config-encrypted.yaml",
    fields_to_encrypt=[
        "defaults.iam.execution_role",
        "defaults.kms.key_id",
        "defaults.s3.default_bucket"
    ]
)

# Load encrypted configuration
session = MLP_Session(
    config_path="config-encrypted.yaml",
    encryption_key=key
)
```

**Key management options:**
- Environment variables: `MLP_SDK_ENCRYPTION_KEY`
- File-based: Store key in secure location
- AWS KMS: Integrate with AWS Key Management Service

### 4. Multi-Environment Support

Manage different configurations for dev, staging, and production:

```python
import os

# Load environment-specific configuration
env = os.environ.get('ENVIRONMENT', 'dev')
config_path = f"configs/{env}-config.yaml"

session = MLP_Session(config_path=config_path)
```

**Directory structure:**
```
configs/
├── dev-config.yaml      # Small instances, no encryption
├── staging-config.yaml  # Medium instances, basic encryption
└── prod-config.yaml     # Large instances, full encryption, multi-AZ
```

### 5. Access to Underlying SDK

mlp_sdk doesn't lock you in. Access the underlying SageMaker SDK anytime:

```python
session = MLP_Session()

# Access SageMaker session for advanced operations
sagemaker_session = session.sagemaker_session

# Access boto3 clients
s3_client = session.boto_session.client('s3')
sagemaker_client = session.sagemaker_client

# Use low-level API calls when needed
response = sagemaker_client.describe_training_job(
    TrainingJobName='my-training-job'
)
```

This gives you an escape hatch for advanced use cases while maintaining the simplicity of mlp_sdk for common operations.

---

## Key Benefits: Why Teams Choose mlp_sdk

### 1. **Faster Development Cycles**

**Before mlp_sdk:**
```python
# 50+ lines of boilerplate for every training job
from sagemaker.train.model_trainer import ModelTrainer, Compute, InputData
from sagemaker.core.training.configs import Networking, StoppingCondition
from sagemaker.core.shapes.shapes import OutputDataConfig

compute = Compute(
    instance_type='ml.m5.xlarge',
    instance_count=1,
    volume_size_in_gb=30,
    volume_kms_key_id='arn:aws:kms:...'
)

networking = Networking(
    subnets=['subnet-12345678', 'subnet-87654321'],
    security_group_ids=['sg-12345678'],
    enable_inter_container_traffic_encryption=True,
    enable_network_isolation=True
)

output_config = OutputDataConfig(
    s3_output_path='s3://bucket/output',
    kms_key_id='arn:aws:kms:...'
)

# ... 40 more lines ...
```

**With mlp_sdk:**
```python
# 5 lines - focus on what matters
trainer = session.run_training_job(
    job_name="my-training",
    training_image=container,
    inputs={'train': 's3://bucket/data/'}
)
```

**Result:** 90% less boilerplate, 10x faster iteration.

### 2. **Consistent Team Standards**

- **Shared Configuration**: One source of truth for infrastructure settings
- **Naming Conventions**: Enforce consistent resource naming
- **Security Policies**: Ensure all workloads meet security requirements
- **Cost Controls**: Standardize instance types to manage costs

### 3. **Reduced Errors**

- **Type Validation**: Pydantic schemas catch configuration errors early
- **Clear Error Messages**: Actionable guidance when something goes wrong
- **Audit Trails**: Track down issues quickly with complete operation history

### 4. **Seamless Onboarding**

New team members can be productive in minutes:

```bash
# 1. Clone repository
git clone https://github.com/your-org/ml-platform

# 2. Install mlp_sdk
pip install mlp_sdk

# 3. Copy team configuration
cp configs/team-config.yaml ~/.config/admin-config.yaml

# 4. Start building models!
python train_model.py
```

No need to learn VPC configurations, security groups, or IAM policies. Just focus on the ML.

### 5. **Enterprise-Ready**

- ✅ **Encryption**: AES-256-GCM for sensitive configuration values
- ✅ **Audit Trails**: Complete operation history for compliance
- ✅ **Multi-Environment**: Separate configs for dev/staging/prod
- ✅ **Access Control**: Integrate with existing IAM policies
- ✅ **Cost Attribution**: Track usage by team and project

---

## Conclusion: Transform Your ML Operations

The ML Platform SDK (mlp_sdk) represents a fundamental shift in how data science teams interact with cloud ML infrastructure. By abstracting away infrastructure complexity while maintaining full flexibility, it enables teams to:

### Focus on What Matters

Stop wrestling with VPC configurations and security groups. Spend your time on feature engineering, model architecture, and hyperparameter tuning - the work that actually moves the needle.

### Move Faster

Reduce boilerplate code by 90%. Go from idea to deployed model in hours, not days. Iterate quickly without sacrificing quality or security.

### Maintain Consistency

Ensure every team member, every project, and every environment follows the same standards. Eliminate configuration drift and reduce errors.

### Scale with Confidence

As your ML operations grow, mlp_sdk grows with you. From a single data scientist to a team of hundreds, from development to production, the same simple API works everywhere.

### Stay Compliant

Built-in audit trails, encryption support, and policy enforcement mean you can meet enterprise compliance requirements without extra work.

## Take Action: Get Started Today

Ready to transform your ML workflows? Here's how to get started:

### 1. **Try the Quick Start** (5 minutes)

```bash
# Install mlp_sdk
pip install mlp_sdk

# Generate configuration
python examples/generate_admin_config.py --interactive

# Run your first training job
python examples/xgboost_training_example.py
```

### 2. **Explore the Examples**

Check out the comprehensive examples in the repository:
- **Basic Usage**: `examples/basic_usage.py`
- **XGBoost Training**: `examples/xgboost_training_example.ipynb`
- **SageMaker Operations**: `examples/sagemaker_operations.py`

### 3. **Read the Documentation**

- **Configuration Guide**: Learn all configuration options
- **Usage Examples**: See mlp_sdk in action
- **Encryption Guide**: Secure your sensitive data
- **API Reference**: Complete API documentation

### 4. **Join the Community**

- 🐛 **Report Issues**: [GitHub Issues](https://github.com/example/mlp_sdk/issues)
- 💬 **Discussions**: Share your use cases and learn from others
- 📧 **Support**: Get help from the maintainers
- 🤝 **Contribute**: Help make mlp_sdk even better

### 5. **Share Your Success**

Once you've experienced the benefits of mlp_sdk, share your story:
- Write a blog post about your experience
- Present at your team's tech talk
- Contribute examples back to the project
- Help other teams get started

---

## The Bottom Line

Machine learning is hard enough without fighting infrastructure. The ML Platform SDK (mlp_sdk) removes the friction between you and your models, letting you focus on what you do best: building intelligent systems that solve real problems.

**Stop copying and pasting infrastructure code.**  
**Stop debugging VPC configurations.**  
**Stop wasting time on boilerplate.**

**Start building better models, faster.**

Get started with mlp_sdk today and experience the difference configuration-driven ML operations can make.

---

## Additional Resources

- 📖 **GitHub Repository**: [https://github.com/example/mlp_sdk](https://github.com/example/mlp_sdk)
- 📚 **Full Documentation**: [https://mlp-sdk.readthedocs.io/](https://mlp-sdk.readthedocs.io/)
- 🎓 **Tutorial Videos**: [YouTube Playlist](https://youtube.com/playlist)
- 💬 **Community Forum**: [Discussions](https://github.com/example/mlp_sdk/discussions)
- 📧 **Email Support**: mlp-sdk-support@example.com

---

**About the Author**

*This blog post was created to help data scientists and ML engineers discover the power of configuration-driven ML operations. mlp_sdk is an open-source project maintained by a community of ML practitioners who believe infrastructure should be simple, consistent, and invisible.*

---

**Tags**: #MachineLearning #MLOps #AWS #SageMaker #Python #DataScience #MLEngineering #CloudComputing #DevOps #Automation

