# Dockerfile for AWS App Runner deployment
# Using AWS ECR Public base image to avoid Docker Hub rate limits
FROM public.ecr.aws/docker/library/python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies including uv for MCP server and GraphViz for diagrams
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    graphviz \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Add uv to PATH
ENV PATH="/root/.local/bin:${PATH}"

# Set MCP server environment variables
ENV FASTMCP_LOG_LEVEL="ERROR"
ENV DIAGRAM_GENERATION_TIMEOUT="180"

# Pre-install AWS Diagram MCP Server to avoid first-run timeout
# This downloads and caches all dependencies during build time
RUN uvx --version && \
    uvx --from awslabs.aws-diagram-mcp-server@latest awslabs.aws-diagram-mcp-server --help || true

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create necessary directories
RUN mkdir -p generated-diagrams logs

# Expose port for App Runner
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run the application
CMD ["streamlit", "run", "app.py"]
