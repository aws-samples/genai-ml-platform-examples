from aws_cdk import (
    aws_s3 as s3,
    aws_apigatewayv2 as apigatewayv2,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3deploy,
    DockerImage,
    BundlingOptions,
    BundlingOutput,
    RemovalPolicy,
    Stack,
)
from constructs import Construct


class FrontendConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, websocket_stage_url: str, api_url: str, user_pool_id: str, user_pool_client_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "FrontendBucket",
            website_index_document="index.html",
            website_error_document="index.html",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        self.distribution = cloudfront.Distribution(
            self,
            "FrontendDistribution",
            default_behavior=cloudfront.BehaviorOptions(
                # origin=origins.S3BucketOrigin(bucket, origin_access_identity=oai),
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket, origin_access_levels=[cloudfront.AccessLevel.READ]),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            default_root_object="index.html",
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                )
            ],
        )

        
        # Deploy the built frontend
        s3deploy.BucketDeployment(
            self,
            "FrontendDeployment",
            sources=[
                s3deploy.Source.asset(
                    "../frontend",
                    bundling=BundlingOptions(
                        image=DockerImage.from_registry("node:18"),
                        command=[
                            "bash", "-c",
                            # Create temp dir, copy only needed files there, cd into it
                            "mkdir -p /tmp/builddir && "
                            "cp -r /asset-input/package.json /tmp/builddir/ && "
                            "cp -r /asset-input/package-lock.json /tmp/builddir/ && "
                            "cp -r /asset-input/public /tmp/builddir/ && "
                            "cp -r /asset-input/scripts /tmp/builddir/ && "
                            "cp -r /asset-input/src /tmp/builddir/ && "
                            "cd /tmp/builddir && "
                            "npm ci --cache /tmp/npm-cache && "
                            "sed -i \"s|\\${WEBSOCKET_URL}|${WEBSOCKET_URL}|g\" src/config/AppConfig.js && "
                            "sed -i \"s|\\${API_URL}|${API_URL}|g\" src/config/AppConfig.js && "
                            "sed -i \"s|\\${USER_POOL_ID}|${USER_POOL_ID}|g\" src/config/AppConfig.js && "
                            "sed -i \"s|\\${USER_POOL_CLIENT_ID}|${USER_POOL_CLIENT_ID}|g\" src/config/AppConfig.js && "
                            "npm run build && "
                            "cp -r build/. /asset-output/ || (echo 'No build output!' && exit 1)"
                        ],
                        environment={
                            "WEBSOCKET_URL": websocket_stage_url,
                            "API_URL": api_url,
                            "USER_POOL_ID": user_pool_id,
                            "USER_POOL_CLIENT_ID": user_pool_client_id,
                            "HOME": "/tmp"
                        },
                        output_type=BundlingOutput.NOT_ARCHIVED,
                        user="node"
                    )
                )
            ],
            destination_bucket=bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )


