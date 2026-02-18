# Diagram & PDF Flow - Technical Reference

## How It Works

The application automatically detects the environment and stores diagrams in the correct location:

**Local Development:**
- Location: `{project}/generated-diagrams/`
- Persistence: ✅ Files persist across sessions

**ECS/Fargate:**
- Location: `/tmp/generated-diagrams/`
- Persistence: ❌ Ephemeral (cleared on container restart)
- Works: ✅ Within same user session

## Current Status

**Lite Mode:** ✅ Uses `path_utils.get_diagram_folder()` - works correctly in all environments

**Regular Mode:** ⚠️ Uses `os.getcwd()` - may fail in ECS/Fargate

## Fix Required for Regular Mode

Update `sagemaker_migration_advisor.py` around line 350:

```python
# Replace this:
current_dir = os.getcwd()
diagram_folder = os.path.join(current_dir, 'generated-diagrams')

# With this:
from path_utils import get_diagram_folder
diagram_folder = get_diagram_folder()
```

## User Experience

**Same Session:** Generate diagrams → Generate PDF → Download ✅

**New Session (ECS/Fargate):** Must regenerate diagrams (ephemeral storage)

**Recommendation:** Use ALB session stickiness to keep users on same container during their session.

## For Persistent Storage (Optional)

If diagrams must persist across sessions, consider:
- **EFS Mount:** Add persistent volume to ECS task
- **S3 Storage:** Upload diagrams to S3, download for PDF generation
- **Current Approach:** Accept ephemeral nature (simplest, no infrastructure changes)

See `ECS_FARGATE_COMPATIBILITY.md` for deployment details.
