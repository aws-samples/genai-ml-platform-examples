#!/usr/bin/env python3
"""
Launcher script for SageMaker Migration Advisor Streamlit Application
"""

import subprocess
import sys
import os
from pathlib import Path

def check_requirements():
    """Check if required packages are installed"""
    required_packages = [
        'streamlit',
        'strands',
        'strands_tools',
        'boto3',
        'PIL'  # Pillow is imported as PIL
    ]
    
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing required packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\n📦 Install missing packages with:")
        print("   pip install -r requirements.txt")
        return False
    
    return True

def check_aws_credentials():
    """Check if AWS credentials are configured"""
    aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
    aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
    aws_profile = os.environ.get('AWS_PROFILE')
    
    if not (aws_access_key and aws_secret_key) and not aws_profile:
        print("⚠️  AWS credentials not found in environment variables.")
        print("   Make sure you have configured AWS credentials via:")
        print("   - Environment variables (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)")
        print("   - AWS CLI (aws configure)")
        print("   - IAM roles (if running on EC2)")
        return False
    
    return True

def main():
    """Main launcher function"""
    print("🚀 SageMaker Migration Advisor Launcher")
    print("=" * 50)
    
    # Check current directory
    current_dir = Path.cwd()
    app_file = current_dir / "sagemaker_migration_advisor_lite.py"
    
    if not app_file.exists():
        print(f"❌ Application file not found: {app_file}")
        print("   Make sure you're running this from the correct directory.")
        sys.exit(1)
    
    # Check requirements
    print("📋 Checking requirements...")
    if not check_requirements():
        sys.exit(1)
    
    # Check AWS credentials
    print("🔐 Checking AWS credentials...")
    if not check_aws_credentials():
        print("   ⚠️  Continuing anyway - you may encounter authentication errors.")
    
    # Check for required files
    required_files = [
        "prompts.py",
        "logger_config.py",
        "tools/__init__.py",
        "tools/user_prompt.py"
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("   Make sure all required files are present.")
        sys.exit(1)
    
    print("✅ All checks passed!")
    print("\n🌐 Starting Streamlit application...")
    print("   The app will open in your default web browser.")
    print("   Press Ctrl+C to stop the application.")
    print("\n" + "=" * 50)
    
    # Check if port is already in use and try to kill it
    port = 8501
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('localhost', port))
        sock.close()
        
        if result == 0:
            print(f"\n⚠️  Port {port} is already in use.")
            print("   Attempting to free the port...")
            try:
                # Try to kill the process using the port
                subprocess.run(f"lsof -ti:{port} | xargs kill -9", shell=True, stderr=subprocess.DEVNULL)
                print(f"   ✅ Port {port} freed successfully.")
                import time
                time.sleep(1)  # Wait a moment for port to be released
            except:
                print(f"   ⚠️  Could not automatically free port {port}.")
                print(f"   Please run: lsof -ti:{port} | xargs kill -9")
                print(f"   Or use a different port by editing run_sagemaker_migration_advisor.py")
                sys.exit(1)
    except:
        pass  # If we can't check, just try to start anyway
    
    # Launch Streamlit
    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run", 
            "sagemaker_migration_advisor.py",
            "--server.port", str(port),
            "--server.address", "localhost"
        ], check=True)
    except KeyboardInterrupt:
        print("\n👋 Application stopped by user.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running Streamlit: {e}")
        print(f"\n💡 Try running manually with a different port:")
        print(f"   streamlit run sagemaker_migration_advisor.py --server.port 8502")
        sys.exit(1)

if __name__ == "__main__":
    main()