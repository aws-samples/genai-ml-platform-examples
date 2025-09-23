from aws_cdk import (
    Stack,
    CfnOutput,
)
from constructs import Construct
from constructs.backend import BackendConstruct
from constructs.frontend import FrontendConstruct

class InfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        backend = BackendConstruct(self, "Backend")

        frontend = FrontendConstruct(self, "Frontend", backend.websocket_stage.url)

        CfnOutput(
            self,
            "WebSocketAPIUrl",
            value=backend.websocket_api.api_endpoint,
        )

        CfnOutput(
            self,
            "FrontendUrl",
            value=f"https://{frontend.distribution.distribution_domain_name}",
        )
