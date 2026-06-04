import boto3
import json
from datetime import datetime

def datetime_handler(obj):
    """Handle datetime objects for JSON serialization"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

def check_project_status(domain_id, project_id):
    """Check if DataZone project is ready"""
    try:
        datazone_client = boto3.client('datazone')
        response = datazone_client.get_project(
            domainIdentifier=domain_id,
            identifier=project_id
        )
        
        deployment_details = response.get('environmentDeploymentDetails', {})
        status = deployment_details.get('overallDeploymentStatus')
        print(f"Project Status: {status}")
        
        return status, response
        
    except Exception as e:
        print(f"Error checking project status: {str(e)}")
        raise

def lambda_handler(event, context):
    try:
        print("Received event:", json.dumps(event, indent=2))
        
        # Get project details from event
        if 'detail' in event:
            # First invocation
            detail = event['detail']
            project_id = detail.get('responseElements', {}).get('id')
            domain_id = detail.get('requestParameters', {}).get('domainIdentifier')
            user_params = detail.get('requestParameters', {}).get('userParameters', [])
        else:
            # Subsequent invocations
            project_id = event.get('projectId')
            domain_id = event.get('domainId')
            user_params = event.get('userParameters', [])

        if not project_id or not domain_id:
            raise Exception("Missing required project or domain ID")

        status, project_details = check_project_status(domain_id, project_id)
        
        # Create response with custom JSON serialization
        response = {
            'status': status,
            'projectId': project_id,
            'domainId': domain_id,
            'userParameters': user_params,
            'projectDetails': project_details
        }
        
        # Return JSON-serialized response using the custom handler
        return json.loads(json.dumps(response, default=datetime_handler))

    except Exception as e:
        print(f"Error: {str(e)}")
        raise
