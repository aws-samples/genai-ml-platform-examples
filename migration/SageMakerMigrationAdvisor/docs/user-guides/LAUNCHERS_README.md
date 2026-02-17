# Launcher Files - Overview

This directory contains multiple launcher options to accommodate different preferences and environments.

## 📁 Launcher Files

### Shell Scripts (Recommended - Most Reliable)

| File | Platform | Purpose |
|------|----------|---------|
| `launch_lite.sh` | macOS/Linux | Launch Lite version |
| `launch_regular.sh` | macOS/Linux | Launch Regular version |
| `launch_lite.bat` | Windows | Launch Lite version |
| `launch_regular.bat` | Windows | Launch Regular version |

**Usage:**
```bash
# macOS/Linux
./launch_lite.sh

# Windows
launch_lite.bat
```

**Pros:**
- ✅ Simplest and most reliable
- ✅ Direct Streamlit execution
- ✅ No Python complexity
- ✅ Works on all platforms

**Cons:**
- ❌ No interactive menu
- ❌ Must know which version you want

---

### Python Launchers

#### Simple CLI Launcher: `launch_advisor.py`

**Usage:**
```bash
python launch_advisor.py
```

**Features:**
- Interactive menu (choose 1 or 2)
- Validates Streamlit installation
- Clear error messages
- Cross-platform

**Pros:**
- ✅ Interactive selection
- ✅ Simple and reliable
- ✅ Good error handling
- ✅ No GUI dependencies

**Cons:**
- ❌ Command-line only
- ❌ No visual interface

---

#### GUI Launcher: `run_sagemaker_migration_advisor_main.py`

**Usage:**
```bash
python run_sagemaker_migration_advisor_main.py

# Or CLI mode
python run_sagemaker_migration_advisor_main.py --cli
```

**Features:**
- Visual dropdown menu
- Mode descriptions
- Status updates
- Submit/Exit buttons
- Automatic fallback to CLI

**Pros:**
- ✅ Visual interface
- ✅ Detailed mode descriptions
- ✅ Status feedback
- ✅ Professional appearance

**Cons:**
- ❌ Requires tkinter
- ❌ More complex (threading, subprocess)
- ❌ May have platform-specific issues

**Known Issues:**
- Submit button may not respond on some systems
- Use alternative launchers if issues occur

---

### Direct Streamlit Execution

**Usage:**
```bash
streamlit run sagemaker_migration_advisor_lite.py
# or
streamlit run sagemaker_migration_advisor.py
```

**Pros:**
- ✅ Most direct method
- ✅ No launcher overhead
- ✅ Full Streamlit control

**Cons:**
- ❌ Must know exact filename
- ❌ No mode selection help

---

## 🎯 Which Launcher Should I Use?

### For Most Users: Shell Scripts
```bash
./launch_lite.sh  # or launch_lite.bat
```
**Why?** Simplest, most reliable, works everywhere

### For Interactive Selection: Simple Python Launcher
```bash
python launch_advisor.py
```
**Why?** Menu-driven, good error handling, no GUI complexity

### For Visual Interface: GUI Launcher
```bash
python run_sagemaker_migration_advisor_main.py
```
**Why?** Professional appearance, detailed descriptions

**Note:** If GUI launcher has issues, use shell scripts or simple Python launcher

### For Advanced Users: Direct Streamlit
```bash
streamlit run sagemaker_migration_advisor_lite.py
```
**Why?** Direct control, no launcher overhead

---

## 🔧 Troubleshooting Launchers

### GUI Launcher Submit Button Not Working

**Symptoms:**
- Button appears but doesn't launch
- No error messages
- Process doesn't start

**Solutions:**

1. **Check Console Output**
   ```bash
   python run_sagemaker_migration_advisor_main.py
   ```
   Look for DEBUG messages

2. **Use Alternative Launcher**
   ```bash
   python launch_advisor.py
   ```

3. **Use Shell Scripts**
   ```bash
   ./launch_lite.sh
   ```

4. **Direct Streamlit**
   ```bash
   streamlit run sagemaker_migration_advisor_lite.py
   ```

### Streamlit Not Found

**All launchers need Streamlit installed:**
```bash
pip install streamlit
streamlit --version
```

### Permission Denied (Shell Scripts)

**macOS/Linux:**
```bash
chmod +x launch_lite.sh launch_regular.sh
```

### tkinter Not Available (GUI Launcher)

**Automatic fallback to CLI mode**

Or install tkinter:
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# macOS (usually included)
brew install python-tk

# Windows (usually included)
# Reinstall Python from python.org
```

---

## 📊 Launcher Comparison

| Feature | Shell Scripts | Simple Python | GUI Launcher | Direct Streamlit |
|---------|--------------|---------------|--------------|------------------|
| Reliability | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐ |
| Simplicity | ⭐⭐⭐ | ⭐⭐ | ⭐ | ⭐⭐⭐ |
| Interactive | ❌ | ✅ | ✅ | ❌ |
| Visual | ❌ | ❌ | ✅ | ❌ |
| Cross-platform | ✅ | ✅ | ✅ | ✅ |
| Dependencies | None | Python | Python + tkinter | Streamlit |

---

## 🚀 Quick Start Recommendations

### Scenario 1: First Time User
**Use:** Shell scripts
```bash
./launch_lite.sh
```
**Why:** Simplest, most reliable

### Scenario 2: Want to Choose Version Interactively
**Use:** Simple Python launcher
```bash
python launch_advisor.py
```
**Why:** Menu-driven, easy to use

### Scenario 3: Prefer Visual Interface
**Use:** GUI launcher (with fallback)
```bash
python run_sagemaker_migration_advisor_main.py
```
**Fallback:** If issues, use shell scripts

### Scenario 4: Advanced User
**Use:** Direct Streamlit
```bash
streamlit run sagemaker_migration_advisor_lite.py
```
**Why:** Full control, no overhead

---

## 📝 Implementation Details

### Shell Scripts
- Direct `streamlit run` command
- No Python wrapper
- Minimal overhead
- Platform-specific (.sh vs .bat)

### Simple Python Launcher
- Single-threaded
- Direct subprocess execution
- Input validation
- Error handling

### GUI Launcher
- Multi-threaded (for responsiveness)
- tkinter GUI
- Subprocess management
- Complex error handling
- Debug output

### Direct Streamlit
- No launcher
- Streamlit's built-in server
- Full Streamlit options available

---

## 🔍 Debug Information

### GUI Launcher Debug Output

The GUI launcher now prints debug information:

```
DEBUG: Checking for Streamlit...
DEBUG: Streamlit path: /usr/local/bin/streamlit
DEBUG: Launching Migration Advisor Lite
DEBUG: Command: streamlit run /path/to/script.py
DEBUG: Working directory: /path/to/dir
DEBUG: Script exists: True
DEBUG: Process started with PID: 12345
DEBUG: Streamlit appears to be running
```

Look for these messages when troubleshooting.

---

## 📚 Related Documentation

- **[QUICK_START.md](QUICK_START.md)** - Get started in 30 seconds
- **[LAUNCHER_OPTIONS.md](LAUNCHER_OPTIONS.md)** - All launch methods
- **[LAUNCHER_GUIDE.md](LAUNCHER_GUIDE.md)** - Detailed launcher guide
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Common issues
- **[README.md](README.md)** - Main documentation

---

## 💡 Best Practices

1. **Start Simple**: Use shell scripts first
2. **Have Backups**: Know multiple launch methods
3. **Check Logs**: Look at console output for errors
4. **Test Streamlit**: Verify `streamlit --version` works
5. **Use Alternatives**: If one launcher fails, try another

---

## 🆘 Support

If all launchers fail:

1. Verify Streamlit installation: `streamlit --version`
2. Check Python version: `python --version` (need 3.8+)
3. Test Streamlit directly: `streamlit hello`
4. Check AWS credentials: `aws sts get-caller-identity`
5. Review [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

**Remember:** Multiple launcher options ensure you can always run the advisor, regardless of your environment or preferences!
