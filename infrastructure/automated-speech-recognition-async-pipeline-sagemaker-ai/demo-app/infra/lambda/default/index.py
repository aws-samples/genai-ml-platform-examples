import os
import boto3
import json
import logging

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def handler(event, context):
    connection_id = event['requestContext']['connectionId']
    domain_name = event['requestContext']['domainName']
    stage = event['requestContext']['stage']
    
    # Set up API Gateway Management API endpoint
    endpoint_url = f"https://{domain_name}/{stage}"
    apigateway_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)
    
    try:
        # Parse the incoming message
        body = json.loads(event.get('body', '{}'))
        action = body.get('action', '')
        
        if action == 'getConnectionId':
            # Send connection ID back to client
            response_message = {
                'type': 'connectionId',
                'connectionId': connection_id
            }
            
            apigateway_client.post_to_connection(
                ConnectionId=connection_id,
                Data=json.dumps(response_message)
            )
            
        return {
            'statusCode': 200,
            'body': 'Message processed'
        }
        
    except Exception as e:
        logger.error(f'Error processing message: {str(e)}')
        return {
            'statusCode': 500,
            'body': 'Internal server error'
        }