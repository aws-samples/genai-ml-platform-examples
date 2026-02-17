# Troubleshooting Guide - SageMaker Migration Advisor

## Launcher Issues

### Submit Button Not Responding

**Symptoms**: Clicking Submit button in GUI launcher doesn't start the advisor

**Solutions**:

1. **Check Console Output**
   - Run launcher from terminal to see debug messages
   - Look for error messages or exceptions
   ```bash
   python run_sagemaker_migration_advisor_main.py
   ```

2. **Verify Streamlit Installation**
   ```bash
   # Check if Streamlit is installed
   streamlit --version
   
   # If not installed
   pip install streamlit
   
   # Verify it's in PATH
   which streamlit  # macOS/Linux
   where streamlit  # Windows
   ```

3. **Use Alternative Launchers**
   
   If GUI launcher has issues, try these alternatives:
   
   **Simple Python Launcher:**
   ```bash
   python launch_advisor.py
   ```
   
   **Shell Scripts (macOS/Linux):**
   ```bash
   ./launch_lite.sh
   # or
   ./launch_regular.sh
   ```
   
   **Batch Files (Windows):**
   ```cmd
   launch_lite.bat
   REM or
   launch_regular.bat
   ```
   
   **Direct Streamlit:**
   ```bash
   streamlit run sagemaker_migration_advisor_lite.py
   # or
   streamlit run sagemaker_migration_advisor.py
   ```

4. **Check Debug Output**
   
   The updated launcher prints debug information:
   - Streamlit path detection
   - Command being executed
   - Process ID
   - Any errors
   
   Look for lines starting with "DEBUG:" in the console

5. **Test Streamlit Manually**
   ```bash
   # Try running Streamlit directly
   cd migration/SageMakerMigrationAdvisor
   streamlit run sagemaker_migration_advisor_lite.py
   ```

### GUI Not Available

**Symptoms**: "Warning: tkinter not available"

**Solutions**:

**macOS:**
```bash
# tkinter usually comes with Python
# If missing, reinstall Python from python.org
brew install python-tk  # if using Homebrew
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install python3-tk

# CentOS/RHEL
sudo yum install python3-tkinter

# Fedora
sudo dnf install python3-tkinter
```

**Windows:**
```
# tkinter is included with standard Python
# Reinstall Python from python.org if needed
```

**Workaround**: Use CLI mode or alternative launchers (see above)

### Streamlit Not Found

**Symptoms**: "Streamlit command not found" or "FileNotFoundError"

**Solutions**:

1. **Install Streamlit**
   ```bash
   pip install streamlit
   ```

2. **Check Installation**
   ```bash
   pip list | grep streamlit
   streamlit --version
   ```

3. **Use Python Module Syntax**
   ```bash
   python -m streamlit run sagemaker_migration_advisor_lite.py
   ```

4. **Check PATH**
   ```bash
   # macOS/Linux
   echo $PATH
   which streamlit
   
   # Windows
   echo %PATH%
   where streamlit
   ```

5. **Reinstall in Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # macOS/Linux
   # or
   venv\Scripts\activate  # Windows
   
   pip install -r requirements.txt
   ```

### Process Starts But Browser Doesn't Open

**Symptoms**: Launcher says "running" but no browser window

**Solutions**:

1. **Manual Browser Access**
   - Look for URL in console output (usually `http://localhost:8501`)
   - Open browser manually and navigate to that URL

2. **Check Port Availability**
   ```bash
   # Check if port 8501 is in use
   # macOS/Linux
   lsof -i :8501
   
   # Windows
   netstat -ano | findstr :8501
   ```

3. **Use Different Port**
   ```bash
   streamlit run sagemaker_migration_advisor_lite.py --server.port 8502
   ```

4. **Check Firewall**
   - Ensure firewall allows localhost connections
   - Temporarily disable firewall to test

### Windows Encoding Errors

**Symptoms**: `'charmap' codec can't encode character`

**Solutions**:

This has been fixed in the latest version. If you still see this:

1. **Update Files**
   - Ensure you have the latest version with UTF-8 encoding fixes

2. **Set Environment Variable**
   ```cmd
   set PYTHONIOENCODING=utf-8
   python run_sagemaker_migration_advisor_main.py
   ```

3. **Use PowerShell**
   ```powershell
   $env:PYTHONIOENCODING="utf-8"
   python run_sagemaker_migration_advisor_main.py
   ```

## Application Issues

### Blank Page in Streamlit

**Symptoms**: Streamlit loads but shows blank page

**Solutions**:

1. **Check Browser Console**
   - Open browser developer tools (F12)
   - Look for JavaScript errors

2. **Clear Browser Cache**
   - Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (macOS)
   - Clear cache and cookies

3. **Try Different Browser**
   - Chrome, Firefox, Safari, Edge

4. **Check Streamlit Version**
   ```bash
   pip install --upgrade streamlit
   ```

### Diagram Generation Blank (Lite Version)

**Symptoms**: Diagram step shows blank page in Lite version

**Status**: Fixed in latest version

**Solution**: Update to latest version where diagram step is automatically skipped in Lite mode

### AWS Credentials Issues

**Symptoms**: "Unable to locate credentials" or authentication errors

**Solutions**:

1. **Configure AWS CLI**
   ```bash
   aws configure
   # or for SSO
   aws configure sso
   ```

2. **Check Credentials**
   ```bash
   aws sts get-caller-identity
   ```

3. **Set Environment Variables**
   ```bash
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-west-2
   ```

4. **Check Bedrock Access**
   ```bash
   aws bedrock list-foundation-models --region us-west-2
   ```

### PDF Generation Fails

**Symptoms**: Error during PDF report generation

**Solutions**:

1. **Check Dependencies**
   ```bash
   pip install reportlab pillow
   ```

2. **Check Disk Space**
   - Ensure sufficient disk space for PDF generation

3. **Check Permissions**
   - Ensure write permissions in output directory

4. **Check Logs**
   - Look for detailed error messages in console output

## Performance Issues

### Slow Response Times

**Solutions**:

1. **Use Lite Version**
   - Faster execution for quick assessments

2. **Check Network**
   - Ensure stable internet connection for AWS API calls

3. **Check AWS Region**
   - Use region closest to you
   - Ensure Bedrock is available in that region

### High Memory Usage

**Solutions**:

1. **Close Other Applications**
   - Free up system memory

2. **Use Lite Version**
   - Lower memory footprint

3. **Restart Application**
   - Fresh start can help

## Getting Help

### Debug Mode

Run with debug output:
```bash
# The GUI launcher now includes debug output
python run_sagemaker_migration_advisor_main.py
```

Look for lines starting with "DEBUG:" for detailed information.

### Log Files

Check log files in:
- `logs/app.log` - Application logs
- `advisor_agent_interactions.txt` - Agent interaction logs

### Report Issues

When reporting issues, include:
1. Python version: `python --version`
2. Streamlit version: `streamlit --version`
3. Operating system
4. Error messages from console
5. Steps to reproduce

### Quick Fixes Summary

| Issue | Quick Fix |
|-------|-----------|
| Submit button not working | Use `python launch_advisor.py` |
| GUI not available | Use `--cli` flag or shell scripts |
| Streamlit not found | `pip install streamlit` |
| Browser doesn't open | Manually open `http://localhost:8501` |
| Encoding errors | Already fixed in latest version |
| Blank diagram page | Already fixed in latest version |
| AWS credentials | Run `aws configure` |

### Alternative Launch Methods (In Order of Simplicity)

1. **Shell Scripts** (Simplest)
   ```bash
   ./launch_lite.sh  # or launch_lite.bat on Windows
   ```

2. **Simple Python Launcher**
   ```bash
   python launch_advisor.py
   ```

3. **GUI Launcher**
   ```bash
   python run_sagemaker_migration_advisor_main.py
   ```

4. **Direct Streamlit**
   ```bash
   streamlit run sagemaker_migration_advisor_lite.py
   ```

Choose the method that works best for your environment!
