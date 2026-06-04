import boto3
import json
import os
import requests
import subprocess
import shutil
import time

class GitOperations:
    def __init__(self, org_name, repo_name, profile_name, private_repo, public_aiops_code_folder):
        print("\n=== Initializing GitOperations ===")
        print(f"Organization Name: {org_name}")
        print(f"Repository Name: {repo_name}")
        print(f"Profile Name: {profile_name}")
        print(f"Private Repo: {private_repo}")
        print(f"Public AIOPS Code Folder: {public_aiops_code_folder}")
        
        self.org_name = org_name
        self.repo_name = repo_name
        self.profile_name = profile_name.lower()  
        self.private_repo = private_repo
        self.public_aiops_code_folder = public_aiops_code_folder
        self.temp_dir = '/tmp'
        self.source_repo_path = os.path.join(self.temp_dir, 'source_repo')
        self.private_repo_path = os.path.join(self.temp_dir, 'private_repo')

    def _get_git_credentials(self):
        try:
            secret_name = os.environ.get('GITHUB_TOKEN_SECRET_NAME')
            if not secret_name:
                raise Exception("GITHUB_TOKEN_SECRET_NAME environment variable not set")

            secrets_client = boto3.client('secretsmanager')
            response = secrets_client.get_secret_value(SecretId=secret_name)
            return json.loads(response['SecretString'])['token']
        except Exception as e:
            print(f"Error getting git credentials: {str(e)}")
            raise

    def _run_git_command(self, command, cwd=None):
        try:
            print(f"\nExecuting git command in {cwd or 'current directory'}")
            result = subprocess.run(
                ['git'] + command,
                cwd=cwd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: {e.stderr}")
            raise

    def create_github_secrets(self, secrets_data):
        """Create GitHub secrets in the repository"""
        try:
            git_token = self._get_git_credentials()
            
            print("\nCreating GitHub secrets...")
            for secret_name, secret_value in secrets_data.items():
                if secret_value:
                    command = [
                        '/opt/gh/gh', 'secret', 'set',
                        secret_name,
                        '--body', str(secret_value),
                        '--repo', self.private_repo
                    ]
                    
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        env={
                            'GITHUB_TOKEN': git_token,
                            'PATH': os.environ['PATH']
                        }
                    )
                    
                    if result.returncode == 0:
                        print(f"Successfully created secret: {secret_name}")
                    else:
                        raise Exception(f"Failed to create GitHub secret {secret_name}: {result.stderr}")
        
        except Exception as e:
            print(f"Error creating GitHub secrets: {str(e)}")
            raise

    def create_github_variables(self, variables_data):
        """Create GitHub repository variables"""
        try:
            git_token = self._get_git_credentials()
            
            print("\nCreating GitHub repository variables...")
            for variable_name, variable_value in variables_data.items():
                if variable_value is not None:
                    command = [
                        '/opt/gh/gh', 'variable', 'set',
                        variable_name,
                        '--body', str(variable_value),
                        '--repo', self.private_repo
                    ]
                    
                    result = subprocess.run(
                        command,
                        capture_output=True,
                        text=True,
                        env={
                            'GITHUB_TOKEN': git_token,
                            'PATH': os.environ['PATH']
                        }
                    )
                    
                    if result.returncode == 0:
                        print(f"Successfully created variable: {variable_name} = {variable_value}")
                    else:
                        raise Exception(f"Failed to create GitHub variable {variable_name}: {result.stderr}")
        
        except Exception as e:
            print(f"Error creating GitHub variables: {str(e)}")
            raise

    def sync_model_build_folder(self):
        try:
            # Clean up existing directories
            for path in [self.source_repo_path, self.private_repo_path]:
                if os.path.exists(path):
                    shutil.rmtree(path)

            git_token = self._get_git_credentials()
            # Include token in source repo URL since it's a private repository
            source_repo_url = f"https://github.com/{self.org_name}/{self.repo_name}.git"
            private_repo_url = f"https://{git_token}@github.com/{self.private_repo}.git"

            print(f"\nStep 1: Cloning source repository for profile {self.profile_name}")
            self._run_git_command(['clone', '--depth', '1', source_repo_url, self.source_repo_path])

            print("\nStep 2: Cloning private repository")
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    self._run_git_command(['clone', private_repo_url, self.private_repo_path])
                    break
                except subprocess.CalledProcessError as e:
                    if attempt < max_retries - 1:
                        print(f"Retry {attempt + 1} of {max_retries}")
                        time.sleep(30)
                    else:
                        raise

            print("\nStep 3: Configuring git")
            self._run_git_command(['config', 'user.name', 'SMUS-AIOPS'], self.private_repo_path)
            self._run_git_command(['config', 'user.email', 'smus-aiops@example.com'], self.private_repo_path)

            print("\nStep 4: Locating and copying model_build folder")
            build_folder_found = False

            # Look for the model_build folder in the hierarchical structure
            aiops_code_path = os.path.join(self.source_repo_path, self.public_aiops_code_folder)
            if os.path.exists(aiops_code_path):
                profile_path = os.path.join(aiops_code_path, self.profile_name)
                if os.path.exists(profile_path):
                    model_build_path = os.path.join(profile_path, 'model_build')
                    if os.path.exists(model_build_path):
                        print(f"Found model_build folder at: {model_build_path}")
                        
                        # Copy model_build contents
                        for item in os.listdir(model_build_path):
                            src_item = os.path.join(model_build_path, item)
                            dst_item = os.path.join(self.private_repo_path, item)
                            
                            if os.path.isdir(src_item):
                                if os.path.exists(dst_item):
                                    shutil.rmtree(dst_item)
                                shutil.copytree(src_item, dst_item)
                            else:
                                shutil.copy2(src_item, dst_item)
                        
                        # Check for .github/workflows in model_build
                        github_workflows_path = os.path.join(model_build_path, '.github', 'workflows')
                        if os.path.exists(github_workflows_path):
                            print(f"Found .github/workflows in model_build folder")
                            dst_github_dir = os.path.join(self.private_repo_path, '.github')
                            if not os.path.exists(dst_github_dir):
                                os.makedirs(dst_github_dir)
                            
                            dst_workflows_dir = os.path.join(dst_github_dir, 'workflows')
                            if not os.path.exists(dst_workflows_dir):
                                os.makedirs(dst_workflows_dir)
                            
                            # Copy workflow files
                            for workflow_file in os.listdir(github_workflows_path):
                                src_workflow = os.path.join(github_workflows_path, workflow_file)
                                dst_workflow = os.path.join(dst_workflows_dir, workflow_file)
                                if os.path.isfile(src_workflow):
                                    shutil.copy2(src_workflow, dst_workflow)
                                    print(f"Copied workflow file: {workflow_file}")
                        
                        build_folder_found = True

            if not build_folder_found:
                raise Exception(f"model_build folder not found in expected path: {self.public_aiops_code_folder}/{self.profile_name}/")

            # Force add .github directory to ensure it's included in the commit
            if os.path.exists(os.path.join(self.private_repo_path, '.github')):
                print("Explicitly adding .github directory to Git")
                self._run_git_command(['add', '.github', '-f'], self.private_repo_path)
            
            print("\nStep 5: Checking for changes")
            status = subprocess.run(
                ['git', 'status', '--porcelain'],
                cwd=self.private_repo_path,
                capture_output=True,
                text=True,
                check=True
            )

            return status.stdout.strip()

        except Exception as e:
            print(f"Error in sync_model_build_folder: {str(e)}")
            raise

    def commit_and_push_changes(self):
        try:
            print("\nCommitting and pushing changes")
            self._run_git_command(['add', '-A'], self.private_repo_path)
            self._run_git_command(
                ['commit', '-m', f'Initial setup - Copying model_build folder from {self.profile_name}'],
                self.private_repo_path
            )
            self._run_git_command(['push', 'origin', 'main'], self.private_repo_path)
            print("Successfully pushed changes")
        except Exception as e:
            print(f"Error in commit_and_push_changes: {str(e)}")
            raise
        finally:
            # Cleanup private repository
            if os.path.exists(self.private_repo_path):
                shutil.rmtree(self.private_repo_path)

def get_project_profile_details(project_profile_id, domain_id):
    """Get project profile name and account ID from DataZone"""
    try:
        print(f"Getting project profile for ID: {project_profile_id} in domain: {domain_id}")
        datazone_client = boto3.client('datazone')
        response = datazone_client.get_project_profile(
            identifier=project_profile_id,
            domainIdentifier=domain_id
        )    
        profile_name = response.get('name')
        account_id = None
        env_configs = response.get('environmentConfigurations', [])
        if env_configs:
            account_id = env_configs[0].get('awsAccount', {}).get('awsAccountId')
            
        return profile_name, account_id
    except Exception as e:
        print(f"Error getting project profile: {str(e)}")
        raise

def get_datazone_details(domain_id, project_id):
    """Get DataZone domain and project details"""
    try:
        datazone = boto3.client('datazone')
        
        print(f"\nGetting DataZone domain details for ID: {domain_id}")
        domain_response = datazone.get_domain(
            identifier=domain_id
        )
        print(f"DataZone domain response: {json.dumps(domain_response, default=str)}")
        
        print(f"\nGetting DataZone project details for ID: {project_id}")
        project_response = datazone.get_project(
            domainIdentifier=domain_id,
            identifier=project_id
        )
        print(f"DataZone project response: {json.dumps(project_response, default=str)}")

        return {
            'datazone_domain_arn': domain_response.get('arn'),
            'project_name': project_response.get('name'),
            'domain_unit_id': project_response.get('domainUnitId'),
            'root_domain_unit_id': domain_response.get('rootDomainUnitId')
        }
    except Exception as e:
        print(f"Error getting DataZone details: {str(e)}")
        raise

def get_sagemaker_details(project_id, project_name):
    """Get SageMaker domain and space details by finding domain with matching project tag"""
    try:
        sagemaker = boto3.client('sagemaker')
        
        paginator = sagemaker.get_paginator('list_domains')
        matching_domain = None
        project_s3_path = None

        print(f"\n Searching for SageMaker domain with project tag: {project_id}")
        for page in paginator.paginate():
            for domain in page['Domains']:
                domain_id = domain['DomainId']
                tags = sagemaker.list_tags(ResourceArn=domain['DomainArn'])['Tags']
                for tag in tags:
                    if tag['Key'] == 'AmazonDataZoneProject' and tag['Value'] == project_id:
                        matching_domain = domain
                        # Look for ProjectS3Path tag
                        for tag in tags:
                            if tag['Key'] == 'ProjectS3Path':
                                project_s3_path = tag['Value']
                        break
                if matching_domain:
                    break
            if matching_domain:
                break

        if not matching_domain:
            raise ValueError(f"No SageMaker domain found with project tag {project_id}")

        domain_id = matching_domain['DomainId']
        print(f"Found matching domain: {domain_id}")

        # If we didn't find the S3 path in tags, use a default format
        if not project_s3_path:
            account_id = boto3.client('sts').get_caller_identity()['Account']
            region = boto3.session.Session().region_name
            project_s3_path = f"s3://amazon-sagemaker-{account_id}-{region}/dzd_{domain_id}/{project_id}"
            print(f"Using default S3 path: {project_s3_path}")
        else:
            print(f"Found S3 path in tags: {project_s3_path}")

        domain_response = sagemaker.describe_domain(DomainId=domain_id)
        domain_arn = domain_response['DomainArn']
        execution_role = domain_response.get('DefaultSpaceSettings', {}).get('ExecutionRole')

        space_arn = None
        user_profile_arn = None
        wait_for_space = True
        print(f"\nListing spaces for domain {domain_id}")
        spaces_response = sagemaker.list_spaces(DomainIdEquals=domain_id)
        
        if spaces_response['Spaces']:
            space = spaces_response['Spaces'][0]
            space_name = space['SpaceName']

            try:
                space_details = sagemaker.describe_space(
                    DomainId=domain_id,
                    SpaceName=space_name
                )
                print(f"Space details: {json.dumps(space_details, default=str)}")
                
                if space_details.get('Status') == 'InService':
                    space_arn = space_details['SpaceArn']
                    wait_for_space = False  # Space is ready
                    
                    try:
                        owner_user_profile_name = space_details['OwnershipSettings']['OwnerUserProfileName']
                        if owner_user_profile_name:
                            user_profile_details = sagemaker.describe_user_profile(
                                DomainId=domain_id,
                                UserProfileName=owner_user_profile_name
                            )
                            user_profile_arn = user_profile_details['UserProfileArn']
                    except Exception as e:
                        print(f"Error getting user profile: {str(e)}")
                else:
                    print(f"Space exists but status is: {space_details.get('Status')}")
            except Exception as e:
                print(f"Error retrieving space details: {str(e)}")
        else:
            print("No spaces found.")

        return {
            'domain_arn': domain_arn,
            'execution_role': execution_role,
            'space_arn': space_arn,
            'user_profile_arn': user_profile_arn,
            'wait_for_space': wait_for_space,
            'project_s3_path': project_s3_path
        }

    except Exception as e:
        print(f"Error getting SageMaker details: {str(e)}")
        raise


def update_execution_role_permissions(role_arn, bucket_path):
    """Update the execution role with necessary S3 bucket permissions"""
    try:
        # Extract role name from ARN
        role_name = role_arn.split('/')[-1]
        print(f"Updating permissions for role: {role_name}")

        # Extract just the bucket name from the full S3 URI if needed
        if bucket_path.startswith('s3://'):
            bucket_name = bucket_path.split('/')[2]
        else:
            bucket_name = bucket_path.split('/')[0]
        
        print(f"Extracted bucket name: {bucket_name}")
        
        # Get account ID and region for SageMaker default bucket
        account_id = boto3.client('sts').get_caller_identity()['Account']
        region = boto3.session.Session().region_name
        sagemaker_default_bucket = f"sagemaker-{region}-{account_id}"
        
        iam_client = boto3.client('iam')
        
        # Create policy document for S3 bucket access
        policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "s3:ListBucket",
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}",
                        f"arn:aws:s3:::{sagemaker_default_bucket}"
                    ]
                },
                {
                    "Effect": "Allow",
                    "Action": [
                        "s3:GetObject",
                        "s3:PutObject",
                        "s3:DeleteObject"
                    ],
                    "Resource": [
                        f"arn:aws:s3:::{bucket_name}/*",
                        f"arn:aws:s3:::{sagemaker_default_bucket}/*"
                    ]
                }
            ]
        }

        print(f"Applying policy document: {json.dumps(policy_document, indent=2)}")
        
        # Put role policy
        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName='SageMakerArtifactBucketAccess',
            PolicyDocument=json.dumps(policy_document)
        )
        
        print(f"Successfully updated role {role_name} with bucket permissions for {bucket_name}")

        # Add Glue catalog read permissions for SageMaker pipeline
        glue_policy_document = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": [
                        "glue:GetTable",
                        "glue:GetTables",
                        "glue:GetDatabase",
                        "glue:GetDatabases",
                        "glue:GetPartitions"
                    ],
                    "Resource": "*"
                }
            ]
        }

        print(f"Applying Glue policy document: {json.dumps(glue_policy_document, indent=2)}")

        iam_client.put_role_policy(
            RoleName=role_name,
            PolicyName='SageMakerGlueCatalogAccess',
            PolicyDocument=json.dumps(glue_policy_document)
        )

        print(f"Successfully updated role {role_name} with Glue catalog permissions")
        return True

    except Exception as e:
        print(f"Error updating role permissions: {str(e)}")
        raise

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event, indent=2))
        if 'additionalInfo' in event:
            # Reconstruct the original event structure
            project_id = event.get('projectId')
            domain_id = event.get('domainId')
            additional_info = event.get('additionalInfo', {})
            project_profile_id = additional_info.get('projectProfileId')
            
            # Reconstruct the event data
            event_data = {
                'projectId': project_id,
                'domainId': domain_id,
                'projectDetails': {
                    'projectProfileId': project_profile_id
                },
                'userParameters': [
                    {
                        'environmentParameters': [
                            {
                                'name': 'gitFullRepositoryId',
                                'value': event.get('buildRepo')
                            }
                        ]
                    }
                ],
                'region': additional_info.get('sagemaker', {}).get('region', 'us-west-2')
            }
        else:

            event_data = event.get('body', event)
            if isinstance(event_data, str):
                event_data = json.loads(event_data)

        # Extract parameters and validate
        project_id = event_data.get('projectId')
        domain_id = event_data.get('domainId')
        project_details = event_data.get('projectDetails', {})
        project_profile_id = project_details.get('projectProfileId')
        user_params = event_data.get('userParameters', [])
        model_package_group_name = f"aiops-{project_id}-models"
        # Get current region from Lambda environment
        region = boto3.session.Session().region_name
        
        print(f"Extracted parameters:")
        print(f"project_id: {project_id}")
        print(f"domain_id: {domain_id}")
        print(f"project_profile_id: {project_profile_id}")
        print(f"region: {region}")
        

        if not all([project_id, domain_id, project_profile_id]):
            raise ValueError("Missing required parameters in event")

        # Extract git parameters
        git_params = None
        for param_group in user_params:
            env_params = param_group.get('environmentParameters', [])
            git_repo = next((param for param in env_params if param['name'] == 'gitFullRepositoryId'), None)
            if git_repo:
                git_params = {param['name']: param['value'] for param in env_params}
                break

        if not git_params:
            raise ValueError("Git parameters not found in event")

        print(f"Git parameters: {git_params}")

        # Get project profile name
        profile_name, account_id = get_project_profile_details(project_profile_id, domain_id)
        print(f"Project Profile Name: {profile_name}")
        print(f"Account ID: {account_id}")
    
        # Get additional details
        datazone_details = get_datazone_details(domain_id, project_id)
        project_name = datazone_details['project_name']

        print(f"DataZone details:")
        print(f"project_name: {project_name}")
        print(f"domain_unit_id: {datazone_details['domain_unit_id']}")
        print(f"root_domain_unit_id: {datazone_details['root_domain_unit_id']}")

        # Get SageMaker details
        sagemaker_details = get_sagemaker_details(project_id, project_name)

        print(f"SageMaker details:")
        print(f"domain_arn: {sagemaker_details['domain_arn']}")
        print(f"space_arn: {sagemaker_details['space_arn']}")
        print(f"execution_role: {sagemaker_details['execution_role']}")
        if sagemaker_details.get('wait_for_space', True):
            return {
                'statusCode': 200,
                'projectId': project_id,
                'domainId': domain_id,
                'status': 'WAITING_FOR_SPACE',
                'buildRepo': git_params.get('gitFullRepositoryId'),
                'additionalInfo': {
                    'profileName': profile_name,
                    'projectName': project_name,
                    'message': 'Waiting for SageMaker space to be ready',
                    'waitForSpace': True,
                    'domainUnitId': datazone_details['domain_unit_id'],
                    'deployAcct': account_id,
                    'projectProfileId': project_profile_id, 
                    'sagemaker': {
                        'domainArn': sagemaker_details['domain_arn'],
                        'spaceArn': sagemaker_details.get('space_arn'),
                        'UPNArn': sagemaker_details.get('user_profile_arn'),
                        'executionRole': sagemaker_details['execution_role'],
                        'modelPackageGroup': model_package_group_name
                    }
                }
            }
            
        # Use the S3 path from SageMaker details
        artifact_bucket = sagemaker_details['project_s3_path']
        if sagemaker_details['execution_role']:
            update_execution_role_permissions(
                sagemaker_details['execution_role'],
                artifact_bucket
            )

        # Extract just the bucket name from the full S3 URI if needed
        artifact_bucket_name = artifact_bucket
        if artifact_bucket.startswith('s3://'):
            artifact_bucket_name = artifact_bucket.split('/')[2]
            
        # Create secrets dictionary - only include secrets used in the workflow
        secrets = {
            "SAGEMAKER_DOMAIN_ARN": sagemaker_details['domain_arn'],
            "SAGEMAKER_SPACE_ARN": sagemaker_details['space_arn'],
            "SAGEMAKER_PIPELINE_ROLE_ARN": sagemaker_details['execution_role'],
            "OIDC_ROLE_GITHUB_WORKFLOW": os.environ.get('OIDC_ROLE_GITHUB_WORKFLOW'),
            "SAGEMAKER_PROJECT_NAME": project_name,    
            "SAGEMAKER_PROJECT_ID": project_id,        
            "AMAZON_DATAZONE_DOMAIN": domain_id,
            "AMAZON_DATAZONE_SCOPENAME": datazone_details['domain_unit_id'],
            "AMAZON_DATAZONE_PROJECT": project_id,     
            "REGION": region,
            "ARTIFACT_BUCKET": artifact_bucket_name,
            "MODEL_PACKAGE_GROUP_NAME": model_package_group_name,
            "GLUE_DATABASE": "glue_db",
            "GLUE_TABLE": "abalone",
            "MLFLOW_TRACKING_URI": os.environ.get('MLFLOW_TRACKING_URI')
        }

        print("\nSecrets to be created:")
        for key, value in secrets.items():
            print(f"{key}: {'<empty>' if not value else value}...")

        # Initialize GitOperations
        git_ops = GitOperations(
            org_name=os.environ['PUBLIC_SMUS_AIOPS_ORG'],
            repo_name=os.environ['PUBLIC_SMUS_AIOPS_ORG_REPO'], 
            profile_name=profile_name,
            private_repo=git_params['gitFullRepositoryId'],
            public_aiops_code_folder=os.environ['PUBLIC_SMUS_AIOPS_ORG_REPO_FOLDER']
        )

        # Create GitHub secrets first
        git_ops.create_github_secrets(secrets)

        # Create GitHub repository variables
        variables = {
            "TRIGGER_PIPELINE_EXECUTION": "false"
        }
        
        print("\nVariables to be created:")
        for key, value in variables.items():
            print(f"{key}: {value}")
            
        git_ops.create_github_variables(variables)

        # Then sync repositories and check for changes
        changes = git_ops.sync_model_build_folder()

        # Commit and push changes if there are any
        if changes:
            git_ops.commit_and_push_changes()
            commit_message = "Changes were committed and pushed"
        else:
            commit_message = "No changes to commit"

        return {
            'statusCode': 200,
            'projectId': project_id,
            'domainId': domain_id,
            'status': 'SUCCESSFUL',
            'buildRepo': git_params.get('gitFullRepositoryId'),
            'additionalInfo': {
                'profileName': profile_name,
                'projectName': project_name,
                'sourceRepo': f"https://github.com/{os.environ['PUBLIC_SMUS_AIOPS_ORG']}/{os.environ['PUBLIC_SMUS_AIOPS_ORG_REPO']}",
                'message': f'Successfully created GitHub secrets, variables and {commit_message.lower()}',
                'secretsCreated': list(secrets.keys()),
                'variablesCreated': list(variables.keys()),
                'domainUnitId': datazone_details['domain_unit_id'],
                'deployAcct': account_id,
                'sagemaker': {
                    'domainArn': sagemaker_details['domain_arn'],
                    'spaceArn': sagemaker_details['space_arn'],
                    'UPNArn': sagemaker_details['user_profile_arn'],
                    'executionRole': sagemaker_details['execution_role'],
                    'modelPackageGroup': model_package_group_name,
                    'artifact_bucket': artifact_bucket_name
                }
            }
        }

    except Exception as e:
        error_message = str(e)
        print(f"Error: {error_message}")
        return {
            'statusCode': 500,
            'status': 'FAILED',
            'error': error_message,
            'projectId': event_data.get('projectId') if 'event_data' in locals() else None,
            'domainId': event_data.get('domainId') if 'event_data' in locals() else None
        }
