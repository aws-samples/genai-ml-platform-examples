#!/usr/bin/env bash
# One-command local setup for MediFlow AI.
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

echo "=== MediFlow AI — Setup ==="
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.11+ first."
    exit 1
fi

PYVER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Python version: $PYVER"

# Create .env if missing
if [ ! -f .env ]; then
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "  -> Edit .env if you need to change region or model."
else
    echo ".env already exists — keeping it."
fi

# Install dependencies
echo ""
echo "Installing Python dependencies..."
pip install -e ".[dev]" --quiet
echo "  -> Dependencies installed."

# Build frontend
echo ""
echo "Building frontend..."
if command -v node &>/dev/null; then
    (cd frontend && npm install --silent && npx vite build)
    echo "  -> Frontend built."
else
    echo "  -> Node.js not found — skipping frontend build."
    echo "     Install Node 18+ and run ./scripts/build-frontend.sh"
fi

# Seed database
echo ""
echo "Seeding database..."
python3 -m backend.seed.seed_data
echo "  -> Database ready."

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Start the server with:"
echo "  uvicorn backend.main:app --reload"
echo ""
echo "Then open http://localhost:8000"
