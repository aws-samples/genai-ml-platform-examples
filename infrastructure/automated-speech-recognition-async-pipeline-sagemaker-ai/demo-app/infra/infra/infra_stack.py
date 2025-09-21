from aws_cdk import (
    Stack,
    CfnOutput,
)
from constructs import Construct
from constructs.frontend import FrontendConstruct

class InfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        frontend = FrontendConstruct(self, "Frontend")

        print(f'frontend: {frontend}')

        # CfnOutput(
        #     self,
        #     "FrontendUrl",
        #     value=f"https://{frontend.distribution.distribution_domain_name}",
        # )
