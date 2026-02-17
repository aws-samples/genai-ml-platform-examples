# ECS/Fargate Compatibility

## Overview
Automatic environment detection ensures diagrams work in both local development and ECS/Fargate deployment without configuration.

## How It Works

**Local Development:**
- Diagrams stored in `generated-diagrams/` (persistent)
- Works from any directory

**ECS/Fargate:**
- Diagrams stored in `/tmp/generated-diagrams` (ephemeral)
- Automatic detection via AWS environment variables
- No configuration required

## Key Features

✅ **Zero Configuration** - Automatic environment detection  
✅ **Concurrent Users** - Unique filenames prevent collisions  
✅ **Storage Efficient** - ~2.7MB per report, 7,000+ reports capacity  
✅ **Production Ready** - Fully tested and deployed

## Deployment Notes

### Default Behavior
- Container filesystem is read-only except `/tmp`
- Diagrams automatically use `/tmp/generated-diagrams` in ECS/Fargate
- Ephemeral storage: 20GB default (configurable)
- Diagrams cleared on container restart (acceptable - regenerated per report)

### Optional Configuration
Only needed for high-volume scenarios (>7,000 concurrent reports):

```json
{
  "ephemeralStorage": {
    "sizeInGiB": 40
  }
}
```

## Troubleshooting

**No diagrams in PDF:**
```bash
# Check CloudWatch logs for:
"AWS environment detected - using /tmp for diagrams"
"Found X diagram file(s) to embed"
```

**Storage issues:**
```bash
# Monitor usage
df -h /tmp
du -sh /tmp/generated-diagrams
```

**Verify environment detection:**
```python
from path_utils import get_diagram_folder, is_aws_environment
print(f"AWS Env: {is_aws_environment()}")
print(f"Diagram Folder: {get_diagram_folder()}")
```

## Implementation

Uses `path_utils.py` for automatic path resolution:
- Detects AWS environment via `AWS_EXECUTION_ENV` or `ECS_CONTAINER_METADATA_URI`
- Returns appropriate paths for diagram storage and workspace
- Integrated in both Lite and Regular modes

**Status:** ✅ Production Ready
