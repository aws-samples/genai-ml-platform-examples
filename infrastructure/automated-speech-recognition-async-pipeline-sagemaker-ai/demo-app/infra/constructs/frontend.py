from aws_cdk import (
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3deploy,
    DockerImage,
    RemovalPolicy,
)
from constructs import Construct


class FrontendConstruct(Construct):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
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

        # oai = cloudfront.OriginAccessIdentity(self, "OAI", comment="OAI for FrontendBucket")

        # bucket.grant_read(oai)

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

        s3deploy.BucketDeployment(
            self,
            "FrontendDeployment",
            sources=[
                s3deploy.Source.asset(
                    "../frontend",
                    bundling={
                        "image": DockerImage.from_registry("node:18"),
                        "command": [
                            "bash", "-c",
                            "npm ci --cache /tmp/empty-cache && npm run build && cp -r build/* /asset-output/"
                        ],
                    },
                )
            ],
            destination_bucket=bucket,
            distribution=self.distribution,
            distribution_paths=["/*"],
        )
