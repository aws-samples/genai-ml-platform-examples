#!/usr/bin/env python3
"""
Basic usage example for mlp_sdk

This script demonstrates how to use mlp_sdk with a configuration file.

Prerequisites:
1. Generate admin-config.yaml using generate_admin_config.py
2. Place it at /home/sagemaker-user/.config/admin-config.yaml (or specify custom path)
3. Ensure AWS credentials are configured
"""

from mlp_sdk import MLP_Session
from mlp_sdk.exceptions import MLPSDKError, ConfigurationError


def example_session_initialization():
    """Example: Initialize MLP_Session with default config"""
    print("\n=== Example 1: Session Initialization ===\n")
    
    try:
        session = MLP_Session()
        
        print("✅ Session initialized successfully")
        print(f"   Config loaded from: {session.config_manager.config_path}")
        print(f"   SageMaker region: {session.region_name}")
        
    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
        print("\nTip: Generate config with: python examples/generate_admin_config.py")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_custom_config_path():
    """Example: Initialize with custom config path"""
    print("\n=== Example 2: Custom Config Path ===\n")
    
    try:
        # Initialize with custom config path
        session = MLP_Session(config_path="./admin-config.yaml")
        print("✅ Session initialized with custom config")
        print(f"   Config loaded from: {session.config_manager.config_path}")
        
    except ConfigurationError as e:
        print(f"❌ Configuration error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


def example_view_configuration():
    """Example: View loaded configuration"""
    print("\n=== Example 3: View Configuration ===\n")
    
    try:
        session = MLP_Session()
        mlp_config = session.config_manager.MLP_config
        
        if mlp_config:
            print("📋 Loaded Configuration:")
            print(f"   S3 Bucket: {mlp_config.s3_config.default_bucket}")
            print(f"   VPC ID: {mlp_config.networking_config.vpc_id}")
            print(f"   Processing Instance: {mlp_config.compute_config.processing_instance_type}")
            print(f"   Training Instance: {mlp_config.compute_config.training_instance_type}")
            print(f"   Execution Role: {mlp_config.iam_config.execution_role}")
        else:
            print("📋 No configuration loaded (using SageMaker SDK defaults)")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def example_logging_configuration():
    """Example: Configure logging"""
    print("\n=== Example 4: Logging Configuration ===\n")
    
    try:
        # Initialize with custom log level
        session = MLP_Session(log_level="DEBUG")
        print("✅ Session initialized with DEBUG logging")
        
        # Change log level at runtime
        session.set_log_level("INFO")
        print("✅ Log level changed to INFO")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def example_audit_trail():
    """Example: View audit trail"""
    print("\n=== Example 5: Audit Trail ===\n")
    
    try:
        # Initialize with audit trail enabled (default)
        session = MLP_Session()
        
        # Perform some operations (these would normally be actual SageMaker operations)
        # For this example, we'll just show how to access the audit trail
        
        # Get audit trail
        audit_entries = session.get_audit_trail()
        print(f"📊 Audit trail entries: {len(audit_entries)}")
        
        if audit_entries:
            print("\nRecent operations:")
            for entry in audit_entries[-5:]:  # Show last 5
                print(f"   - {entry.get('timestamp')}: {entry.get('operation')}")
        
    except Exception as e:
        print(f"❌ Error: {e}")


def example_error_handling():
    """Example: Error handling"""
    print("\n=== Example 6: Error Handling ===\n")
    
    try:
        # Try to initialize with non-existent config
        session = MLP_Session(config_path="/nonexistent/path/config.yaml")
        
    except ConfigurationError as e:
        print(f"✅ Caught ConfigurationError as expected: {e}")
        
    except MLPSDKError as e:
        print(f"✅ Caught MLPSDKError: {e}")
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")


def main():
    """Run all examples"""
    print("=" * 60)
    print("mlp_sdk Basic Usage Examples")
    print("=" * 60)
    
    # Run examples
    example_session_initialization()
    example_custom_config_path()
    example_view_configuration()
    example_logging_configuration()
    example_audit_trail()
    example_error_handling()
    
    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)
    print("\n📚 For more examples, see:")
    print("   - docs/USAGE_EXAMPLES.md")
    print("   - docs/CONFIGURATION_GUIDE.md")
    print("   - docs/ENCRYPTION_GUIDE.md")
    print()


if __name__ == "__main__":
    main()
