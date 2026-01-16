#!/usr/bin/env python3
"""
Generate admin-config.yaml for mlp_sdk

This script generates a sample admin-config.yaml file with default values
that can be customized for your AWS environment.

Usage:
    python generate_admin_config.py [--output PATH] [--encrypted] [--key-source SOURCE]

Options:
    --output PATH           Output path for the config file (default: admin-config.yaml)
    --encrypted            Generate encrypted configuration
    --key-source SOURCE    Key source for encryption: env, file, or kms (default: env)
    --interactive          Interactive mode to prompt for values
"""

import argparse
import sys
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def get_default_config() -> Dict[str, Any]:
    """Return default configuration structure"""
    return {
        "defaults": {
            "s3": {
                "default_bucket": "my-sagemaker-bucket",
                "input_prefix": "input/",
                "output_prefix": "output/",
                "model_prefix": "models/",
            },
            "networking": {
                "vpc_id": "vpc-12345678",
                "security_group_ids": ["sg-12345678"],
                "subnets": ["subnet-12345678", "subnet-87654321"],
            },
            "compute": {
                "processing_instance_type": "ml.m5.large",
                "training_instance_type": "ml.m5.xlarge",
                "processing_instance_count": 1,
                "training_instance_count": 1,
            },
            "feature_store": {
                "offline_store_s3_uri": "s3://my-sagemaker-bucket/feature-store/",
                "enable_online_store": False,
            },
            "iam": {
                "execution_role": "arn:aws:iam::123456789012:role/SageMakerExecutionRole",
            },
            "kms": {
                "key_id": "arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID",
            },
        }
    }


def get_interactive_config() -> Dict[str, Any]:
    """Prompt user for configuration values interactively"""
    print("\n=== Interactive Configuration Generator ===\n")
    print("Press Enter to use default values shown in [brackets]\n")
    
    config = {"defaults": {}}
    
    # S3 Configuration
    print("--- S3 Configuration ---")
    default_bucket = input("S3 Bucket [my-sagemaker-bucket]: ").strip() or "my-sagemaker-bucket"
    input_prefix = input("Input Prefix [input/]: ").strip() or "input/"
    output_prefix = input("Output Prefix [output/]: ").strip() or "output/"
    model_prefix = input("Model Prefix [models/]: ").strip() or "models/"
    
    config["defaults"]["s3"] = {
        "default_bucket": default_bucket,
        "input_prefix": input_prefix,
        "output_prefix": output_prefix,
        "model_prefix": model_prefix,
    }
    
    # Networking Configuration
    print("\n--- Networking Configuration ---")
    vpc_id = input("VPC ID [vpc-12345678]: ").strip() or "vpc-12345678"
    sg_ids = input("Security Group IDs (comma-separated) [sg-12345678]: ").strip() or "sg-12345678"
    subnets = input("Subnets (comma-separated) [subnet-12345678,subnet-87654321]: ").strip() or "subnet-12345678,subnet-87654321"
    
    config["defaults"]["networking"] = {
        "vpc_id": vpc_id,
        "security_group_ids": [sg.strip() for sg in sg_ids.split(",")],
        "subnets": [subnet.strip() for subnet in subnets.split(",")],
    }
    
    # Compute Configuration
    print("\n--- Compute Configuration ---")
    proc_instance = input("Processing Instance Type [ml.m5.large]: ").strip() or "ml.m5.large"
    train_instance = input("Training Instance Type [ml.m5.xlarge]: ").strip() or "ml.m5.xlarge"
    proc_count = input("Processing Instance Count [1]: ").strip() or "1"
    train_count = input("Training Instance Count [1]: ").strip() or "1"
    
    config["defaults"]["compute"] = {
        "processing_instance_type": proc_instance,
        "training_instance_type": train_instance,
        "processing_instance_count": int(proc_count),
        "training_instance_count": int(train_count),
    }
    
    # Feature Store Configuration
    print("\n--- Feature Store Configuration ---")
    fs_s3_uri = input(f"Feature Store S3 URI [s3://{default_bucket}/feature-store/]: ").strip() or f"s3://{default_bucket}/feature-store/"
    enable_online = input("Enable Online Store? (yes/no) [no]: ").strip().lower() in ["yes", "y"]
    
    config["defaults"]["feature_store"] = {
        "offline_store_s3_uri": fs_s3_uri,
        "enable_online_store": enable_online,
    }
    
    # IAM Configuration
    print("\n--- IAM Configuration ---")
    exec_role = input("Execution Role ARN [arn:aws:iam::123456789012:role/SageMakerExecutionRole]: ").strip() or "arn:aws:iam::123456789012:role/SageMakerExecutionRole"
    
    config["defaults"]["iam"] = {
        "execution_role": exec_role,
    }
    
    # KMS Configuration
    print("\n--- KMS Configuration ---")
    kms_key = input("KMS Key ID [arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID]: ").strip() or "arn:aws:kms:REGION:ACCOUNT-ID:key/KEY-ID"
    
    config["defaults"]["kms"] = {
        "key_id": kms_key,
    }
    
    return config


def write_config(config: Dict[str, Any], output_path: Path, encrypted: bool = False, key_source: str = "env") -> None:
    """Write configuration to YAML file"""
    
    if encrypted:
        print("\n⚠️  Encryption requested but not yet implemented in this generator.")
        print("To encrypt your config file:")
        print("1. Generate the plain config first")
        print("2. Use mlp_sdk.config.ConfigurationManager.encrypt_config_file()")
        print("3. See docs/ENCRYPTION_GUIDE.md for details\n")
        
        response = input("Continue with plain text config? (yes/no): ").strip().lower()
        if response not in ["yes", "y"]:
            print("Aborted.")
            sys.exit(0)
    
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write YAML file
    with open(output_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, indent=2)
    
    print(f"\n✅ Configuration file generated: {output_path}")
    print(f"   File size: {output_path.stat().st_size} bytes")
    
    # Print next steps
    print("\n📋 Next Steps:")
    print(f"1. Review and customize the values in {output_path}")
    print("2. Update AWS resource IDs (VPC, subnets, security groups, etc.)")
    print("3. Set the correct IAM execution role ARN")
    print("4. Update S3 bucket names to match your environment")
    
    if not encrypted:
        print("5. (Optional) Encrypt the config file - see docs/ENCRYPTION_GUIDE.md")
    
    print(f"\n📍 Default config location: /home/sagemaker-user/.config/admin-config.yaml")
    print(f"   Current location: {output_path.absolute()}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate admin-config.yaml for mlp_sdk",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate default config
  python generate_admin_config.py
  
  # Generate config at specific location
  python generate_admin_config.py --output /home/sagemaker-user/.config/admin-config.yaml
  
  # Interactive mode
  python generate_admin_config.py --interactive
  
  # Generate encrypted config (requires setup)
  python generate_admin_config.py --encrypted --key-source env
        """
    )
    
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("admin-config.yaml"),
        help="Output path for the config file (default: admin-config.yaml)"
    )
    
    parser.add_argument(
        "--encrypted",
        action="store_true",
        help="Generate encrypted configuration (requires encryption key setup)"
    )
    
    parser.add_argument(
        "--key-source",
        choices=["env", "file", "kms"],
        default="env",
        help="Key source for encryption: env, file, or kms (default: env)"
    )
    
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode to prompt for values"
    )
    
    args = parser.parse_args()
    
    # Check if output file already exists
    if args.output.exists():
        print(f"⚠️  Warning: {args.output} already exists!")
        response = input("Overwrite? (yes/no): ").strip().lower()
        if response not in ["yes", "y"]:
            print("Aborted.")
            sys.exit(0)
    
    # Generate configuration
    if args.interactive:
        config = get_interactive_config()
    else:
        config = get_default_config()
    
    # Write configuration
    write_config(config, args.output, args.encrypted, args.key_source)


if __name__ == "__main__":
    main()
