import boto3
import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

bedrock_client = boto3.client('bedrock-runtime')
endpoint_url = os.environ['ENDPOINT_URL']
apigateway_client = boto3.client('apigatewaymanagementapi', endpoint_url=endpoint_url)

s3_client = boto3.client('s3')

def handler(event, context):
    # Handle sns topic
    if 'Records' in event:
        # Only get the first record
        record = event['Records'][0]

        print(f'record: {record}')

        # Get the message
        message = json.loads(record['Sns']['Message'])

        print(f'message: {message}')
        output_location = message['responseParameters']['outputLocation']

        # Get the customAttributes (convert json string to dict)
        custom_attributes = json.loads(message['requestParameters']['customAttributes'])
        connection_id = custom_attributes['session_id']
        style = custom_attributes['style']
        
        # Load transcription from outputLocation
        transcription  = s3_client.get_object(
            Bucket=output_location.split('/')[2],
            Key='/'.join(output_location.split('/')[3:])
        )['Body'].read().decode('utf-8')

    else:
        # Real-time
        transcription = event.get('transcription', '')
        transcription = transcription['predictions'][0]['results']
        # Convert to string
        transcription = json.dumps(transcription)
        connection_id = event.get('session_id', '')
        style = event.get('style', 'brief')

    print(f"Connection ID: {connection_id}")
    print(f"Transcription: {transcription}")

    system_prompt = None
    if style == 'brief':
        system_prompt = f'Create a brief summary of the following audio transcription. Return in markdown format.'
    elif style == 'detailed':
        system_prompt = f'Create a detailed summary of the following audio transcription. Return in markdown format.'
    elif style == 'bullet-points':
        system_prompt = f'Create a bullet point summary of the following audio transcription. Return in markdown format.'
    
    try:
        # Use Bedrock converse streaming API
        response = bedrock_client.converse_stream(
            modelId='global.anthropic.claude-sonnet-4-20250514-v1:0',
            messages=[
                {
                    'role': 'user',
                    'content': [{'text': transcription}]
                }
            ],
            system=[{'text': system_prompt}]
        )
        
        # Stream response chunks to WebSocket
        for chunk in response['stream']:
            if 'contentBlockDelta' in chunk:
                delta_text = chunk['contentBlockDelta']['delta']['text']
                apigateway_client.post_to_connection(
                    ConnectionId=connection_id,
                    Data=json.dumps({'text': delta_text})
                )
        
        # Send completion signal
        apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({'complete': True})
        )
        
        return {'statusCode': 200}
        
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        apigateway_client.post_to_connection(
            ConnectionId=connection_id,
            Data=json.dumps({'error': str(e)})
        )
        return {'statusCode': 500}
