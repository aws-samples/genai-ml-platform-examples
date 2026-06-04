import boto3
import json
import os
import requests
import subprocess
import shutil
import time

def create_github_repository(private_organization_name, repo_name, git_token):
    """Create a new GitHub repository in the specified organization"""
    try:
        print(f"\nCreating GitHub repository: {private_organization_name}/{repo_name}")
        headers = {
            'Accept': 'application/json',
            'Authorization': f'token {git_token}'
        }      

        payload = {
            'name': repo_name,            
            'private': True,
            'auto_init': True,
            'description': f'Deploy repository for AIOps project'
        }

        # First, check if the organization exists
        org_check_response = requests.get(
            f"https://api.github.com/orgs/{private_organization_name}",
            headers=headers
        )

        if org_check_response.status_code == 200:
            # It's an organization, use org endpoint
            api_url = f"https://api.github.com/orgs/{private_organization_name}/repos"
            print(f"Creating repository in organization: {private_organization_name}")
        else:
            # It's likely a user account, use user endpoint
            api_url = "https://api.github.com/user/repos"
            print(f"Creating repository in user account: {private_organization_name}")

        response = requests.post(
            api_url,
            headers=headers,
            json=payload
        )

        if response.status_code not in [201, 200]:
            raise Exception(f"Failed to create repository: {response.text}")

        print(f"Successfully created repository: {private_organization_name}/{repo_name}")
        return f"{private_organization_name}/{repo_name}"  

    except Exception as e:
        print(f"Error creating GitHub repository: {str(e)}")
        raise


def create_github_secrets(repo_full_name, secrets_data, git_token):
    """Create GitHub secrets in the repository"""
    try:
        print(f"\nCreating GitHub secrets in repository: {repo_full_name}")

        # Poll until the repo Actions API is ready (race condition after repo creation)
        headers = {
            'Accept': 'application/json',
            'Authorization': f'token {git_token}'
        }
        public_key_url = f"https://api.github.com/repos/{repo_full_name}/actions/secrets/public-key"
        max_retries = 10
        for attempt in range(max_retries):
            resp = requests.get(public_key_url, headers=headers)
            if resp.status_code == 200:
                print("Repository Actions API is ready")
                break
            print(f"Waiting for repo Actions to initialize (attempt {attempt + 1}/{max_retries})...")
            time.sleep(3)
        else:
            raise Exception(f"Repository Actions API not ready after {max_retries} attempts")

        for secret_name, secret_value in secrets_data.items():
            if secret_value:
                print(f"Creating secret: {secret_name}")
                command = [
                    '/opt/gh/gh', 'secret', 'set',
                    secret_name,
                    '--body', str(secret_value),
                    '--repo', repo_full_name
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
        
        print(f"Successfully created all secrets in {repo_full_name}")
    except Exception as e:
        print(f"Error creating GitHub secrets: {str(e)}")
        raise

def find_template_repository(project_profile_name):
    """Find template repository based on project profile name"""
    try:
        public_templates_org = os.environ['PUBLIC_SMUS_AIOPS_ORG']
        public_templates_repo = os.environ['PUBLIC_SMUS_AIOPS_ORG_REPO']
        aiops_code_folder = os.environ['PUBLIC_SMUS_AIOPS_ORG_REPO_FOLDER']
        
        # Convert profile name to lowercase for consistency
        project_profile_name = project_profile_name.lower()

        print(f"\nLooking for template in:")
        print(f"Organization: {public_templates_org}")
        print(f"Repository: {public_templates_repo}")
        print(f"Code Folder: {aiops_code_folder}")
        print(f"Profile Name: {project_profile_name}")

        
        
        # Construct the template repository URL
        template_repo_url = f"https://github.com/{public_templates_org}/{public_templates_repo}.git"
        print(f"\nUsing template repository: {template_repo_url}")

        #  verify the repository exists
        verify_url = f"https://api.github.com/repos/{public_templates_org}/{public_templates_repo}"
        response = requests.get(verify_url)
        if response.status_code != 200:
            raise Exception(f"Template repository not found: {template_repo_url}")
            
        return template_repo_url

    except Exception as e:
        print(f"Error finding template repository: {str(e)}")
        raise

def copy_template_content(template_repo_url, deploy_repo_name, git_token, profile_name):
    """Copy model_deploy folder contents from template to new repository"""
    work_dir = '/tmp'
    template_repo_path = os.path.join(work_dir, 'template_repo')
    deploy_repo_path = os.path.join(work_dir, 'deploy_repo')
    default_branch = os.environ['PRIVATE_DEPLOY_REPO_DEFAULT_BRANCH']

    try:
        # Clean up existing directories
        for path in [template_repo_path, deploy_repo_path]:
            if os.path.exists(path):
                shutil.rmtree(path)

        # Clone template repository
        print("\nCloning template repository...")
        subprocess.run(
            ['git', 'clone', '--depth', '1', template_repo_url, template_repo_path],
            check=True,
            capture_output=True,
            text=True
        )

        # Clone deploy repository
        print("\nCloning deploy repository...")
        deploy_repo_url = f"https://{git_token}@github.com/{deploy_repo_name}.git"
        subprocess.run(
            ['git', 'clone', deploy_repo_url, deploy_repo_path],
            check=True,
            capture_output=True,
            text=True
        )

        # Configure git locally for the deploy repository
        subprocess.run(
            ['git', 'config', 'user.name', 'SMUS-AIOPS'],
            cwd=deploy_repo_path,
            check=True
        )
        subprocess.run(
            ['git', 'config', 'user.email', 'smus-aiops@example.com'],
            cwd=deploy_repo_path,
            check=True
        )

        # Find and copy model_deploy folder
        aiops_code_folder = os.environ['PUBLIC_SMUS_AIOPS_ORG_REPO_FOLDER']
        src_path = os.path.join(template_repo_path, aiops_code_folder, profile_name, 'model_deploy')

        if not os.path.exists(os.path.join(template_repo_path, aiops_code_folder)):
            raise Exception(f"Code folder '{aiops_code_folder}' not found in template repository")

        if not os.path.exists(os.path.join(template_repo_path, aiops_code_folder, profile_name)):
            raise Exception(f"Profile folder '{profile_name}' not found in {aiops_code_folder}")

        if not os.path.exists(src_path):
            raise Exception(f"model_deploy folder not found in {aiops_code_folder}/{profile_name}/")

        
        print(f"Found model_deploy folder at: {src_path}")
        
        # Copy contents
        for item in os.listdir(src_path):
            src_item = os.path.join(src_path, item)
            dst_item = os.path.join(deploy_repo_path, item)
            
            if os.path.isdir(src_item):
                if os.path.exists(dst_item):
                    shutil.rmtree(dst_item)
                shutil.copytree(src_item, dst_item)
            else:
                shutil.copy2(src_item, dst_item)

        # Commit and push changes
        subprocess.run(['git', 'add', '-A'], cwd=deploy_repo_path, check=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Initial setup - Copying model_deploy folder contents from {profile_name}'],
            cwd=deploy_repo_path,
            check=True
        )
        subprocess.run(['git', 'push', 'origin', default_branch], cwd=deploy_repo_path, check=True)
        print("Successfully pushed template content to deploy repository")

        return True

    except Exception as e:
        print(f"Error copying template content: {str(e)}")
        raise

    finally:
        # Cleanup
        for path in [template_repo_path, deploy_repo_path]:
            if os.path.exists(path):
                shutil.rmtree(path)

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event, indent=2))
        
        # Extract from body if present
        event_data = event.get('body', event)
        if isinstance(event_data, str):
            event_data = json.loads(event_data)

        # Get required parameters from event
        project_id = event_data.get('projectId')
        domain_id = event_data.get('domainId')
        build_repo = event_data.get('buildRepo')
        additional_info = event_data.get('additionalInfo', {})
        
        # Get values from additionalInfo
        profile_name = additional_info.get('profileName')
        project_name = additional_info.get('projectName')
        domain_unit_id = additional_info.get('domainUnitId')
        sagemaker_info = additional_info.get('sagemaker', {})
        model_package_group_name = sagemaker_info.get('modelPackageGroup')
        deploy_account = additional_info.get('deployAcct')
        
        # Get current region from Lambda environment
        region = boto3.session.Session().region_name

        print(f"\nExtracted parameters:")
        print(f"project_id: {project_id}")
        print(f"domain_id: {domain_id}")
        print(f"build_repo: {build_repo}")
        print(f"profile_name: {profile_name}")
        print(f"project_name: {project_name}")
        
        # Validate required parameters
        if not all([project_id, domain_id, build_repo, profile_name, project_name]):
            missing_params = []
            if not project_id: missing_params.append('project_id')
            if not domain_id: missing_params.append('domain_id')
            if not build_repo: missing_params.append('build_repo')
            if not profile_name: missing_params.append('profile_name')
            if not project_name: missing_params.append('project_name')
            raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")

        # Get GitHub token
        secret_name = os.environ.get('GITHUB_TOKEN_SECRET_NAME')
        secrets_client = boto3.client('secretsmanager')
        response = secrets_client.get_secret_value(SecretId=secret_name)
        git_token = json.loads(response['SecretString'])['token']

        # Create deploy repository
        # Get organization name from environment variable (set from config)
        private_organization_name = os.environ.get('PRIVATE_GITHUB_ORGANIZATION')
        repo_name = f"{project_id}-{domain_id}-deploy-repo"
        deploy_repo = create_github_repository(private_organization_name, repo_name, git_token)
        print(f"Created deploy repository: {deploy_repo}")

            
        # Create secrets dictionary - only include secrets used in the workflow
        secrets = {
            "SAGEMAKER_DOMAIN_ARN": sagemaker_info.get('domainArn'),
            "SAGEMAKER_SPACE_ARN": sagemaker_info.get('spaceArn'),
            "SAGEMAKER_PIPELINE_ROLE_ARN": sagemaker_info.get('executionRole'),
            "OIDC_ROLE_GITHUB_WORKFLOW": os.environ.get('OIDC_ROLE_GITHUB_WORKFLOW'),
            "SAGEMAKER_PROJECT_NAME": project_name,    
            "SAGEMAKER_PROJECT_ID": project_id,        
            "AMAZON_DATAZONE_DOMAIN": domain_id,
            "AMAZON_DATAZONE_SCOPENAME": domain_unit_id,
            "AMAZON_DATAZONE_PROJECT": project_id,     
            "REGION": region,
            "ARTIFACT_BUCKET":sagemaker_info.get('artifact_bucket'),
            "MODEL_PACKAGE_GROUP_NAME": model_package_group_name,
            "DEPLOY_ACCOUNT": deploy_account,
            "GLUE_DATABASE": "glue_db", # default value
            "GLUE_TABLE": "abalone" # default value
        }

        print("\nSecrets to be created:")
        for key, value in secrets.items():
            print(f"{key}: {'<empty>' if not value else value[:5]}...")

        # Create GitHub secrets
        create_github_secrets(deploy_repo, secrets, git_token)

        # Find template repository
        template_repo_url = find_template_repository(project_profile_name=profile_name)
        print(f"Found template repository: {template_repo_url}")

        # Copy template content
        copy_template_content(template_repo_url, deploy_repo, git_token, profile_name)
        
        return {
            'statusCode': 200,
            'status': 'SUCCESSFUL',
            'projectId': project_id,
            'domainId': domain_id,
            'deployRepo': deploy_repo,
            'additionalInfo': {
                'projectProfileName': profile_name,
                'secretsCreated': list(secrets.keys()),
                'templateRepo': template_repo_url,
                'message': 'Successfully created deploy repository, secrets, and copied template content'
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
