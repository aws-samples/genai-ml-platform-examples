# Quick Start: Publishing mlp_sdk to PyPI

This is a condensed guide to get your package on PyPI quickly.

## Prerequisites (5 minutes)

1. **Install tools:**
   ```bash
   pip install --upgrade pip build twine
   ```

2. **Create accounts:**
   - PyPI: https://pypi.org/account/register/
   - TestPyPI: https://test.pypi.org/account/register/
   - Verify your email for both

## Before You Publish (10 minutes)

1. **Update `pyproject.toml`:**
   - Replace `"Your Name or Team"` with your actual name
   - Replace `"your-email@example.com"` with your email
   - Update GitHub URLs with your repository URL

2. **Update `LICENSE`:**
   - Replace `[Your Name or Organization]` with your name

3. **Check package name availability:**
   - Visit: https://pypi.org/project/mlp-sdk/
   - If taken, change `name = "mlp_sdk"` in `pyproject.toml`

## Publish to TestPyPI (5 minutes)

```bash
cd platform/mlp-sdk-v3

# Clean and build
rm -rf dist/ build/ *.egg-info
python -m build

# Check package
twine check dist/*

# Upload to TestPyPI
twine upload --repository testpypi dist/*
```

Enter your TestPyPI username and password when prompted.

**Test installation:**
```bash
pip install --index-url https://test.pypi.org/simple/ --no-deps mlp_sdk
python -c "from mlp_sdk import MLP_Session; print('Success!')"
```

## Publish to PyPI (2 minutes)

Once TestPyPI works:

```bash
twine upload dist/*
```

Enter your PyPI username and password when prompted.

**Verify:**
```bash
pip install mlp_sdk
python -c "from mlp_sdk import MLP_Session; print('Published!')"
```

Your package is now live at: https://pypi.org/project/mlp-sdk/

## Using the Automated Script

Make the script executable:
```bash
chmod +x publish_to_pypi.sh
```

Publish to TestPyPI:
```bash
./publish_to_pypi.sh test
```

Publish to PyPI:
```bash
./publish_to_pypi.sh prod
```

## Using API Tokens (Recommended)

Instead of passwords, use API tokens:

1. **Generate token:**
   - PyPI: https://pypi.org/manage/account/token/
   - TestPyPI: https://test.pypi.org/manage/account/token/

2. **Create `~/.pypirc`:**
   ```ini
   [distutils]
   index-servers =
       pypi
       testpypi

   [pypi]
   username = __token__
   password = pypi-YOUR-PYPI-TOKEN

   [testpypi]
   repository = https://test.pypi.org/legacy/
   username = __token__
   password = pypi-YOUR-TESTPYPI-TOKEN
   ```

3. **Secure the file:**
   ```bash
   chmod 600 ~/.pypirc
   ```

Now you can upload without entering credentials!

## Updating Your Package

1. **Update version** in `pyproject.toml`:
   ```toml
   version = "0.2.0"
   ```

2. **Rebuild and upload:**
   ```bash
   rm -rf dist/
   python -m build
   twine upload dist/*
   ```

## Troubleshooting

**"Package already exists"**
- You can't re-upload the same version
- Increment version number in `pyproject.toml`

**"Invalid credentials"**
- Check username/password
- Or use API tokens (recommended)

**"Package name taken"**
- Change `name` in `pyproject.toml`
- Try: `your-org-mlp-sdk` or similar

## Need More Details?

- Full guide: `PYPI_PUBLISHING_GUIDE.md`
- Checklist: `CHECKLIST.md`
- Package docs: `README.md`

## Support

- PyPI Help: https://pypi.org/help/
- Packaging Guide: https://packaging.python.org/
