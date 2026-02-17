# Diagram Flow Quick Reference

## 🎯 Quick Answer

**Q: How does the app use generated images in PDF creation?**

**A:** The app generates diagrams to a folder, then embeds them in PDFs by reading from that same folder.

---

## 📁 Directory Locations

### Local Development:
```
{project}/generated-diagrams/
Example: /Users/you/project/migration/SageMakerMigrationAdvisor/generated-diagrams/
```

### ECS/Fargate Deployment:
```
/tmp/generated-diagrams/
```

---

## 🔄 Complete Flow

```
1. USER ACTION: Click "Generate Architecture Diagram"
   ↓
2. DIAGRAM GENERATION:
   - DiagramGenerator initialized with workspace_dir
   - Creates folder: {workspace_dir}/generated-diagrams/
   - Calls AWS Diagram MCP Server (via uvx)
   - Saves PNG files to folder
   ↓
3. FILES CREATED:
   Local:     {project}/generated-diagrams/*.png
   ECS:       /tmp/generated-diagrams/*.png
   ↓
4. USER ACTION: Click "Generate Reports"
   ↓
5. PDF GENERATION:
   - PDFReportGenerator initialized with diagram_folder path
   - Calls _add_diagrams() method
   - Lists all PNG/JPG files in diagram_folder
   - Opens each image with PIL
   - Calculates display dimensions (max 6"x4")
   - Embeds images in PDF using ReportLab
   ↓
6. PDF DOWNLOAD:
   - User receives PDF with embedded diagrams
```

---

## 🚀 ECS/Fargate Behavior

### ✅ What Works:
- Generate diagrams → Generate PDF → Download (all in same session)
- Diagrams are found and embedded correctly
- No special configuration needed

### ❌ What Doesn't Work:
- Diagrams don't persist across container restarts
- If user comes back later (new container), diagrams are gone
- Must regenerate diagrams before creating PDF

### 🔧 Why It Works:
1. **Same Container Session**: User stays on same container (ALB stickiness)
2. **Same /tmp Space**: Diagrams and PDF generator use same `/tmp` directory
3. **Environment Detection**: `path_utils.py` automatically detects ECS and uses `/tmp`

---

## 🔍 Path Detection Logic

```python
# path_utils.py
def get_diagram_folder():
    # Checks environment variables:
    # - AWS_EXECUTION_ENV (Lambda/ECS)
    # - ECS_CONTAINER_METADATA_URI (ECS/Fargate)
    
    if running_in_aws:
        return '/tmp/generated-diagrams'  # Writable in containers
    else:
        return '{script_dir}/generated-diagrams'  # Local development
```

---

## 📊 PDF Embedding Process

```python
# pdf_report_generator.py - _add_diagrams() method

1. Check if folder exists:
   if not os.path.exists(self.diagram_folder):
       return  # No diagrams to embed

2. List image files:
   diagram_files = [f for f in os.listdir(self.diagram_folder)
                    if f.endswith(('.png', '.jpg', '.jpeg', '.gif'))]

3. For each diagram (max 4):
   - Verify file exists and has content
   - Open with PIL to validate
   - Calculate dimensions (maintain aspect ratio)
   - Embed in PDF using ReportLab Image

4. Result:
   - Up to 4 diagrams embedded in PDF
   - Remaining diagrams noted in text
```

---

## ⚙️ Configuration

### ALB Session Stickiness (Recommended):
```hcl
# terraform/ecs-fargate.tf
stickiness {
  enabled         = true
  type            = "lb_cookie"
  cookie_duration = 3600  # 1 hour
}
```

This keeps users on the same container during their session.

---

## 🐛 Troubleshooting

### Issue: "No diagrams found in PDF"

**Check 1: Verify diagram folder**
```bash
# Local
ls -la generated-diagrams/

# ECS/Fargate (exec into container)
ls -la /tmp/generated-diagrams/
```

**Check 2: Check logs**
```bash
# Look for these log messages:
"Diagram folder ready: /tmp/generated-diagrams"
"Found X diagram file(s) to embed"
"Successfully embedded diagram 1"
```

**Check 3: Verify path detection**
```python
# In Python console:
from path_utils import get_diagram_folder
print(get_diagram_folder())
# Should print: /tmp/generated-diagrams (in ECS)
```

### Issue: "Diagrams disappeared"

**Cause**: Container restarted, `/tmp` cleared

**Solution**: Regenerate diagrams in new session

---

## 📋 File Responsibilities

| File | Responsibility |
|------|---------------|
| `path_utils.py` | Environment detection, path resolution |
| `diagram_generator.py` | Generate diagrams, save to folder |
| `pdf_report_generator.py` | Read diagrams from folder, embed in PDF |
| `sagemaker_migration_advisor.py` | Regular mode UI, calls generators |
| `sagemaker_migration_advisor_lite.py` | Lite mode UI, calls generators |

---

## ✅ Verification Checklist

### Local Development:
- [ ] Diagrams saved to `{project}/generated-diagrams/`
- [ ] PDF finds diagrams in same location
- [ ] Diagrams visible in PDF
- [ ] Diagrams persist after app restart

### ECS/Fargate Deployment:
- [ ] Diagrams saved to `/tmp/generated-diagrams/`
- [ ] PDF finds diagrams in `/tmp/generated-diagrams/`
- [ ] Diagrams visible in PDF
- [ ] ALB session stickiness enabled
- [ ] Works within same user session
- [ ] Diagrams cleared on container restart (expected)

---

## 🎓 Key Takeaways

1. **Environment-Aware**: App automatically detects local vs ECS/Fargate
2. **Same Session**: Diagrams and PDF generation must happen in same session
3. **Ephemeral in ECS**: `/tmp` is cleared on container restart
4. **No Persistence**: Diagrams don't survive container restarts (by design)
5. **ALB Stickiness**: Keeps user on same container during session
6. **Both Modes Aligned**: Regular and lite modes use identical path logic

---

## 📚 Related Documentation

- `DIAGRAM_PDF_FLOW_EXPLANATION.md` - Detailed technical explanation
- `DIAGRAM_PATH_FIX_SUMMARY.md` - Recent fix for regular mode
- `ECS_FARGATE_COMPATIBILITY.md` - ECS/Fargate deployment guide
- `path_utils.py` - Source code for path detection
