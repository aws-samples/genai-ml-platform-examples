# Quick Start Guide - SageMaker Migration Advisor

## 🚀 Get Started in 30 Seconds

### Step 1: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 2: Configure AWS
```bash
aws configure
# or for SSO
aws configure sso
```

### Step 3: Launch the Advisor

**Easiest Method (Recommended):**

**macOS/Linux:**
```bash
./launch_lite.sh
```

**Windows:**
```cmd
launch_lite.bat
```

That's it! Your browser will open automatically.

---

## 🎯 Choose Your Version

### Lite Version (5-10 minutes)
**Best for:** Quick assessments, POCs, straightforward migrations

**Launch:**
```bash
./launch_lite.sh          # macOS/Linux
launch_lite.bat           # Windows
```

### Regular Version (15-30 minutes)
**Best for:** Complex migrations, detailed planning, enterprise deployments

**Launch:**
```bash
./launch_regular.sh       # macOS/Linux
launch_regular.bat        # Windows
```

---

## 🔧 Alternative Launch Methods

### Method 1: Simple Python Launcher
```bash
python launch_advisor.py
```
Then choose 1 (Lite) or 2 (Regular)

### Method 2: GUI Launcher
```bash
python run_sagemaker_migration_advisor_main.py
```
Select from dropdown and click Submit

### Method 3: Direct Streamlit
```bash
streamlit run sagemaker_migration_advisor_lite.py
# or
streamlit run sagemaker_migration_advisor.py
```

---

## ❓ Troubleshooting

### Streamlit Not Found?
```bash
pip install streamlit
streamlit --version
```

### Browser Doesn't Open?
Look for URL in console (usually `http://localhost:8501`) and open manually

### GUI Launcher Not Working?
Use shell scripts instead - they're more reliable:
```bash
./launch_lite.sh
```

### More Help?
See [TROUBLESHOOTING.md](TROUBLESHOOTING.md) for detailed solutions

---

## 📖 What Happens Next?

After launching, you'll:

1. **Provide Architecture Info**
   - Upload diagram OR describe your architecture

2. **Get Analysis** (Lite version)
   - Architecture analysis
   - SageMaker design recommendations
   - TCO comparison
   - Migration roadmap
   - PDF report

3. **Get Comprehensive Analysis** (Regular version)
   - Everything in Lite, plus:
   - Interactive Q&A session
   - Architecture diagrams
   - Detailed TCO breakdown
   - Step-by-step migration plan

---

## 📊 Output Files

After completion, check these directories:

- `generated-reports/` - PDF reports
- `generated-diagrams/` - Architecture diagrams (Regular version)
- `logs/` - Application logs

---

## 💡 Tips

- **First time?** Use Lite version to understand the workflow
- **Complex migration?** Use Regular version for detailed analysis
- **Quick iteration?** Lite version is faster for rapid prototyping
- **Production planning?** Regular version provides comprehensive guidance

---

## 🆘 Need Help?

1. Check [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
2. See [LAUNCHER_OPTIONS.md](LAUNCHER_OPTIONS.md) for all launch methods
3. Read [LAUNCHER_GUIDE.md](LAUNCHER_GUIDE.md) for detailed documentation
4. Check [README.md](README.md) for complete documentation

---

## ⚡ Quick Command Reference

| Task | Command |
|------|---------|
| Install | `pip install -r requirements.txt` |
| Configure AWS | `aws configure` |
| Launch Lite | `./launch_lite.sh` or `launch_lite.bat` |
| Launch Regular | `./launch_regular.sh` or `launch_regular.bat` |
| Interactive | `python launch_advisor.py` |
| GUI | `python run_sagemaker_migration_advisor_main.py` |
| Direct | `streamlit run sagemaker_migration_advisor_lite.py` |

---

**Ready to start? Run this now:**

```bash
# macOS/Linux
./launch_lite.sh

# Windows
launch_lite.bat
```

Your migration advisor will open in your browser! 🎉
