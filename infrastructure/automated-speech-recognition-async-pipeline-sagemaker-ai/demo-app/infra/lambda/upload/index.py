import boto3
import json
import uuid
import os
from botocore.exceptions import ClientError

s3_client = boto3.client('s3')
bucket_name = os.environ['S3_INPUT_BUCKET']

def handler(event, context):
    try:
        body = json.loads(event.get('body', '{}'))
        file_name = body.get('fileName', f'audio-{uuid.uuid4()}.wav')
        content_type = body.get('contentType', 'audio/wav')
        
        # Generate presigned URL for PUT operation
        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket_name,
                'Key': f'audio-input/{file_name}',
                'ContentType': content_type
            },
            ExpiresIn=3600  # 1 hour
        )
        
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type',
                'Access-Control-Allow-Methods': 'POST, OPTIONS'
            },
            'body': json.dumps({
                'uploadUrl': presigned_url,
                's3Key': f'audio-input/{file_name}',
                's3Uri': f's3://{bucket_name}/audio-input/{file_name}'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }