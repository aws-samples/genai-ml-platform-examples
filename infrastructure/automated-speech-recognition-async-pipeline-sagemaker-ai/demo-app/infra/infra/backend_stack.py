from aws_cdk import (
    Stack,
    CfnOutput,
)
from constructs import Construct
from constructs.backend import BackendConstruct

class BackendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, configs, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        sagemaker_endpoints = configs.get('sagemaker_endpoints')

        backend = BackendConstruct(self, "Backend", sagemaker_endpoints)
        
        # Output the WebSocket URL for the frontend stack to use
        self.websocket_url_output = CfnOutput(
            self,
            "WebSocketURL",
            value=backend.websocket_stage.url,
            export_name="WebSocketURL"
        )

        # Output the HTTP API URL for the frontend stack to use
        self.http_api_url_output = CfnOutput(
            self,
            "HTTPAPIURL",
            value=backend.http_api.url or "",
            export_name="HTTPAPIURL"
        )
