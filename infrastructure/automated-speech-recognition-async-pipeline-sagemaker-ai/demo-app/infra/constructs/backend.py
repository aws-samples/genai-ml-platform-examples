
from aws_cdk import (
    aws_apigatewayv2 as apigatewayv2,
    aws_apigatewayv2_integrations as integrations,
    aws_dynamodb as dynamodb,
    aws_lambda as _lambda,
    aws_logs as logs,
    aws_iam as iam,
    aws_s3 as s3,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    RemovalPolicy,
    Duration
)
from constructs import Construct
import json

class BackendConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, sagemaker_endpoints, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create an s3 bucket to upload files for async
        audio_s3_bucket = s3.Bucket(self, 'AudioBucket')

        # Create DynamoDB table for sessions
        sessions_table = dynamodb.Table(
            self, 'VoiceAISessions',
            partition_key=dynamodb.Attribute(
                name='ConnectionId',
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create Lambda functions
        connect_fn = _lambda.Function(
            self, 'ConnectHandler',
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=_lambda.Code.from_asset('lambda/connect'),
            environment={
                'SESSION_TBL': sessions_table.table_name
            }
        )

        disconnect_fn = _lambda.Function(
            self, 'DisconnectHandler', 
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=_lambda.Code.from_asset('lambda/disconnect'),
            environment={
                'SESSION_TBL': sessions_table.table_name
            }
        )

        # Create a transcribe API iam role
        post_to_connection_role = iam.Role(
            self, 'PostToConnectionRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonBedrockFullAccess'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonAPIGatewayInvokeFullAccess'),
            ]
        )

        # Create IAM role for default handler
        default_role = iam.Role(
            self, 'DefaultHandlerRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonAPIGatewayInvokeFullAccess'),
            ]
        )

        default_fn = _lambda.Function(
            self, 'DefaultHandler',
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=_lambda.Code.from_asset('lambda/default'),
            role=default_role
        )

        # Create WebSocket API
        self.websocket_api = apigatewayv2.WebSocketApi(
            self, 'WebSocketAPI',
            connect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=integrations.WebSocketLambdaIntegration(
                    'ConnectIntegration',
                    connect_fn
                )
            ),
            disconnect_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=integrations.WebSocketLambdaIntegration(
                    'DisconnectIntegration',
                    disconnect_fn
                )
            ),
            default_route_options=apigatewayv2.WebSocketRouteOptions(
                integration=integrations.WebSocketLambdaIntegration(
                    'DefaultIntegration',
                    default_fn
                )
            )
        )

        # # Create CloudWatch log group for WebSocket API
        # log_group = logs.LogGroup(
        #     self, 'WebSocketAPILogGroup',
        #     removal_policy=RemovalPolicy.DESTROY
        # )

        # Deploy the WebSocket API with logging enabled
        self.websocket_stage = apigatewayv2.WebSocketStage(
            self, 'WebSocketStage',
            web_socket_api=self.websocket_api,
            stage_name='prod',
            auto_deploy=True
        )

        post_to_connection_fn = _lambda.Function(
            self, 'PostToConnectionHandler',
            runtime=_lambda.Runtime.PYTHON_3_9, 
            handler='index.handler',
            code=_lambda.Code.from_asset('lambda/post-to-connection'),
            environment={
                'SESSION_TBL': sessions_table.table_name,
                'ENDPOINT_URL': self.websocket_stage.callback_url
            },
            role=post_to_connection_role,
            timeout=Duration.seconds(30)
        )

        # For each sns_arn, add a trigger to the post_to_connection_fn
        for sagemaker_endpoint in sagemaker_endpoints:
            if sagemaker_endpoint.get('type') == 'async':
                if 'sns_topic_arn' in sagemaker_endpoint:
                    sns_topic = sns.Topic.from_topic_arn(self, sagemaker_endpoint.get('name'), sagemaker_endpoint.get('sns_topic_arn'))
                    sns_topic.add_subscription(
                        subs.LambdaSubscription(post_to_connection_fn)
                    )

                # Grant S3 permissions to post_to_connection_role
                input_s3_bucket = s3.Bucket.from_bucket_name(self, f'InputBucket-{sagemaker_endpoint.get("name")}', sagemaker_endpoint.get('output_bucket'))
                input_s3_bucket.grant_read(post_to_connection_role)

        # Grant DynamoDB permissions to Lambda functions
        sessions_table.grant_read_write_data(connect_fn)
        sessions_table.grant_read_write_data(disconnect_fn)
        sessions_table.grant_read_write_data(post_to_connection_fn)

        # Create a transcribe API iam role
        transcribe_api_role = iam.Role(
            self, 'TranscribeAPIRole',
            assumed_by=iam.ServicePrincipal('lambda.amazonaws.com'),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AWSLambdaBasicExecutionRole'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonBedrockFullAccess'),
                iam.ManagedPolicy.from_aws_managed_policy_name('AmazonSageMakerFullAccess'),
            ]
        )

        audio_s3_bucket.grant_put(transcribe_api_role)
        post_to_connection_fn.grant_invoke(transcribe_api_role)

        # Deploy a transcription API
        transcribe_fn = _lambda.Function(
            self, 'TranscribeHandler',
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler='index.handler',
            code=_lambda.Code.from_asset('lambda/transcribe'),
            environment={
                'SESSION_TBL': sessions_table.table_name,
                'SAGEMAKER_ENDPOINTS': json.dumps(sagemaker_endpoints),
                'AUDIO_BUCKET': audio_s3_bucket.bucket_name,
                'SUMMARIZE_FN': post_to_connection_fn.function_name
            },
            role=transcribe_api_role,
            timeout=Duration.seconds(30)
        )

        # Create HTTP API
        self.http_api = apigatewayv2.HttpApi(
            self, 'TranscribeAPI',
            cors_preflight={
                'allow_origins': [
                    '*',
                    'http://localhost:3000' # for local testing
                    ],
                'allow_methods': [
                    apigatewayv2.CorsHttpMethod.POST,
                    apigatewayv2.CorsHttpMethod.GET,
                    apigatewayv2.CorsHttpMethod.PUT,
                    apigatewayv2.CorsHttpMethod.OPTIONS
                    ],
                'allow_headers': ['Content-Type', 'Authorization', '*'],  # add needed headers 
            }
        )

        # Add route for transcribe function
        self.http_api.add_routes(
            path='/transcribe',
            methods=[apigatewayv2.HttpMethod.POST],
            integration=integrations.HttpLambdaIntegration(
                'TranscribeIntegration',
                transcribe_fn
            )
        )   