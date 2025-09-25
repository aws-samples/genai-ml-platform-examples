import boto3
import os
import json
import base64
import uuid

sagemaker_endpoints = json.loads(os.environ['SAGEMAKER_ENDPOINTS'])
audio_bucket = os.environ['AUDIO_BUCKET']
summarize_function_name = os.environ['SUMMARIZE_FN']

sagemaker_client = boto3.client('sagemaker-runtime')
s3_client = boto3.client('s3')

lambda_client = boto3.client('lambda')

def validate_body(body):
    # Check for either audio data or S3 URI
    if 'audio' not in body and 's3Uri' not in body:
        return {
            'statusCode': 400,
            'body': 'No audio or s3Uri provided'
        }

    # Get endpoint_name from body
    if 'endpoint_name' not in body:
        return {
            'statusCode': 400,
            'body': 'No endpoint_name provided'
        }
    
    if 'session_id' not in body:
        return {
            'statusCode': 400,
            'body': 'No session_id provided'
        }
    
    return True

def handler(event, context):
    body = event.get('body')
    
    if not body:
        return {
            'statusCode': 400,
            'body': 'No body provided'
        }

    body_json = json.loads(body)
    validated = validate_body(body_json)

    if validated != True:
        return validated

    endpoint_name = body_json['endpoint_name']
    session_id = body_json.get('session_id')

    # Get the matching endpoint from sagemaker_endpoints
    matching_endpoint = None
    for endpoint in sagemaker_endpoints:
        if endpoint.get('name') == endpoint_name:
            matching_endpoint = endpoint
            break

    if not matching_endpoint:
        return {
            'statusCode': 400,
            'body': 'No matching endpoint found'
        }
    try:
        print("matching_endpoint:")
        print(matching_endpoint)
        
        # Handle S3 URI or base64 audio data
        if 's3Uri' in body_json:
            # Use provided S3 URI
            input_location = body_json['s3Uri']
            audio_data = None
            
            # For real-time endpoints, we need to download the file
            if matching_endpoint.get('type') != 'async':
                # Parse S3 URI to get bucket and key
                s3_parts = input_location.replace('s3://', '').split('/', 1)
                bucket = s3_parts[0]
                key = s3_parts[1]
                
                # Download audio data for real-time processing
                response = s3_client.get_object(Bucket=bucket, Key=key)
                audio_data = response['Body'].read()
        else:
            # Decode base64 audio
            audio_data = base64.b64decode(body_json['audio'])
            input_location = None
        
        # Invoke endpoint based on type
        if matching_endpoint.get('type') == 'async':
            print('Async endpoint')
            
            # For async, use S3 location or upload audio to S3 first
            if not input_location:
                audio_key = f"audio-input/{uuid.uuid4()}.wav"
                s3_client.put_object(
                    Bucket=audio_bucket,
                    Key=audio_key,
                    Body=audio_data,
                    ContentType='audio/wav'
                )
                input_location = f"s3://{audio_bucket}/{audio_key}"
            
            response = sagemaker_client.invoke_endpoint_async(
                EndpointName=matching_endpoint.get('endpoint_name'),
                InputLocation=input_location,
                CustomAttributes=json.dumps({
                    'session_id': session_id,
                    'style': body_json.get('style','brief')
                })
            )

            print(f'Async Response: {response}')
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'job_name': response['OutputLocation'].split('/')[-1],
                    'input_location': input_location
                })
            }
        else:
            # Real-time
            print('Real-time endpoint')
            response = sagemaker_client.invoke_endpoint(
                EndpointName=matching_endpoint.get('endpoint_name'),
                Body=audio_data,
                ContentType='audio/wav'
            )

            # Parse the response
            result = json.loads(response['Body'].read().decode())
            print(f'Real-time Response: {result}')

            # Invoke summarize lambda function and send results
            output = {
                    'transcription': result,
                    'session_id': session_id,
                    'style': body_json.get('style','brief'),
                    'type': 'realtime'
                }
            
            print('Invoking summarization function')
            lambda_client.invoke(
                FunctionName=summarize_function_name,
                Payload=json.dumps(output)
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'transcription': result,
                    'session_id': session_id
                })
            }
            
    except Exception as e:
        print(f'Error processing audio: {str(e)}')
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

    return {
        'statusCode': 200,
        'body': 'Processed Audio'
    }
