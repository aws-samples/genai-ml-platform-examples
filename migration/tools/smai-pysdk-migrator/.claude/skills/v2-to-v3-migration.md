# SageMaker SDK V2 to V3 Migration Skill

This skill helps migrate SageMaker Python SDK code from V2 to V3 APIs.

## Usage

Invoke this skill when:
- User asks to migrate V2 code to V3
- User provides notebooks or scripts using V2 APIs (Estimators, Models, boto3 training APIs)
- User wants to understand V3 equivalents for V2 code

## Quick Reference: Critical Parameter Changes

When migrating to V3, watch out for these parameter name changes:

| V2/boto3 Parameter | V3 Parameter | Component |
|--------------------|--------------|-----------|
| `model_data` | `s3_model_data_url` | ModelBuilder |
| `role` | `role_arn` | ModelBuilder |
| `predictor.predict()` | `endpoint.invoke()` | Inference |
| `predictor.delete_endpoint()` | `endpoint.delete()` | Cleanup |
| Serializers/Deserializers | Manual parsing | Inference |

## Quick Reference: Object Type Changes

| V2 SDK | V3 SDK | Key Difference |
|--------|--------|----------------|
| `Predictor` | `Endpoint` | Use `.invoke()` not `.predict()` |
| `predictor.predict(data)` | `endpoint.invoke(body=data, content_type=...)` | Must specify content_type |
| Auto deserialization | Manual parsing | Parse `result.body.read().decode('utf-8')` |

## Migration Patterns

### 1. Session and Role

**V2 Pattern:**
```python
import sagemaker

sess = sagemaker.Session()
role = sagemaker.get_execution_role()
```

**V3 Pattern:**
```python
from sagemaker.core.helper.session_helper import Session, get_execution_role

sagemaker_session = Session()
role = get_execution_role()
```

### 2. Image URIs

**V2 Pattern:**
```python
from sagemaker import image_uris

container = image_uris.retrieve("xgboost", region, "1.7-1")
```

**V3 Pattern:**
```python
from sagemaker.core import image_uris

container = image_uris.retrieve("xgboost", region, "1.7-1")
```

### 3. Training Jobs

**V2 Pattern (Estimator):**
```python
from sagemaker.estimator import Estimator

estimator = Estimator(
    image_uri=container,
    role=role,
    instance_type='ml.m5.xlarge',
    instance_count=1,
    volume_size=5,
    max_run=3600,
    output_path=output_path,
    hyperparameters={...}
)

estimator.fit({'train': train_input, 'validation': val_input})
```

**V2 Pattern (Raw boto3):**
```python
sm_client = boto3.client('sagemaker')

response = sm_client.create_training_job(
    TrainingJobName='my-job',
    AlgorithmSpecification={
        'TrainingImage': container,
        'TrainingInputMode': 'File'
    },
    RoleArn=role,
    InputDataConfig=[
        {
            'ChannelName': 'train',
            'DataSource': {
                'S3DataSource': {
                    'S3DataType': 'S3Prefix',
                    'S3Uri': 's3://bucket/train',
                    'S3DataDistributionType': 'FullyReplicated'
                }
            },
            'ContentType': 'libsvm'
        }
    ],
    OutputDataConfig={
        'S3OutputPath': 's3://bucket/output'
    },
    ResourceConfig={
        'InstanceType': 'ml.m5.xlarge',
        'InstanceCount': 1,
        'VolumeSizeInGB': 5
    },
    StoppingCondition={
        'MaxRuntimeInSeconds': 3600
    },
    HyperParameters={...}
)
```

**V3 Pattern (ModelTrainer):**
```python
from sagemaker.train import ModelTrainer
from sagemaker.train.configs import InputData, Compute, StoppingCondition, OutputDataConfig

train_input = InputData(
    channel_name="train",
    data_source="s3://bucket/path/train",
    content_type="libsvm"
)

validation_input = InputData(
    channel_name="validation",
    data_source="s3://bucket/path/validation",
    content_type="libsvm"
)

compute_config = Compute(
    instance_type="ml.m5.xlarge",
    instance_count=1,
    volume_size_in_gb=5
)

stopping_config = StoppingCondition(max_runtime_in_seconds=3600)

output_config = OutputDataConfig(
    s3_output_path="s3://bucket/path/output"
)

trainer = ModelTrainer(
    training_image=container,
    role=role,
    compute=compute_config,
    stopping_condition=stopping_config,
    output_data_config=output_config,
    hyperparameters={
        "max_depth": "5",
        "eta": "0.2",
        "objective": "reg:linear",
        "num_round": "50"
    }
)

trainer.train(
    input_data_config=[train_input, validation_input],
    wait=True
)

# Access model artifacts
model_artifacts = trainer._latest_training_job.model_artifacts.s3_model_artifacts
```

### 4. Hyperparameter Tuning

**V2 Pattern (HyperparameterTuner):**
```python
from sagemaker.tuner import HyperparameterTuner

tuner = HyperparameterTuner(
    estimator=estimator,
    objective_metric_name='validation:rmse',
    objective_type='Minimize',
    hyperparameter_ranges=hyperparameter_ranges,
    max_jobs=20,
    max_parallel_jobs=3
)

tuner.fit({'train': train_input, 'validation': val_input})
```

**V3 Pattern (HyperparameterTuner):**
```python
from sagemaker.train.tuner import HyperparameterTuner
from sagemaker.core.parameter import ContinuousParameter, IntegerParameter

hyperparameter_ranges = {
    "eta": ContinuousParameter(min_value=0.1, max_value=0.5),
    "gamma": ContinuousParameter(min_value=0, max_value=5),
    "max_depth": IntegerParameter(min_value=0, max_value=10),
    "num_round": IntegerParameter(min_value=1, max_value=4000),
}

# Create base trainer with static hyperparameters only
# Note: Pass sagemaker_session to ModelTrainer if needed, NOT to HyperparameterTuner
base_trainer = ModelTrainer(
    training_image=container,
    role=role,
    compute=compute_config,
    stopping_condition=stopping_config,
    output_data_config=output_config,
    hyperparameters={
        "objective": "reg:linear",
        "verbosity": "2"
    },
    sagemaker_session=sagemaker_session  # Pass to ModelTrainer
)

# Don't pass sagemaker_session to HyperparameterTuner
tuner = HyperparameterTuner(
    model_trainer=base_trainer,
    objective_metric_name="validation:rmse",
    objective_type="Minimize",
    hyperparameter_ranges=hyperparameter_ranges,
    max_jobs=20,
    max_parallel_jobs=3,
    strategy="Bayesian"
    # No sagemaker_session parameter
)

tuner.tune(
    inputs=[train_input, validation_input],
    wait=True
)

# Get best training job name
best_job_name = tuner.best_training_job()

# Get model artifacts from best training job
# Note: TrainingJob.get() doesn't accept sagemaker_session parameter
from sagemaker.core.resources import TrainingJob
best_training_job = TrainingJob.get(training_job_name=best_job_name)
model_data = best_training_job.model_artifacts.s3_model_artifacts
```

### 5. Model Deployment

**V2 Pattern (Model + deploy):**
```python
from sagemaker.model import Model

model = Model(
    model_data=model_artifacts,
    image_uri=container,
    role=role
)

predictor = model.deploy(
    instance_type='ml.m5.xlarge',
    initial_instance_count=1,
    endpoint_name='my-endpoint'
)
```

**V2 Pattern (boto3 3-step deployment):**
```python
# Step 1: Create model
client.create_model(
    ModelName=model_name,
    ExecutionRoleArn=role,
    PrimaryContainer={
        "Image": container,
        "ModelDataUrl": model_data
    }
)

# Step 2: Create endpoint config
client.create_endpoint_config(
    EndpointConfigName=endpoint_config_name,
    ProductionVariants=[{
        "InstanceType": "ml.m5.xlarge",
        "InitialInstanceCount": 1,
        "ModelName": model_name,
        "VariantName": "AllTraffic"
    }]
)

# Step 3: Create endpoint
client.create_endpoint(
    EndpointName=endpoint_name,
    EndpointConfigName=endpoint_config_name
)
```

**V3 Pattern (ModelBuilder):**
```python
from sagemaker.serve.model_builder import ModelBuilder
from sagemaker.serve.mode.function_pointers import Mode

# IMPORTANT: Use correct parameter names!
# - s3_model_data_url (NOT model_data)
# - role_arn (NOT role)
model_builder = ModelBuilder(
    s3_model_data_url=model_artifacts,  # NOT model_data
    role_arn=role,                       # NOT role
    image_uri=container,
    mode=Mode.SAGEMAKER_ENDPOINT,
    sagemaker_session=sagemaker_session
)

# Build the model (creates Model resource)
model = model_builder.build()

# Deploy to endpoint
# IMPORTANT: Call deploy() on model_builder, NOT on model
endpoint = model_builder.deploy(
    instance_type="ml.m5.xlarge",
    initial_instance_count=1,
    endpoint_name="my-endpoint",
    wait=True
)

print(f"Endpoint deployed: {endpoint.endpoint_name}")
```

### 6. Prediction / Inference

**V2 Pattern:**
```python
from sagemaker.serializers import LibSVMSerializer
from sagemaker.deserializers import CSVDeserializer

predictor.serializer = LibSVMSerializer()
predictor.deserializer = CSVDeserializer()

# Automatic serialization/deserialization
result = predictor.predict(data)
```

**V2 Pattern (boto3):**
```python
runtime_client = boto3.client("runtime.sagemaker")
response = runtime_client.invoke_endpoint(
    EndpointName=endpoint_name,
    ContentType="text/x-libsvm",
    Body=payload
)
result = response["Body"].read().decode("utf-8")
```

**V3 Pattern:**
```python
# V3 does NOT use serializers/deserializers
# Handle serialization manually

# Make prediction using endpoint.invoke()
result = endpoint.invoke(
    body=payload,                    # Raw payload data
    content_type="text/x-libsvm"     # MIME type required
)

# Parse response manually
response_body = result.body.read().decode('utf-8')

# Handle different response formats (XGBoost can return various formats)
if '\n' in response_body.strip():
    # Batch predictions are newline-separated
    predictions = [float(num.strip()) for num in response_body.strip().split('\n') if num.strip()]
elif ',' in response_body.strip():
    # Some predictions are comma-separated
    predictions = [float(num.strip()) for num in response_body.strip().split(',') if num.strip()]
else:
    # Single value
    predictions = [float(response_body.strip())]
```

### 7. Cleanup

**V2 Pattern:**
```python
predictor.delete_endpoint(delete_endpoint_config=True)
```

**V3 Pattern:**
```python
# Get endpoint config name before deleting
endpoint_config_name = endpoint.endpoint_config_name

# Delete the endpoint
endpoint.delete()

# Delete the endpoint config separately
from sagemaker.core.resources import EndpointConfig
endpoint_config = EndpointConfig.get(endpoint_config_name=endpoint_config_name)
endpoint_config.delete()
```

## Key Differences Summary

| Aspect | V2 | V3 |
|--------|----|----|
| Training | `Estimator` or boto3 `create_training_job` | `ModelTrainer` |
| Tuning | `HyperparameterTuner` with estimator | `HyperparameterTuner` with `ModelTrainer` |
| Deployment | `Model.deploy()` | `ModelBuilder.build()` then `ModelBuilder.deploy()` |
| Inference | `predictor.predict()` with serializers | `endpoint.invoke()` with manual parsing |
| Config | Dict-based | Pydantic config classes (`InputData`, `Compute`, etc.) |
| Session | `sagemaker.Session()` | `sagemaker.core.helper.session_helper.Session()` |
| Image URIs | `sagemaker.image_uris` | `sagemaker.core.image_uris` |
| Cleanup | `predictor.delete_endpoint()` | `endpoint.delete()` + `EndpointConfig.delete()` |
| RecordIO Utils | `sagemaker.amazon.common` | `sagemaker.core.serializers.utils` |

## Common Pitfalls and Errors

### 1. TypeError: ModelBuilder.__init__() got an unexpected keyword argument 'model_data'

**Wrong:**
```python
model_builder = ModelBuilder(
    model_data=model_data,  # WRONG parameter name
    role=role,              # WRONG parameter name
    image_uri=container
)
```

**Correct:**
```python
model_builder = ModelBuilder(
    s3_model_data_url=model_data,  # Correct
    role_arn=role,                  # Correct
    image_uri=container
)
```

### 2. AttributeError: 'Model' object has no attribute 'deploy'

**Wrong:**
```python
model_builder = ModelBuilder(...)
model = model_builder.build()
endpoint = model.deploy(...)  # WRONG - Model doesn't have deploy()
```

**Correct:**
```python
model_builder = ModelBuilder(...)
model = model_builder.build()
endpoint = model_builder.deploy(...)  # Correct - call on model_builder
```

### 3. Using Predictor API on Endpoint Object

**Wrong:**
```python
endpoint = model_builder.deploy(...)
endpoint.serializer = LibSVMSerializer()  # WRONG - V3 Endpoint doesn't have serializers
result = endpoint.predict(payload)         # WRONG - Endpoint has invoke(), not predict()
```

**Correct:**
```python
endpoint = model_builder.deploy(...)
result = endpoint.invoke(
    body=payload,
    content_type="text/x-libsvm"
)
response_str = result.body.read().decode('utf-8')
predictions = [float(i) for i in response_str.strip().split(',')]
```

### 4. Accessing Training Job Outputs from Tuner

**Wrong:**
```python
best_job_name = tuner.best_training_job()
model_data = best_job_name.model_artifacts  # WRONG - it's just a string
```

**Correct:**
```python
from sagemaker.core.resources import TrainingJob

best_job_name = tuner.best_training_job()  # Returns string
best_training_job = TrainingJob.get(training_job_name=best_job_name)  # Get resource
model_data = best_training_job.model_artifacts.s3_model_artifacts
```

### 5. ValueError when parsing predictions

**Problem:** XGBoost returns different response formats depending on batch size.

**Solution:** Handle multiple formats:
```python
response_body = result.body.read().decode('utf-8')

if '\n' in response_body.strip():
    predictions = [float(num.strip()) for num in response_body.strip().split('\n') if num.strip()]
elif ',' in response_body.strip():
    predictions = [float(num.strip()) for num in response_body.strip().split(',') if num.strip()]
else:
    predictions = [float(response_body.strip())]
```

### 6. ValidationError: Extra inputs are not permitted for 'compression'

**Wrong:**
```python
train_input = InputData(
    channel_name="train",
    data_source="s3://bucket/path/train",
    content_type="libsvm",
    compression="None"  # WRONG - passing string "None"
)
```

**Correct:**
```python
train_input = InputData(
    channel_name="train",
    data_source="s3://bucket/path/train",
    content_type="libsvm"  # Correct - omit compression if not needed
)
```

### 7. ValidationError: Extra inputs are not permitted for 'training_job_name'

**Wrong:**
```python
trainer = ModelTrainer(
    training_job_name="my-training-job",  # WRONG - not allowed in V3
    training_image=container,
    role=role,
    # ...
)
```

**Correct:**
```python
# Job names are auto-generated in V3
trainer = ModelTrainer(
    training_image=container,
    role=role,
    compute=Compute(...),
    # ...
)

# Start training
trainer.train(input_data_config=[train_input], wait=True)

# Get the auto-generated job name after training
training_job_name = trainer._latest_training_job.training_job_name
print(f"Training job name: {training_job_name}")
```

### 8. ValidationError: Extra inputs are not permitted for 'tuning_job_name'

**Wrong:**
```python
tuner = HyperparameterTuner(
    tuning_job_name="my-tuning-job",  # WRONG - not allowed in V3
    model_trainer=base_trainer,
    # ...
)
```

**Correct:**
```python
# Tuning job names are auto-generated in V3
tuner = HyperparameterTuner(
    model_trainer=base_trainer,
    objective_metric_name="validation:rmse",
    hyperparameter_ranges=hyperparameter_ranges,
    # ...
)

# Start tuning
tuner.tune(inputs=[train_input, validation_input], wait=True)

# Get the auto-generated job name after tuning
tuning_job_name = tuner._current_job_name
print(f"Tuning job name: {tuning_job_name}")
```

### 9. ImportError: cannot import name 'ContinuousParameter' from 'sagemaker.train.configs'

**Wrong:**
```python
from sagemaker.train.configs import ContinuousParameter, IntegerParameter  # WRONG import path
```

**Correct:**
```python
from sagemaker.core.parameter import ContinuousParameter, IntegerParameter  # Correct path

hyperparameter_ranges = {
    "eta": ContinuousParameter(0.1, 0.5),
    "max_depth": IntegerParameter(0, 10),
}
```

### 10. TypeError: HyperparameterTuner got unexpected keyword argument 'sagemaker_session'

**Wrong:**
```python
tuner = HyperparameterTuner(
    model_trainer=base_trainer,
    objective_metric_name="validation:rmse",
    sagemaker_session=sagemaker_session,  # WRONG - not accepted
)
```

**Correct:**
```python
# Pass sagemaker_session to the base ModelTrainer, not the tuner
base_trainer = ModelTrainer(
    training_image=container,
    role=role,
    compute=Compute(...),
    sagemaker_session=sagemaker_session  # Correct - pass to ModelTrainer
)

# Don't pass sagemaker_session to HyperparameterTuner
tuner = HyperparameterTuner(
    model_trainer=base_trainer,  # Session is inherited from base_trainer
    objective_metric_name="validation:rmse",
    hyperparameter_ranges=hyperparameter_ranges
)
```

### 11. ValidationError: TrainingJob.get() unexpected keyword argument 'sagemaker_session'

**Wrong:**
```python
training_job = TrainingJob.get(
    training_job_name=job_name,
    sagemaker_session=sagemaker_session  # WRONG - not accepted
)
```

**Correct:**
```python
# Don't pass sagemaker_session to TrainingJob.get()
training_job = TrainingJob.get(training_job_name=job_name)  # Correct
model_data = training_job.model_artifacts.s3_model_artifacts
```

### 12. ValidationError: Endpoint.delete() unexpected keyword argument 'delete_endpoint_config'

**Wrong:**
```python
endpoint.delete(delete_endpoint_config=True)  # WRONG - parameter not supported
```

**Correct:**
```python
# Get endpoint config name before deleting endpoint
endpoint_config_name = endpoint.endpoint_config_name

# Delete the endpoint
endpoint.delete()

# Delete the endpoint config separately
from sagemaker.core.resources import EndpointConfig
endpoint_config = EndpointConfig.get(endpoint_config_name=endpoint_config_name)
endpoint_config.delete()
```

### 13. TypeError: expected string or bytes-like object (S3 bucket issue)

**Problem:** `default_bucket` might be a property or method, and could return `None`.

**Solution:**
```python
# Handle both property and method access
output_bucket = sagemaker_session.default_bucket
if callable(output_bucket):
    output_bucket = output_bucket()

# Fallback if still not valid
if not isinstance(output_bucket, str) or not output_bucket:
    account_id = boto3.client('sts').get_caller_identity()['Account']
    output_bucket = f"sagemaker-{region}-{account_id}"

# Ensure bucket exists
try:
    s3_client.head_bucket(Bucket=output_bucket)
except s3_client.exceptions.NoSuchBucket:
    if region == 'us-east-1':
        s3_client.create_bucket(Bucket=output_bucket)
    else:
        s3_client.create_bucket(
            Bucket=output_bucket,
            CreateBucketConfiguration={'LocationConstraint': region}
        )
```

## Instructions for Migration

When migrating code:

1. **Update imports** - Change to V3 import paths first (see checklist below)
2. **Identify V2 patterns** - Look for `Estimator`, `Model`, `Predictor`, boto3 training APIs
3. **Map to V3 equivalents** - Use the patterns above
4. **Use config classes** - Replace dicts with Pydantic config classes
5. **Fix parameter names** - `s3_model_data_url` not `model_data`, `role_arn` not `role`
6. **Remove custom job names** - Don't pass `training_job_name` or `tuning_job_name`
7. **Remove invalid parameters** - Don't pass `compression="None"` to `InputData`
8. **Fix import paths** - Use `sagemaker.core.parameter` for `ContinuousParameter`/`IntegerParameter`
9. **Fix session handling** - Don't pass `sagemaker_session` to `HyperparameterTuner` or `.get()` methods
10. **Handle bucket names** - Check if `default_bucket` is callable and validate it's a string
11. **Update inference code** - Replace `predictor.predict()` with `endpoint.invoke()`
12. **Remove serializers** - Handle serialization/deserialization manually
13. **Fix cleanup code** - Delete endpoint and endpoint config separately (no `delete_endpoint_config=True`)
14. **Test thoroughly** - Ensure behavior is preserved

## Migration Checklist

### Imports
- [ ] `from sagemaker.core.helper.session_helper import Session, get_execution_role`
- [ ] `from sagemaker.core import image_uris`
- [ ] `from sagemaker.train import ModelTrainer`
- [ ] `from sagemaker.train.configs import InputData, Compute, StoppingCondition, OutputDataConfig`
- [ ] `from sagemaker.train.tuner import HyperparameterTuner`
- [ ] `from sagemaker.core.parameter import ContinuousParameter, IntegerParameter`
- [ ] `from sagemaker.serve.model_builder import ModelBuilder`
- [ ] `from sagemaker.serve.mode.function_pointers import Mode`
- [ ] `from sagemaker.core.resources import TrainingJob, EndpointConfig`
- [ ] `from sagemaker.core.serializers.utils import write_numpy_to_dense_tensor` (replaces `sagemaker.amazon.common`)

### Training
- [ ] Replace `Estimator` or `create_training_job()` with `ModelTrainer.train()`
- [ ] Use typed config classes: `InputData`, `Compute`, `StoppingCondition`, `OutputDataConfig`
- [ ] **Remove `training_job_name` parameter** - job names are auto-generated in V3
- [ ] **Remove `compression="None"` from `InputData`** - omit parameter if not needed
- [ ] Access job name after training: `trainer._latest_training_job.training_job_name`
- [ ] Replace `HyperparameterTuner.fit()` with `HyperparameterTuner.tune()`
- [ ] Use `tuner.tune(inputs=[...])` not `tuner.fit({...})`
- [ ] **Remove `tuning_job_name` parameter** - job names are auto-generated in V3
- [ ] **Don't pass `sagemaker_session` to HyperparameterTuner** - pass to base ModelTrainer instead
- [ ] Access tuning job name after completion: `tuner._current_job_name`
- [ ] Import parameters from correct location: `from sagemaker.core.parameter import ContinuousParameter, IntegerParameter`

### Deployment
- [ ] Use `s3_model_data_url` parameter (NOT `model_data`)
- [ ] Use `role_arn` parameter (NOT `role`)
- [ ] Call `model_builder.build()` to create Model resource
- [ ] Call `model_builder.deploy()` (NOT `model.deploy()`) to create Endpoint

### Inference
- [ ] Replace `predictor.predict()` with `endpoint.invoke()`
- [ ] Add `content_type` parameter to `endpoint.invoke()`
- [ ] Remove all serializers/deserializers
- [ ] Parse response manually: `result.body.read().decode('utf-8')`

### Cleanup
- [ ] Replace `predictor.delete_endpoint()` with `endpoint.delete()`
- [ ] **Don't use `delete_endpoint_config=True`** - not supported in V3
- [ ] Delete endpoint and endpoint config separately
- [ ] Get endpoint config name before deleting: `endpoint.endpoint_config_name`
- [ ] Use `EndpointConfig.get()` and `endpoint_config.delete()` to delete config

### Training Job Artifacts
- [ ] Access model artifacts via `trainer._latest_training_job.model_artifacts.s3_model_artifacts`
- [ ] For tuning jobs, use `TrainingJob.get(training_job_name=best_job_name)` to get artifacts
- [ ] **Don't pass `sagemaker_session` to `.get()` methods** - `TrainingJob.get()`, `EndpointConfig.get()`, etc.

### Session and Bucket Configuration
- [ ] Handle `default_bucket` carefully - it may be a property or method
- [ ] Check if `default_bucket` is callable and call it if needed
- [ ] Validate bucket name is a string before using
- [ ] Create bucket if it doesn't exist (with proper region configuration)

## Complete Example

See [v2-to-v3-migration/sm-regression_xgboost_v3.ipynb](../../../v2-to-v3-migration/sm-regression_xgboost_v3.ipynb) for a complete working example.

## Examples Location

See `v3-examples/` directory in the repository for more examples:
- `training-examples/` - ModelTrainer usage
- `inference-examples/` - ModelBuilder usage
- `model-customization-examples/` - Fine-tuning examples
