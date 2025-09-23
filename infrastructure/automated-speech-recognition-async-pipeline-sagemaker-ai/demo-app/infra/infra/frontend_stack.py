from aws_cdk import (
    Stack,
    CfnOutput,
    Fn,
)
from constructs import Construct
from constructs.frontend import FrontendConstruct

class FrontendStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, configs, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        websocket_url = configs.get('websocket_url')
        api_url = configs.get('api_url')

        frontend = FrontendConstruct(self, "Frontend", websocket_url, api_url)

        CfnOutput(
            self,
            "FrontendUrl",
            value=f"https://{frontend.distribution.distribution_domain_name}",
        )