# SageMaker Migration Advisor Launcher Guide

## Overview

The `run_sagemaker_migration_advisor_main.py` script provides a unified launcher with a dropdown menu to choose between two migration advisor modes:

- **Migration Advisor Lite**: Quick assessment for rapid evaluations
- **Migration Advisor Regular**: Comprehensive analysis with full features

## Quick Start

### GUI Mode (Default)

Simply run the launcher:

```bash
python run_sagemaker_migration_advisor_main.py
```

This will open a graphical interface where you can:
1. Select your preferred mode from the dropdown
2. Read the mode description
3. Click "Launch Advisor" to start

### CLI Mode (Fallback)

If GUI is not available or you prefer command-line:

```bash
python run_sagemaker_migration_advisor_main.py --cli
```

Or:

```bash
python run_sagemaker_migration_advisor_main.py --no-gui
```

## Mode Comparison

### Migration Advisor Lite

**Best for:**
- Initial assessments
- Quick wins
- Straightforward migrations
- Proof-of-concepts

**Features:**
- ✅ Streamlined workflow
- ✅ Core architecture analysis
- ✅ Basic TCO estimation
- ✅ Simplified migration roadmap
- ✅ PDF report generation
- ⚡ Faster execution (5-10 minutes)

**Runs:** `sagemaker_migration_advisor_lite.py`

### Migration Advisor Regular

**Best for:**
- Complex migrations
- Enterprise deployments
- Detailed planning
- Comprehensive analysis

**Features:**
- ✅ Complete multi-agent workflow
- ✅ Interactive Q&A session
- ✅ Detailed architecture analysis
- ✅ Comprehensive TCO comparison
- ✅ Step-by-step migration roadmap
- ✅ Architecture diagrams generation
- ✅ Detailed PDF report
- 🔬 Thorough analysis (15-30 minutes)

**Runs:** `sagemaker_migration_advisor.py`

## GUI Features

The launcher provides:

1. **Dropdown Selection**: Easy mode selection with visual feedback
2. **Mode Descriptions**: Detailed information about each mode
3. **Status Updates**: Real-time status of the advisor execution
4. **Error Handling**: Clear error messages if issues occur
5. **Window Management**: Launcher hides during execution and reappears when done

## Screenshots

### Main Launcher Window

```
┌─────────────────────────────────────────────┐
│  🚀 SageMaker Migration Advisor             │
│     Select your migration advisor mode      │
├─────────────────────────────────────────────┤
│                                             │
│  Choose Migration Mode:                     │
│  ┌─────────────────────────────────────┐   │
│  │ Migration Advisor Lite          ▼   │   │
│  └─────────────────────────────────────┘   │
│                                             │
│  ┌─ Mode Description ──────────────────┐   │
│  │ 🎯 Quick Migration Assessment       │   │
│  │                                     │   │
│  │ Perfect for rapid evaluations...    │   │
│  │                                     │   │
│  │ Features:                           │   │
│  │ • Streamlined workflow              │   │
│  │ • Faster execution time             │   │
│  │ • Core architecture analysis        │   │
│  │ ...                                 │   │
│  └─────────────────────────────────────┘   │
│                                             │
│     [Launch Advisor]  [Exit]                │
│                                             │
│  Ready to launch                            │
└─────────────────────────────────────────────┘
```

## Requirements

### GUI Mode
- Python 3.8+
- tkinter (usually included with Python)
- All dependencies from requirements.txt

### CLI Mode
- Python 3.8+
- All dependencies from requirements.txt

## Troubleshooting

### GUI Not Available

If you see "Warning: tkinter not available", the launcher will automatically fall back to CLI mode. To fix:

**macOS:**
```bash
# tkinter is usually included with Python
# If not, reinstall Python from python.org
```

**Linux:**
```bash
sudo apt-get install python3-tk  # Ubuntu/Debian
sudo yum install python3-tkinter  # CentOS/RHEL
```

**Windows:**
```bash
# tkinter is included with standard Python installation
# Reinstall Python from python.org if needed
```

### Submit Button Not Launching

If clicking Submit doesn't launch the advisor:

1. **Check console output**: Run the launcher from terminal/command prompt to see debug messages
   ```bash
   python run_sagemaker_migration_advisor_main.py
   ```

2. **Verify Streamlit is installed**:
   ```bash
   streamlit --version
   ```
   If not installed:
   ```bash
   pip install streamlit
   ```

3. **Check PATH**: Ensure Streamlit is in your system PATH
   ```bash
   # macOS/Linux
   which streamlit
   
   # Windows
   where streamlit
   ```

4. **Try the simple launcher**: Use the alternative launcher without GUI complexity
   ```bash
   python launch_advisor.py
   ```

5. **Run directly**: If launcher issues persist, run the advisor directly
   ```bash
   streamlit run sagemaker_migration_advisor_lite.py
   # or
   streamlit run sagemaker_migration_advisor.py
   ```

### Streamlit Not Found

If you get "Streamlit command not found":

```bash
# Install Streamlit
pip install streamlit

# Verify installation
streamlit --version

# If still not found, try with full path
python -m streamlit run sagemaker_migration_advisor_lite.py
```

### Process Starts But Browser Doesn't Open

1. **Manual browser access**: If Streamlit starts but browser doesn't open, look for the URL in console output (usually `http://localhost:8501`)

2. **Port already in use**: If port 8501 is busy, Streamlit will use another port. Check console for the actual URL.

3. **Firewall issues**: Ensure your firewall allows localhost connections

### Script Not Found Error

Ensure both advisor scripts exist:
- `sagemaker_migration_advisor_lite.py`
- `sagemaker_migration_advisor.py`

### Permission Denied

Make the launcher executable:
```bash
chmod +x run_sagemaker_migration_advisor_main.py
```

### Debug Mode

To see detailed debug output, check the console where you launched the GUI. The updated launcher prints:
- Streamlit path detection
- Command being executed
- Working directory
- Process ID
- Any errors that occur

## Advanced Usage

### Force CLI Mode

Even if GUI is available:
```bash
python run_sagemaker_migration_advisor_main.py --cli
```

### Direct Script Execution

You can still run the advisors directly:

```bash
# Run Lite version directly
python sagemaker_migration_advisor_lite.py

# Run Regular version directly
python sagemaker_migration_advisor.py
```

## Integration

The launcher can be integrated into:

1. **IDE/Editor**: Add as a run configuration
2. **CI/CD Pipeline**: Use CLI mode for automation
3. **Desktop Shortcut**: Create a shortcut to the launcher
4. **Docker Container**: Include in containerized workflows

## Example Workflow

1. **Start the launcher:**
   ```bash
   python run_sagemaker_migration_advisor_main.py
   ```

2. **Select mode:**
   - Choose "Migration Advisor Lite" for quick assessment
   - Or "Migration Advisor Regular" for comprehensive analysis

3. **Review description:**
   - Read the mode features and best use cases

4. **Launch:**
   - Click "Launch Advisor" button
   - Launcher window hides during execution

5. **Complete:**
   - Launcher reappears when done
   - Check output directory for results

## Output

Both modes generate:
- PDF report in `generated-reports/` directory
- Diagrams in `generated-diagrams/` directory (Regular mode)
- Interaction logs for debugging

## Tips

- **First time users**: Start with Lite mode to understand the workflow
- **Complex migrations**: Use Regular mode for detailed analysis
- **Quick iterations**: Use Lite mode for rapid prototyping
- **Production planning**: Use Regular mode for final recommendations

## Support

For issues or questions:
1. Check the main README.md
2. Review the advisor-specific documentation
3. Check logs in the output directory
4. Ensure all dependencies are installed

## Version History

- **v1.0**: Initial launcher with GUI and CLI modes
- Supports both Lite and Regular advisor modes
- Automatic fallback to CLI when GUI unavailable
