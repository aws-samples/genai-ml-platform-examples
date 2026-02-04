# Pre-Publication Checklist for mlp_sdk

Complete this checklist before publishing to PyPI.

## Package Information

- [ ] Updated author name and email in `pyproject.toml`
- [ ] Updated project URLs (GitHub, documentation) in `pyproject.toml`
- [ ] Updated copyright year in `LICENSE` file
- [ ] Version number is correct in `pyproject.toml`
- [ ] Package name `mlp_sdk` is available on PyPI (check at https://pypi.org/project/mlp-sdk/)

## Documentation

- [ ] README.md is complete and accurate
- [ ] Installation instructions are correct
- [ ] Usage examples work
- [ ] API documentation is up to date
- [ ] All placeholder URLs are replaced with real ones

## Code Quality

- [ ] All tests pass: `pytest tests/`
- [ ] Code is formatted: `black mlp_sdk tests`
- [ ] Imports are sorted: `isort mlp_sdk tests`
- [ ] No linting errors: `flake8 mlp_sdk tests`
- [ ] Type checking passes: `mypy mlp_sdk`
- [ ] No sensitive information in code (API keys, passwords, etc.)

## Package Structure

- [ ] `LICENSE` file exists
- [ ] `README.md` exists
- [ ] `pyproject.toml` is properly configured
- [ ] `MANIFEST.in` includes all necessary files
- [ ] `.gitignore` excludes build artifacts

## PyPI Accounts

- [ ] Created PyPI account at https://pypi.org/account/register/
- [ ] Created TestPyPI account at https://test.pypi.org/account/register/
- [ ] Email verified for both accounts
- [ ] API tokens generated (recommended)

## Build and Test

- [ ] Clean build: `rm -rf dist/ build/ *.egg-info`
- [ ] Package builds successfully: `python -m build`
- [ ] Package passes checks: `twine check dist/*`
- [ ] Tested on TestPyPI first
- [ ] Installed and tested from TestPyPI

## Version Control

- [ ] All changes committed to git
- [ ] Created git tag for version: `git tag v0.1.0`
- [ ] Pushed tag to remote: `git push origin v0.1.0`

## Final Steps

- [ ] Uploaded to TestPyPI and verified
- [ ] Ready to upload to production PyPI
- [ ] Prepared announcement/release notes

## Post-Publication

- [ ] Verified package appears on PyPI
- [ ] Tested installation: `pip install mlp_sdk`
- [ ] Updated documentation with PyPI badge
- [ ] Announced release (if applicable)

---

## Quick Commands Reference

```bash
# Install tools
pip install --upgrade build twine

# Clean
rm -rf dist/ build/ *.egg-info

# Build
python -m build

# Check
twine check dist/*

# Test on TestPyPI
twine upload --repository testpypi dist/*

# Publish to PyPI
twine upload dist/*
```
