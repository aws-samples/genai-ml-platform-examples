# Contributing to MediFlow AI

Thank you for your interest in contributing! This project is part of the [aws-samples/genai-ml-platform-examples](https://github.com/aws-samples/genai-ml-platform-examples) repository.

## How to Contribute

Please refer to the [repository-level CONTRIBUTING guide](https://github.com/aws-samples/genai-ml-platform-examples/blob/main/CONTRIBUTING.md) for the full contribution process including:

- Reporting bugs and feature requests
- Submitting pull requests
- Code of conduct

## Local Development

### Setup

```bash
# Install Python dependencies
pip install -e ".[dev]"

# Install frontend dependencies
cd frontend && npm install && cd ..

# Seed the database
python -m backend.seed.seed_data

# Start the dev server
uvicorn backend.main:app --reload
```

### Running Tests

```bash
pytest tests/
```

### Building the Frontend

```bash
./scripts/build-frontend.sh
```

### Code Style

- Python: Follow PEP 8. Use type hints for function signatures.
- JavaScript/React: Standard React patterns with functional components and hooks.
- No comments unless explaining a non-obvious "why".

## Architecture Notes

- **Backend tools** (`backend/tools/`) are decorated with `@tool` from the Strands SDK. Each tool function is self-contained with its own DB queries.
- **Analysis pipeline** (`backend/analysis/`) runs four stages sequentially. Stages 1 and 4 are deterministic; stages 2 and 3 call Bedrock.
- **Frontend** is a React SPA built with Vite. The built output in `frontend/dist/` is served by FastAPI as static files.

## Security

If you discover a potential security issue, please notify AWS/Amazon Security via the [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Do not create a public GitHub issue for security vulnerabilities.

## License

By contributing, you agree that your contributions will be licensed under the MIT-0 License.
