# SageMaker Python SDK V2 to V3 Migration Tool

This directory contains a Claude Code skill that helps you migrate Amazon SageMaker Python SDK code from version 2 to version 3.

## What is the v2-to-v3-migration Skill?

The v2-to-v3-migration skill is an AI-powered assistant that automatically converts SageMaker SDK V2 code to the new V3 API patterns. It handles the complex migration patterns, parameter name changes, and API restructuring required when upgrading from SDK V2 to V3.

## Key Features

- **Automatic code migration** - Converts V2 patterns (Estimator, Model, Predictor) to V3 patterns (ModelTrainer, ModelBuilder, Endpoint)
- **Parameter name fixing** - Automatically corrects parameter name changes (e.g., `model_data` → `s3_model_data_url`, `role` → `role_arn`)
- **Import path updates** - Updates all import statements to V3 module paths
- **Config class conversion** - Replaces dictionary configurations with typed Pydantic classes
- **Inference code updates** - Migrates from `predictor.predict()` to `endpoint.invoke()` with manual serialization
- **Error prevention** - Avoids common migration pitfalls and validation errors
- **Complete notebook migration** - Can migrate entire Jupyter notebooks at once

## Prerequisites

- Claude Code CLI installed and configured or VS Code installed with Claude Code plugin
- Access to SageMaker notebooks or Python scripts using SDK V2
- Basic familiarity with SageMaker concepts (training, deployment, inference)

## How to Use the Skill

### Method 1: Invoke Directly with a File Path

Navigate to the directory containing your V2 code and invoke the skill:

```bash
cd /path/to/your/project
claude
```

Then in the Claude Code session:

```
/v2-to-v3-migration path/to/your_notebook.ipynb
```

Or for Python scripts:

```
/v2-to-v3-migration path/to/your_script.py
```

### Method 2: Natural Language Request

You can also describe what you need:

```
Please migrate my SageMaker notebook from SDK V2 to V3. The file is at notebooks/training.ipynb
```

```
Help me convert this V2 training code to V3: [paste code snippet]
```

```
I have a notebook using Estimator and Model.deploy() - can you migrate it to V3?
```

### Method 3: From Within a Notebook

If you have a notebook open in your IDE:

1. Open the V2 notebook in VSCode or your IDE
2. Start Claude Code
3. Type: `/v2-to-v3-migration` or "Migrate this notebook to SDK V3"

The skill will automatically detect the open file and migrate it.

## What Gets Migrated

The skill handles these common V2 → V3 migrations:

### 1. **Session and Role Initialization**
- `sagemaker.Session()` → `sagemaker.core.helper.session_helper.Session()`
- `sagemaker.get_execution_role()` → `get_execution_role()` from session_helper

### 2. **Training Jobs**
- `Estimator` classes → `ModelTrainer` with config classes
- `estimator.fit()` → `trainer.train()`
- boto3 `create_training_job()` → `ModelTrainer`
- Dictionary configurations → Typed config classes (`InputData`, `Compute`, `OutputDataConfig`)

### 3. **Hyperparameter Tuning**
- `HyperparameterTuner` with Estimator → `HyperparameterTuner` with `ModelTrainer`
- `tuner.fit()` → `tuner.tune()`
- Parameter range definitions with proper import paths

### 4. **Model Deployment**
- `Model.deploy()` → `ModelBuilder.build()` + `ModelBuilder.deploy()`
- 3-step boto3 deployment → Single `ModelBuilder` workflow
- Parameter name corrections (`model_data` → `s3_model_data_url`, `role` → `role_arn`)

### 5. **Inference**
- `predictor.predict()` → `endpoint.invoke()`
- Serializers/Deserializers → Manual parsing
- Response handling with proper format detection

### 6. **Cleanup**
- `predictor.delete_endpoint()` → Separate `endpoint.delete()` and `EndpointConfig.delete()`

### 7. **Common Pitfalls**
- Removes invalid parameters (e.g., `training_job_name`, `compression="None"`)
- Fixes import paths for `ContinuousParameter`, `IntegerParameter`
- Handles `default_bucket` property vs. method detection
- Removes `sagemaker_session` from `.get()` methods

## Example Usage

### Example 1: Migrate a Training Notebook

```bash
# Start Claude Code
claude

# In Claude Code session
/v2-to-v3-migration notebooks/xgboost_training.ipynb
```

**Before (V2):**
```python
from sagemaker.estimator import Estimator

estimator = Estimator(
    image_uri=container,
    role=role,
    instance_type='ml.m5.xlarge',
    instance_count=1,
    output_path=output_path
)

estimator.fit({'train': train_input})
```

**After (V3):**
```python
from sagemaker.train import ModelTrainer
from sagemaker.train.configs import InputData, Compute, OutputDataConfig

trainer = ModelTrainer(
    training_image=container,
    role=role,
    compute=Compute(
        instance_type="ml.m5.xlarge",
        instance_count=1
    ),
    output_data_config=OutputDataConfig(
        s3_output_path=output_path
    )
)

trainer.train(input_data_config=[train_input], wait=True)
```

### Example 2: Migrate Deployment Code

```bash
/v2-to-v3-migration deployment.py
```

**Before (V2):**
```python
from sagemaker.model import Model

model = Model(
    model_data=model_artifacts,
    image_uri=container,
    role=role
)

predictor = model.deploy(
    instance_type='ml.m5.xlarge',
    initial_instance_count=1
)

result = predictor.predict(data)
```

**After (V3):**
```python
from sagemaker.serve.model_builder import ModelBuilder
from sagemaker.serve.mode.function_pointers import Mode

model_builder = ModelBuilder(
    s3_model_data_url=model_artifacts,
    role_arn=role,
    image_uri=container,
    mode=Mode.SAGEMAKER_ENDPOINT
)

model = model_builder.build()
endpoint = model_builder.deploy(
    instance_type="ml.m5.xlarge",
    initial_instance_count=1
)

result = endpoint.invoke(
    body=data,
    content_type="text/csv"
)
response = result.body.read().decode('utf-8')
```

### Example 3: Complete Notebook Migration

See the example notebooks in this directory:
- [sm-regression_xgboost.ipynb](sm-regression_xgboost.ipynb) - Original V2 notebook
- [sm-regression_xgboost_v3.ipynb](sm-regression_xgboost_v3.ipynb) - Migrated V3 notebook

To see the migration in action:

```bash
claude
```

Then:
```
/v2-to-v3-migration sm-regression_xgboost.ipynb
```

## What to Expect

When you invoke the skill, it will:

1. **Analyze your code** - Identify V2 patterns and dependencies
2. **Plan the migration** - Determine which components need updating
3. **Perform the migration** - Convert code to V3 patterns
4. **Update imports** - Fix all import statements
5. **Fix parameters** - Correct parameter names and remove invalid ones
6. **Add comments** - Mark V3-specific changes with inline comments
7. **Validate** - Check for common errors and pitfalls
8. **Create new file** - Generate a `_v3` version of your file (e.g., `notebook.ipynb` → `notebook_v3.ipynb`)

## Output

The skill creates a new file with `_v3` suffix:
- `training.ipynb` → `training_v3.ipynb`
- `deploy.py` → `deploy_v3.py`

Your original file is never modified.

## Common Migration Scenarios

### Scenario 1: You have a V2 training notebook
```
I have a notebook that uses Estimator to train an XGBoost model. Can you migrate it to V3?
```

### Scenario 2: You need to migrate inference code
```
/v2-to-v3-migration inference.py

This code uses predictor.predict() - please convert to V3
```

### Scenario 3: You have a complete ML pipeline
```
Migrate my entire ML pipeline from V2 to V3. I have:
- train.py (training with Estimator)
- deploy.py (deployment with Model)
- inference.py (predictions with Predictor)
```

### Scenario 4: You're getting migration errors
```
I tried migrating manually but I'm getting "TypeError: unexpected keyword argument 'model_data'". Can you help?
```

The skill will automatically fix this and other common errors.

## Migration Checklist

After migration, verify:

- [ ] All imports updated to V3 paths
- [ ] `ModelTrainer` used instead of `Estimator`
- [ ] Config classes used (`InputData`, `Compute`, etc.)
- [ ] `ModelBuilder` used for deployment
- [ ] `endpoint.invoke()` used instead of `predictor.predict()`
- [ ] Manual serialization/deserialization implemented
- [ ] Parameter names corrected (`s3_model_data_url`, `role_arn`)
- [ ] Invalid parameters removed (`training_job_name`, `compression="None"`)
- [ ] Session handling fixed (no `sagemaker_session` in wrong places)
- [ ] Cleanup code updated (separate endpoint and config deletion)

## Troubleshooting

### Issue: Skill doesn't recognize my file
**Solution:** Provide the full path or open the file in your IDE first

### Issue: Migration incomplete
**Solution:** The skill works iteratively. You can ask follow-up questions:
```
Can you also update the cleanup code at the end?
I'm still seeing V2 patterns in cell 15
```

### Issue: Need to understand a specific change
**Solution:** Ask the skill:
```
Why did you change predictor.predict() to endpoint.invoke()?
What's the difference between Estimator and ModelTrainer?
```

## Additional Resources

- **Skill Reference**: [.claude/skills/v2-to-v3-migration.md](.claude/skills/v2-to-v3-migration.md)
- **Complete Example**: [sm-regression_xgboost_v3.ipynb](sm-regression_xgboost_v3.ipynb)
- **AWS Documentation**: [SageMaker Python SDK V3 Migration Guide](https://sagemaker.readthedocs.io/)

## Tips for Best Results

1. **Start with one file at a time** - Migrate incrementally rather than entire projects at once
2. **Review the changes** - The skill adds comments to explain V3-specific changes
3. **Test thoroughly** - Run the migrated code to ensure behavior is preserved
4. **Ask questions** - If something is unclear, ask the skill to explain
5. **Iterate** - You can request refinements or additional changes

## Support

If you encounter issues:

1. Check the [skill documentation](.claude/skills/v2-to-v3-migration.md) for detailed patterns
2. Review the [example notebook](sm-regression_xgboost_v3.ipynb)
3. Ask Claude Code for help with specific errors
4. Refer to the [SageMaker SDK V3 documentation](https://sagemaker.readthedocs.io/)

## License

This tool is part of the AWS GenAI ML Platform Examples repository and follows the same license terms.
