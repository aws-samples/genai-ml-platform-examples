#!/usr/bin/env python3
"""
Simple launcher for SageMaker Migration Advisor
Direct execution without complex threading
"""

import sys
import subprocess
from pathlib import Path

def main():
    print("\n" + "="*60)
    print("  SageMaker Migration Advisor Launcher")
    print("="*60 + "\n")
    
    print("Select Migration Mode:\n")
    print("1. Migration Advisor Lite")
    print("   - Quick assessment (5-10 minutes)")
    print("   - Essential analysis and basic TCO")
    print()
    print("2. Migration Advisor Regular")
    print("   - Comprehensive analysis (15-30 minutes)")
    print("   - Detailed TCO and architecture diagrams")
    print()
    
    while True:
        choice = input("Enter your choice (1 or 2): ").strip()
        
        if choice == "1":
            script_name = "sagemaker_migration_advisor_lite.py"
            display_name = "Migration Advisor Lite"
            break
        elif choice == "2":
            script_name = "sagemaker_migration_advisor.py"
            display_name = "Migration Advisor Regular"
            break
        else:
            print("Invalid choice. Please enter 1 or 2.")
    
    # Get script path
    script_path = Path(__file__).parent / script_name
    
    if not script_path.exists():
        print(f"\n❌ Error: Script not found: {script_name}")
        print(f"   Please ensure the file exists in: {script_path.parent}")
        sys.exit(1)
    
    # Check if streamlit is installed
    try:
        result = subprocess.run(
            ["streamlit", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode != 0:
            raise FileNotFoundError()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print("\n❌ Error: Streamlit is not installed or not in PATH")
        print("\nPlease install Streamlit:")
        print("  pip install streamlit")
        print("\nThen run this launcher again.")
        sys.exit(1)
    
    print(f"\n🚀 Launching {display_name}...")
    print(f"   Script: {script_name}")
    print(f"   A browser window will open shortly...")
    print("\n" + "="*60 + "\n")
    
    try:
        # Launch streamlit directly
        subprocess.run(
            ["streamlit", "run", str(script_path)],
            cwd=str(script_path.parent)
        )
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error launching {display_name}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
