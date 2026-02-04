# PyPI Publishing Guide for mlp_sdk

This guide walks you through publishing the mlp_sdk package to PyPI.

## Prerequisites

1. **Create PyPI Account**
   - Go to [https://pypi.org/account/register/](https://pypi.org/account/register/)
   - Create an account and verify your email

2. **Create TestPyPI Account** (recommended for testing)
   - Go to [https://test.pypi.org/account/register/](https://test.pypi.org/account/register/)
   - Create a separate account for testing

3. **Install Required Tools**
   ```bash
   pip install --upgrade pip
   pip install --upgrade build twine
   ```

## Step-by-Step Publishing Process

### Step 1: Update Package Information

Before publishing, ensure you've updated:

1. **Author information** in `pyproject.toml`:
   ```toml
   authors = [
       {name = "Your Name", email = "your-email@example.com"}
   ]
   ```

2. **Project URLs** in `pyproject.toml`:
   ```toml
   [project.urls]
   Homepage = "https://github.com/your-username/mlp_sdk"
   Repository = "https://github.com/your-username/mlp_sdk"
   ```

3. **Copyright** in `LICENSE` file

### Step 2: Clean Previous Builds

```bash
cd platform/mlp-sdk-v3
rm -rf dist/ build/ *.egg-info
```

### Step 3: Build the Package

```bash
python -m build
```

This creates two files in the `dist/` directory:
- `mlp_sdk-0.1.0.tar.gz` (source distribution)
- `mlp_sdk-0.1.0-py3-none-any.whl` (wheel distribution)

### Step 4: Test on TestPyPI (Recommended)

#### Upload to TestPyPI

```bash
python -m twine upload --repository testpypi dist/*
```

You'll be prompted for:
- Username: Your TestPyPI username
- Password: Your TestPyPI password or API token

#### Test Installation from TestPyPI

```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps mlp_sdk
```

Note: Use `--no-deps` because dependencies might not be available on TestPyPI.

#### Test the Package

```python
from mlp_sdk import MLP_Session
print("Package imported successfully!")
```

### Step 5: Publish to PyPI

Once you've verified everything works on TestPyPI:

```bash
python -m twine upload dist/*
```

You'll be prompted for:
- Username: Your PyPI username
- Password: Your PyPI password or API token

### Step 6: Verify Publication

1. Visit your package page: `https://pypi.org/project/mlp-sdk/`
2. Install from PyPI:
   ```bash
   pip install mlp_sdk
   ```

## Using API Tokens (Recommended)

API tokens are more secure than passwords.

### Create API Token

1. **For PyPI:**
   - Go to [https://pypi.org/manage/account/token/](https://pypi.org/manage/account/token/)
   - Click "Add API token"
   - Give it a name (e.g., "mlp_sdk_upload")
   - Set scope to "Entire account" or specific project
   - Copy the token (starts with `pypi-`)

2. **For TestPyPI:**
   - Go to [https://test.pypi.org/manage/account/token/](https://test.pypi.org/manage/account/token/)
   - Follow same steps

### Configure API Token

Create or edit `~/.pypirc`:

```ini
[distutils]
index-servers =
    pypi
    testpypi

[pypi]
username = __token__
password = pypi-YOUR-API-TOKEN-HERE

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi-YOUR-TESTPYPI-TOKEN-HERE
```

Set proper permissions:
```bash
chmod 600 ~/.pypirc
```

Now you can upload without entering credentials:
```bash
python -m twine upload --repository testpypi dist/*
python -m twine upload dist/*
```

## Automated Publishing with GitHub Actions

Create `.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install build twine
      
      - name: Build package
        run: python -m build
      
      - name: Publish to PyPI
        env:
          TWINE_USERNAME: __token__
          TWINE_PASSWORD: ${{ secrets.PYPI_API_TOKEN }}
        run: python -m twine upload dist/*
```

Add your PyPI API token to GitHub Secrets:
1. Go to your repository settings
2. Navigate to Secrets and variables → Actions
3. Add new secret named `PYPI_API_TOKEN`
4. Paste your PyPI API token

## Version Management

### Updating Version Number

Edit `pyproject.toml`:
```toml
[project]
version = "0.2.0"  # Update this
```

### Semantic Versioning

Follow [Semantic Versioning](https://semver.org/):
- **MAJOR** (1.0.0): Breaking changes
- **MINOR** (0.1.0): New features, backward compatible
- **PATCH** (0.0.1): Bug fixes, backward compatible

### Publishing New Version

1. Update version in `pyproject.toml`
2. Update CHANGELOG (if you have one)
3. Commit changes
4. Create git tag:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
5. Build and publish:
   ```bash
   rm -rf dist/
   python -m build
   python -m twine upload dist/*
   ```

## Troubleshooting

### Package Name Already Exists

If `mlp_sdk` is taken, you can:
1. Choose a different name in `pyproject.toml`
2. Use a prefix: `your-org-mlp-sdk`
3. Check availability: [https://pypi.org/project/mlp-sdk/](https://pypi.org/project/mlp-sdk/)

### Upload Fails

- **Invalid credentials**: Check username/password or API token
- **File already exists**: You can't re-upload the same version. Increment version number.
- **Invalid package**: Run `twine check dist/*` to validate

### Testing Issues

If imports fail after installation:
```bash
pip install -e .  # Install in editable mode for development
```

## Best Practices

1. **Always test on TestPyPI first**
2. **Use API tokens instead of passwords**
3. **Keep your `.pypirc` file secure** (never commit it)
4. **Tag releases in git** for version tracking
5. **Write a CHANGELOG.md** to document changes
6. **Run tests before publishing**: `pytest`
7. **Check package before upload**: `twine check dist/*`
8. **Use semantic versioning**

## Quick Reference Commands

```bash
# Clean build artifacts
rm -rf dist/ build/ *.egg-info

# Build package
python -m build

# Check package
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*

# Upload to PyPI
twine upload dist/*

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ mlp_sdk

# Install from PyPI
pip install mlp_sdk
```

## Resources

- [PyPI](https://pypi.org/)
- [TestPyPI](https://test.pypi.org/)
- [Python Packaging Guide](https://packaging.python.org/)
- [Twine Documentation](https://twine.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)
