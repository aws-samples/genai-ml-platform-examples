#!/usr/bin/env python3
"""
SageMaker Domain Deletion Script

Safely deletes a SageMaker domain and all dependent resources in the correct order:
1. Delete all apps in all spaces
2. Delete all spaces
3. Delete all user profiles
4. Delete the domain
5. Clean up EFS mounts and ENIs (optional)

Usage:
    python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2
    python delete_sagemaker_domain.py --domain-name my-domain --region us-west-2 --cleanup-network
"""

import argparse
import boto3
import time
import sys
from typing import List, Dict, Optional
from botocore.exceptions import ClientError


class SageMakerDomainCleaner:
    """Handles safe deletion of SageMaker domains and dependent resources."""
    
    def __init__(self, region: str, dry_run: bool = False):
        """
        Initialize the domain cleaner.
        
        Args:
            region: AWS region
            dry_run: If True, only print what would be deleted without actually deleting
        """
        self.region = region
        self.dry_run = dry_run
        self.sagemaker = boto3.client('sagemaker', region_name=region)
        self.ec2 = boto3.client('ec2', region_name=region)
        self.efs = boto3.client('efs', region_name=region)
        
        print(f"Initialized SageMaker Domain Cleaner for region: {region}")
        if dry_run:
            print("DRY RUN MODE: No resources will be deleted")
        print()
    
    def get_domain_id(self, domain_name: str) -> Optional[str]:
        """
        Get domain ID from domain name.
        
        Args:
            domain_name: Name of the domain
            
        Returns:
            Domain ID or None if not found
        """
        try:
            response = self.sagemaker.list_domains()
            for domain in response.get('Domains', []):
                if domain['DomainName'] == domain_name:
                    return domain['DomainId']
            
            print(f"ERROR: Domain '{domain_name}' not found")
            return None
            
        except ClientError as e:
            print(f"ERROR: Failed to list domains: {e}")
            return None
    
    def get_domain_details(self, domain_id: str) -> Optional[Dict]:
        """
        Get domain details.
        
        Args:
            domain_id: Domain ID
            
        Returns:
            Domain details or None if not found
        """
        try:
            response = self.sagemaker.describe_domain(DomainId=domain_id)
            return response
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFound':
                print(f"ERROR: Domain '{domain_id}' not found")
            else:
                print(f"ERROR: Failed to describe domain: {e}")
            return None
    
    def list_apps(self, domain_id: str, user_profile_name: Optional[str] = None, 
                  space_name: Optional[str] = None) -> List[Dict]:
        """
        List all apps in a domain, user profile, or space.
        
        Args:
            domain_id: Domain ID
            user_profile_name: Optional user profile name
            space_name: Optional space name
            
        Returns:
            List of app details
        """
        try:
            params = {'DomainIdEquals': domain_id}
            if user_profile_name:
                params['UserProfileNameEquals'] = user_profile_name
            if space_name:
                params['SpaceNameEquals'] = space_name
            
            apps = []
            paginator = self.sagemaker.get_paginator('list_apps')
            for page in paginator.paginate(**params):
                apps.extend(page.get('Apps', []))
            
            return apps
            
        except ClientError as e:
            print(f"ERROR: Failed to list apps: {e}")
            return []
    
    def delete_app(self, domain_id: str, app_name: str, app_type: str,
                   user_profile_name: Optional[str] = None,
                   space_name: Optional[str] = None) -> bool:
        """
        Delete a single app.
        
        Args:
            domain_id: Domain ID
            app_name: App name
            app_type: App type (JupyterServer, KernelGateway, etc.)
            user_profile_name: Optional user profile name
            space_name: Optional space name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            params = {
                'DomainId': domain_id,
                'AppName': app_name,
                'AppType': app_type
            }
            
            if user_profile_name:
                params['UserProfileName'] = user_profile_name
            if space_name:
                params['SpaceName'] = space_name
            
            location = f"user profile '{user_profile_name}'" if user_profile_name else f"space '{space_name}'"
            
            if self.dry_run:
                print(f"  [DRY RUN] Would delete app '{app_name}' ({app_type}) in {location}")
                return True
            
            print(f"  Deleting app '{app_name}' ({app_type}) in {location}...", end='')
            self.sagemaker.delete_app(**params)
            print(" ✓")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFound':
                print(f" (already deleted)")
                return True
            else:
                print(f" ✗")
                print(f"    ERROR: {e}")
                return False
    
    def wait_for_apps_deletion(self, domain_id: str, max_wait: int = 600) -> bool:
        """
        Wait for all apps to be deleted.
        
        Args:
            domain_id: Domain ID
            max_wait: Maximum wait time in seconds
            
        Returns:
            True if all apps deleted, False if timeout
        """
        if self.dry_run:
            return True
        
        print(f"\nWaiting for apps to be deleted (max {max_wait}s)...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            apps = self.list_apps(domain_id)
            
            # Filter out deleted apps
            active_apps = [app for app in apps if app['Status'] != 'Deleted']
            
            if not active_apps:
                print("All apps deleted ✓")
                return True
            
            print(f"  {len(active_apps)} apps still deleting...", end='\r')
            time.sleep(10)
        
        print(f"\nWARNING: Timeout waiting for apps deletion")
        return False
    
    def list_spaces(self, domain_id: str) -> List[Dict]:
        """
        List all spaces in a domain.
        
        Args:
            domain_id: Domain ID
            
        Returns:
            List of space details
        """
        try:
            spaces = []
            paginator = self.sagemaker.get_paginator('list_spaces')
            for page in paginator.paginate(DomainIdEquals=domain_id):
                spaces.extend(page.get('Spaces', []))
            
            return spaces
            
        except ClientError as e:
            print(f"ERROR: Failed to list spaces: {e}")
            return []
    
    def delete_space(self, domain_id: str, space_name: str) -> bool:
        """
        Delete a space.
        
        Args:
            domain_id: Domain ID
            space_name: Space name
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if self.dry_run:
                print(f"  [DRY RUN] Would delete space '{space_name}'")
                return True
            
            print(f"  Deleting space '{space_name}'...", end='')
            self.sagemaker.delete_space(DomainId=domain_id, SpaceName=space_name)
            print(" ✓")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFound':
                print(f" (already deleted)")
                return True
            else:
                print(f" ✗")
                print(f"    ERROR: {e}")
                return False
    
    def wait_for_spaces_deletion(self, domain_id: str, max_wait: int = 300) -> bool:
        """
        Wait for all spaces to be deleted.
        
        Args:
            domain_id: Domain ID
            max_wait: Maximum wait time in seconds
            
        Returns:
            True if all spaces deleted, False if timeout
        """
        if self.dry_run:
            return True
        
        print(f"\nWaiting for spaces to be deleted (max {max_wait}s)...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            spaces = self.list_spaces(domain_id)
            
            # Filter out deleted spaces
            active_spaces = [space for space in spaces if space.get('Status') != 'Deleted']
            
            if not active_spaces:
                print("All spaces deleted ✓")
                return True
            
            print(f"  {len(active_spaces)} spaces still deleting...", end='\r')
            time.sleep(10)
        
        print(f"\nWARNING: Timeout waiting for spaces deletion")
        return False
    
    def list_user_profiles(self, domain_id: str) -> List[Dict]:
        """
        List all user profiles in a domain.
        
        Args:
            domain_id: Domain ID
            
        Returns:
            List of user profile details
        """
        try:
            profiles = []
            paginator = self.sagemaker.get_paginator('list_user_profiles')
            for page in paginator.paginate(DomainIdEquals=domain_id):
                profiles.extend(page.get('UserProfiles', []))
            
            return profiles
            
        except ClientError as e:
            print(f"ERROR: Failed to list user profiles: {e}")
            return []
    
    def delete_user_profile(self, domain_id: str, user_profile_name: str, max_retries: int = 3) -> bool:
        """
        Delete a user profile with retry logic.
        
        Args:
            domain_id: Domain ID
            user_profile_name: User profile name
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print(f"  [DRY RUN] Would delete user profile '{user_profile_name}'")
            return True
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"  Retrying user profile '{user_profile_name}' (attempt {attempt + 1}/{max_retries})...", end='')
                else:
                    print(f"  Deleting user profile '{user_profile_name}'...", end='')
                
                self.sagemaker.delete_user_profile(
                    DomainId=domain_id,
                    UserProfileName=user_profile_name
                )
                print(" ✓")
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFound':
                    print(f" (already deleted)")
                    return True
                elif e.response['Error']['Code'] == 'ResourceInUse' and attempt < max_retries - 1:
                    print(f" (resource in use, waiting...)")
                    time.sleep(30)  # Wait before retry
                else:
                    print(f" ✗")
                    print(f"    ERROR: {e}")
                    return False
        
        return False
    
    def delete_domain(self, domain_id: str, retention_policy: str = 'Delete', max_retries: int = 3) -> bool:
        """
        Delete the domain with retry logic.
        
        Args:
            domain_id: Domain ID
            retention_policy: 'Delete' or 'Retain' for EFS
            max_retries: Maximum number of retry attempts
            
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print(f"[DRY RUN] Would delete domain '{domain_id}' with retention policy '{retention_policy}'")
            return True
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    print(f"Retrying domain deletion (attempt {attempt + 1}/{max_retries})...", end='')
                else:
                    print(f"Deleting domain '{domain_id}'...", end='')
                
                self.sagemaker.delete_domain(
                    DomainId=domain_id,
                    RetentionPolicy={'HomeEfsFileSystem': retention_policy}
                )
                print(" ✓")
                return True
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFound':
                    print(f" (already deleted)")
                    return True
                elif e.response['Error']['Code'] == 'ResourceInUse' and attempt < max_retries - 1:
                    print(f" (resource in use, waiting...)")
                    time.sleep(30)  # Wait before retry
                else:
                    print(f" ✗")
                    print(f"    ERROR: {e}")
                    return False
        
        return False
    
    def cleanup_network_resources(self, domain_details: Dict) -> bool:
        """
        Clean up network resources (ENIs) associated with the domain.
        
        Args:
            domain_details: Domain details from describe_domain
            
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print("[DRY RUN] Would clean up network resources")
            return True
        
        print("\nCleaning up network resources...")
        
        # Get VPC and subnets from domain
        vpc_id = domain_details.get('VpcId')
        subnet_ids = domain_details.get('SubnetIds', [])
        
        if not vpc_id or not subnet_ids:
            print("  No VPC/subnet information found")
            return True
        
        try:
            # Find ENIs associated with SageMaker in these subnets
            response = self.ec2.describe_network_interfaces(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'subnet-id', 'Values': subnet_ids},
                    {'Name': 'description', 'Values': ['*SageMaker*']}
                ]
            )
            
            enis = response.get('NetworkInterfaces', [])
            
            if not enis:
                print("  No SageMaker ENIs found")
                return True
            
            print(f"  Found {len(enis)} SageMaker ENIs")
            
            for eni in enis:
                eni_id = eni['NetworkInterfaceId']
                status = eni['Status']
                
                if status == 'in-use':
                    print(f"    ENI {eni_id} is in use, skipping")
                    continue
                
                try:
                    print(f"    Deleting ENI {eni_id}...", end='')
                    self.ec2.delete_network_interface(NetworkInterfaceId=eni_id)
                    print(" ✓")
                except ClientError as e:
                    print(f" ✗")
                    print(f"      ERROR: {e}")
            
            return True
            
        except ClientError as e:
            print(f"  ERROR: Failed to clean up network resources: {e}")
            return False
    
    def cleanup_efs(self, domain_details: Dict) -> bool:
        """
        Clean up EFS file system associated with the domain.
        
        Args:
            domain_details: Domain details from describe_domain
            
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print("[DRY RUN] Would clean up EFS file system")
            return True
        
        print("\nCleaning up EFS file system...")
        
        efs_id = domain_details.get('HomeEfsFileSystemId')
        
        if not efs_id:
            print("  No EFS file system found")
            return True
        
        try:
            # Delete mount targets first
            response = self.efs.describe_mount_targets(FileSystemId=efs_id)
            mount_targets = response.get('MountTargets', [])
            
            if mount_targets:
                print(f"  Found {len(mount_targets)} mount targets")
                for mt in mount_targets:
                    mt_id = mt['MountTargetId']
                    try:
                        print(f"    Deleting mount target {mt_id}...", end='')
                        self.efs.delete_mount_target(MountTargetId=mt_id)
                        print(" ✓")
                    except ClientError as e:
                        print(f" ✗")
                        print(f"      ERROR: {e}")
                
                # Wait for mount targets to be deleted
                print("  Waiting for mount targets to be deleted...")
                time.sleep(30)
            
            # Delete the file system
            print(f"  Deleting EFS file system {efs_id}...", end='')
            self.efs.delete_file_system(FileSystemId=efs_id)
            print(" ✓")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'FileSystemNotFound':
                print("  (already deleted)")
                return True
            else:
                print(f"  ERROR: Failed to clean up EFS: {e}")
                return False
    
    def check_vpc_usage(self, vpc_id: str) -> Dict[str, List]:
        """
        Check if VPC is used by other resources.
        
        Args:
            vpc_id: VPC ID
            
        Returns:
            Dictionary with lists of resources using the VPC
        """
        usage = {
            'sagemaker_domains': [],
            'ec2_instances': [],
            'rds_instances': [],
            'lambda_functions': [],
            'eni_count': 0
        }
        
        try:
            # Check for other SageMaker domains
            response = self.sagemaker.list_domains()
            for domain in response.get('Domains', []):
                try:
                    details = self.sagemaker.describe_domain(DomainId=domain['DomainId'])
                    if details.get('VpcId') == vpc_id:
                        usage['sagemaker_domains'].append(domain['DomainId'])
                except ClientError:
                    pass
            
            # Check for EC2 instances
            response = self.ec2.describe_instances(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    if instance['State']['Name'] not in ['terminated', 'shutting-down']:
                        usage['ec2_instances'].append(instance['InstanceId'])
            
            # Check for network interfaces
            response = self.ec2.describe_network_interfaces(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            usage['eni_count'] = len(response.get('NetworkInterfaces', []))
            
            # Check for RDS instances
            try:
                rds = boto3.client('rds', region_name=self.region)
                response = rds.describe_db_instances()
                for db in response.get('DBInstances', []):
                    if db.get('DBSubnetGroup', {}).get('VpcId') == vpc_id:
                        usage['rds_instances'].append(db['DBInstanceIdentifier'])
            except Exception:
                pass  # RDS check is optional
            
            # Check for Lambda functions
            try:
                lambda_client = boto3.client('lambda', region_name=self.region)
                paginator = lambda_client.get_paginator('list_functions')
                for page in paginator.paginate():
                    for func in page.get('Functions', []):
                        vpc_config = func.get('VpcConfig', {})
                        if vpc_config.get('VpcId') == vpc_id:
                            usage['lambda_functions'].append(func['FunctionName'])
            except Exception:
                pass  # Lambda check is optional
            
        except ClientError as e:
            print(f"  WARNING: Error checking VPC usage: {e}")
        
        return usage
    
    def check_subnet_usage(self, subnet_id: str) -> Dict[str, List]:
        """
        Check if subnet is used by other resources.
        
        Args:
            subnet_id: Subnet ID
            
        Returns:
            Dictionary with lists of resources using the subnet
        """
        usage = {
            'sagemaker_domains': [],
            'ec2_instances': [],
            'eni_count': 0
        }
        
        try:
            # Check for SageMaker domains
            response = self.sagemaker.list_domains()
            for domain in response.get('Domains', []):
                try:
                    details = self.sagemaker.describe_domain(DomainId=domain['DomainId'])
                    if subnet_id in details.get('SubnetIds', []):
                        usage['sagemaker_domains'].append(domain['DomainId'])
                except ClientError:
                    pass
            
            # Check for EC2 instances
            response = self.ec2.describe_instances(
                Filters=[{'Name': 'subnet-id', 'Values': [subnet_id]}]
            )
            for reservation in response.get('Reservations', []):
                for instance in reservation.get('Instances', []):
                    if instance['State']['Name'] not in ['terminated', 'shutting-down']:
                        usage['ec2_instances'].append(instance['InstanceId'])
            
            # Check for network interfaces
            response = self.ec2.describe_network_interfaces(
                Filters=[{'Name': 'subnet-id', 'Values': [subnet_id]}]
            )
            usage['eni_count'] = len(response.get('NetworkInterfaces', []))
            
        except ClientError as e:
            print(f"  WARNING: Error checking subnet usage: {e}")
        
        return usage
    
    def cleanup_subnets(self, subnet_ids: List[str], force: bool = False) -> bool:
        """
        Clean up subnets if they're not used by other resources.
        
        Args:
            subnet_ids: List of subnet IDs
            force: If True, skip usage checks (dangerous!)
            
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print(f"[DRY RUN] Would clean up {len(subnet_ids)} subnets")
            return True
        
        print(f"\nCleaning up subnets...")
        print(f"Found {len(subnet_ids)} subnets to check")
        
        for subnet_id in subnet_ids:
            print(f"\n  Subnet: {subnet_id}")
            
            # Check usage unless force is enabled
            if not force:
                usage = self.check_subnet_usage(subnet_id)
                
                # Check if subnet is in use
                if usage['sagemaker_domains']:
                    print(f"    ⚠ SKIPPING: Used by {len(usage['sagemaker_domains'])} SageMaker domain(s)")
                    continue
                
                if usage['ec2_instances']:
                    print(f"    ⚠ SKIPPING: Used by {len(usage['ec2_instances'])} EC2 instance(s)")
                    continue
                
                if usage['eni_count'] > 0:
                    print(f"    ⚠ SKIPPING: Has {usage['eni_count']} network interface(s)")
                    continue
                
                print("    ✓ Not in use by other resources")
            
            # Delete the subnet
            try:
                print(f"    Deleting subnet...", end='')
                self.ec2.delete_subnet(SubnetId=subnet_id)
                print(" ✓")
            except ClientError as e:
                if e.response['Error']['Code'] == 'DependencyViolation':
                    print(f" ✗")
                    print(f"      ERROR: Subnet has dependencies: {e}")
                else:
                    print(f" ✗")
                    print(f"      ERROR: {e}")
        
        return True
    
    def cleanup_vpc(self, vpc_id: str, force: bool = False) -> bool:
        """
        Clean up VPC if it's not used by other resources.
        
        Args:
            vpc_id: VPC ID
            force: If True, skip usage checks (dangerous!)
            
        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            print("[DRY RUN] Would clean up VPC")
            return True
        
        print(f"\nCleaning up VPC...")
        print(f"VPC ID: {vpc_id}")
        
        # Check usage unless force is enabled
        if not force:
            usage = self.check_vpc_usage(vpc_id)
            
            # Check if VPC is in use
            if usage['sagemaker_domains']:
                print(f"  ⚠ SKIPPING: Used by {len(usage['sagemaker_domains'])} SageMaker domain(s)")
                print(f"    Domains: {', '.join(usage['sagemaker_domains'])}")
                return False
            
            if usage['ec2_instances']:
                print(f"  ⚠ SKIPPING: Used by {len(usage['ec2_instances'])} EC2 instance(s)")
                return False
            
            if usage['rds_instances']:
                print(f"  ⚠ SKIPPING: Used by {len(usage['rds_instances'])} RDS instance(s)")
                return False
            
            if usage['lambda_functions']:
                print(f"  ⚠ SKIPPING: Used by {len(usage['lambda_functions'])} Lambda function(s)")
                return False
            
            if usage['eni_count'] > 0:
                print(f"  ⚠ SKIPPING: Has {usage['eni_count']} network interface(s)")
                return False
            
            print("  ✓ Not in use by other resources")
        
        try:
            # Delete internet gateways
            response = self.ec2.describe_internet_gateways(
                Filters=[{'Name': 'attachment.vpc-id', 'Values': [vpc_id]}]
            )
            for igw in response.get('InternetGateways', []):
                igw_id = igw['InternetGatewayId']
                print(f"  Detaching internet gateway {igw_id}...", end='')
                self.ec2.detach_internet_gateway(InternetGatewayId=igw_id, VpcId=vpc_id)
                print(" ✓")
                print(f"  Deleting internet gateway {igw_id}...", end='')
                self.ec2.delete_internet_gateway(InternetGatewayId=igw_id)
                print(" ✓")
            
            # Delete NAT gateways
            response = self.ec2.describe_nat_gateways(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for nat in response.get('NatGateways', []):
                if nat['State'] not in ['deleted', 'deleting']:
                    nat_id = nat['NatGatewayId']
                    print(f"  Deleting NAT gateway {nat_id}...", end='')
                    self.ec2.delete_nat_gateway(NatGatewayId=nat_id)
                    print(" ✓")
            
            # Wait for NAT gateways to be deleted
            if response.get('NatGateways'):
                print("  Waiting for NAT gateways to be deleted...")
                time.sleep(30)
            
            # Delete route table associations and routes
            response = self.ec2.describe_route_tables(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for rt in response.get('RouteTables', []):
                rt_id = rt['RouteTableId']
                is_main = any(assoc.get('Main', False) for assoc in rt.get('Associations', []))
                
                if not is_main:
                    # Delete non-main route tables
                    print(f"  Deleting route table {rt_id}...", end='')
                    try:
                        self.ec2.delete_route_table(RouteTableId=rt_id)
                        print(" ✓")
                    except ClientError as e:
                        print(f" ✗")
                        print(f"    ERROR: {e}")
            
            # Delete security groups (except default)
            response = self.ec2.describe_security_groups(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for sg in response.get('SecurityGroups', []):
                if sg['GroupName'] != 'default':
                    sg_id = sg['GroupId']
                    print(f"  Deleting security group {sg_id}...", end='')
                    try:
                        self.ec2.delete_security_group(GroupId=sg_id)
                        print(" ✓")
                    except ClientError as e:
                        print(f" ✗")
                        print(f"    ERROR: {e}")
            
            # Delete network ACLs (except default)
            response = self.ec2.describe_network_acls(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            for acl in response.get('NetworkAcls', []):
                if not acl.get('IsDefault', False):
                    acl_id = acl['NetworkAclId']
                    print(f"  Deleting network ACL {acl_id}...", end='')
                    try:
                        self.ec2.delete_network_acl(NetworkAclId=acl_id)
                        print(" ✓")
                    except ClientError as e:
                        print(f" ✗")
                        print(f"    ERROR: {e}")
            
            # Finally, delete the VPC
            print(f"  Deleting VPC {vpc_id}...", end='')
            self.ec2.delete_vpc(VpcId=vpc_id)
            print(" ✓")
            return True
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'DependencyViolation':
                print(f" ✗")
                print(f"  ERROR: VPC has dependencies: {e}")
            else:
                print(f" ✗")
                print(f"  ERROR: {e}")
            return False
    
    def delete_domain_complete(self, domain_id: str, cleanup_network: bool = False,
                              cleanup_efs_manual: bool = False, cleanup_subnets: bool = False,
                              cleanup_vpc: bool = False, force_vpc_cleanup: bool = False) -> bool:
        """
        Complete domain deletion workflow.
        
        Args:
            domain_id: Domain ID
            cleanup_network: If True, clean up network resources (ENIs)
            cleanup_efs_manual: If True, manually clean up EFS (use with caution)
            cleanup_subnets: If True, clean up subnets if not used by other resources
            cleanup_vpc: If True, clean up VPC if not used by other resources
            force_vpc_cleanup: If True, skip usage checks for VPC/subnet cleanup (dangerous!)
            
        Returns:
            True if successful, False otherwise
        """
        print("=" * 80)
        print(f"SageMaker Domain Deletion: {domain_id}")
        print("=" * 80)
        print()
        
        # Get domain details
        domain_details = self.get_domain_details(domain_id)
        if not domain_details:
            return False
        
        domain_name = domain_details.get('DomainName', 'Unknown')
        print(f"Domain Name: {domain_name}")
        print(f"Domain ID: {domain_id}")
        print(f"Status: {domain_details.get('Status', 'Unknown')}")
        print()
        
        # Step 1: Delete all apps in all spaces
        print("Step 1: Deleting apps in spaces...")
        spaces = self.list_spaces(domain_id)
        
        if spaces:
            print(f"Found {len(spaces)} spaces")
            for space in spaces:
                space_name = space['SpaceName']
                print(f"\n  Space: {space_name}")
                
                apps = self.list_apps(domain_id, space_name=space_name)
                if apps:
                    print(f"    Found {len(apps)} apps")
                    for app in apps:
                        if app['Status'] != 'Deleted':
                            self.delete_app(
                                domain_id,
                                app['AppName'],
                                app['AppType'],
                                space_name=space_name
                            )
                else:
                    print("    No apps found")
        else:
            print("No spaces found")
        
        # Step 2: Delete all apps in user profiles
        print("\nStep 2: Deleting apps in user profiles...")
        user_profiles = self.list_user_profiles(domain_id)
        
        if user_profiles:
            print(f"Found {len(user_profiles)} user profiles")
            for profile in user_profiles:
                user_profile_name = profile['UserProfileName']
                print(f"\n  User Profile: {user_profile_name}")
                
                apps = self.list_apps(domain_id, user_profile_name=user_profile_name)
                if apps:
                    print(f"    Found {len(apps)} apps")
                    for app in apps:
                        if app['Status'] != 'Deleted':
                            self.delete_app(
                                domain_id,
                                app['AppName'],
                                app['AppType'],
                                user_profile_name=user_profile_name
                            )
                else:
                    print("    No apps found")
        else:
            print("No user profiles found")
        
        # Wait for all apps to be deleted
        if not self.wait_for_apps_deletion(domain_id):
            print("\nWARNING: Some apps may still be deleting. Continuing anyway...")
        
        # Step 3: Delete all spaces
        print("\nStep 3: Deleting spaces...")
        spaces = self.list_spaces(domain_id)
        
        if spaces:
            print(f"Found {len(spaces)} spaces")
            for space in spaces:
                self.delete_space(domain_id, space['SpaceName'])
            
            # Wait for spaces to be fully deleted
            if not self.wait_for_spaces_deletion(domain_id):
                print("\nWARNING: Some spaces may still be deleting. Continuing anyway...")
        else:
            print("No spaces found")
        
        # Step 4: Delete all user profiles
        print("\nStep 4: Deleting user profiles...")
        user_profiles = self.list_user_profiles(domain_id)
        
        if user_profiles:
            print(f"Found {len(user_profiles)} user profiles")
            for profile in user_profiles:
                self.delete_user_profile(domain_id, profile['UserProfileName'])
        else:
            print("No user profiles found")
        
        # Wait a bit for resources to clean up
        if not self.dry_run and (spaces or user_profiles):
            print("\nWaiting for resources to clean up...")
            time.sleep(30)
        
        # Step 5: Delete the domain
        print("\nStep 5: Deleting domain...")
        retention_policy = 'Delete' if cleanup_efs_manual else 'Retain'
        success = self.delete_domain(domain_id, retention_policy)
        
        if not success:
            return False
        
        # Step 6: Clean up network resources (optional)
        if cleanup_network:
            time.sleep(10)  # Wait a bit before cleaning up network
            self.cleanup_network_resources(domain_details)
        
        # Step 7: Clean up EFS manually (optional)
        if cleanup_efs_manual:
            time.sleep(30)  # Wait for domain deletion to progress
            self.cleanup_efs(domain_details)
        
        # Step 8: Clean up subnets (optional)
        if cleanup_subnets:
            subnet_ids = domain_details.get('SubnetIds', [])
            if subnet_ids:
                time.sleep(10)
                self.cleanup_subnets(subnet_ids, force=force_vpc_cleanup)
            else:
                print("\nNo subnets to clean up")
        
        # Step 9: Clean up VPC (optional)
        if cleanup_vpc:
            vpc_id = domain_details.get('VpcId')
            if vpc_id:
                time.sleep(10)
                self.cleanup_vpc(vpc_id, force=force_vpc_cleanup)
            else:
                print("\nNo VPC to clean up")
        
        print("\n" + "=" * 80)
        print("Domain deletion initiated successfully!")
        print("=" * 80)
        print()
        print("Note: Domain deletion is asynchronous and may take several minutes.")
        print("You can check the status with:")
        print(f"  aws sagemaker describe-domain --domain-id {domain_id}")
        print()
        
        return True


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Delete a SageMaker domain and all dependent resources',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Delete domain by ID
  python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2
  
  # Delete domain by name
  python delete_sagemaker_domain.py --domain-name my-domain --region us-west-2
  
  # Delete domain and clean up network resources
  python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2 --cleanup-network
  
  # Delete domain and clean up subnets (if not used by other resources)
  python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2 --cleanup-subnets
  
  # Delete domain and clean up VPC (if not used by other resources)
  python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2 --cleanup-vpc
  
  # Delete everything including VPC and subnets
  python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2 \\
    --cleanup-network --cleanup-efs --cleanup-subnets --cleanup-vpc
  
  # Force VPC cleanup without usage checks (DANGEROUS!)
  python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2 \\
    --cleanup-vpc --force-vpc-cleanup
  
  # Dry run (show what would be deleted)
  python delete_sagemaker_domain.py --domain-id d-xxxxx --region us-west-2 --dry-run
        """
    )
    
    parser.add_argument(
        '--domain-id',
        help='SageMaker domain ID (e.g., d-xxxxx)'
    )
    
    parser.add_argument(
        '--domain-name',
        help='SageMaker domain name (alternative to --domain-id)'
    )
    
    parser.add_argument(
        '--region',
        default='us-west-2',
        help='AWS region (default: us-west-2)'
    )
    
    parser.add_argument(
        '--cleanup-network',
        action='store_true',
        help='Clean up network resources (ENIs) after domain deletion'
    )
    
    parser.add_argument(
        '--cleanup-efs',
        action='store_true',
        help='Manually clean up EFS file system (use with caution)'
    )
    
    parser.add_argument(
        '--cleanup-subnets',
        action='store_true',
        help='Clean up subnets if not used by other resources'
    )
    
    parser.add_argument(
        '--cleanup-vpc',
        action='store_true',
        help='Clean up VPC if not used by other resources'
    )
    
    parser.add_argument(
        '--force-vpc-cleanup',
        action='store_true',
        help='Force VPC/subnet cleanup without usage checks (DANGEROUS!)'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be deleted without actually deleting'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.domain_id and not args.domain_name:
        parser.error('Either --domain-id or --domain-name must be specified')
    
    # Initialize cleaner
    cleaner = SageMakerDomainCleaner(args.region, dry_run=args.dry_run)
    
    # Get domain ID if name was provided
    domain_id = args.domain_id
    if args.domain_name:
        domain_id = cleaner.get_domain_id(args.domain_name)
        if not domain_id:
            sys.exit(1)
    
    # Confirm deletion (unless dry run)
    if not args.dry_run:
        print(f"WARNING: This will delete domain '{domain_id}' and all dependent resources!")
        print("This action cannot be undone.")
        print()
        response = input("Are you sure you want to continue? (yes/no): ")
        if response.lower() != 'yes':
            print("Deletion cancelled.")
            sys.exit(0)
        print()
    
    # Execute deletion
    success = cleaner.delete_domain_complete(
        domain_id,
        cleanup_network=args.cleanup_network,
        cleanup_efs_manual=args.cleanup_efs,
        cleanup_subnets=args.cleanup_subnets,
        cleanup_vpc=args.cleanup_vpc,
        force_vpc_cleanup=args.force_vpc_cleanup
    )
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
