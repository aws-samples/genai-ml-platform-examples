import os
import boto3
import logging

# Initialize logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables
SESSION_TBL = os.environ.get('SESSION_TBL')

# Initialize AWS SDK clients
dynamodb = boto3.resource('dynamodb')

def handler(event, context):
    connection_id = event['requestContext']['connectionId']
    logger.info(f'WebSocket connection closed: {connection_id}')
    
    table = dynamodb.Table(SESSION_TBL)
    try:
        table.delete_item(
            Key={
                'ConnectionId': connection_id,
            }
        )
        logger.info(f'Removed connection {connection_id}.')
    except Exception as e:
        logger.error(f'Error updating DynamoDB: {str(e)}')
        return {
            'statusCode': 500,
            'body': 'Internal server error'
        }

    return {
        'statusCode': 200,
        'body': 'Disconnected.'
    }
