# Diagram Generation - Status & Troubleshooting

**Status:** ✅ OPERATIONAL  
**Last Updated:** 2026-02-06

## Quick Status Check

**Diagram Generation:**
- Expected time: 10-30 seconds (first generation), 5-15 seconds (subsequent)
- Timeout threshold: 180 seconds
- Success rate: Expected 100%

**Infrastructure:**
- MCP server dependencies: Pre-cached ✅
- GraphViz: Installed ✅
- Environment: Configured ✅

## Fixes Applied

### 1. Pre-cached MCP Dependencies
- Dependencies cached during Docker build
- Eliminates first-run download delays
- Reduces cold-start from 90+ seconds to <30 seconds

### 2. GraphViz Installation
- Required system package for diagram rendering
- Available at `/usr/bin/dot`

### 3. Timeout Configuration
- Extended timeout: 180 seconds
- Reduced log noise: `FASTMCP_LOG_LEVEL=ERROR`

## Troubleshooting

### Check Diagram Generation Logs
```bash
aws logs tail /ecs/sagemaker-migration-advisor --since 5m --follow | grep -i "diagram"
```

### Check for Timeout Errors
```bash
aws logs tail /ecs/sagemaker-migration-advisor --since 10m | grep -i "timeout"
```

### Verify Service Health
```bash
aws ecs describe-services \
  --cluster sagemaker-migration-advisor-cluster \
  --services sagemaker-migration-advisor \
  --region us-east-1
```

## Expected Behavior

**First Diagram (Cold Start):**
- Time: 10-30 seconds
- MCP server initializes
- Dependencies loaded from cache

**Subsequent Diagrams (Warm):**
- Time: 5-15 seconds
- MCP server already initialized
- Faster processing

## If Issues Occur

1. **Check CloudWatch logs** for specific error messages
2. **Verify MCP cache** exists in container: `/root/.cache/uv/`
3. **Review timeout settings** in environment variables
4. **Check network connectivity** if external dependencies fail

## Technical Details

**MCP Server Cache:** `/root/.cache/uv/archive-v0/` (64 packages)  
**GraphViz Commands:** `/usr/bin/dot`, `/usr/bin/neato`, etc.  
**Environment:** `DIAGRAM_GENERATION_TIMEOUT=180`, `FASTMCP_LOG_LEVEL=ERROR`

## Related Documentation

- **Fix Details:** `DIAGRAM_TIMEOUT_FIX.md`
- **Diagram Flow:** `DIAGRAM_FLOW_QUICK_REFERENCE.md`
- **PDF Integration:** `DIAGRAM_PDF_FLOW_EXPLANATION.md`
