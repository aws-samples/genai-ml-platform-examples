# SageMaker Migration Advisor - All Launch Options

## Quick Reference

Choose the launch method that works best for you:

### 🎯 Recommended: Simple Shell Scripts

**macOS/Linux:**
```bash
./launch_lite.sh      # Quick assessment (5-10 min)
./launch_regular.sh   # Full analysis (15-30 min)
```

**Windows:**
```cmd
launch_lite.bat       # Quick assessment (5-10 min)
launch_regular.bat    # Full analysis (15-30 min)
```

**Why use this?**
- Simplest and most reliable
- No GUI complexity
- Direct Streamlit execution
- Works on all platforms

---

### 🐍 Python Launchers

#### Simple CLI Launcher
```bash
python launch_advisor.py
```
- Interactive menu
- No GUI dependencies
- Reliable execution

#### GUI Launcher with Dropdown
```bash
python run_sagemaker_migration_advisor_main.py
```
- Visual interface
- Mode descriptions
- Status updates

**CLI Mode (if GUI unavailable):**
```bash
python run_sagemaker_migration_advisor_main.py --cli
```

---

### 🚀 Direct Streamlit Execution

```bash
# Lite version (quick assessment)
streamlit run sagemaker_migration_advisor_lite.py

# Regular version (full analysis)
streamlit run sagemaker_migration_advisor.py
```

**Why use this?**
- Most direct method
- No launcher overhead
- Full control over Streamlit options

---

## Comparison Table

| Method | Complexity | Reliability | Platform | GUI |
|--------|-----------|-------------|----------|-----|
| Shell scripts | ⭐ Lowest | ⭐⭐⭐ High | All | No |
| `launch_advisor.py` | ⭐⭐ Low | ⭐⭐⭐ High | All | No |
| GUI launcher | ⭐⭐⭐ Medium | ⭐⭐ Medium | All | Yes |
| Direct Streamlit | ⭐ Lowest | ⭐⭐⭐ High | All | No |

---

## Troubleshooting

### If GUI Launcher Doesn't Work

Try in this order:

1. **Shell scripts** (most reliable)
   ```bash
   ./launch_lite.sh
   ```

2. **Simple Python launcher**
   ```bash
   python launch_advisor.py
   ```

3. **Direct Streamlit**
   ```bash
   streamlit run sagemaker_migration_advisor_lite.py
   ```

### If Streamlit Not Found

```bash
# Install Streamlit
pip install streamlit

# Verify installation
streamlit --version

# If still not found, use Python module syntax
python -m streamlit run sagemaker_migration_advisor_lite.py
```

### If Browser Doesn't Open

1. Look for URL in console output (usually `http://localhost:8501`)
2. Open browser manually and navigate to that URL

---

## Which Version Should I Use?

### Use **Lite Version** when:
- ✅ You need quick assessment (5-10 minutes)
- ✅ Straightforward migration scenario
- ✅ Proof-of-concept or initial evaluation
- ✅ You want core recommendations fast

### Use **Regular Version** when:
- ✅ Complex migration with many components
- ✅ Enterprise deployment planning
- ✅ You need detailed architecture diagrams
- ✅ Comprehensive TCO analysis required
- ✅ Interactive Q&A for clarifications

---

## Files Overview

| File | Purpose | When to Use |
|------|---------|-------------|
| `launch_lite.sh` | Shell script for Lite | macOS/Linux quick start |
| `launch_regular.sh` | Shell script for Regular | macOS/Linux full analysis |
| `launch_lite.bat` | Batch file for Lite | Windows quick start |
| `launch_regular.bat` | Batch file for Regular | Windows full analysis |
| `launch_advisor.py` | Simple Python launcher | Cross-platform CLI |
| `run_sagemaker_migration_advisor_main.py` | GUI launcher | Visual interface |
| `sagemaker_migration_advisor_lite.py` | Lite version app | Direct execution |
| `sagemaker_migration_advisor.py` | Regular version app | Direct execution |

---

## Documentation

- **[LAUNCHER_GUIDE.md](LAUNCHER_GUIDE.md)** - Detailed launcher documentation
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues and solutions
- **[README.md](README.md)** - Main documentation

---

## Examples

### Example 1: Quick Assessment (Recommended)
```bash
# macOS/Linux
./launch_lite.sh

# Windows
launch_lite.bat
```

### Example 2: Full Analysis
```bash
# macOS/Linux
./launch_regular.sh

# Windows
launch_regular.bat
```

### Example 3: Interactive Selection
```bash
python launch_advisor.py
# Then choose 1 or 2
```

### Example 4: GUI with Dropdown
```bash
python run_sagemaker_migration_advisor_main.py
# Select from dropdown and click Submit
```

---

## Tips

1. **First time?** Start with shell scripts - they're the most reliable
2. **Having issues?** Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
3. **Want GUI?** Try the GUI launcher, but have shell scripts as backup
4. **Need speed?** Use Lite version for quick assessments
5. **Need detail?** Use Regular version for comprehensive analysis

---

## Support

If you encounter issues:

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. Try alternative launch methods
3. Run from terminal to see error messages
4. Verify Streamlit is installed: `streamlit --version`
5. Check AWS credentials: `aws sts get-caller-identity`
