import os
import boto3
import logging
from datetime import datetime, timezone

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
session_tbl = os.environ.get('SESSION_TBL')

# Initialize AWS SDK clients
dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    connection_id = event['requestContext']['connectionId']
    logger.info(f'New WebSocket connection established: {connection_id}')

    
    timestamp = datetime.now(timezone.utc).isoformat()
    table = dynamodb.Table(session_tbl)
    
    try:
        table.put_item(
            Item={
                'ConnectionId': connection_id,  # Use 'connectionId' as the key (lowercase 'c')
                'Timestamp': timestamp,
            }
        )
        logger.info(f'Registered connection {connection_id}.')
    except Exception as e:
        logger.error(f'Error registering connection: {str(e)}')
        return {
            'statusCode': 500,
            'body': 'Internal server error'
        }

    return {
        'statusCode': 200,
        'body': 'Connected.'
    }