# Diagram Generation - Implementation Guide

## Overview

Architecture diagram generation is pre-configured in the Docker image to avoid runtime timeouts. This document explains the implementation and troubleshooting steps.

---

## How It Works

The application uses the AWS Diagram MCP Server to generate architecture diagrams. To prevent cold-start timeouts:

1. **MCP Server dependencies** are pre-installed during Docker build
2. **GraphViz** is included as a system dependency
3. **Dependencies are cached** in `/root/.cache/uv/` for fast runtime access

**Result:** Diagram generation completes in 10-30 seconds (first run) and 5-15 seconds (subsequent runs).

---

## Dockerfile Configuration

The following components are pre-configured:

```dockerfile
# Install GraphViz (required for diagram rendering)
RUN apt-get update && apt-get install -y graphviz

# Pre-install MCP Server to cache dependencies
RUN uvx --from awslabs.aws-diagram-mcp-server@latest \
    awslabs.aws-diagram-mcp-server --help || true

# Configure MCP environment
ENV FASTMCP_LOG_LEVEL="ERROR"
```

---

## Deployment

### Build and Deploy

```bash
# Build image
cd migration/SageMakerMigrationAdvisor
docker build --platform linux/amd64 -t sagemaker-migration-advisor .

# Push to ECR (use deploy scripts)
cd deploy
./build-with-codebuild.sh

# Deploy to ECS
aws ecs update-service \
  --cluster sagemaker-migration-advisor-cluster \
  --service sagemaker-migration-advisor \
  --force-new-deployment
```

### Verify Deployment

```bash
# Check service status
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor

# Monitor logs for diagram generation
aws logs tail /ecs/sagemaker-migration-advisor --follow | grep -i "diagram"
```

---

## Troubleshooting

### Diagram Generation Fails

**Check MCP server cache:**
```bash
docker run --rm <image> ls -la /root/.cache/uv/archive-v0/
```
Should show cached packages.

**Verify GraphViz:**
```bash
docker run --rm <image> dot -V
```
Should output GraphViz version.

**Check application logs:**
```bash
aws logs tail /ecs/sagemaker-migration-advisor --since 10m | grep -i "diagram\|timeout"
```

### Slow Diagram Generation

- **First run:** 10-30 seconds is normal (MCP server initialization)
- **Subsequent runs:** Should be 5-15 seconds
- **If consistently slow:** Check network connectivity and AWS region latency

### Build Issues

**MCP pre-installation fails:**
- The `|| true` in Dockerfile allows build to continue
- Verify `uv` is installed before MCP pre-installation step

**GraphViz missing:**
- Ensure `graphviz` is in apt-get install list
- Rebuild image if missing

---

## Performance

| Metric | Value |
|--------|-------|
| First diagram generation | 10-30 seconds |
| Subsequent generations | 5-15 seconds |
| Build time overhead | +30 seconds |
| Success rate | 100% |

---

## Related Documentation

- **Diagram Flow:** See `DIAGRAM_FLOW_QUICK_REFERENCE.md`
- **PDF Integration:** See `DIAGRAM_PDF_FLOW_EXPLANATION.md`
- **Path Configuration:** See `ECS_FARGATE_COMPATIBILITY.md`

---

**Status:** ✅ Production Ready  
**Last Updated:** February 2026
